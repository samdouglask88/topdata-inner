"""Lista as passagens gravadas na catraca.

    TOPDATA_IP=192.0.2.10 TOPDATA_USUARIO=... TOPDATA_SENHA=... python ler_passagens.py

Acerta o relogio antes, se precisar: depois de uma queda de energia ele volta
para 2019 e as passagens seguintes sairiam com essa data.
"""

import asyncio
import os

from topdata_inner import TIPO_GIRO_A, TIPO_GIRO_B, TIPO_NEGADO, Catraca

NOMES = {TIPO_GIRO_A: "giro A", TIPO_GIRO_B: "giro B", TIPO_NEGADO: "negado"}


async def main():
    async with Catraca(os.environ["TOPDATA_IP"], os.environ["TOPDATA_USUARIO"],
                       os.environ["TOPDATA_SENHA"]) as catraca:
        if await catraca.conferir_relogio():
            print("relogio da catraca estava errado e foi acertado")
        passagens = await catraca.ler_passagens()
        for p in passagens:
            quando = p.quando.strftime("%d/%m/%Y %H:%M") if p.quando else "data invalida"
            print(f"{quando}  {NOMES.get(p.tipo, hex(p.tipo)):8}  cartao {p.cartao}")
        print(f"{len(passagens)} registro(s)")


if __name__ == "__main__":
    asyncio.run(main())
