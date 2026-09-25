"""Cliente assincrono da API HTTP da catraca.

Todos os endpoints ficam na raiz (http://ip/<endpoint>) e as respostas vem
sempre comprimidas em gzip (o httpx descomprime sozinho). Inclusao e POST com
corpo; exclusao e DELETE com query string - POST num endpoint de exclusao
devolve 404, o que parece "endpoint inexistente" e engana.
"""

import asyncio
import base64
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional

import httpx

from . import digital as _digital
from ._util import cartao_16, validar_cartao
from .constantes import (
    CONFIGURACOES,
    EM_ANDAMENTO,
    HORARIO_BLOQUEADO,
    HORARIO_LIBERADO,
    Estado,
    mensagem,
)
from .cripto import cifrar, montar_bearer
from .erros import (
    ErroAutenticacao,
    ErroCadastroDigital,
    ErroDigital,
    ErroHttp,
    ErroLeituraCartao,
    ErroPrazo,
    ErroTopdata,
)
from .horarios import Horario, Plano, TAMANHO_REGISTRO, mesclar_tabela, parsear_horarios, plano_tem_faixa
from .listas import ItemLista, parsear_lista_acesso, parsear_lista_somente_cartao
from .passagens import REGISTROS_POR_PEDACO, Passagem, numerar_repeticoes, parsear_passagens

log = logging.getLogger("topdata_inner")

# Conectar rapido e desistir cedo; ler com folga, porque o equipamento
# responde devagar quando esta ocupado com a biometria.
TIMEOUT_PADRAO = httpx.Timeout(10.0, connect=3.0)

MAIOR_NUMERO_HORARIO = 100


