import base64
import json
import unittest
from datetime import datetime

import httpx

from topdata_inner import (
    ErroAutenticacao,
    ErroCadastroDigital,
    ErroLeituraCartao,
    ErroPrazo,
    bearer_da_credencial,
)
from topdata_inner import digital
from topdata_inner import horarios as h
from test_digital import template_sintetico
from test_passagens import pedaco, registro
from falso import CatracaFalsa, js

OK = httpx.Response(200)


class TestSessao(unittest.IsolatedAsyncioTestCase):
    async def test_login_manda_credencial_cifrada_e_usa_bearer(self):
        f = CatracaFalsa()
        vistos = []

        def info(req):
            vistos.append(req.headers.get("authorization"))
            return js({"produto": "FIT"})

        f.rotas[("GET", "info")] = info
        async with f.cliente() as c:
            self.assertEqual(await c.info(), {"produto": "FIT"})
        self.assertEqual(vistos, ["Bearer " + bearer_da_credencial("usuario", "senha-exemplo")])

    async def test_401_refaz_login_e_repete(self):
        f = CatracaFalsa()
        f.rota("GET", "info", httpx.Response(401), js({"ok": 1}))
        async with f.cliente() as c:
            self.assertEqual(await c.info(), {"ok": 1})
        self.assertEqual(f.endpoints(), ["logme", "info", "logme", "info"])

    async def test_401_repetido_e_credencial(self):
        f = CatracaFalsa()
        f.rota("GET", "info", httpx.Response(401))
        async with f.cliente() as c:
            with self.assertRaises(ErroAutenticacao):
                await c.info()

    async def test_login_recusado(self):
        f = CatracaFalsa()
        f.rota("POST", "logme", httpx.Response(401))
        async with f.cliente() as c:
            with self.assertRaises(ErroAutenticacao):
                await c.info()


class TestLista(unittest.IsolatedAsyncioTestCase):
    async def test_garantir_exclui_antes_de_incluir(self):
        f = CatracaFalsa()
        f.rota("DELETE", "listaacessoexcluihorario", httpx.Response(400))
        f.rota("POST", "listaacessoincluiregistro", OK)
        async with f.cliente() as c:
            await c.garantir_na_lista("12345678", 101)
        passos = [(m, e, p.get("horario")) for m, e, p in f.chamadas if e != "logme"]
        self.assertEqual(passos, [
            ("DELETE", "listaacessoexcluihorario", "102"),
            ("DELETE", "listaacessoexcluihorario", "101"),
            ("POST", "listaacessoincluiregistro", None),
        ])
        self.assertTrue(all(p.get("identificador") == "12345678" for m, e, p in f.chamadas if m == "DELETE"))

    async def test_garantir_horario_tira_liberado_e_bloqueado(self):
        f = CatracaFalsa()
        f.rota("DELETE", "listaacessoexcluihorario", OK)
        corpos = []

        def incluir(req):
            corpos.append(req.content)
            return OK

        f.rotas[("POST", "listaacessoincluiregistro")] = incluir
        async with f.cliente() as c:
            await c.garantir_na_lista(12345678, 5)
        excluidos = [p["horario"] for m, e, p in f.chamadas if m == "DELETE"]
        self.assertEqual(excluidos, ["101", "102", "5"])
        self.assertEqual([json.loads(c) for c in corpos], [{"identificador": "12345678", "horario": 5}])

    async def test_ler_lista_repete_quando_vem_vazia(self):
        corpo = b"\x01" + (1).to_bytes(2, "big") + bytes.fromhex("0000000012345678") + bytes([101])
        f = CatracaFalsa()
        f.rota("GET", "listaacesso", httpx.Response(200, content=b""), httpx.Response(200, content=corpo))
        async with f.cliente() as c:
            itens = await c.ler_lista_acesso()
        self.assertEqual([(i.cartao, i.horario) for i in itens], [("12345678", 101)])


class TestPassagens(unittest.IsolatedAsyncioTestCase):
    async def test_leitura_sequencial_do_zero_ate_pedaco_curto(self):
        cheio = pedaco(*[registro(i, 0x0A, 1, 1, 26, 8, i % 60, "12345678") for i in range(111)])
        curto = pedaco(*[registro(111 + i, 0x0B, 1, 1, 26, 9, i, "87654321") for i in range(5)])
        f = CatracaFalsa()
        f.rota("GET", "listabilhetes", httpx.Response(200, content=cheio), httpx.Response(200, content=curto))
        async with f.cliente() as c:
            ps = await c.ler_passagens()
        self.assertEqual(len(ps), 116)
        pedidos = [(e, p.get("posicao")) for m, e, p in f.chamadas if e != "logme"]
        self.assertEqual(pedidos, [("listabilhetes", "0"), ("listabilhetes", "111")])


