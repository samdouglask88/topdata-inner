"""Codigos numericos da catraca, com nomes.

Os valores vem das enumeracoes da interface web do proprio equipamento e
foram conferidos no firmware 6.12. Onde um numero tem significado diferente
do que o nome sugere, o comentario diz.
"""

from enum import IntEnum

# Endpoints de configuracao: GET le o objeto JSON, POST grava o objeto inteiro
# de volta (nao ha atualizacao parcial - leia, altere, grave).
CONFIGURACOES = frozenset({
    "configuracaoacesso",
    "configuracaoseguranca",
    "configuracaobiometria",
    "configuracaomaster",
    "configuracaorelogio",
    "configuracaomensagem",
    "configuracaohorarioverao",
    "configuracaocomunicacao",
})


class TipoLeitor(IntEnum):
    """configuracaoacesso.tipoLeitor.

    O MESMO cartao produz numeros diferentes conforme o tipo de leitor e o
    numero de digitos configurados. Sempre obtenha o numero lendo o cartao
    pela catraca (`Catraca.ler_cartao`), nunca digitando o que esta impresso.
    """

    BARRAS = 0
    MAGNETICO = 1
    PROXIMIDADE = 2  # Abatrack; leitor de proximidade embutido
    WIEGAND = 3  # so escuta a entrada Wiegand externa, ignora o embutido
    SMARTCARD = 4
    BARRAS_SERIAL = 5
    WIEGAND_SEM_SEPARADOR = 6
    ASCII = 7


class TipoLista(IntEnum):
    """configuracaoseguranca.tipoLista.

    Com DESABILITADO a catraca nao consulta a lista e gira para qualquer
    identificacao valida - inclusive digital de quem nao esta na lista. Para
    a catraca decidir sozinha quem passa, use SOMENTE_LISTADOS.
    """

    DESABILITADO = 0
    SOMENTE_LISTADOS = 1
    NAO_LISTADOS_PASSAM = 2


class PadraoCartaoBarras(IntEnum):
    """configuracaoacesso.padraoCartaoBarras."""

    TOPDATA = 0
    LIVRE = 1


def mascara_digitos_variaveis(*quantidades: int) -> int:
    """Valor de configuracaoacesso.digitosVariaveis.

    E um mapa de bits: cada quantidade N de digitos aceita liga o bit N-1
    (4 -> 8, 6 -> 32, 8 -> 128, ..., 16 -> 32768). Todas as quantidades
    pares de 4 a 16 somam 43688.
    """
    mascara = 0
    for n in quantidades:
        if n not in (4, 6, 8, 10, 12, 14, 16):
            raise ValueError(f"quantidade de digitos nao suportada: {n}")
        mascara |= 1 << (n - 1)
    return mascara


DIGITOS_VARIAVEIS_TODOS = mascara_digitos_variaveis(4, 6, 8, 10, 12, 14, 16)

# Valores especiais de `horario` na lista de acesso. 1..34 apontam para a
# tabela de horarios (ver horarios.py e a armadilha do "mais um").
HORARIO_LIBERADO = 101
HORARIO_BLOQUEADO = 102


class Estado(IntEnum):
    """Estados de `cadastrocartaostatus` e `cadastrobiometriastatus`.

    As duas consultas usam a mesma enumeracao. 0 e 1 significam que a catraca
    ainda esta esperando; qualquer outro valor e final.
    """

    NENHUM = 0
    PROCESSANDO = 1
    CARTAO_LIDO = 2
    CARTAO_DESISTIU = 3  # ~10 s sem cartao; cartao vem todo zero
    CARTAO_JA_NA_LISTA = 4  # tambem traz o numero lido
    CARTAO_COM_DIGITAL = 5
    CARTAO_MASTER = 6
    CARTAO_ERRO_LEITURA = 7  # detectou mas nao decodificou
    DIGITAL_OK = 8
    DIGITAL_ERRO_LEITURA = 9
    DIGITAL_ERRO = 10  # ~5 s sem dedo, ou amostras que nao formaram digital
    DIGITAL_DUPLICADA = 11
    DIGITAL_MEMORIA_CHEIA = 12
    LISTA_CHEIA = 13
    INDISPONIVEL = 14


EM_ANDAMENTO = frozenset({Estado.NENHUM, Estado.PROCESSANDO})

MENSAGENS = {
    Estado.CARTAO_DESISTIU: "nenhum cartao apresentado a tempo",
    Estado.CARTAO_JA_NA_LISTA: "cartao ja esta na lista",
    Estado.CARTAO_COM_DIGITAL: "cartao ja tem digital",
    Estado.CARTAO_MASTER: "este e o cartao master da catraca",
    Estado.CARTAO_ERRO_LEITURA: (
        "a catraca detectou o cartao mas nao conseguiu decodifica-lo "
        "(confira tipo de leitor + digitos, jumper/cabo e a placa leitora)"
    ),
    Estado.DIGITAL_OK: "digital cadastrada",
    Estado.DIGITAL_ERRO_LEITURA: "nao foi possivel ler o dedo",
    Estado.DIGITAL_ERRO: "sem dedo a tempo, ou amostras que nao formaram uma digital",
    Estado.DIGITAL_DUPLICADA: "esta digital ja esta cadastrada na catraca",
    Estado.DIGITAL_MEMORIA_CHEIA: "memoria de digitais cheia",
    Estado.LISTA_CHEIA: "lista de acesso cheia",
    Estado.INDISPONIVEL: "recurso indisponivel no equipamento",
}


def mensagem(codigo) -> str:
    try:
        return MENSAGENS.get(Estado(codigo), f"codigo {codigo}")
    except ValueError:
        return f"codigo desconhecido {codigo}"
