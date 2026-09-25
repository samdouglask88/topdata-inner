"""Cifra do login e montagem do Bearer.

A interface web da propria catraca cifra usuario e senha antes de mandar ao
`/logme`, com um XOR de chave fixa que esta no JavaScript servido pelo
equipamento. A biblioteca reproduz exatamente o mesmo algoritmo porque e o
que o firmware espera receber.

Isto NAO e seguranca: qualquer pessoa na rede que capture o trafego (HTTP
puro, porta 80) reverte a cifra. Troque a senha padrao do equipamento e
restrinja quem alcanca a catraca pela rede.
"""

import base64

_ESTADO_INICIAL = 3535
_MULTIPLICADOR = 19436
_MODULO = 43117


def cifrar(texto: str) -> str:
    """Cifra `texto` do jeito que o `/logme` espera.

    Para cada byte: aplica XOR com o byte alto e com o byte baixo do estado,
    emite dois digitos hexadecimais em MAIUSCULO e avanca o estado. O
    firmware testado aceitou maiusculo e minusculo; maiusculo e o que a
    interface dele gera.

    O texto e tratado como latin-1 (um byte por caractere), que e o que a
    interface faz ao iterar caractere a caractere. Caractere fora do latin-1
    nao tem representacao de um byte e levanta ValueError, em vez de gerar uma
    cifra que o equipamento nunca aceitaria.
    """
    try:
        dados = texto.encode("latin-1")
    except UnicodeEncodeError as exc:
        raise ValueError("credencial com caractere fora do latin-1") from exc

    estado = _ESTADO_INICIAL
    saida = []
    for byte in dados:
        valor = byte ^ (estado // 256) ^ (estado % 256)
        saida.append(f"{valor:02X}")
        estado = (_MULTIPLICADOR * estado) % _MODULO
    return "".join(saida)


def montar_bearer(usuario_cifrado: str, senha_cifrada: str) -> str:
    """Token do cabecalho `Authorization: Bearer ...`.

    E so base64 de "usuario_cifrado:senha_cifrada". O servidor nao devolve
    token nenhum no login; ele apenas confirma que a credencial vale, e dali
    em diante cada pedido carrega este valor calculado aqui.
    """
    bruto = f"{usuario_cifrado}:{senha_cifrada}".encode("ascii")
    return base64.b64encode(bruto).decode("ascii")


def bearer_da_credencial(usuario: str, senha: str) -> str:
    """Atalho: cifra usuario e senha e monta o Bearer."""
    return montar_bearer(cifrar(usuario), cifrar(senha))