class TestLeituraCartao(unittest.IsolatedAsyncioTestCase):
    async def test_rearma_quando_desiste_e_devolve_numero(self):
        f = CatracaFalsa()
        f.rota("GET", "cadastrolecartao", OK)
        f.rota(
            "GET", "cadastrocartaostatus",
            js({"status": 1}),
            js({"status": 3, "cartao": "0000000000000000"}),
            js({"status": 0}),
            js({"status": 2, "cartao": "0000000012345678"}),
        )
        async with f.cliente() as c:
            self.assertEqual(await c.ler_cartao(prazo=30), "12345678")
        self.assertEqual(f.endpoints().count("cadastrolecartao"), 2)
        self.assertNotIn("cadastrocartao", f.endpoints())

    async def test_ja_na_lista_tambem_traz_numero(self):
        f = CatracaFalsa()
        f.rota("GET", "cadastrolecartao", OK)
        f.rota("GET", "cadastrocartaostatus", js({"status": 4, "cartao": "0000000012345678"}))
        async with f.cliente() as c:
            self.assertEqual(await c.ler_cartao(), "12345678")

    async def test_erro_de_leitura_7(self):
        f = CatracaFalsa()
        f.rota("GET", "cadastrolecartao", OK)
        f.rota("GET", "cadastrocartaostatus", js({"status": 1}), js({"status": 7, "cartao": "0" * 16}))
        async with f.cliente() as c:
            with self.assertRaises(ErroLeituraCartao) as ctx:
                await c.ler_cartao()
        self.assertEqual(ctx.exception.codigo, 7)

    async def test_prazo(self):
        f = CatracaFalsa()
        f.rota("GET", "cadastrolecartao", OK)
        f.rota("GET", "cadastrocartaostatus", js({"status": 1}))
        async with f.cliente() as c:
            with self.assertRaises(ErroPrazo):
                await c.ler_cartao(prazo=0)


class TestCadastroDigital(unittest.IsolatedAsyncioTestCase):
    async def test_sucesso_sem_cancelar(self):
        f = CatracaFalsa()
        f.rota("GET", "cadastrobiometria", OK)
        f.rota("GET", "cadastrobiometriastatus", js({"status": 1}), js({"status": 8}))
        async with f.cliente() as c:
            await c.cadastrar_digital("12345678", dedo=2)
        arme = [p for m, e, p in f.chamadas if e == "cadastrobiometria"][0]
        self.assertEqual(arme, {"identificador": "12345678", "numeroBiometria": "2"})
        consulta = [p for m, e, p in f.chamadas if e == "cadastrobiometriastatus"][0]
        self.assertEqual(consulta, {"identificador": "0000000012345678"})
        self.assertNotIn("listabiometriareqnumdigitais", f.endpoints())

    async def test_prazo_desarma_a_catraca(self):
        f = CatracaFalsa()
        f.rota("GET", "cadastrobiometria", OK)
        f.rota("GET", "cadastrobiometriastatus", js({"status": 1}))
        f.rota("GET", "listabiometriareqnumdigitais", OK)
        async with f.cliente() as c:
            with self.assertRaises(ErroPrazo):
                await c.cadastrar_digital("12345678", prazo=0)
        cancel = [p for m, e, p in f.chamadas if e == "listabiometriareqnumdigitais"]
        self.assertEqual(cancel, [{"identificador": "0000000012345678"}])

    async def test_falha_final_nao_precisa_desarmar(self):
        f = CatracaFalsa()
        f.rota("GET", "cadastrobiometria", OK)
        f.rota("GET", "cadastrobiometriastatus", js({"status": 11}))
        async with f.cliente() as c:
            with self.assertRaises(ErroCadastroDigital) as ctx:
                await c.cadastrar_digital("12345678")
        self.assertEqual(ctx.exception.codigo, 11)
        self.assertNotIn("listabiometriareqnumdigitais", f.endpoints())

    async def test_dedo_invalido(self):
        async with CatracaFalsa().cliente() as c:
            with self.assertRaises(ValueError):
                await c.cadastrar_digital("1", dedo=3)


