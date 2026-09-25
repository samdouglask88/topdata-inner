"""Tabela de horarios (`listahorarios`).

A catraca decide o acesso sozinha, sem consultar servidor: um horario so vale
se estiver gravado nela antes. Cada registro tem 58 bytes:

    [0:2]    posicao na tabela (uint16 big-endian), a partir de 0
    [2:58]   7 dias x 8 bytes, na ordem segunda, terca, ..., sabado, domingo
             cada dia: hi1 mi1 hf1 mf1 hi2 mi2 hf2 mf2
             (duas faixas: hora/minuto de inicio e de fim; 255 = vazio)

ARMADILHA DO "MAIS UM": na lista de acesso, `horario=N` aponta para a
POSICAO N-1 desta tabela (a interface da catraca faz horario = posicao + 1).
Gravar o horario 1 na posicao 1 deixa a posicao 0 vazia, e o horario 1 passa
a significar "ninguem passa nunca". Aqui voce sempre fala em NUMERO do
horario (1, 2, ...) e a conversao para posicao e feita por
`posicao_do_horario`.

Dia sem faixa = dia fechado. Horario sem faixa nenhuma = ninguem passa.

Os dias sao identificados como em `date.isoweekday()`: 1 = segunda ... 7 =
domingo, que coincide com a ordem dentro do registro.
"""

from dataclasses import dataclass, field
from datetime import time
from typing import Dict, List, Tuple, Union

TAMANHO_REGISTRO = 58
CAMPO_VAZIO = 255
VAGAS_PADRAO = 34
DIAS = (1, 2, 3, 4, 5, 6, 7)
FAIXAS_POR_DIA = 2

Hora = Union[str, time]
Faixa = Tuple[Hora, Hora]
# {dia (1..7): (inicio, fim) ou [(inicio, fim), (inicio, fim)]}
Plano = Dict[int, Union[Faixa, List[Faixa]]]


@dataclass
class Horario:
    """Um registro lido da catraca."""

    posicao: int
    dias: Dict[int, List[Tuple[str, str]]] = field(default_factory=dict)

    @property
    def numero(self) -> int:
        """O numero que se usa na lista de acesso para este registro."""
        return self.posicao + 1

    @property
    def vazio(self) -> bool:
        return not any(self.dias.values())


def posicao_do_horario(numero: int, vagas: int = VAGAS_PADRAO) -> int:
    """Numero do horario (como na lista de acesso) -> posicao na tabela."""
    if not isinstance(numero, int) or not 1 <= numero <= vagas:
        raise ValueError(f"horario {numero!r} fora de 1..{vagas}")
    return numero - 1


def _hora(valor: Hora) -> Tuple[int, int]:
    if isinstance(valor, time):
        return valor.hour, valor.minute
    try:
        h, m = str(valor).strip().split(":")
        h, m = int(h), int(m)
    except ValueError as exc:
        raise ValueError(f"hora invalida: {valor!r} (use 'HH:MM')") from exc
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"hora invalida: {valor!r}")
    return h, m


def _faixas_do_dia(valor) -> List[Faixa]:
    if not valor:
        return []
    if isinstance(valor, tuple) and len(valor) == 2 and not isinstance(valor[0], (tuple, list)):
        return [valor]
    return list(valor)


def montar_registro(posicao: int, plano: Plano) -> bytes:
    """Os 58 bytes de um registro, na `posicao` da tabela (a partir de 0).

    Prefira `montar_registro_do_horario`, que recebe o numero usado na lista
    de acesso e evita o erro de posicao.
    """
    registro = bytearray(posicao.to_bytes(2, "big"))
    for dia in DIAS:
        faixas = _faixas_do_dia((plano or {}).get(dia))
        if len(faixas) > FAIXAS_POR_DIA:
            raise ValueError(f"dia {dia}: no maximo {FAIXAS_POR_DIA} faixas")
        bytes_dia = []
        for inicio, fim in faixas:
            bytes_dia += [*_hora(inicio), *_hora(fim)]
        bytes_dia += [CAMPO_VAZIO] * (8 - len(bytes_dia))
        registro += bytes(bytes_dia)
    return bytes(registro)


def montar_registro_do_horario(numero: int, plano: Plano, vagas: int = VAGAS_PADRAO) -> bytes:
    """Registro do horario `numero` (1..vagas), gravado na posicao numero-1."""
    return montar_registro(posicao_do_horario(numero, vagas), plano)


def plano_tem_faixa(plano: Plano) -> bool:
    return any(_faixas_do_dia(v) for v in (plano or {}).values())


def parsear_horarios(dados: bytes) -> List[Horario]:
    """Le o binario de `listahorarios`. Sobra incompleta e descartada.

    A posicao de cada registro e a ORDEM dele na resposta. O campo de posicao
    gravado no proprio registro e ignorado de proposito: a ordem e o que o
    equipamento usa, e o campo pode estar zerado em vagas nunca escritas.
    """
    horarios = []
    if not dados:
        return horarios
    for indice, inicio in enumerate(range(0, len(dados) - TAMANHO_REGISTRO + 1, TAMANHO_REGISTRO)):
        r = dados[inicio:inicio + TAMANHO_REGISTRO]
        dias = {}
        for i, dia in enumerate(DIAS):
            b = r[2 + i * 8: 10 + i * 8]
            faixas = []
            for k in (0, 4):
                hi, mi, hf, mf = b[k:k + 4]
                if CAMPO_VAZIO in (hi, mi, hf, mf):
                    continue
                faixas.append((f"{hi:02d}:{mi:02d}", f"{hf:02d}:{mf:02d}"))
            dias[dia] = faixas
        horarios.append(Horario(posicao=indice, dias=dias))
    return horarios


def mesclar_tabela(atual: bytes, planos: Dict[int, Plano], vagas: int = None) -> Tuple[bytes, int]:
    """Tabela completa com `planos` sobrescritos, pronta para enviar.

    `atual` e o binario lido de `listahorarios`; ele define quantas vagas a
    catraca tem e preserva os horarios que voce nao mencionou. Mandar so os
    registros alterados deixaria em aberto se o equipamento apaga o resto;
    reenviar a tabela inteira elimina a duvida.

    Devolve (corpo, quantidade_de_registros).
    """
    registros = [
        bytearray(atual[i:i + TAMANHO_REGISTRO])
        for i in range(0, len(atual) - TAMANHO_REGISTRO + 1, TAMANHO_REGISTRO)
    ]
    if vagas is None:
        vagas = len(registros)
    if not registros and vagas:
        registros = [bytearray(montar_registro(0, {})) for _ in range(vagas)]
    for numero, plano in planos.items():
        posicao = posicao_do_horario(numero, len(registros))
        registros[posicao] = bytearray(montar_registro(posicao, plano))
    for posicao, registro in enumerate(registros):
        registro[0:2] = posicao.to_bytes(2, "big")
    return b"".join(bytes(r) for r in registros), len(registros)
