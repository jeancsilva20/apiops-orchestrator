# Mensagens e apresentação do `sen validate`

| Meta | Valor |
|---|---|
| Aberto em | 2026-10-15 |
| Estado | **aplicado** em 2026-10-15 — as sugestões da revisão viraram código |
| Como pedir mudança | preencher a linha `**Novo:**` do item; vazio = fica como está |
| Cobertura | 23 mensagens + o prompt + a apresentação no terminal |

## O que mudou nesta rodada

1. **Texto de todas as 23 mensagens**, pelas três regras da §"Como foram escritas".
2. **Vocabulário**: "régua" → **API-template**, "tombstone" → **marcação de interceptor removido**,
   "escopo" → **ponto** ou o próprio rótulo. Decisões em **T2**.
3. **Prompt de confirmação** reescrito: deixava parecer que subia algo para um ambiente.
4. **Quality gate**: `(gate: ≥70% — trava em DEV+, não aqui)` → `Quality gate: ≥70%`.
5. **Apresentação no terminal**: caixa, tabela e barra de progresso, no padrão do `sen login` e do
   `sen list`. Detalhe na §"Apresentação".

## Como foram escritas

1. **Começar pelo fato, não pelo conceito.** "Este repositório parece apontar para outra API" antes
   de explicar o que é `basePath`. Quem lê um erro quer saber primeiro o que aconteceu.
2. **Separar consequência de instrução.** Cada mensagem responde, nessa ordem: *o que é*, *o que vai
   acontecer*, *o que fazer*. Quando a resposta a "chegou a escrever?" não for óbvia, ela fecha a
   mensagem numa linha própria.
3. **Nada de marcação de cor no texto.** As mensagens nascem na camada de aplicação e viajam também
   para o JSON da esteira; `[bold]` apareceria literal lá. Ênfase vem da ordem das palavras.

## Os canais

| Canal | Quando aparece | Quem lê | Exit |
|---|---|---|---|
| **A** · erros | abortam antes ou depois da escrita | dev no terminal **e** log da esteira | 1 (A7 = 3) |
| **B** · avisos do repositório | o comando segue; algo vai mudar ou sumir | dev, decidindo se publica | 0 |
| **C** · conformidade com a API-template | divergência de padrão, nunca bloqueia | dev **e** code review | 0 |
| **D** · conferência pós-publicação | montam o texto da **A6** | dev depois de uma escrita já feita | 1 |
| **E** · prompt | confirmação interativa, só em modo local | dev | — |

---

# A · Erros que abortam

> Saem como `Erro: {mensagem}` em vermelho, e como `message` no JSON. Exit 1, salvo a A7.

## A1 · Identidade divergente
`application/exceptions/validate_exceptions.py:40`

**Agora:**
```
Este repositório parece apontar para outra API. O `{campo}` declarado aqui é
{no_repo}, mas a API {api_id} no Manager tem {no_manager} — e esse campo não muda
depois que a API é criada.

Confira o `id` em `api-basic-info.yaml`. Se o id estiver certo, só um
administrador do Manager pode acertar o valor divergente.

Nada foi publicado.
```

**Novo:**

## A2 · Template ausente
`validate_exceptions.py:61`

**Agora:**
```
Esta API ainda não tem uma API-template vinculada, e é a template que define o
padrão contra o qual o `validate` compara.

Preencha `spec.template` em `api-basic-info.yaml` com o id da template. Se não
souber qual é, peça ao administrador do Manager.
```

**Novo:**

## A3 · Layout inválido
`validate_exceptions.py:78` — aborta antes de qualquer rede.

**Agora:**
```
Não encontrei o arquivo `{caminho}`, que é obrigatório.{detalhe}

O nome precisa ser exatamente esse, inclusive maiúsculas e minúsculas. O comando
parou antes de acessar o Manager.
```

**Novo:**

## A4 · Custom inexistente
`validate_exceptions.py:95`

**Agora:**
```
O interceptor Custom de id {id}, declarado em {escopo}, não existe neste
ambiente.

Ids de Custom valem só dentro de um ambiente — se este repositório veio de
outro, o id precisa ser atualizado. Confira o id na lista de interceptors
customizados do Manager.

Nada foi publicado.
```

**Novo:**

## A5 · API-template inalcançável
`validate_exceptions.py:116-131`