class TestMoverDigital(unittest.IsolatedAsyncioTestCase):
    async def test_grava_no_novo_confere_e_so_depois_apaga(self):
        t = template_sintetico("12345678")
        enviados = []

        def incluir(req):
            enviados.append(req.content)
            return OK

        f = CatracaFalsa()
        f.rota("GET", "listabiometriareqnumdigitais", OK)
        f.rota("GET", "listabiometriastatusnumdigitais", js({"status": 1, "quantidade": 1}))
        f.rota("GET", "biometriale", OK)
        f.rota("GET", "biometriastatusleitura", js({"status": 1, "templates": base64.b64encode(t).decode()}))
        f.rotas[("POST", "biometriainclui")] = incluir
        f.rota("GET", "biometriastatusinclusao", js({"status": 1}))
        f.rota("DELETE", "biometriaexclui", httpx.Response(500), OK)
        async with f.cliente() as c:
            self.assertTrue(await c.mover_digital("12345678", "87654321"))

        (corpo,) = enviados
        self.assertEqual(len(corpo), 1080)
        self.assertEqual(corpo[5:13], digital.codificar_identificador("87654321"))
        self.assertEqual(corpo[13:570], t[13:])
        ordem = [e for e in f.endpoints() if e in ("biometriainclui", "biometriaexclui")]
        self.assertEqual(ordem, ["biometriainclui", "biometriaexclui", "biometriaexclui"])
        exclusao = [p for m, e, p in f.chamadas if e == "biometriaexclui"][-1]
        self.assertEqual(exclusao, {"identificador": "12345678"})


class TestConfigERelogio(unittest.IsolatedAsyncioTestCase):
    async def test_trocar_digitos_exige_confirmacao(self):
        f = CatracaFalsa()
        f.rota("GET", "configuracaoacesso", js({"numeroDigitosCartao": 14, "tipoLeitor": 2}))
        f.rota("POST", "configuracaoacesso", OK)
        async with f.cliente() as c:
            with self.assertRaises(ValueError):
                await c.gravar_config("configuracaoacesso", {"numeroDigitosCartao": 8, "tipoLeitor": 6})
            self.assertNotIn(("POST", "configuracaoacesso"), [(m, e) for m, e, _ in f.chamadas])
            await c.gravar_config("configuracaoacesso", {"numeroDigitosCartao": 14, "tipoLeitor": 2})
            await c.gravar_config(
                "configuracaoacesso", {"numeroDigitosCartao": 8}, aceito_apagar_listas=True
            )
        self.assertEqual(f.endpoints("POST").count("configuracaoacesso"), 2)

    async def test_acertar_relogio_domingo_e_ano_curto(self):
        corpos = []

        def gravar(req):
            corpos.append(req.content)
            return OK

        f = CatracaFalsa()
        f.rotas[("POST", "configuracaorelogio")] = gravar
        async with f.cliente() as c:
            await c.acertar_relogio(datetime(2026, 3, 1, 7, 8, 9))  # domingo
        self.assertEqual(json.loads(corpos[0]), {
            "segundos": 9, "minutos": 8, "hora": 7, "diaSemana": 1, "dia": 1, "mes": 3, "ano": 26,
        })

    async def test_conferir_relogio_depois_de_queda_de_energia(self):
        f = CatracaFalsa()
        f.rota("GET", "configuracaorelogio", js(
            {"segundos": 0, "minutos": 0, "hora": 0, "diaSemana": 3, "dia": 1, "mes": 1, "ano": 19}
        ))
        f.rota("POST", "configuracaorelogio", OK)
        async with f.cliente() as c:
            self.assertTrue(await c.conferir_relogio(agora=datetime(2026, 5, 4, 10, 0)))
            self.assertFalse(await c.conferir_relogio(agora=datetime(2019, 1, 1, 0, 0, 30)))


class TestEnviarHorarios(unittest.IsolatedAsyncioTestCase):
    async def test_numero_n_vai_para_posicao_n_menos_1(self):
        tabela = b"".join(h.montar_registro(i, {}) for i in range(34))
        enviados = []

        def gravar(req):
            enviados.append((req.content, dict(req.url.params), req.headers.get("content-type")))
            return OK

        f = CatracaFalsa()
        f.rota("GET", "listahorarios", httpx.Response(200, content=tabela))
        f.rotas[("POST", "listahorarios")] = gravar
        async with f.cliente() as c:
            qtd = await c.enviar_horarios({1: {1: ("08:00", "14:00"), 5: ("08:00", "14:00")}})
        self.assertEqual(qtd, 34)
        corpo, params, tipo = enviados[0]
        self.assertEqual(params, {"quantidade": "34", "primeiro": "true", "ultimo": "true"})
        self.assertEqual(tipo, "application/octet-stream")
        lida = h.parsear_horarios(corpo)
        self.assertEqual(lida[0].dias[1], [("08:00", "14:00")])
        self.assertTrue(lida[1].vazio)

    async def test_recusa_horario_sem_faixa(self):
        f = CatracaFalsa()
        async with f.cliente() as c:
            with self.assertRaises(ValueError):
                await c.enviar_horarios({1: {}})
        self.assertEqual(f.chamadas, [])


if __name__ == "__main__":
    unittest.main()
