"""Cliente Python para a API HTTP das catracas Topdata com controladora Inner.

Projeto independente, sem vinculo com a Topdata. Nao oficial.
"""

from .cliente import Catraca
from .constantes import (
    DIGITOS_VARIAVEIS_TODOS,
    HORARIO_BLOQUEADO,
    HORARIO_LIBERADO,
    Estado,
    PadraoCartaoBarras,
    TipoLeitor,
    TipoLista,
    mascara_digitos_variaveis,
)
from .cripto import bearer_da_credencial, cifrar, montar_bearer
from .erros import (
    ErroAutenticacao,
    ErroCadastroDigital,
    ErroDigital,
    ErroHttp,
    ErroLeituraCartao,
    ErroOperacao,
    ErroPrazo,
    ErroTopdata,
)
from .horarios import Horario, montar_registro_do_horario, parsear_horarios, posicao_do_horario
from .listas import ItemLista, parsear_lista_acesso, parsear_lista_somente_cartao
from .passagens import TIPO_GIRO_A, TIPO_GIRO_B, TIPO_NEGADO, Passagem, parsear_passagens

__version__ = "0.1.0"

__all__ = [
    "Catraca",
    "DIGITOS_VARIAVEIS_TODOS",
    "HORARIO_BLOQUEADO",
    "HORARIO_LIBERADO",
    "Estado",
    "PadraoCartaoBarras",
    "TipoLeitor",
    "TipoLista",
    "mascara_digitos_variaveis",
    "bearer_da_credencial",
    "cifrar",
    "montar_bearer",
    "ErroAutenticacao",
    "ErroCadastroDigital",
    "ErroDigital",
    "ErroHttp",
    "ErroLeituraCartao",
    "ErroOperacao",
    "ErroPrazo",
    "ErroTopdata",
    "Horario",
    "montar_registro_do_horario",
    "parsear_horarios",
    "posicao_do_horario",
    "ItemLista",
    "parsear_lista_acesso",
    "parsear_lista_somente_cartao",
    "TIPO_GIRO_A",
    "TIPO_GIRO_B",
    "TIPO_NEGADO",
    "Passagem",
    "parsear_passagens",
]