**Agora:**
```
MOLDE:  Não consegui ler a API-template {id}, e sem ela não há padrão para
        comparar. {causa}

        Nada foi publicado.

404  →  Essa API não existe neste Manager. Confira o id em `spec.template`, no
        `api-basic-info.yaml`.

403  →  O acesso foi negado. Normalmente é sessão expirada: rode `sen login` e
        tente de novo. Se continuar negado, a template pode pertencer a outro
        ambiente.

outro → O Manager não respondeu. Tente de novo em alguns instantes; se persistir,
        acione o time de acesso.
```

> A ordem das hipóteses no 403 é parte da mensagem: sessão expirada é a causa mais comum e a única
> que o dev resolve sozinho. Um teste trava essa ordem.

**Novo (molde):**

**Novo (404):**

**Novo (403):**

**Novo (outro):**

## A6 · Publicação divergente
`validate_exceptions.py:149` — o `{lista}` são as mensagens do bloco **D**, agora em linhas.

**Agora:**
```
O Manager aceitou a publicação, mas o que ficou gravado não é o que foi enviado:

  - {diferença}
  - {diferença}

Parte da alteração se perdeu no caminho. Confira o estado atual da revisão no
Manager antes de publicar de novo.
```

**Novo:**

## A7 · Governança bloqueou · *exit 3*
`validate_exceptions.py:176` — **o exit 3 não muda**, só o texto.

**Agora:**
```
A governança do Manager não liberou a publicação. A API precisa ter estes
atributos antes de subir:

  - {atributo}

Adicione em `apiTags`, no `api-basic-info.yaml`, e rode o comando de novo.

Nada foi publicado. (workflow {wf}, stage {st})
```

> Os atributos foram para uma lista porque, separados por vírgula, o nome quebrava no meio em
> terminal estreito (`My \nnew`) — justamente o dado que o dev precisa copiar.

**Novo:**

---

# B · Avisos do repositório

> `WARNING` em amarelo, no bloco **"O que vai mudar no Manager"**. Não bloqueiam.

## B1 · Herança pura apaga a lista própria · **novo na V-27**
`domain/services/revision_payload.py:113`

**Agora:**
```
{escopo}: hoje tem {n} interceptor(es) próprio(s) no Manager ({itens}), mas o
repositório declara que este ponto apenas herda. Ao publicar, esses interceptors
saem e o fluxo passa a ser o do nível acima.
Se a intenção era mantê-los, liste-os no arquivo com `inherit: false`.
```

**Novo:**

## B2 · `inherit: false` sem itens · **novo na V-27**
`revision_payload.py:94`

**Agora:**
```
{escopo}: o arquivo declara `inherit: false` mas não lista nenhum interceptor.
O Manager não consegue representar "não executa nada" — lista vazia sempre
significa herdar. Na prática este ponto vai continuar herdando o fluxo do nível
acima.
Para que ele execute outra coisa, liste os interceptors que devem valer aqui.
```

**Novo:**

## B3 · Raiz esvaziada · **novo na V-27**
`revision_payload.py:105`

**Agora** — o rótulo do escopo saiu: renderizava "raiz da revision", e falar do `all.yaml`
diretamente é mais claro.
```
O `all.yaml` não declara nenhum interceptor, e a API tem {n} hoje no Manager
({itens}). O `all.yaml` é o nível mais alto e não herda de ninguém, então ao
publicar esses interceptors saem — e com eles o fluxo de todos os recursos e
rotas que os herdavam.
Se a intenção era mantê-los, declare-os no `all.yaml`.
```

**Novo:**

## B4 · Recursos que somem
`revision_payload.py:261`

**Agora:**
```
Estes recursos existem no Manager e não no repositório, e serão removidos ao
publicar: {nomes}. O que não está no repositório não é enviado, e o que não é
enviado o Manager apaga.
```

**Novo:**

## B5 · API-template sem interceptors
`application/services/regua_service.py:156`

**Agora:**
```
A API-template {id} não tem nenhum interceptor configurado, então não há padrão
para comparar. A validação segue, mas sem verificar conformidade.
```

**Novo:**

## B6 · A template do cofre vence o manifesto
`regua_service.py:129` — só na esteira.

**Agora:**
```
O `api-basic-info.yaml` aponta a API-template {x}, mas a esteira está usando a
{y}, definida em variável de ambiente. A variável tem prioridade de propósito:
assim a template não pode ser trocada por um commit. Seguindo com a {y}.
```

**Novo:**

---

# C · Conformidade com a API-template

> Linhas de tabela. São as mais lidas do comando — aparecem dezenas de vezes num relatório, então
> brevidade vale acima de tudo. O escopo tem coluna própria e não se repete no texto.
>
> `{interceptor}` renderiza como `Custom #33 — CyberArk and OAuth Autentication`, ou só
> `Custom #33`, ou o próprio tipo nos nativos.

