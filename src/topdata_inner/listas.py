"""Leitura binaria da lista de acesso e da lista "somente cartao".

listaacesso         1 byte de cabecalho + registros de 11 bytes:
                    uint16 id | 8 bytes BCD do cartao | 1 byte horario
listasomentecartao  registros de 10 bytes: uint16 id | 8 bytes BCD do cartao

A lista de acesso e a que manda: e nela que a catraca confere quem pode
passar (com tipoLista = 1). A lista "somente cartao" e auxiliar e sozinha nao
libera ninguem.

Uma pessoa pode ocupar VARIAS linhas da lista de acesso, uma por horario. Um
101 (liberado sempre) esquecido convive com um horario restrito e libera a
pessoa o dia inteiro.
"""

from dataclasses import dataclass
from typing import List

from ._util import bcd_para_cartao, pular_cabecalho

TAMANHO_ITEM_ACESSO = 11
TAMANHO_ITEM_SOMENTE_CARTAO = 10


@dataclass
class ItemLista:
    """Uma linha da lista de acesso: o cartao e o horario que ele tem."""

    id: int
    cartao: str
    horario: int


def parsear_lista_acesso(dados: bytes) -> List[ItemLista]:
    corpo = pular_cabecalho(dados, TAMANHO_ITEM_ACESSO)
    itens = []
    for i in range(0, len(corpo) - TAMANHO_ITEM_ACESSO + 1, TAMANHO_ITEM_ACESSO):
        r = corpo[i:i + TAMANHO_ITEM_ACESSO]
        cartao = bcd_para_cartao(r[2:10])
        if cartao is None:
            continue
        itens.append(ItemLista(id=int.from_bytes(r[0:2], "big"), cartao=cartao, horario=r[10]))
    return itens


def parsear_lista_somente_cartao(dados: bytes) -> List[str]:
    corpo = pular_cabecalho(dados, TAMANHO_ITEM_SOMENTE_CARTAO)
    cartoes = []
    for i in range(0, len(corpo) - TAMANHO_ITEM_SOMENTE_CARTAO + 1, TAMANHO_ITEM_SOMENTE_CARTAO):
        cartao = bcd_para_cartao(corpo[i + 2:i + TAMANHO_ITEM_SOMENTE_CARTAO])
        if cartao is not None:
            cartoes.append(cartao)
    return cartoes
