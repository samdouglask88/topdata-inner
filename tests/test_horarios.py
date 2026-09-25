import unittest
from datetime import time

from topdata_inner import horarios as h


def tabela_vazia(vagas=34):
    return b"".join(h.montar_registro(i, {}) for i in range(vagas))


class TestPosicao(unittest.TestCase):
    def test_horario_n_na_posicao_n_menos_1(self):
        self.assertEqual(h.posicao_do_horario(1), 0)
        self.assertEqual(h.posicao_do_horario(34), 33)

    def test_fora_da_faixa(self):
        for n in (0, 35, 101):
            with self.assertRaises(ValueError):
                h.posicao_do_horario(n)

    def test_registro_do_horario_1_leva_posicao_0(self):
        r = h.montar_registro_do_horario(1, {1: ("08:00", "18:00")})
        self.assertEqual(r[0:2], b"\x00\x00")


class TestRegistro(unittest.TestCase):
    def test_layout_58_bytes(self):
        r = h.montar_registro(4, {1: ("08:00", "18:00"), 7: [("09:00", "12:00"), (time(13, 0), time(17, 30))]})
        self.assertEqual(len(r), 58)
        self.assertEqual(int.from_bytes(r[0:2], "big"), 4)
        self.assertEqual(list(r[2:10]), [8, 0, 18, 0, 255, 255, 255, 255])  # segunda
        self.assertEqual(list(r[10:18]), [255] * 8)  # terca fechada
        self.assertEqual(list(r[50:58]), [9, 0, 12, 0, 13, 0, 17, 30])  # domingo

    def test_hora_invalida(self):
        with self.assertRaises(ValueError):
            h.montar_registro(0, {1: ("25:00", "26:00")})

    def test_mais_de_duas_faixas(self):
        with self.assertRaises(ValueError):
            h.montar_registro(0, {1: [("01:00", "02:00")] * 3})

    def test_ida_e_volta(self):
        r = h.montar_registro(0, {3: ("07:15", "11:45")})
        (lido,) = h.parsear_horarios(r)
        self.assertEqual(lido.numero, 1)
        self.assertEqual(lido.dias[3], [("07:15", "11:45")])
        self.assertEqual(lido.dias[1], [])

    def test_plano_vazio(self):
        self.assertFalse(h.plano_tem_faixa({}))
        self.assertFalse(h.plano_tem_faixa({1: None}))
        self.assertTrue(h.plano_tem_faixa({1: ("08:00", "09:00")}))


class TestMesclar(unittest.TestCase):
    def test_substitui_so_a_posicao_do_numero(self):
        atual = bytearray(tabela_vazia())
        atual[5 * 58 + 2] = 6  # horario 6 ja tinha algo: deve ser preservado
        corpo, qtd = h.mesclar_tabela(bytes(atual), {3: {1: ("08:00", "14:00")}})
        self.assertEqual(qtd, 34)
        tabela = h.parsear_horarios(corpo)
        self.assertEqual(tabela[2].numero, 3)
        self.assertEqual(tabela[2].dias[1], [("08:00", "14:00")])
        self.assertTrue(tabela[0].vazio)
        self.assertTrue(tabela[3].vazio)
        self.assertEqual(corpo[5 * 58 + 2], 6)

    def test_reescreve_campo_de_posicao(self):
        corpo, _ = h.mesclar_tabela(bytes(58 * 3), {})
        self.assertEqual([int.from_bytes(corpo[i * 58:i * 58 + 2], "big") for i in range(3)], [0, 1, 2])

    def test_numero_alem_da_capacidade(self):
        with self.assertRaises(ValueError):
            h.mesclar_tabela(tabela_vazia(34), {35: {1: ("08:00", "09:00")}})


if __name__ == "__main__":
    unittest.main()