## C1 · Configuração diverge · WARNING
`domain/services/template_conformance.py:194`

**Agora:**
```
"{interceptor}" está configurado diferente da template ({campo}: {obtido}, na template {esperado})
```

**Novo:**

## C2 · Item além da template · INFO
`template_conformance.py:221`

**Agora:**
```
"{interceptor}" não existe na template — é um acréscimo desta API
```

**Novo:**

## C3 · Item da template não executado · WARNING
`template_conformance.py:234`

**Agora:**
```
"{interceptor}" está na template, mas não é executado aqui
```

**Novo:**

## C4 · Substituição que ficou para trás · WARNING
`template_conformance.py:268`

**Agora:**
```
este ponto substitui o fluxo herdado e deixa {n} interceptor(es) de fora, mas a
remoção pretendida era de apenas {m}. O nível acima provavelmente ganhou itens
depois que esta lista foi escrita. Fora: {itens}
```

**Novo:**

---

# D · Conferência pós-publicação

> Compõem a **A6**, agora como itens de lista. Todas ganharam sujeito e verbo — antes eram
> fragmentos. A ação fica só na A6 (**T5**), para não repetir oito vezes.

| # | Agora | Arquivo |
|---|---|---|
| D1 | `a operação {MÉTODO} {path}, do recurso {nome}, foi enviada mas não está no Manager` | `revision_payload.py:341` |
| D2 | `a operação {MÉTODO} {path}, do recurso {nome}, está no Manager mas não foi enviada` | `:346` |
| D3 | `{escopo} foi enviado mas não está no Manager` | `:356` |
| D4 | `{escopo}: foram enviados {n} interceptor(es) e o Manager gravou {m}` | `:358` |
| D5 | `o recurso {nome} foi enviado mas não está no Manager` | `:366` |
| D6 | `o recurso {nome} está no Manager mas não foi enviado` | `:371` |
| D7 | `{escopo}: o Manager ainda tem {n} marcação(ões) de interceptor removido ({itens}) que não foram enviadas; elas continuam suprimindo itens do fluxo herdado` | `:382` |
| D8 | `{escopo}: destination/timeout foi enviado como {x} e gravado como {y}` | `:396` |

**Novo (indique o número):**

---

# E · Prompt de confirmação

## E1 · Confirmar a gravação do rascunho
`application/services/validate_service.py:301` (texto) + `cli_adapter.py` (caixa e pergunta)

O texto anterior — *"Publicar na revisão 1 (id 9161) da API?"* — parecia anunciar uma subida de
ambiente com deploy. Quem roda `validate` quer validar; a gravação do rascunho é o **meio** pelo
qual a governança dá o veredito.

**Agora** — a frase vem do serviço, a pergunta e a caixa vêm da borda:
```
+- Confirmação -------------------------------------------------------------+
| Para validar a sua API, uma versão de rascunho será gravada no API         |
| Manager, na revisão 1 (id 9161).                                           |
| Nenhum ambiente recebe deploy, e nada é promovido.                         |
+----------------------------------------------------------------------------+
Deseja prosseguir? [y/N]:
```

A pergunta ficou na borda de propósito: o serviço não sabe que a confirmação é um sim/não de
terminal — e um teste trava isso (`"?" not in mensagem`).

**Novo:**

---

# Apresentação no terminal

Seguindo o desenho do `sen login` (caixa de sessão) e do `sen list` (tabela): **caixa** para
identidade, **tabela** para itens repetidos, **grade de rótulos** para pares chave/valor, **barra**
para espera. Todas as seções têm a mesma largura — a referência do `sen login` — então as bordas se
alinham.

