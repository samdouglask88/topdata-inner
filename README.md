# topdata-inner

Cliente Python (asyncio + [httpx](https://www.python-httpx.org/)) para a API HTTP
das catracas **Topdata** com controladora **Inner** — a mesma API que a interface
web "Controle Catraca" do próprio equipamento usa.

> **Projeto independente, sem vínculo com a Topdata. Não oficial. Use por sua conta e risco.**

Testado em uma **Topdata FIT com firmware 6.12**. Outros modelos e firmwares podem
se comportar diferente; os pontos que dependem do equipamento estão marcados na
[referência do protocolo](docs/PROTOCOLO.md).

Vai ligar **leitor externo com saída Wiegand** (facial, biométrico, QR) e precisa
de entrada e saída separadas? Isso não passa por esta biblioteca — é fiação e
configuração do equipamento, e está em
[docs/LEITORES-WIEGAND.md](docs/LEITORES-WIEGAND.md).

## O que dá para fazer

- login (cifra da própria interface) e renovação automática da sessão;
- ler e gravar as configurações (`configuracaoacesso`, `configuracaoseguranca`, ...);
- ler e acertar o relógio;
- lista de acesso e lista "somente cartão";
- ler as passagens (giros e acessos negados) sem perder nem duplicar registros;
- ler um cartão pelo leitor da catraca;
- cadastrar digital no sensor da catraca, contar, ler, gravar, **mover para outro
  cartão sem a pessoa presente** e excluir;
- tabela de horários;
- liberar um giro.

## Instalação

```bash
pip install git+https://github.com/samdouglask88/topdata-inner
```

Requer Python 3.10+.

## Início rápido

As credenciais ficam fora do código, em variáveis de ambiente:

```bash
export TOPDATA_IP=192.0.2.10
export TOPDATA_USUARIO=...
export TOPDATA_SENHA=...
```

```python
import asyncio, os
from topdata_inner import Catraca

async def main():
    async with Catraca(os.environ["TOPDATA_IP"],
                       os.environ["TOPDATA_USUARIO"],
                       os.environ["TOPDATA_SENHA"]) as catraca:
        print(await catraca.info())
        await catraca.conferir_relogio()          # acerta se estiver errado

        cartao = await catraca.ler_cartao()       # apresente o cartão no leitor
        await catraca.garantir_na_lista(cartao)   # 101 = liberado sempre
        # com horário restrito: garantir_na_lista(cartao, 1), após enviar_horarios

        for p in await catraca.ler_passagens():
            print(p.quando, hex(p.tipo), p.cartao)

asyncio.run(main())
```

Mais exemplos em [`exemplos/`](exemplos/).

## Armadilhas principais

Cada uma custou horas na bancada. Detalhes em [docs/PROTOCOLO.md](docs/PROTOCOLO.md).

1. **Mudar `numeroDigitosCartao` apaga a lista de acesso e a lista somente cartão**
   (as digitais sobrevivem). `gravar_config` recusa essa troca sem
   `aceito_apagar_listas=True`.
2. **O número do cartão depende da configuração do leitor.** O mesmo cartão dá
   números diferentes em Abatrack 14 dígitos e em Wiegand sem separador 8 dígitos.
   Leia o cartão pela catraca (`ler_cartao`), não digite o número impresso.
3. **`tipoLista = 0` (desabilitado) faz a catraca girar para qualquer um.** Para
   ela decidir pela lista, use `1`.
4. **Passagens: há um único marcador de leitura.** `posicao` não escolhe o que vem;
   `posicao=0` e `listabilhetesquantidade` voltam ao início. Leia tudo do 0 em
   sequência (`ler_passagens`) e identifique a passagem por `Passagem.chave`,
   nunca pelo `id`.
5. **Cadastro de digital trava a catraca** até terminar, e não existe "cancelar".
   A contagem por pessoa (`listabiometriareqnumdigitais`) derruba o cadastro
   pendente — `cadastrar_digital` usa isso para se desarmar sozinho em caso de
   falha; nunca peça essa contagem no meio de um cadastro que você quer manter.
6. **Horário N da lista = posição N−1 da tabela.** Errar isso deixa o horário
   vazio, e horário vazio é "ninguém passa nunca". A biblioteca só fala em número.
7. **Uma pessoa pode ter várias linhas na lista.** Um `101` esquecido ao lado de um
   horário restrito libera o dia inteiro. `garantir_na_lista` remove 101/102
   conflitantes.
8. **Incluir par (cartão, horário) já existente dá HTTP 400.** `garantir_na_lista`
   exclui antes de incluir.
9. **Faltou energia, o relógio volta para 01/01/2019.** Chame `conferir_relogio`
   periodicamente.
10. **Contadores agregados mentem** (`listabiometriaquantidade`, `listaacesso`
    vazio com itens). Confie na contagem por pessoa.

Visor dizendo **"Passe o cartão novamente"** / **"cartão falhou"**? Veja a seção de
diagnóstico na referência.

Uma leitura só acendendo **as duas setas** e soltando a roleta nos dois sentidos? É
o Acionamento 2, que não controla sentido — veja
[docs/LEITORES-WIEGAND.md](docs/LEITORES-WIEGAND.md).

## Segurança

A cifra do login é **ofuscação, não segurança**: a chave está no JavaScript que o
próprio equipamento serve, e o tráfego é HTTP puro. Qualquer um na rede que capture
o login recupera a senha.

- troque a senha padrão do equipamento;
- restrinja o acesso de rede à catraca (idealmente, só o servidor que a controla);
- não registre em log o Bearer nem a credencial cifrada — são reversíveis.

## Testes

```bash
python -m unittest discover -s tests
```

Os testes usam `httpx.MockTransport` e não acessam a rede.

## Licença

MIT — veja [LICENSE](LICENSE).
