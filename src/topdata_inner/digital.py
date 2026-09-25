"""Template de digital no formato que a catraca devolve e aceita.

Layout conhecido do template de UM dedo (570 bytes):

    [0:4]    55 55 AA AA         assinatura
    [5:13]   identificador       16 digitos; cada byte = par BCD + 1
    [-2:]    soma de verificacao uint16 little-endian da soma de [71:-2]

O "+1" em cada byte do identificador significa que os digitos "...135790"
viram 14 58 91 (0x13+1, 0x57+1, 0x90+1), e nao 13 57 90.

A soma de verificacao NAO cobre o identificador. Por isso da para mover uma
digital para outro cartao sem a pessoa presente: le, troca os 8 bytes do
identificador e grava de volta, sem recalcular nada.

O template de DOIS dedos (1072 bytes) tem outro layout, que nao foi
decifrado. As funcoes daqui recusam esse tamanho em vez de adivinhar.
"""

from ._util import cartao_16

ASSINATURA = b"\x55\x55\xaa\xaa"
FAIXA_IDENTIFICADOR = slice(5, 13)
INICIO_SOMA = 71
TAMANHO_UM_DEDO = 570
TAMANHO_DOIS_DEDOS = 1072
# `biometriainclui` espera o template completado com zeros ate este tamanho,
# que e o que a interface da catraca envia ao importar.
TAMANHO_ENVIO = 1080


def codificar_identificador(cartao) -> bytes:
    """Cartao -> 8 bytes do identificador dentro do template."""
    digitos = cartao_16(cartao)
    return bytes(int(digitos[i:i + 2], 16) + 1 for i in range(0, 16, 2))


def decodificar_identificador(dados: bytes):
    """8 bytes do identificador -> cartao sem zeros a esquerda (ou None)."""
    digitos = "".join(f"{(b - 1) & 0xFF:02X}" for b in dados)
    return digitos.lstrip("0") or None


def _conferir_formato(template: bytes) -> None:
    if template[:4] != ASSINATURA:
        raise ValueError("assinatura 55 55 AA AA ausente: nao e um template desta catraca")
    if len(template) == TAMANHO_DOIS_DEDOS:
        raise ValueError("template de dois dedos: formato nao decifrado, nao manipular")
    if len(template) != TAMANHO_UM_DEDO:
        raise ValueError(f"tamanho inesperado de template: {len(template)} bytes")


def calcular_soma(template: bytes) -> int:
    """Soma de verificacao esperada (16 bits) para o template."""
    return sum(template[INICIO_SOMA:-2]) & 0xFFFF


def soma_confere(template: bytes) -> bool:
    """True se os 2 ultimos bytes batem com a soma de [71:-2]."""
    return int.from_bytes(template[-2:], "little") == calcular_soma(template)


def acertar_soma(template: bytes) -> bytes:
    """Reescreve os 2 ultimos bytes com a soma correta."""
    novo = bytearray(template)
    novo[-2:] = calcular_soma(template).to_bytes(2, "little")
    return bytes(novo)


def cartao_do_template(template: bytes):
    """Cartao ao qual o template esta associado."""
    _conferir_formato(template)
    return decodificar_identificador(template[FAIXA_IDENTIFICADOR])


def trocar_cartao(template: bytes, cartao_para, cartao_de=None) -> bytes:
    """O mesmo template, associado a `cartao_para`.

    Com `cartao_de`, confere antes que o template pertence mesmo a esse
    cartao. Se a catraca devolveu a digital de outra pessoa, e melhor falhar
    do que dar a ela o acesso de alguem.
    """
    _conferir_formato(template)
    if cartao_de is not None and template[FAIXA_IDENTIFICADOR] != codificar_identificador(cartao_de):
        raise ValueError(f"o template nao pertence ao cartao {cartao_de}")
    novo = bytearray(template)
    novo[FAIXA_IDENTIFICADOR] = codificar_identificador(cartao_para)
    return bytes(novo)


def preparar_envio(template: bytes) -> bytes:
    """Completa com zeros ate 1080 bytes, como `biometriainclui` espera."""
    if len(template) > TAMANHO_ENVIO:
        raise ValueError("template maior que o tamanho de envio")
    return bytes(template).ljust(TAMANHO_ENVIO, b"\x00")
