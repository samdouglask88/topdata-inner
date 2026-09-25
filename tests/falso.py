"""Catraca de mentira sobre httpx.MockTransport, para testar sem rede."""

import json

import httpx

from topdata_inner import Catraca


class CatracaFalsa:
    """Responde por (metodo, endpoint).

    Cada rota recebe uma lista de respostas consumida em ordem (a ultima se
    repete) ou uma funcao `f(request) -> httpx.Response`. Toda chamada fica
    registrada em `chamadas` como (metodo, endpoint, params).
    """

    def __init__(self):
        self.rotas = {("POST", "logme"): [httpx.Response(200)]}
        self.chamadas = []

    def rota(self, metodo, endpoint, *respostas):
        self.rotas[(metodo, endpoint)] = list(respostas)

    def _responder(self, request):
        endpoint = request.url.path.lstrip("/")
        params = dict(request.url.params)
        self.chamadas.append((request.method, endpoint, params))
        alvo = self.rotas.get((request.method, endpoint))
        if alvo is None:
            return httpx.Response(404)
        if callable(alvo):
            return alvo(request)
        modelo = alvo.pop(0) if len(alvo) > 1 else alvo[0]
        # Copia: o mesmo objeto Response nao pode ser entregue duas vezes.
        return httpx.Response(modelo.status_code, headers=modelo.headers, content=modelo.read())

    def cliente(self, **kwargs):
        return Catraca(
            "192.0.2.10", "usuario", "senha-exemplo",
            transport=httpx.MockTransport(self._responder),
            intervalo_consulta=0, intervalo_curto=0, **kwargs,
        )

    def endpoints(self, metodo=None):
        return [e for m, e, _ in self.chamadas if metodo is None or m == metodo]


def js(obj, status=200):
    return httpx.Response(status, content=json.dumps(obj).encode(),
                          headers={"Content-Type": "application/json"})
