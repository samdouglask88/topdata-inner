"""Cadastra uma digital no sensor da catraca para um cartao.

    TOPDATA_IP=192.0.2.10 TOPDATA_USUARIO=... TOPDATA_SENHA=... \\
        python cadastrar_digital.py 12345678 [1|2]

A pessoa deve estar na frente da catraca: enquanto o cadastro esta armado o
equipamento nao atende mais ninguem. Se o prazo acabar (ou voce interromper
com Ctrl+C), a biblioteca desarma a catraca antes de sair.
"""

import asyncio
import os
import sys

from topdata_inner import Catraca, ErroCadastroDigital, ErroPrazo


async def main(cartao, dedo):
    async with Catraca(os.environ["TOPDATA_IP"], os.environ["TOPDATA_USUARIO"],
                       os.environ["TOPDATA_SENHA"]) as catraca:
        # O cartao precisa estar na lista de acesso antes (garantir_na_lista).
        # Nao e feito aqui de proposito: incluir um 101 para quem tem horario
        # restrito liberaria essa pessoa o dia inteiro.
        print(f"encoste o dedo no sensor da catraca (dedo {dedo})...")
        try:
            await catraca.cadastrar_digital(cartao, dedo=dedo, prazo=60)
        except (ErroCadastroDigital, ErroPrazo) as erro:
            print("cadastro nao concluido:", erro)
            return
        print("digital cadastrada;", await catraca.digitais_da_pessoa(cartao), "no total")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("uso: cadastrar_digital.py CARTAO [DEDO]")
    asyncio.run(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1))
