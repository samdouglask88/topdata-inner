# Leitor Wiegand externo e controle de sentido — Topdata Inner

Como ligar **leitores externos com saída Wiegand** (facial, biométrico, QR) numa
catraca Topdata e fazer **entrada e saída funcionarem separadamente**.

> Projeto independente, sem vínculo com a Topdata. Não oficial.

O resto deste repositório foi conferido numa **FIT firmware 6.12**. Esta página é
de uma **FIT firmware 6.47, Web Server v4.0.1** — interface diferente, ver a
seção 9. O que não foi verificado está na seção 10.

Sumário:

1. [O cenário](#1-o-cenário)
2. [O erro que custa o dia: o Acionamento 2](#2-o-erro-que-custa-o-dia-o-acionamento-2)
3. [Quem decide o sentido](#3-quem-decide-o-sentido)
4. [Configuração que funciona](#4-configuração-que-funciona)
5. [Ligação física](#5-ligação-física)
6. [O que não funciona: botoeira e relé](#6-o-que-não-funciona-botoeira-e-relé)
7. [Teto do Wiegand 26](#7-teto-do-wiegand-26)
8. [Quando o visor diz "passe o cartão novamente"](#8-quando-o-visor-diz-passe-o-cartão-novamente)
9. [Interface 6.47 x 6.12](#9-interface-647-x-612)
10. [Não verificado](#10-não-verificado)

---

## 1. O cenário

Uma catraca, **dois leitores externos**, um de cada lado: um para quem entra,
outro para quem sai. Cada leitor valida a pessoa e manda o número pela saída
Wiegand 26. A catraca só gira.

Em vários leitores faciais a saída Wiegand **não existe no corpo do aparelho** —
vem num módulo acessório separado, que precisa ser comprado junto. Confira isso
antes de fechar o projeto.

Nesse arranjo quem filtra é o leitor, não a catraca. Então o normal é deixar o
controle de acesso da catraca **desligado** (`tipoLista = 0`, seção 3 do
[PROTOCOLO](PROTOCOLO.md)) e deixar a lista de verdade no leitor externo.

## 2. O erro que custa o dia: o Acionamento 2

**O Acionamento 2 não controla sentido. Ele é relé de urna.**

É tentador configurar assim, porque a tela deixa:

```
Acionamento 1 = LIBERA PARA ENTRADA
Acionamento 2 = LIBERA PARA SAÍDA
```

Isso está errado e produz um sintoma que parece defeito de fio: **uma única
leitura acende as duas setas verdes e solta a roleta nos dois sentidos**. Os dois
acionamentos disparam no mesmo acesso concedido.

O Manual do Web Server Controle Catraca (Rev02, cap. 11.2) é explícito:

> "O acionamento 1 na catraca tem como função única o controle do giro e não pode
> ser utilizado para outra finalidade."
>
> "O acionamento 2 na catraca é utilizado quando a catraca utilizar Urna."

E na tabela oficial de modos de operação da catraca — todos eles, montagem
direita e esquerda — **Acionamento 2 aparece como Desabilitado**.

Aquela configuração de dois acionamentos por sentido é a receita de **torniquete
de terceiros**, em que a placa Topdata comanda uma roleta de outro fabricante por
dois relés. Numa catraca Topdata ela não vale.

Sintoma irmão, que confirma o diagnóstico: pondo os **dois** acionamentos em
`LIBERA PARA SAÍDA`, só a saída libera — nos dois leitores. É a prova de que o
acionamento não escolhe sentido, só manda girar.

## 3. Quem decide o sentido

O sentido vem de **por qual conector de leitor a leitura entrou**, cruzado com o
que está configurado em "Leitor 1" e "Leitor 2".

```
leitura chega no conector LEITOR 1  ->  Leitor 1 = SOMENTE ENTRADA  ->  gira para entrada
leitura chega no conector LEITOR 2  ->  Leitor 2 = SOMENTE SAÍDA    ->  gira para saída
```

O Acionamento 1 é o único que manda girar, e ele gira para o lado que o leitor de
origem determinou.

Corolário prático: **se os dois leitores estiverem no mesmo conector** (ou
emendados em paralelo), a catraca não tem como distinguir, e todas as passagens
saem com o mesmo sentido. Um leitor por conector, sem emenda.

## 4. Configuração que funciona

Catraca → Configurações → Acesso:

| Campo | Valor |
| --- | --- |
| Equipamento | CATRACA |
| Tipo de leitor | WIEGAND |

Catraca → Configurações → Acesso → Avançadas:

| Campo | Valor |
| --- | --- |
| Leitor 1 | SOMENTE ENTRADA |
| Leitor 2 | SOMENTE SAÍDA |
| Acionamento 1 | LIBERA PARA ENTRADA E SAÍDA |
| **Acionamento 2** | **DESABILITADO** |
| Tempo de acionamento 1 | 5 |

Catraca → Configurações → Segurança:

| Campo | Valor |
| --- | --- |
| Controle de acesso | DESATIVADO |

Se o seu firmware não oferecer "DESABILITADO" no Acionamento 2, use o **Modo de
operação = ENTRADA E SAÍDA** pronto, que o próprio Web Server preenche certo, e
depois ajuste só Leitor 1 e Leitor 2.

Teste: uma leitura em cada lado. Tem que acender **uma seta de cada vez, cada uma
no seu lado**. Se acender uma só e sempre a mesma, a configuração está certa e o
problema passou a ser de fio — ver a seção 5.

## 5. Ligação física

A placa (**PCI CONTROLE CATRACA V2.2** nos modelos da linha 4) tem **dois
conectores brancos separados, rotulados `LEITOR 1` e `LEITOR 2`**, perto de
`BIO_1` e `SENS BIO`. São distintos dos conectores de biometria (`BIO_1`/`BIO_2`/
`BIO_3`) e dos de facial Topdata (`FACIAL 1`/`FACIAL 2`).

O esquema oficial "Wiegand – Dois leitores" do suporte Topdata diz, com todas as
letras: «Conectar ao "leitor 1" ou "leitor 2" da PCI INNER» e «Habilitar via
software o "leitor 2"».

- leitor da **entrada** → conector `LEITOR 1`
- leitor da **saída** → conector `LEITOR 2`
- um cabo em cada, **sem emenda e sem paralelo**

Conector de 6 vias, modo Wiegand:

| Pino | Função | Cor no chicote Topdata |
| --- | --- | --- |
| 01 | GND | marrom |
| 02 | polarizador (chave mecânica, não é sinal) | — |
| 03 | 5 V | vermelho |
| 04 | CLOCK — é o Data 0 no modo Wiegand | laranja |
| 05 | não conectado | — |
| 06 | DADO — é o Data 1 no modo Wiegand | amarelo |

Dois detalhes que derrubam a ligação:

- **Terra comum é obrigatório.** O leitor externo costuma ter fonte própria. O GND
  dessa fonte tem que ir ao GND da placa. Sem isso o Wiegand não fecha o circuito
  e a leitura simplesmente não chega — sem erro, sem bipe, sem nada.
- **Acima de 15 m não liga direto.** Precisa do módulo opto-isolador (PCI Opto) no
  meio. Abaixo disso, a partir da PCI Inner Acesso v1.1, vai direto no conector.

Se um dos lados não ler, **inverta entre si os fios dos pinos 04 e 06 daquele
lado**. É o par de dados trocado, e é reversível.

## 6. O que não funciona: botoeira e relé

Ideia que parece boa e não é: usar o **relé** do leitor externo numa entrada de
botoeira da catraca, uma para entrada e outra para saída.

Não funciona, por dois motivos, cada um sozinho fatal:

1. **A botoeira é uma entrada só, e é bidirecional.** Não existem duas entradas
   "liberar entrada" e "liberar saída". O jeito clássico (Instrução Técnica
   IP004/Ed.001) é um botão normalmente fechado **em série com a alimentação do
   solenóide** — ele corta a energia e solta o braço nos dois sentidos. O jeito
   novo (IP049/Ed.001) aterra o Sensor 3 e também não tem sentido.
2. **Passagem por botoeira não gera registro.** Some do relatório.

Atenção ao vocabulário: o que a Topdata chama de **relé 1 / relé 2**
(`NA1-C1-NF1`, `NA2-C2-NF2`) são **saídas** da catraca, não entradas. É a catraca
mandando sinal para fora.

## 7. Teto do Wiegand 26

O Wiegand 26 carrega **8 bits de facility code + 16 bits de número**. O número
máximo é **65535**.

Acima disso o valor chega **cortado**, sem erro nenhum: `2000002` vira `33922`. Se
a sua matrícula passa de 65535, ou você usa outro campo como número de cartão, ou
muda o formato.

## 8. Quando o visor diz "passe o cartão novamente"

Esse sintoma é de decodificação, não de lista nem de cadastro, e está detalhado na
[seção 14 do PROTOCOLO](PROTOCOLO.md#14-diagnóstico-passe-o-cartão-novamente).

Dois pontos que valem repetir aqui, porque na prática são os que pegam:

- **Jumper "PC" da placa leitora.** Sem o jumper ela fala Abatrack 14 dígitos; com
  o jumper, Wiegand 26. A posição do jumper tem que bater com o "Tipo de leitor"
  da tela. Essa é física: nenhuma combinação de tela resolve.
- **Trocar o Tipo de leitor apaga a lista de acesso e a lista somente-cartão.**
  Faça backup antes (seção 3 do PROTOCOLO; `gravar_config` exige
  `aceito_apagar_listas=True`).

Regra geral que esta instalação ensinou: **sintoma que não muda com nenhuma
configuração de tela não é configuração.** Antes de trocar mais um campo, vá ver o
número que está chegando na catraca.

## 9. Interface 6.47 x 6.12

Diferenças encontradas, para quem só conhece a 6.12:

- "tipo de lista" virou **"Controle de acesso"**, na aba Segurança.
- "Tipo de leitor" tem seis opções, incluindo `WIEGAND FACILITY CODE SEM
  SEPARADOR`.
- Existe uma aba **"Registros"**, só de exportação.
- Os ajustes de sentido estão atrás do botão **"Avançadas"**, na aba Acesso.

## 10. Não verificado

- **A correspondência pino ↔ Data 0/Data 1.** O esquema da Topdata rotula os dois
  fios de dados como "CLOCK" (pino 04) e "DADO" (pino 06), nomes herdados do
  Abatrack. O diagrama do PCI Opto mostra "Data 0" e "Data 1" do lado do leitor,
  mas não amarra os dois explicitamente. A tabela da seção 5 usa a convenção
  padrão. Se não ler, inverta os dois — é reversível.
- **O manual citado na seção 2 é o "Controle Catraca Rev02"**, da linha Catraca 4
  (Fit 4, Revolution 4, Box 4, PNE 4). Os nomes de campo batem com a 6.47, mas
  outra versão de firmware pode mudar a tela.
- **Confirmação em campo da configuração da seção 4.** O diagnóstico vem do manual
  e o sintoma observado bate com ele; a validação na catraca estava pendente
  quando esta página foi escrita.
- Modelos de catraca fora da linha Inner/FIT.