class Catraca:
    """Uma catraca Topdata com controladora Inner.

    Uso:

        async with Catraca("192.0.2.10", usuario, senha) as catraca:
            print(await catraca.info())

    O login e feito no primeiro pedido e refeito sozinho num 401. Uma
    instancia serializa as operacoes que disputam o mesmo estado interno do
    equipamento (leitura de passagens, leitor de cartao, sensor de digital).
    Isso nao protege contra OUTROS clientes falando com a mesma catraca.
    """

    def __init__(
        self,
        ip: str,
        usuario: str,
        senha: str,
        porta: int = 80,
        timeout=TIMEOUT_PADRAO,
        *,
        transport: Optional[httpx.AsyncBaseTransport] = None,
        intervalo_consulta: float = 1.0,
        intervalo_curto: float = 0.4,
    ):
        self.ip = ip
        self.porta = porta
        # So as formas cifradas ficam guardadas; nunca sao registradas em log,
        # porque a cifra e reversivel.
        self._usuario_cif = cifrar(usuario)
        self._senha_cif = cifrar(senha)
        self._bearer: Optional[str] = None
        self.intervalo_consulta = intervalo_consulta
        self.intervalo_curto = intervalo_curto
        self._http = httpx.AsyncClient(
            base_url=f"http://{ip}:{porta}", timeout=timeout, transport=transport
        )
        self._trava_bilhetes = asyncio.Lock()
        self._trava_leitor = asyncio.Lock()
        self._trava_biometria = asyncio.Lock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.fechar()

    async def fechar(self) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------
    # Transporte
    # ------------------------------------------------------------------

    async def login(self) -> None:
        """Confirma a credencial no `/logme` e passa a usar o Bearer.

        O servidor nao devolve token: o Bearer e calculado aqui a partir da
        credencial cifrada. O `/logme` so diz se ela vale.
        """
        r = await self._http.post(
            "/logme", json={"usuario": self._usuario_cif, "senha": self._senha_cif}
        )
        if r.status_code in (401, 403):
            raise ErroAutenticacao("a catraca recusou usuario/senha")
        if not r.is_success:
            raise ErroHttp("logme", r.status_code, r.content)
        self._bearer = montar_bearer(self._usuario_cif, self._senha_cif)

    async def _pedir(self, metodo, caminho, *, params=None, json=None, conteudo=None):
        if self._bearer is None:
            await self.login()
        cabecalhos = {}
        if conteudo is not None:
            cabecalhos["Content-Type"] = "application/octet-stream"
        if params:
            params = {k: str(v) for k, v in params.items()}
        for tentativa in range(2):
            cabecalhos["Authorization"] = f"Bearer {self._bearer}"
            r = await self._http.request(
                metodo, f"/{caminho}", params=params, json=json, content=conteudo,
                headers=cabecalhos,
            )
            if r.status_code != 401:
                break
            if tentativa == 0:
                # Sessao perdida (por exemplo, a catraca reiniciou): um novo
                # /logme reabre. Se o 401 se repetir, e credencial.
                await self.login()
        else:
            raise ErroAutenticacao(f"{caminho}: 401 mesmo depois de novo login")
        if not r.is_success:
            raise ErroHttp(caminho, r.status_code, r.content)
        return r

    async def get(self, caminho: str, **params) -> httpx.Response:
        return await self._pedir("GET", caminho, params=params or None)

    async def post(self, caminho: str, dados=None, *, conteudo: bytes = None, params=None) -> httpx.Response:
        """POST com corpo JSON (`dados`) ou binario (`conteudo`)."""
        return await self._pedir("POST", caminho, params=params, json=dados, conteudo=conteudo)

    async def delete(self, caminho: str, **params) -> httpx.Response:
        return await self._pedir("DELETE", caminho, params=params or None)

    async def _json(self, caminho: str, **params):
        r = await self.get(caminho, **params)
        try:
            return r.json()
        except ValueError as exc:
            raise ErroTopdata(f"{caminho}: resposta nao e JSON") from exc

    async def _consultar_estado(self, caminho: str, **params) -> Optional[dict]:
        """Uma consulta de estado durante uma operacao em andamento.

        Falha de rede ou resposta estranha conta como "ainda em andamento":
        uma consulta perdida no meio nao pode encerrar uma operacao que o
        equipamento continua executando. O prazo de quem chama e que decide.
        """
        try:
            corpo = await self._json(caminho, **params)
        except ErroAutenticacao:
            raise
        except (ErroTopdata, httpx.TransportError):
            return None
        return corpo if isinstance(corpo, dict) else None

    # ------------------------------------------------------------------
    # Informacao e configuracao
    # ------------------------------------------------------------------

    async def info(self) -> dict:
        """Produto, numero de serie e versao de firmware (GET /info)."""
        return await self._json("info")

    async def ler_config(self, nome: str) -> dict:
        """Le um objeto de configuracao inteiro (ex.: "configuracaoacesso")."""
        if nome not in CONFIGURACOES:
            raise ValueError(f"configuracao desconhecida: {nome!r}")
        return await self._json(nome)

    async def gravar_config(self, nome: str, dados: dict, *, aceito_apagar_listas: bool = False) -> None:
        """Grava um objeto de configuracao inteiro.

        Mande o objeto completo lido por `ler_config`, alterado; nao ha
        gravacao parcial.

        ARMADILHA: mudar `numeroDigitosCartao` em configuracaoacesso faz a
        catraca APAGAR a lista de acesso e a lista "somente cartao" (as
        digitais sobrevivem). Por isso esta troca so e feita com
        `aceito_apagar_listas=True`; faca backup das listas antes.
        """
        if nome not in CONFIGURACOES:
            raise ValueError(f"configuracao desconhecida: {nome!r}")
        if nome == "configuracaoacesso" and "numeroDigitosCartao" in dados and not aceito_apagar_listas:
            atual = await self.ler_config(nome)
            if atual.get("numeroDigitosCartao") != dados["numeroDigitosCartao"]:
                raise ValueError(
                    "mudar numeroDigitosCartao apaga a lista de acesso e a lista somente "
                    "cartao; repita com aceito_apagar_listas=True se for isso mesmo"
                )
        await self.post(nome, dados)

    # ------------------------------------------------------------------
    # Relogio
    # ------------------------------------------------------------------

    async def ler_relogio(self) -> Optional[datetime]:
        """Hora da catraca, ou None se ela devolver uma data impossivel."""
        j = await self._json("configuracaorelogio")
        try:
            return datetime(2000 + j["ano"], j["mes"], j["dia"], j["hora"], j["minutos"], j["segundos"])
        except (KeyError, TypeError, ValueError):
            return None

    async def acertar_relogio(self, quando: Optional[datetime] = None) -> None:
        """Acerta o relogio (padrao: agora, na hora local desta maquina).

        `diaSemana` segue a convencao da catraca, domingo = 1, e o ano vai com
        dois digitos.
        """
        quando = quando or datetime.now()
        await self.post("configuracaorelogio", {
            "segundos": quando.second,
            "minutos": quando.minute,
            "hora": quando.hour,
            "diaSemana": quando.isoweekday() % 7 + 1,
            "dia": quando.day,
            "mes": quando.month,
            "ano": quando.year % 100,
        })

    async def conferir_relogio(self, tolerancia_segundos: int = 60, agora: Optional[datetime] = None) -> bool:
        """Acerta o relogio se ele estiver fora da tolerancia. True se acertou.

        Depois de faltar energia a catraca volta para 01/01/2019, e toda
        passagem dali em diante sai com essa data. Chame isto periodicamente,
        antes de ler passagens.
        """
        agora = agora or datetime.now()
        relogio = await self.ler_relogio()
        if relogio is not None and abs((relogio - agora).total_seconds()) <= tolerancia_segundos:
            return False
        await self.acertar_relogio(agora)
        return True

    # ------------------------------------------------------------------
    # Lista de acesso
    # ------------------------------------------------------------------

    @staticmethod
    def _validar_horario(horario: int) -> int:
        if horario in (HORARIO_LIBERADO, HORARIO_BLOQUEADO) or 1 <= horario <= MAIOR_NUMERO_HORARIO:
            return horario
        raise ValueError(f"horario invalido: {horario!r} (101, 102 ou numero da tabela)")

    async def incluir_na_lista(self, cartao, horario: int = HORARIO_LIBERADO) -> None:
        """Inclui a linha (cartao, horario). Par ja existente -> ErroHttp 400.

        101 = liberado sempre, 102 = bloqueado sempre, 1..N = horario N da
        tabela. Prefira `garantir_na_lista`, que nao falha se o par ja existe.
        """
        await self.post("listaacessoincluiregistro", {
            "identificador": validar_cartao(cartao),
            "horario": self._validar_horario(horario),
        })

    async def excluir_horario_da_lista(self, cartao, horario: int) -> bool:
        """Remove so a linha (cartao, horario). False se ela nao existia."""
        try:
            await self.delete(
                "listaacessoexcluihorario", identificador=validar_cartao(cartao), horario=horario
            )
        except ErroHttp:
            return False
        return True

    async def garantir_na_lista(self, cartao, horario: int = HORARIO_LIBERADO) -> None:
        """Deixa o cartao na lista com este horario, estivesse ele la ou nao.

        A catraca nao tem "substituir" e recusa (HTTP 400) incluir um par que
        ja existe. Entao: exclui o par (ignorando se nao existia) e inclui.
        Ha uma fracao de segundo entre os dois passos em que a pessoa nao esta
        na lista; nao existe operacao atomica no equipamento.

        As linhas 101 e 102 conflitantes tambem saem: um 101 esquecido ao lado
        de um horario restrito libera a pessoa o dia inteiro. Outros numeros de
        horario da mesma pessoa sao mantidos.
        """
        horario = self._validar_horario(horario)
        conflitantes = {HORARIO_LIBERADO, HORARIO_BLOQUEADO} - {horario}
        for outro in sorted(conflitantes):
            await self.excluir_horario_da_lista(cartao, outro)
        await self.excluir_horario_da_lista(cartao, horario)
        await self.incluir_na_lista(cartao, horario)

    async def excluir_da_lista(self, cartao) -> None:
        """Tira a pessoa inteira da lista de acesso (todas as linhas dela).

        Nao apaga a digital: para isso use `excluir_digital`.
        """
        await self.delete("listaacessoexcluiregistro", identificador=validar_cartao(cartao))

    async def limpar_lista(self) -> None:
        """Esvazia a lista de acesso inteira."""
        await self.delete("listaacessoexcluilista")

    async def ler_lista_acesso(self, posicao: int = 0, tentativas: int = 3) -> List[ItemLista]:
        """Linhas da lista de acesso a partir de `posicao`.

        A catraca as vezes devolve 0 bytes mesmo com a lista cheia; por isso
        a leitura e repetida algumas vezes antes de aceitar "vazia". Uma lista
        vazia aqui NAO prova que a lista esta vazia. Paginacao de listas
        grandes nao foi verificada: esta chamada le uma resposta so.
        """
        for i in range(max(1, tentativas)):
            r = await self.get("listaacesso", posicao=posicao)
            if r.content:
                return parsear_lista_acesso(r.content)
            if i + 1 < tentativas:
                await asyncio.sleep(self.intervalo_curto)
        return []

    # ------------------------------------------------------------------
    # Lista "somente cartao"
    # ------------------------------------------------------------------

    async def incluir_somente_cartao(self, cartao) -> None:
        """Marca o cartao como "somente cartao". Nao libera acesso sozinho."""
        await self.post("listasomentecartaoinclui", {"identificador": validar_cartao(cartao)})

    async def excluir_somente_cartao(self, cartao) -> None:
        await self.delete("listasomentecartaoexclui", identificador=validar_cartao(cartao))

    async def limpar_somente_cartao(self) -> None:
        await self.delete("listasomentecartaoexcluilista")

    async def ler_somente_cartao(self, posicao: int = 0) -> List[str]:
        r = await self.get("listasomentecartao", posicao=posicao)
        return parsear_lista_somente_cartao(r.content)

    # ------------------------------------------------------------------
    # Passagens
    # ------------------------------------------------------------------

    async def ler_passagens(self, max_pedacos: int = 1000) -> List[Passagem]:
        """Todas as passagens da memoria, da primeira a ultima.

        A catraca tem UM marcador interno de leitura: cada pedido a
        `listabilhetes` entrega o proximo pedaco a partir dele, seja qual for
        o `posicao` (que so numera os ids da resposta). `posicao=0` volta o
        marcador ao inicio, e `listabilhetesquantidade` tambem. O unico jeito
        confiavel e ler a partir do 0, em sequencia, sem nenhum outro pedido
        de passagens no meio, ate vir um pedaco incompleto.

        Nao guarde "onde parei": compare pela `Passagem.chave`, que nao usa o
        id. So giros (e negados, se `registraAcessoNegado` estiver ligado) sao
        gravados; acesso liberado em que ninguem girou nao gera registro.
        """
        async with self._trava_bilhetes:
            todas: List[Passagem] = []
            posicao = 0
            for _ in range(max_pedacos):
                r = await self.get("listabilhetes", posicao=posicao)
                pedaco = parsear_passagens(r.content)
                todas.extend(pedaco)
                if len(pedaco) < REGISTROS_POR_PEDACO:
                    break
                posicao += len(pedaco)
            else:
                log.warning("ler_passagens parou em %d pedacos sem chegar ao fim", max_pedacos)
            return numerar_repeticoes(todas)

    # ------------------------------------------------------------------
    # Leitura de cartao sob comando
    # ------------------------------------------------------------------

    async def ler_cartao(self, prazo: float = 30.0) -> str:
        """Espera um cartao no leitor da catraca e devolve o numero lido.

        Use isto em vez de digitar o numero impresso: o numero que a catraca
        enxerga depende do tipo de leitor e da quantidade de digitos
        configurados.

        `cadastrolecartao` so le, nao grava nada (ao contrario de
        `cadastrocartao`, que tambem inclui o cartao na lista). A catraca
        desiste sozinha em ~10 s (codigo 3) e volta a funcionar normalmente;
        aqui o pedido e rearmado ate acabar o `prazo`.

        Levanta ErroLeituraCartao com o codigo da catraca (7 = detectou mas
        nao decodificou) ou ErroPrazo.
        """
        limite = time.monotonic() + prazo
        async with self._trava_leitor:
            await self.get("cadastrolecartao")
            while True:
                await asyncio.sleep(self.intervalo_consulta)
                estado = await self._consultar_estado("cadastrocartaostatus")
                codigo = None if estado is None else estado.get("status")
                if codigo is None or codigo in EM_ANDAMENTO:
                    if time.monotonic() >= limite:
                        raise ErroPrazo("nenhum cartao lido dentro do prazo")
                    continue
                if codigo in (Estado.CARTAO_LIDO, Estado.CARTAO_JA_NA_LISTA):
                    cartao = str(estado.get("cartao") or "").lstrip("0")
                    if cartao:
                        return cartao
                    raise ErroLeituraCartao("a catraca respondeu sem numero de cartao", codigo)
                if codigo == Estado.CARTAO_DESISTIU:
                    if time.monotonic() >= limite:
                        raise ErroPrazo("nenhum cartao apresentado dentro do prazo", codigo)
                    await self.get("cadastrolecartao")
                    continue
                raise ErroLeituraCartao(mensagem(codigo), codigo)

    # ------------------------------------------------------------------
    # Digital: cadastro no sensor da catraca
    # ------------------------------------------------------------------

    async def cadastrar_digital(self, cartao, dedo: int = 1, prazo: float = 60.0) -> None:
        """Cadastra um dedo no sensor da propria catraca para este cartao.

        O cartao deve estar na lista de acesso antes. `dedo` e 1 ou 2 (a
        catraca guarda no maximo duas digitais por pessoa).

        ARMADILHA: enquanto o cadastro esta armado a catraca NAO atende
        ninguem - quem encosta o dedo para passar vira amostra de cadastro. E
        nao existe endpoint de cancelar. Por isso, se este metodo sair sem
        resultado final (prazo, erro, tarefa cancelada), ele desarma a catraca
        com `cancelar_cadastro_digital` antes de devolver o controle.

        A catraca desiste em ~5 s sem dedo (codigo 10); aqui o pedido e
        rearmado ate o `prazo`. Cada rearme faz o visor piscar uma mensagem de
        operacao invalida, o que e esperado.
        """
        if dedo not in (1, 2):
            raise ValueError("dedo deve ser 1 ou 2")
        ident = validar_cartao(cartao)
        limite = time.monotonic() + prazo
        async with self._trava_biometria:
            await self.get("cadastrobiometria", identificador=ident, numeroBiometria=dedo)
            armado = True
            try:
                while True:
                    await asyncio.sleep(self.intervalo_consulta)
                    estado = await self._consultar_estado(
                        "cadastrobiometriastatus", identificador=cartao_16(ident)
                    )
                    codigo = None if estado is None else estado.get("status")
                    if codigo is None or codigo in EM_ANDAMENTO:
                        if time.monotonic() >= limite:
                            raise ErroPrazo("nenhuma digital cadastrada dentro do prazo")
                        continue
                    armado = False
                    if codigo == Estado.DIGITAL_OK:
                        return
                    if codigo == Estado.DIGITAL_ERRO and time.monotonic() < limite:
                        await self.get("cadastrobiometria", identificador=ident, numeroBiometria=dedo)
                        armado = True
                        continue
                    raise ErroCadastroDigital(mensagem(codigo), codigo)
            finally:
                if armado:
                    await self._desarmar_silencioso(ident)

    async def _desarmar_silencioso(self, cartao) -> None:
        try:
            await self.cancelar_cadastro_digital(cartao)
        except Exception:  # noqa: BLE001 - desarmar e o melhor esforco
            log.warning("nao consegui desarmar o cadastro de digital; a catraca pode estar esperando um dedo")

    async def cancelar_cadastro_digital(self, cartao) -> None:
        """Tira a catraca do estado "esperando dedo".

        Nao ha endpoint de cancelar. O que funciona e o efeito colateral de
        `listabiometriareqnumdigitais` (pedido de contagem de digitais por
        pessoa): ele derruba o cadastro pendente. Pelo mesmo motivo, nunca
        peca essa contagem DURANTE um cadastro que voce quer manter.
        """
        await self.get("listabiometriareqnumdigitais", identificador=cartao_16(cartao))

    # ------------------------------------------------------------------
    # Digital: contagem, leitura, gravacao, movimentacao, exclusao
    # ------------------------------------------------------------------

    async def _aguardar_estado(self, caminho: str, prazo: float) -> dict:
        """Consulta `caminho` ate `status` sair de 0/None. ErroPrazo se nao sair."""
        limite = time.monotonic() + prazo
        while True:
            await asyncio.sleep(self.intervalo_curto)
            estado = await self._consultar_estado(caminho)
            if estado is not None and estado.get("status") not in (0, None):
                return estado
            if time.monotonic() >= limite:
                raise ErroPrazo(f"{caminho}: sem resposta final dentro do prazo")

    async def digitais_da_pessoa(self, cartao) -> int:
        """Quantas digitais este cartao tem na catraca (0, 1 ou 2).

        Os contadores agregados (`listabiometriaquantidade`, tamanho da lista)
        ja devolveram valores velhos; esta contagem por pessoa e a confiavel.
        ATENCAO: ela cancela um cadastro de digital em andamento.
        """
        async with self._trava_biometria:
            return await self._digitais_da_pessoa(cartao)

    async def _digitais_da_pessoa(self, cartao) -> int:
        await self.get("listabiometriareqnumdigitais", identificador=cartao_16(cartao))
        estado = await self._aguardar_estado("listabiometriastatusnumdigitais", prazo=4.0)
        return int(estado.get("quantidade") or 0)

    async def ler_digital(self, cartao) -> Optional[bytes]:
        """Template da(s) digital(is) do cartao, ou None se nao houver.

        570 bytes para um dedo; 1072 para dois (formato nao decifrado).
        """
        async with self._trava_biometria:
            return await self._ler_digital(cartao)

    async def _ler_digital(self, cartao) -> Optional[bytes]:
        await self.get("biometriale", identificador=cartao_16(cartao))
        estado = await self._aguardar_estado("biometriastatusleitura", prazo=6.0)
        b64 = estado.get("templates")
        if not b64:
            return None
        try:
            return base64.b64decode(b64)
        except ValueError as exc:
            raise ErroDigital("template devolvido nao e base64") from exc

    async def gravar_digital(self, template: bytes) -> None:
        """Grava um template pronto (o cartao dono esta dentro dele).

        O corpo vai em octet-stream, completado com zeros ate 1080 bytes. So
        templates de um dedo sao aceitos.
        """
        async with self._trava_biometria:
            await self._gravar_digital(template)

    async def _gravar_digital(self, template: bytes) -> None:
        _digital.cartao_do_template(template)  # valida assinatura e tamanho
        await self.post("biometriainclui", conteudo=_digital.preparar_envio(template))
        estado = await self._aguardar_estado("biometriastatusinclusao", prazo=6.0)
        if estado.get("status") != 1:
            raise ErroDigital("a catraca recusou o template", estado.get("status"))

    async def excluir_digital(self, cartao, tentativas: int = 3) -> None:
        """Apaga as digitais de um cartao.

        Logo depois de outro comando a catraca pode estar ocupada e recusar;
        por isso ha repeticao com pausa.
        """
        async with self._trava_biometria:
            await self._excluir_digital(cartao, tentativas)

    async def _excluir_digital(self, cartao, tentativas: int) -> None:
        ultimo = None
        for i in range(max(1, tentativas)):
            try:
                await self.delete("biometriaexclui", identificador=validar_cartao(cartao))
                return
            except ErroHttp as exc:
                ultimo = exc
                if i + 1 < tentativas:
                    await asyncio.sleep(self.intervalo_consulta)
        raise ErroDigital(f"nao consegui excluir a digital: {ultimo}")

    async def excluir_todas_as_digitais(self, prazo: float = 10.0) -> None:
        """Apaga TODAS as digitais do equipamento e espera a confirmacao."""
        async with self._trava_biometria:
            await self.get("biometriaexcluitodas")
            await self._aguardar_estado("biometriastatusexclusaotodas", prazo)

    async def mover_digital(self, cartao_de, cartao_para) -> bool:
        """Leva a digital de um cartao para outro, sem a pessoa presente.

        Ordem pensada para nunca trancar ninguem do lado de fora: le, troca o
        identificador, grava no novo, CONFERE que apareceu e so entao apaga
        do antigo. Uma falha antes do fim deixa o antigo intacto.

        Devolve True se tambem apagou do antigo; False se a digital ja esta no
        novo mas o antigo nao pode ser apagado (repita `excluir_digital`).
        O cartao novo precisa estar na lista de acesso para a digital liberar.
        So funciona para quem tem UMA digital.
        """
        async with self._trava_biometria:
            quantidade = await self._digitais_da_pessoa(cartao_de)
            if quantidade == 0:
                raise ErroDigital(f"o cartao {cartao_de} nao tem digital")
            if quantidade > 1:
                raise ErroDigital("duas digitais: o formato de dois dedos nao foi decifrado")
            template = await self._ler_digital(cartao_de)
            if not template:
                raise ErroDigital("a catraca nao devolveu a digital")
            try:
                novo = _digital.trocar_cartao(template, cartao_para, cartao_de)
            except ValueError as exc:
                raise ErroDigital(str(exc)) from exc
            await self._gravar_digital(novo)
            if not await self._digitais_da_pessoa(cartao_para):
                raise ErroDigital("a digital nao apareceu no cartao novo; o antigo foi mantido")
            try:
                await self._excluir_digital(cartao_de, tentativas=3)
            except ErroDigital:
                log.warning("digital copiada para o cartao novo, mas ainda esta no antigo")
                return False
            return True

    # ------------------------------------------------------------------
    # Horarios
    # ------------------------------------------------------------------

    async def ler_horarios(self) -> List[Horario]:
        """A tabela de horarios inteira (34 vagas no FIT)."""
        r = await self.get("listahorarios", posicao=0)
        return parsear_horarios(r.content)

    async def enviar_horarios(self, planos: Dict[int, Plano], *, permitir_vazio: bool = False) -> int:
        """Grava horarios pelo NUMERO usado na lista de acesso.

        `planos` = {numero: {dia: (inicio, fim) ou [(i1, f1), (i2, f2)]}},
        dia 1 = segunda ... 7 = domingo, horas "HH:MM". O horario N vai para a
        posicao N-1 da tabela (armadilha do "mais um", ver horarios.py).

        A tabela atual e lida antes e reenviada inteira, com os numeros pedidos
        substituidos, para nao depender de como o equipamento trata envio
        parcial. Um plano sem nenhuma faixa significa "ninguem passa nunca" e
        so e aceito com `permitir_vazio=True`.

        Devolve a quantidade de registros enviados.
        """
        for numero, plano in planos.items():
            if not plano_tem_faixa(plano) and not permitir_vazio:
                raise ValueError(
                    f"horario {numero} sem nenhuma faixa: ninguem passaria nunca "
                    "(use permitir_vazio=True se for isso)"
                )
        r = await self.get("listahorarios", posicao=0)
        if len(r.content) < TAMANHO_REGISTRO:
            raise ErroTopdata("nao consegui ler a tabela de horarios atual")
        corpo, quantidade = mesclar_tabela(r.content, planos)
        await self.post(
            "listahorarios",
            conteudo=corpo,
            params={"quantidade": quantidade, "primeiro": "true", "ultimo": "true"},
        )
        return quantidade

    # ------------------------------------------------------------------
    # Acionamento
    # ------------------------------------------------------------------

    async def liberar_giro(self) -> None:
        """Libera a catraca para UM giro (GET abreporta)."""
        await self.get("abreporta")
