"""Registros de passagem (`listabilhetes`).

Formato do binario: 1 byte de cabecalho e depois registros de 18 bytes.

    [0:2]    id (uint16 big-endian) - numeracao da RESPOSTA, nao do registro
    [2]      tipo do evento
    [3:8]    dia, mes, ano (2 digitos), hora, minuto - um byte binario cada
    [8:16]   cartao, 16 digitos em BCD empacotado
    [16:18]  00 00

O `id` nao identifica a passagem: ele comeca no `posicao` pedido e so conta
os registros daquela resposta. A mesma passagem lida duas vezes pode vir com
ids diferentes. Para reconhecer o que ja foi visto use `Passagem.chave`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from ._util import bcd_para_cartao

CABECALHO = 1
TAMANHO_REGISTRO = 18
REGISTROS_POR_PEDACO = 111

# Os dois sentidos de giro. Qual deles e "entrada" depende de como a catraca
# foi montada, por isso nao ha nome de sentido aqui: quem instala decide.
TIPO_GIRO_A = 0x0A
TIPO_GIRO_B = 0x0B
# Acesso negado: a pessoa foi identificada mas a catraca nao girou. So e
# gravado com `registraAcessoNegado` ligado em configuracaoseguranca.
TIPO_NEGADO = 0x0C

TIPOS_GIRO = frozenset({TIPO_GIRO_A, TIPO_GIRO_B})


@dataclass
class Passagem:
    """Uma linha da memoria de passagens."""

    id: int
    tipo: int
    dia: int
    mes: int
    ano: int
    hora: int
    minuto: int
    cartao: Optional[str]
    repeticao: int = 0

    @property
    def quando(self) -> Optional[datetime]:
        """Data/hora gravada pela catraca, ou None se for impossivel.

        None em vez de excecao: um registro com data corrompida nao pode
        impedir a leitura dos outros. A resolucao e de minuto.
        """
        try:
            return datetime(2000 + self.ano, self.mes, self.dia, self.hora, self.minuto)
        except ValueError:
            return None

    @property
    def girou(self) -> bool:
        return self.tipo in TIPOS_GIRO

    @property
    def negado(self) -> bool:
        return self.tipo == TIPO_NEGADO

    @property
    def chave(self):
        """Identidade estavel: (tipo, cartao, minuto, repeticao).

        `repeticao` separa passagens identicas de verdade (mesmo cartao, mesmo
        sentido, mesmo minuto), que nao podem ser fundidas numa so. Ela so e
        preenchida por `numerar_repeticoes`, que precisa ver a leitura inteira.
        """
        return (self.tipo, self.cartao, self.quando, self.repeticao)


def parsear_passagens(dados: bytes) -> List[Passagem]:
    """Converte um pedaco binario de `listabilhetes` em passagens.

    Sobra que nao completa 18 bytes e descartada: meio registro produziria um
    cartao inventado.
    """
    if not dados or len(dados) <= CABECALHO:
        return []
    passagens = []
    inicio = CABECALHO
    while inicio + TAMANHO_REGISTRO <= len(dados):
        r = dados[inicio:inicio + TAMANHO_REGISTRO]
        passagens.append(
            Passagem(
                id=int.from_bytes(r[0:2], "big"),
                tipo=r[2],
                dia=r[3],
                mes=r[4],
                ano=r[5],
                hora=r[6],
                minuto=r[7],
                cartao=bcd_para_cartao(r[8:16]),
            )
        )
        inicio += TAMANHO_REGISTRO
    return passagens


def numerar_repeticoes(passagens: List[Passagem]) -> List[Passagem]:
    """Preenche `repeticao` contando ocorrencias de (tipo, cartao, minuto).

    Deve rodar sobre a memoria inteira, lida do inicio: assim a N-esima
    ocorrencia de uma passagem recebe sempre o mesmo indice em leituras
    diferentes, e a `chave` fica estavel entre elas.
    """
    contagem = {}
    for p in passagens:
        base = (p.tipo, p.cartao, p.quando)
        p.repeticao = contagem.get(base, 0)
        contagem[base] = p.repeticao + 1
    return passagens
