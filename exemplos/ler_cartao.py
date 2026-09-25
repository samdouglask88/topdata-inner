"""Le um cartao pelo leitor da catraca e mostra o numero.

    TOPDATA_IP=192.0.2.10 TOPDATA_USUARIO=... TOPDATA_SENHA=... python ler_cartao.py

Use o numero mostrado aqui para cadastrar a pessoa: ele pode ser diferente do
impresso no cartao, conforme o tipo de leitor e a quantidade de digitos.
"""

import asyncio
import os

from topdata_inner import Catraca, ErroLeituraCartao, ErroPrazo


async def main():
    async with Catraca(os.environ["TOPDATA_IP"], os.environ["TOPDATA_USUARIO"],
                       os.environ["TOPDATA_SENHA"]) as catraca:
        print("apresente o cartao no leitor da catraca (30 s)...")
        try:
            print("cartao lido:", await catraca.ler_cartao(prazo=30))
        except ErroPrazo:
            print("nenhum cartao apresentado a tempo")
        except ErroLeituraCartao as erro:
            print("falha na leitura:", erro)


if __name__ == "__main__":
    asyncio.run(main())
