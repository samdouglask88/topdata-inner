"""Leva a digital de um cartao para outro, sem a pessoa presente.

    TOPDATA_IP=192.0.2.10 TOPDATA_USUARIO=... TOPDATA_SENHA=... \\
        python mover_digital.py CARTAO_ANTIGO CARTAO_NOVO [HORARIO]

Util quando alguem troca de cartao. O cartao novo e posto na lista de acesso
com HORARIO (padrao 101 = liberado sempre; use o numero do horario se a
pessoa tiver horario restrito). O antigo so perde a digital depois que ela
aparece no novo.
"""

import asyncio
import os
import sys

from topdata_inner import HORARIO_LIBERADO, Catraca, ErroDigital


async def main(de, para, horario):
    async with Catraca(os.environ["TOPDATA_IP"], os.environ["TOPDATA_USUARIO"],
                       os.environ["TOPDATA_SENHA"]) as catraca:
        await catraca.garantir_na_lista(para, horario)
        try:
            apagou_antigo = await catraca.mover_digital(de, para)
        except ErroDigital as erro:
            print("nao movida:", erro)
            return
        print("digital movida para", para)
        if not apagou_antigo:
            print("atencao: a digital ainda esta no cartao", de, "- repita excluir_digital")
        # O cartao antigo continua na lista de acesso; tire-o quando for o caso:
        # await catraca.excluir_da_lista(de)


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit("uso: mover_digital.py CARTAO_ANTIGO CARTAO_NOVO [HORARIO]")
    horario = int(sys.argv[3]) if len(sys.argv) == 4 else HORARIO_LIBERADO
    asyncio.run(main(sys.argv[1], sys.argv[2], horario))
