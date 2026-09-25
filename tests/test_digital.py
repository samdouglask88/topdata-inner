import unittest

from topdata_inner import digital


def template_sintetico(cartao="12345678"):
    corpo = bytearray(digital.TAMANHO_UM_DEDO)
    corpo[0:4] = digital.ASSINATURA
    corpo[digital.FAIXA_IDENTIFICADOR] = digital.codificar_identificador(cartao)
    for i in range(13, digital.TAMANHO_UM_DEDO - 2):
        corpo[i] = (i * 37 + 11) % 256
    return digital.acertar_soma(bytes(corpo))


class TestIdentificador(unittest.TestCase):
    def test_par_bcd_mais_um(self):
        cod = digital.codificar_identificador("135790")
        self.assertEqual(cod[-3:], bytes([0x14, 0x58, 0x91]))
        self.assertEqual(cod[:5], bytes([0x01] * 5))

    def test_ida_e_volta(self):
        for cartao in ("1", "12345678", "1122334455667788"):
            self.assertEqual(
                digital.decodificar_identificador(digital.codificar_identificador(cartao)), cartao
            )

    def test_mais_de_16_digitos(self):
        with self.assertRaises(ValueError):
            digital.codificar_identificador("12345678901234567")


class TestSoma(unittest.TestCase):
    def test_soma_little_endian_de_71_ate_menos_2(self):
        t = template_sintetico()
        esperado = sum(t[71:-2]) & 0xFFFF
        self.assertEqual(int.from_bytes(t[-2:], "little"), esperado)
        self.assertTrue(digital.soma_confere(t))

    def test_soma_nao_cobre_identificador(self):
        t = template_sintetico()
        alterado = bytearray(t)
        alterado[5] ^= 0xFF
        self.assertTrue(digital.soma_confere(bytes(alterado)))
        alterado[100] ^= 0xFF
        self.assertFalse(digital.soma_confere(bytes(alterado)))


class TestTrocaDeCartao(unittest.TestCase):
    def test_troca_so_o_identificador(self):
        t = template_sintetico("12345678")
        novo = digital.trocar_cartao(t, "87654321", cartao_de="12345678")
        self.assertEqual(digital.cartao_do_template(novo), "87654321")
        self.assertEqual(novo[:5], t[:5])
        self.assertEqual(novo[13:], t[13:])
        self.assertTrue(digital.soma_confere(novo))

    def test_recusa_template_de_outro_cartao(self):
        t = template_sintetico("12345678")
        with self.assertRaises(ValueError):
            digital.trocar_cartao(t, "87654321", cartao_de="11111111")

    def test_recusa_sem_assinatura(self):
        t = bytearray(template_sintetico())
        t[0] = 0
        with self.assertRaises(ValueError):
            digital.trocar_cartao(bytes(t), "1")

    def test_recusa_dois_dedos(self):
        t = digital.ASSINATURA + bytes(digital.TAMANHO_DOIS_DEDOS - 4)
        with self.assertRaises(ValueError):
            digital.trocar_cartao(t, "1")

    def test_envio_completa_ate_1080(self):
        t = template_sintetico()
        envio = digital.preparar_envio(t)
        self.assertEqual(len(envio), 1080)
        self.assertEqual(envio[:570], t)
        self.assertEqual(set(envio[570:]), {0})


if __name__ == "__main__":
    unittest.main()
