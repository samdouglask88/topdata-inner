"""Grava o horario 1 (segunda a sexta, 08:00-12:00 e 13:00-18:00).

    TOPDATA_IP=192.0.2.10 TOPDATA_USUARIO=... TOPDATA_SENHA=... \\
        python enviar_horario.py [CARTAO]

Com CARTAO, passa essa pessoa para o horario 1 (tirando o 101/102 que ela
tiver). O numero 1 e o que vai na lista de acesso; a biblioteca grava na
posicao 0 da tabela, como o equipamento espera.
"""

import asyncio
import os
import sys

from topdata_inner import Catraca

EXPEDIENTE = [("08:00", "12:00"), ("13:00", "18:00")]
HORARIO_1 = {dia: EXPEDIENTE for dia in (1, 2, 3, 4, 5)}  # sabado e domingo fechados


async def main(cartao=None):
    async with Catraca(os.environ["TOPDATA_IP"], os.environ["TOPDATA_USUARIO"],
                       os.environ["TOPDATA_SENHA"]) as catraca:
        enviados = await catraca.enviar_horarios({1: HORARIO_1})
        print(f"tabela reenviada ({enviados} registros)")
        for horario in await catraca.ler_horarios():
            if not horario.vazio:
                print(f"horario {horario.numero}: {horario.dias}")
        if cartao:
            await catraca.garantir_na_lista(cartao, 1)
            print(f"cartao {cartao} agora no horario 1")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
