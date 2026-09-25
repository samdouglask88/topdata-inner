import base64
import unittest

from topdata_inner.cripto import bearer_da_credencial, cifrar, montar_bearer


class TestCifra(unittest.TestCase):
    def test_vetores_conhecidos(self):
        self.assertEqual(cifrar("a"), "A3")
        self.assertEqual(cifrar("usuario"), "B7ADCD92901522")
        self.assertEqual(cifrar("senha-exemplo"), "B1BBD69B8351287F5D629408CA")

    def test_vazio(self):
        self.assertEqual(cifrar(""), "")

    def test_latin1_um_byte_por_caractere(self):
        self.assertEqual(cifrar("A\u00e7a\u00ed"), "8339D91E")

    def test_fora_do_latin1_recusa(self):
        with self.assertRaises(ValueError):
            cifrar("\u20ac")

    def test_saida_sempre_hex_maiusculo_dois_por_byte(self):
        c = cifrar("qualquer coisa 123")
        self.assertEqual(len(c), 2 * len("qualquer coisa 123"))
        self.assertEqual(c, c.upper())
        int(c, 16)


class TestBearer(unittest.TestCase):
    def test_base64_de_usuario_dois_pontos_senha(self):
        b = montar_bearer("B7AD", "B1BB")
        self.assertEqual(base64.b64decode(b).decode(), "B7AD:B1BB")

    def test_atalho(self):
        self.assertEqual(
            bearer_da_credencial("usuario", "senha-exemplo"),
            "QjdBRENEOTI5MDE1MjI6QjFCQkQ2OUI4MzUxMjg3RjVENjI5NDA4Q0E=",
        )


if __name__ == "__main__":
    unittest.main()
