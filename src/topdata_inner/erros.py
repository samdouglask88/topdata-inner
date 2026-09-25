"""Excecoes da biblioteca.

Todas herdam de `ErroTopdata`, para quem quiser tratar "qualquer problema com
a catraca" num `except` so.
"""


class ErroTopdata(Exception):
    """Base de todos os erros desta biblioteca."""


class ErroAutenticacao(ErroTopdata):
    """A catraca recusou usuario/senha.

    O Bearer e montado localmente a partir da credencial cifrada; o servidor
    nao emite token. Por isso um 401 que se repete logo depois de um novo
    /logme significa credencial errada, e nao sessao vencida: insistir em
    laco nao resolve.
    """


class ErroHttp(ErroTopdata):
    """Resposta HTTP fora de 2xx."""

    def __init__(self, caminho, status, corpo=b""):
        self.caminho = caminho
        self.status = status
        self.corpo = corpo
        super().__init__(f"{caminho}: HTTP {status}")


class ErroOperacao(ErroTopdata):
    """A catraca respondeu, mas terminou a operacao com um codigo de falha.

    `codigo` e o numero cru devolvido pelo equipamento (None quando o prazo
    acabou antes de haver codigo final) e `mensagem` uma explicacao curta.
    """

    def __init__(self, mensagem, codigo=None):
        self.codigo = codigo
        self.mensagem = mensagem
        super().__init__(mensagem if codigo is None else f"{mensagem} (codigo {codigo})")


class ErroLeituraCartao(ErroOperacao):
    """A leitura de cartao sob comando nao devolveu um numero."""


class ErroCadastroDigital(ErroOperacao):
    """O cadastro de digital no sensor da catraca nao foi concluido."""


class ErroDigital(ErroOperacao):
    """Falha ao ler, gravar, mover ou excluir um template de digital."""


class ErroPrazo(ErroOperacao):
    """A catraca nao chegou a um estado final dentro do prazo pedido."""
