"""Tratamento do numero do cartao, comum a varios modulos.

A catraca guarda o identificador como 16 digitos em BCD empacotado (8 bytes).
Alguns endpoints aceitam o numero cru ("12345678"); os de consulta de estado
so encontram o registro com os 16 digitos completos ("0000000012345678").
Centralizar aqui evita que cada metodo escolha um formato por conta propria.
"""

DIGITOS_IDENTIFICADOR = 16


def validar_cartao(cartao) -> str:
    """Devolve o cartao como texto de digitos, sem zeros a esquerda.

    Aceita int ou str. Rejeita vazio, nao numerico e mais de 16 digitos: um
    numero que nao cabe no BCD de 8 bytes seria truncado pelo equipamento e
    passaria a apontar para outra pessoa.
    """
    texto = str(cartao).strip()
    if not texto.isdigit():
        raise ValueError(f"cartao invalido: {cartao!r}")
    sem_zeros = texto.lstrip("0") or "0"
    if len(sem_zeros) > DIGITOS_IDENTIFICADOR:
        raise ValueError(f"cartao com mais de {DIGITOS_IDENTIFICADOR} digitos: {cartao!r}")
    return sem_zeros


def cartao_16(cartao) -> str:
    """O cartao com 16 digitos, zeros a esquerda."""
    return validar_cartao(cartao).zfill(DIGITOS_IDENTIFICADOR)


def bcd_para_cartao(dados: bytes):
    """8 bytes BCD -> numero sem zeros a esquerda, ou None se for todo zero.

    Todo zero e o que a catraca usa para "nenhum cartao"; devolver "0" faria
    parecer um cartao de verdade. Nibble acima de 9 (BCD invalido) sai como
    letra hexadecimal em vez de ser escondido, para o erro ficar visivel.
    """
    digitos = "".join(f"{b:02X}" for b in dados).lstrip("0")
    return digitos or None


def pular_cabecalho(dados: bytes, tamanho_registro: int, cabecalho: int = 1) -> bytes:
    """Remove o byte de cabecalho das listas binarias, quando ele existe.

    As listas de acesso e de passagens comecam com um byte de cabecalho antes
    dos registros. Sem pula-lo, todos os campos saem deslocados em um byte e
    o numero do cartao vira um valor plausivel e errado. Quando o tamanho ja e
    multiplo exato do registro, nao ha cabecalho a pular.
    """
    if not dados:
        return b""
    if len(dados) % tamanho_registro == cabecalho % tamanho_registro and len(dados) >= cabecalho:
        return dados[cabecalho:]
    if len(dados) % tamanho_registro == 0:
        return dados
    return dados[cabecalho:]
