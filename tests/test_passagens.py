import unittest
from datetime import datetime

from topdata_inner.passagens import (
    TIPO_GIRO_A,
    TIPO_GIRO_B,
    TIPO_NEGADO,
    numerar_repeticoes,
    parsear_passagens,
)


def registro(ident, tipo, dia, mes, ano, hora, minuto, cartao):
    return (
        ident.to_bytes(2, "big")
        + bytes([tipo, dia, mes, ano, hora, minuto])
        + bytes.fromhex(str(cartao).zfill(16))
        + b"\x00\x00"
    )


def pedaco(*registros):
    return b"\x01" + b"".join(registros)


class TestParser(unittest.TestCase):
    def test_pula_cabecalho_e_le_campos(self):
        dados = pedaco(registro(7, TIPO_GIRO_A, 14, 9, 26, 12, 26, "12345678"))
        (p,) = parsear_passagens(dados)
        self.assertEqual(p.id, 7)
        self.assertEqual(p.tipo, 0x0A)
        self.assertEqual(p.cartao, "12345678")
        self.assertEqual(p.quando, datetime(2026, 9, 14, 12, 26))
        self.assertTrue(p.girou)
        self.assertFalse(p.negado)

    def test_cartao_de_16_digitos(self):
        dados = pedaco(registro(0, TIPO_GIRO_B, 1, 1, 26, 0, 0, "1122334455667788"))
        self.assertEqual(parsear_passagens(dados)[0].cartao, "1122334455667788")

    def test_cartao_zero_vira_none(self):
        dados = pedaco(registro(0, TIPO_NEGADO, 1, 1, 26, 0, 0, "0"))
        p = parsear_passagens(dados)[0]
        self.assertIsNone(p.cartao)
        self.assertTrue(p.negado)
        self.assertFalse(p.girou)

    def test_data_impossivel_vira_none(self):
        dados = pedaco(registro(0, TIPO_GIRO_A, 31, 2, 26, 10, 0, "1"))
        self.assertIsNone(parsear_passagens(dados)[0].quando)

    def test_sobra_incompleta_descartada(self):
        dados = pedaco(registro(0, TIPO_GIRO_A, 1, 1, 26, 0, 0, "1")) + b"\x00" * 10
        self.assertEqual(len(parsear_passagens(dados)), 1)

    def test_vazio_ou_so_cabecalho(self):
        self.assertEqual(parsear_passagens(b""), [])
        self.assertEqual(parsear_passagens(b"\x01"), [])

    def test_pedaco_cheio_de_111(self):
        regs = [registro(i, TIPO_GIRO_A, 1, 1, 26, 8, i % 60, "12345678") for i in range(111)]
        dados = pedaco(*regs)
        self.assertEqual(len(dados), 1999)
        self.assertEqual(len(parsear_passagens(dados)), 111)


class TestRepeticao(unittest.TestCase):
    def test_passagens_identicas_ganham_indices_diferentes(self):
        r = registro(0, TIPO_GIRO_A, 1, 1, 26, 8, 0, "12345678")
        outro = registro(1, TIPO_GIRO_B, 1, 1, 26, 8, 0, "12345678")
        ps = numerar_repeticoes(parsear_passagens(pedaco(r, outro, r)))
        self.assertEqual([p.repeticao for p in ps], [0, 0, 1])
        self.assertNotEqual(ps[0].chave, ps[2].chave)

    def test_chave_nao_depende_do_id(self):
        a = numerar_repeticoes(parsear_passagens(pedaco(registro(5, TIPO_GIRO_A, 1, 1, 26, 8, 0, "9"))))
        b = numerar_repeticoes(parsear_passagens(pedaco(registro(222, TIPO_GIRO_A, 1, 1, 26, 8, 0, "9"))))
        self.assertEqual(a[0].chave, b[0].chave)


if __name__ == "__main__":
    unittest.main()