```
┌─ Validação ───────────────────────────────────────────────────────────────┐
│ API          Servico de Letras 2.0.0                                      │
│              id 417  ·  v1.0.0  ·  /letras/v2                             │
│ Rascunho     #1 (id 9161)                                                 │
│ Template     API 414  revisão #3  ·  8 interceptor(es)  ·  a1b2c3d4       │
│ Modo         local                                                        │
└───────────────────────────────────────────────────────────────────────────┘

Conformidade com a API-template  2 aviso(s) · 1 informativo(s)
┌────────────┬────────────────────────┬─────────────────────────────────────┐
│ SEVERIDADE │ ONDE                   │ O QUE                               │
├────────────┼────────────────────────┼─────────────────────────────────────┤
│ WARNING    │ raiz da revision       │ "Custom #33 — CyberArk..." está na  │
│            │                        │ template, mas não é executado aqui  │
└────────────┴────────────────────────┴─────────────────────────────────────┘
Nenhum deles impede a publicação.

O que vai mudar no Manager  1 aviso(s)
▸ POST /tarefas/{id}/...: hoje tem 1 interceptor(es) próprio(s) no Manager...

Governança  liberada (2 atributo(s) exigido(s), nenhum faltando)
  workflow 500 · stage 1402 (lidos da revisão)

Rascunho  gravado e conferido (nenhum ambiente recebeu deploy)

Quality score  42.0%  Quality gate: ≥70%
 1. Adicione exemplos de request e response
```

## Decisões da apresentação

| # | Decisão | Por quê |
|---|---|---|
| V1 | **Conformidade em tabela; avisos do repositório em bloco** | São coisas diferentes. Os achados de conformidade são curtos e repetitivos — tabela. Os avisos do repositório têm várias frases e quebra própria: numa coluna viram uma coluna de palavras soltas |
| V2 | A coluna **ONDE quebra em vez de truncar** | `POST /tarefas/{id}/atribuicao-responsavel` cortado em `…atribuicao-res…` não identifica rota nenhuma |
| V3 | **Barra de progresso nomeia a etapa** | São cinco chamadas de rede em sequência; uma barra sem rótulo não diz se o que demora é ler a template ou gravar o rascunho |
| V4 | **Progresso não existe em `-o json`/`-o yaml`** | O stdout carrega o documento que a esteira parseia, e muita esteira captura `2>&1` — stderr também não salvaria. Fora de terminal mas em `-o text`, cada etapa vira uma linha em stderr |
| V5 | **A confirmação pausa a barra** | Uma `Live` animando por baixo de um prompt embaralha o que o dev está lendo na hora de decidir |
| V6 | `≥` **cai para `>=`** quando o console não suporta | O comando não pode morrer com `UnicodeEncodeError` por causa de um glifo decorativo — já aconteceu na primeira renderização |

**Novo (indique o número):**

---

# Decisões transversais

## T1 · Citação de documento interno — **removida**
`(V-27 §2)`, `(T06)`, `(V-27 §8, E-1)` saíram do texto do usuário. A rastreabilidade continua nos
docs e nos comentários do código, que é onde a regra 4 do AGENTS.md atua.

**Novo:**

## T2 · Vocabulário — **aplicado**

| Antes | Agora | Observação |
|---|---|---|
| régua | **API-template** | é o nome do objeto no Manager; "régua" não existe na interface |
| tombstone | **marcação de interceptor removido** | |
| escopo | **ponto**, ou o próprio rótulo (`GET /tarefas`, `all.yaml`) | mantido como `{escopo}` onde é o prefixo da linha |
| interceptor governado | **interceptor** | o recorte `FIRST`/`SECOND` é interno |
| herança pura | **apenas herda** | |
| tenant | **ambiente** | |

**Novo:**

## T3 · Ênfase — **caixa alta removida**
`REMOVIDA`/`REMOVIDO`/`HERDA` saíram. Negrito viraria `[bold]` literal no JSON, porque a mensagem
nasce na camada de aplicação. "Ao publicar, esses interceptors saem" carrega o mesmo peso.

**Novo:**

## T4 · Fechamento dos erros — **só onde a dúvida é real**
"Nada foi publicado." ficou em A1, A4, A5, A6 e A7. Saiu da A3, onde o comando nem abriu conexão —
ali virou "o comando parou antes de acessar o Manager", que responde a mesma pergunta sem sugerir
que houve risco.

**Novo:**

## T5 · Formato da A6 — **lista em linhas**
O `; ` virou lista. Com três ou mais diferenças, a frase única produzia um parágrafo corrido em que
nada se distinguia. A ação aparece uma vez, no fim.

**Novo:**

---

# O que **não** mudou, de propósito

| Item | Por quê |
|---|---|
| **exit 3** da A7, e os exits 0/1 | a esteira ramifica por eles sem ler texto; mudar quebraria o contrato |
| **chaves do JSON** (`regua`, `findings`, `gatePercent`…) | é o contrato `apiops.sen-validate/v1` que a esteira consome. O vocabulário mudou na **apresentação**; renomear chave é outra decisão, e vale discutir à parte |
| `workflow {wf}, stage {st}` na A7 | presumo que operação use para rastrear; foi para o fim da mensagem, mas continua lá |
