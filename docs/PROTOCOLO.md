# Referência do protocolo HTTP — Topdata Inner

Esta é a API que a interface web "Controle Catraca" do próprio equipamento usa.
Tudo aqui foi conferido em uma **Topdata FIT, firmware 6.12**. Onde algo não foi
verificado, está dito.

> Projeto independente, sem vínculo com a Topdata. Não oficial.

Sumário:

1. [Transporte](#1-transporte)
2. [Login e sessão](#2-login-e-sessão)
3. [Configuração](#3-configuração)
4. [Lista de acesso](#4-lista-de-acesso)
5. [Lista "somente cartão"](#5-lista-somente-cartão)
6. [Passagens](#6-passagens-listabilhetes)
7. [Relógio](#7-relógio)
8. [Leitura de cartão sob comando](#8-leitura-de-cartão-sob-comando)
9. [Digital: cadastro no sensor](#9-digital-cadastro-no-sensor-da-catraca)
10. [Digital: contagem, leitura, gravação, exclusão](#10-digital-contagem-leitura-gravação-exclusão)
11. [Template de digital](#11-template-de-digital)
12. [Horários](#12-horários)
13. [Outros endpoints](#13-outros-endpoints)
14. [Diagnóstico: "Passe o cartão novamente"](#14-diagnóstico-passe-o-cartão-novamente)
15. [Não verificado](#15-não-verificado)

---

## 1. Transporte

- HTTP puro na **porta 80**. Todos os endpoints ficam na **raiz**:
  `http://<ip>/<endpoint>` (sem `/api`).
- As respostas vêm **sempre com `Content-Encoding: gzip`**, mesmo sem
  `Accept-Encoding`. httpx e requests descomprimem sozinhos; `urllib` não.
- **Inclusão = POST com corpo. Exclusão = DELETE com query string.** POST num
  endpoint de exclusão devolve 404 — parece endpoint inexistente, mas é método
  errado.
- Listas e passagens são **binárias** (`application/octet-stream`); o resto é JSON.
- A porta 3570 (protocolo online EasyInner) fica fechada neste modo e não é coberta
  por esta biblioteca.

## 2. Login e sessão

### Cifra

`POST /logme` com `{"usuario": cif(usuario), "senha": cif(senha)}`.

A cifra é a mesma do JavaScript da interface:

```
n = 3535
para cada byte b do texto:
    e = b XOR (n // 256) XOR (n % 256)
    saída += dois dígitos hexadecimais de e (maiúsculos)
    n = (19436 * n) % 43117
```

O firmware testado aceita o hexadecimal em maiúsculo ou minúsculo.

### Bearer

Toda chamada seguinte leva:

```
Authorization: Bearer base64(cif(usuario) + ":" + cif(senha))
```

O Bearer é **montado pelo cliente**; o `/logme` não devolve token, só confirma que
a credencial vale. Sem o cabeçalho, tudo responde **401 com `WWW-Authenticate`
vazio** (não é Basic nem Digest — `curl --digest`/`--anyauth` não ajudam).

Consequência: se um 401 se repete logo depois de um novo `/logme`, é **senha
errada**, não sessão vencida. A biblioteca refaz o login uma vez e depois desiste.

### Segurança

A cifra é ofuscação: a chave está no JavaScript servido pelo equipamento e o
tráfego é HTTP puro. Troque a senha padrão, restrinja o acesso de rede à catraca e
nunca registre em log o Bearer nem os valores cifrados.

## 3. Configuração

GET lê o objeto JSON; POST grava **o objeto inteiro** de volta (leia, altere,
grave).

| Endpoint | Conteúdo |
|---|---|
| `info` | produto, número de série, versão de firmware (só GET) |
| `configuracaoacesso` | tipo de leitor, dígitos do cartão, modo de operação, acionamentos |
| `configuracaoseguranca` | `tipoLista`, `registraAcessoNegado` |
| `configuracaobiometria` | nível de segurança, módulo |
| `configuracaomaster` | cartão/senha master |
| `configuracaorelogio` | data e hora (ver seção 7) |
| `configuracaomensagem` | mensagens do visor |
| `configuracaohorarioverao` | horário de verão |
| `configuracaocomunicacao` | rede |

### `configuracaoacesso.tipoLeitor`

| Valor | Leitor |
|---|---|
| 0 | código de barras |
| 1 | magnético |
| 2 | proximidade (Abatrack) — leitor embutido |
| 3 | Wiegand — só escuta a entrada externa e **ignora o leitor embutido** |
| 4 | smart card |
| 5 | código de barras serial |
| 6 | Wiegand sem separador (facility code sem separador) |
| 7 | ASCII |

### `configuracaoacesso.numeroDigitosCartao`

> ⚠️ **Mudar este campo faz a catraca APAGAR a lista de acesso e a lista
> "somente cartão".** As digitais sobrevivem. Faça backup das listas antes.
> Trocar o tipo de leitor pela tela do equipamento pode mudar este campo sozinho.
> `Catraca.gravar_config` recusa a troca sem `aceito_apagar_listas=True`.

**O número lido do MESMO cartão depende de tipo de leitor + dígitos.** Por exemplo,
Abatrack com 14 dígitos e Wiegand sem separador com 8 dígitos produzem números
diferentes para o mesmo cartão (o facility code entra com larguras diferentes).
Sempre obtenha o número lendo o cartão pela catraca (seção 8), nunca digitando o
número impresso.

### `configuracaoacesso.digitosVariaveis`

Mapa de bits: aceitar N dígitos liga o bit N−1.

| Dígitos | 4 | 6 | 8 | 10 | 12 | 14 | 16 | todos |
|---|---|---|---|---|---|---|---|---|
| Valor | 8 | 32 | 128 | 512 | 2048 | 8192 | 32768 | 43688 |

`padraoCartaoBarras`: 0 = padrão Topdata, 1 = livre.

### `configuracaoseguranca.tipoLista`

| Valor | Efeito |
|---|---|
| 0 | desabilitado: **não consulta a lista**; gira para qualquer identificação válida |
| 1 | só cartões da lista passam |
| 2 | cartões fora da lista podem passar |

Para a catraca decidir sozinha quem passa (cartão ou digital no sensor dela), use
**1**. O 0 só faz sentido quando outro equipamento decide e manda o sinal pela
entrada Wiegand.

`registraAcessoNegado`: quando ligado, tentativas negadas viram registro de
passagem tipo `0x0C`.

### Placa leitora TopProx

A placa de proximidade fala **Abatrack 14 dígitos sem o jumper "PC"** ou
**Wiegand 26 com o jumper**. O tipo de leitor configurado tem de bater com a
posição do jumper.

### Sentido do giro e modos

Na `configuracaoacesso`, `configLeitor1`/`configLeitor2` dizem o que cada leitor
faz e `acionamento1`/`acionamento2` para que lado a catraca libera. Mapa observado
para catraca de braço (`tipoEquipamento: 1`):

| Modo (tela) | configLeitor1 | configLeitor2 | acionamento1 |
|---|---|---|---|
| Entrada e saída | 3 | 2 | 1 (libera os dois lados) |
| Só entrada | 1 | 0 (desligado) | 2 |
| Só saída | 2 | 0 | 3 |
| Entrada com saída livre | 1 | 0 | 6 |
| Saída com entrada livre | 2 | 0 | 7 |

Variantes para catraca montada invertida usam 4/5/6 em `configLeitor`. Não há
antipassback no firmware. Há **um único sensor de digital** para os dois sentidos,
e a lista de acesso não tem direção — não existe "cada lado no seu sentido" com
biometria. O sentido de cada passagem vem no próprio registro (seção 6).

## 4. Lista de acesso

É a lista que a catraca confere (com `tipoLista = 1`).

| Operação | Chamada |
|---|---|
| incluir linha | `POST listaacessoincluiregistro` `{"identificador": "<cartão>", "horario": N}` |
| excluir uma linha | `DELETE listaacessoexcluihorario?identificador=<cartão>&horario=N` |
| excluir a pessoa (todas as linhas) | `DELETE listaacessoexcluiregistro?identificador=<cartão>` |
| esvaziar | `DELETE listaacessoexcluilista` |
| ler | `GET listaacesso?posicao=0` (binário) |
| quantidade | `GET listaacessoquantidade` (não confiável) |

`horario`:

| Valor | Significado |
|---|---|
| 101 | liberado sempre |
| 102 | bloqueado sempre |
| 1..34 | número do horário na tabela (seção 12) |

Armadilhas:

- **Incluir um par (cartão, horário) que já existe → HTTP 400.** Não há
  "substituir": para garantir, exclua o par e inclua (`garantir_na_lista`).
- **Uma pessoa pode ter várias linhas.** Um 101 esquecido convive com um horário
  restrito e libera o dia inteiro. Ao trocar de horário, tire 101/102 antes.
- **`GET listaacesso` às vezes volta com 0 bytes** mesmo com itens. Lista vazia na
  leitura não prova lista vazia.

Formato binário: 1 byte de cabeçalho + registros de 11 bytes:
`uint16 id (big-endian) | 8 bytes BCD do cartão (16 dígitos) | 1 byte horário`.

## 5. Lista "somente cartão"

Auxiliar (o checkbox "somente cartão" por usuário na interface). **Sozinha não
libera ninguém.**

| Operação | Chamada |
|---|---|
| incluir | `POST listasomentecartaoinclui` `{"identificador": "<cartão>"}` |
| excluir | `DELETE listasomentecartaoexclui?identificador=<cartão>` |
| esvaziar | `DELETE listasomentecartaoexcluilista` |
| ler | `GET listasomentecartao?posicao=0` — registros de 10 bytes: `uint16 id | 8 bytes BCD` |

## 6. Passagens (`listabilhetes`)

`GET listabilhetes?posicao=N` → binário: **1 byte de cabeçalho** + até **111
registros de 18 bytes** (pedaço cheio = 1999 bytes).

| Bytes | Campo |
|---|---|
| 0–1 | id (uint16 BE) — numeração da resposta, não do registro |
| 2 | tipo |
| 3–7 | dia, mês, ano (2 dígitos), hora, minuto — um byte **binário** cada |
| 8–15 | cartão, 16 dígitos em BCD empacotado |
| 16–17 | `00 00` |

| Tipo | Significado |
|---|---|
| `0x0A` | giro num sentido |
| `0x0B` | giro no outro sentido |
| `0x0C` | acesso negado (não girou) |

Qual dos giros é "entrada" depende de como a catraca foi montada — confira uma vez
na instalação.

> ⚠️ **Há UM marcador interno de leitura.** Cada pedido entrega o próximo pedaço a
> partir do marcador, **qualquer que seja o `posicao`** — ele só numera os ids da
> resposta. `posicao=0` volta o marcador ao início. **`listabilhetesquantidade`
> também volta ao início**, e o número que ela devolve é um contador constante, não
> uma posição.

Método seguro (o de `Catraca.ler_passagens`):

1. pedir `posicao=0`, depois o próximo, em sequência, **sem nenhum outro pedido de
   `listabilhetes*` no meio** (de nenhum cliente);
2. parar no primeiro pedaço com menos de 111 registros;
3. identificar cada passagem por **(tipo, cartão, minuto, índice de repetição)**,
   nunca pelo id. O índice separa passagens idênticas no mesmo minuto;
4. não guardar "onde parei": ler tudo e comparar com o que já foi visto.

Só são gravados giros (e negados, com `registraAcessoNegado`). Acesso liberado em
que ninguém girou não gera registro.

## 7. Relógio

`GET`/`POST configuracaorelogio`:

```json
{"segundos": 0, "minutos": 30, "hora": 8, "diaSemana": 2, "dia": 4, "mes": 5, "ano": 26}
```

`ano` com dois dígitos; `diaSemana` com domingo = 1.

> ⚠️ **Depois de uma queda de energia o relógio volta para 01/01/2019.** Toda
> passagem dali em diante sai com essa data. Confira e acerte periodicamente
> (`Catraca.conferir_relogio`), de preferência antes de ler passagens.

## 8. Leitura de cartão sob comando

1. `GET cadastrolecartao` → 200 com corpo **vazio**; o leitor fica esperando.
2. `GET cadastrocartaostatus` a cada ~1 s enquanto `status` for 0 ou 1.
3. Resposta final: `{"status": 2, "cartao": "0000000012345678"}` (16 dígitos).

| Status | Significado |
|---|---|
| 0, 1 | esperando / processando |
| 2 | lido |
| 3 | desistiu (~10 s sem cartão; `cartao` todo zero). A catraca continua funcionando — basta rearmar |
| 4 | lido, e o cartão já está na lista (também traz o número) |
| 6 | é o cartão master |
| 7 | **erro de leitura**: detectou o cartão mas não decodificou (seção 14) |
| 13 | lista cheia |
| 14 | indisponível |

`GET cadastrocartao` também lê, mas **inclui o cartão na lista** no mesmo gesto. A
biblioteca não usa esse endpoint.

## 9. Digital: cadastro no sensor da catraca

A catraca lê o dedo no sensor dela e grava sob o número do cartão. O cartão deve
estar na lista de acesso antes. Máximo **2 dedos por pessoa**.

1. `GET cadastrobiometria?identificador=<cartão>&numeroBiometria=<1|2>`
2. `GET cadastrobiometriastatus?identificador=<cartão com 16 dígitos>` a cada
   0,7–1,5 s enquanto `status` for 0 ou 1. **Sem os zeros à esquerda a consulta não
   encontra o cadastro.**

Tabela de estados (a mesma enumeração da seção 8):

| Status | Nome | Status | Nome |
|---|---|---|---|
| 0 | nenhum | 8 | **digital cadastrada** |
| 1 | processando | 9 | erro de leitura do dedo |
| 2 | cartão lido | 10 | erro / tempo esgotado (~5 s sem dedo) — rearmar |
| 3 | erro de cartão | 11 | digital duplicada |
| 4 | cartão duplicado | 12 | memória de digitais cheia |
| 5 | cartão já com digital | 13 | lista de acesso cheia |
| 6 | cartão master | 14 | indisponível |
| 7 | erro de leitura do cartão | | |

> ⚠️ **Enquanto o cadastro está armado a catraca não atende ninguém**: quem
> encosta o dedo para passar vira amostra de cadastro e nem a tentativa é
> registrada. **Não existe endpoint de cancelar.** O que funciona:
> `GET listabiometriareqnumdigitais?identificador=<16 dígitos>` (o pedido de
> contagem por pessoa) **derruba o cadastro pendente**. Pelo mesmo motivo, nunca
> peça essa contagem durante um cadastro que você quer manter.

Rearmar depois do status 10 funciona, mas o visor pisca uma mensagem de operação
inválida a cada ciclo.

## 10. Digital: contagem, leitura, gravação, exclusão

| Operação | Chamadas |
|---|---|
| contagem por pessoa | `GET listabiometriareqnumdigitais?identificador=<16>` e depois `GET listabiometriastatusnumdigitais` até `status` ≠ 0 → `quantidade` |
| ler template | `GET biometriale?identificador=<16>` e depois `GET biometriastatusleitura` até `status` ≠ 0 → `templates` (base64) |
| gravar template | `POST biometriainclui` (octet-stream, template completado com zeros até **1080 bytes**) e depois `GET biometriastatusinclusao` (`status` 1 = ok) |
| excluir de um cartão | `DELETE biometriaexclui?identificador=<cartão>` |
| excluir todas | `GET biometriaexcluitodas` e depois `GET biometriastatusexclusaotodas` |

- Os contadores agregados (`listabiometriaquantidade`, tamanho da lista) já
  devolveram valores velhos. **Confie só na contagem por pessoa.**
- `biometriaexclui` logo depois de outro comando pode falhar (equipamento ocupado):
  repita com uma pausa.

## 11. Template de digital

Um dedo = **570 bytes**; dois dedos = 1072 bytes (formato **não decifrado** — não
manipule).

| Bytes | Campo |
|---|---|
| 0–3 | assinatura `55 55 AA AA` |
| 5–12 | identificador: 16 dígitos, cada byte = **par BCD + 1** |
| últimos 2 | soma de verificação: uint16 little-endian de `soma(bytes[71:-2])` |

Exemplo do identificador: dígitos `...135790` → bytes `... 14 58 91`.

A soma **não cobre o identificador**. Isso permite **mover uma digital para outro
cartão sem a pessoa**:

1. ler o template do cartão antigo;
2. conferir que o identificador dentro dele é mesmo o do cartão antigo;
3. reescrever os bytes 5–12 com o cartão novo;
4. gravar (`biometriainclui`) e **conferir** pela contagem que apareceu no novo;
5. só então excluir do antigo.

Nessa ordem, qualquer falha no meio deixa a pessoa passando pelo cartão antigo, em
vez de trancada do lado de fora.

## 12. Horários

`GET listahorarios?posicao=0` → binário, registros de **58 bytes**, sem cabeçalho.
O FIT tem **34 vagas** (1972 bytes).

| Bytes | Campo |
|---|---|
| 0–1 | posição na tabela (uint16 BE), a partir de 0 |
| 2–57 | 7 dias × 8 bytes, na ordem **segunda, terça, quarta, quinta, sexta, sábado, domingo** |

Cada dia: `hi1 mi1 hf1 mf1 hi2 mi2 hf2 mf2` — duas faixas (hora/minuto de início e
fim); **255 = vazio**.

Gravar: `POST listahorarios?quantidade=<n>&primeiro=true&ultimo=true` com os
registros concatenados (octet-stream).

> ⚠️ **"Mais um": o `horario N` da lista de acesso aponta para a POSIÇÃO N−1 da
> tabela** (a interface faz `horario = posição + 1`). Gravar o horário 1 na posição
> 1 deixa a posição 0 vazia, e o horário 1 passa a barrar todo mundo.

- Dia sem faixa = dia fechado.
- Horário sem nenhuma faixa = **ninguém passa nunca**.
- A biblioteca lê a tabela, substitui só os números pedidos e reenvia a tabela
  inteira, para não depender de como o equipamento trata envio parcial.

## 13. Outros endpoints

| Endpoint | Efeito |
|---|---|
| `GET abreporta` | libera a catraca para um giro |
| `GET cadastrobiometriasemcartao` | cadastro de digital sem cartão (não coberto) |

## 14. Diagnóstico: "Passe o cartão novamente"

Visor mostrando **"Passe o cartão novamente"** ou **"cartão falhou"** (na leitura
sob comando: status 7, "captura falhou") significa que a catraca **detectou** o
cartão mas **não conseguiu decodificá-lo**. Não é problema de lista nem de
cadastro. Na ordem:

1. **Combinação tipo de leitor + número de dígitos.** Teste a combinação completa
   (por exemplo, Abatrack 14; Wiegand sem separador 8), não só o tipo. Lembre que
   mudar os dígitos apaga as listas (seção 3) — faça backup antes.
2. **Jumper e cabo** da placa leitora: Abatrack sem o jumper "PC", Wiegand 26 com
   ele; confira o cabo até a controladora.
3. **Placa leitora com defeito.** Na prática, trocar a placa resolveu quando nada
   acima resolvia.

Sintoma diferente: **cartão encostado não faz nada** (sem bipe, sem registro) com
`tipoLeitor = 3` (Wiegand) → a catraca está ouvindo só a entrada externa e ignora o
leitor embutido. Use proximidade (2).

## 15. Não verificado

- Paginação de `listaacesso` e `listasomentecartao` com listas grandes (a
  biblioteca lê uma resposta só).
- Presença do byte de cabeçalho em `listasomentecartao` (o parser detecta pelo
  tamanho).
- Layout do template de dois dedos.
- Se `listaacessoexcluiregistro` também apaga a digital (assuma que não; use
  `biometriaexclui`).
- Outros modelos e versões de firmware.
