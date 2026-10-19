# Plano dos comandos `sen` — comportamento, fluxo e exceções

| Meta | Valor |
|---|---|
| Data | 2026-10-15 |
| Natureza | **Plano de refinamento.** Não autoriza código. Entrada da divisão em specs/changes OpenSpec |
| Escopo | Peças e comandos afetados pelo novo layout (D-005) e pela régua via Manager (D-004/V-11) |
| Fora de escopo | `sen deploy` (CD, não toca layout) · `sen list` e `sen completeness` (já entregues) · esteiras (ÉPICO 05) |
| Antecedentes | [análise de complexidade](analise-complexidade-orquestrador.md) · [D-005](d005-layout-revisado.md) · [comandos canônicos](../../../../arquitetura-apiops-memory-bank/knowledge/comandos-cli-sen.md) · [backlog](../../../../arquitetura-apiops-memory-bank/delivery/backlog-orquestrador.md) |

> Convenção dos cenários: `DADO / QUANDO / ENTÃO`. Cada cenário é um teste a escrever. Os marcados
> com ⚠️ dependem de decisão aberta (§9) e **não devem virar teste antes dela**.

---

## 1. Vocabulário — fechado nesta sessão

Dois termos vinham sendo usados com sentidos trocados. Ficam assim:

| Termo | Direção | Natureza |
|---|---|---|
| **importer** | repositório → orquestrador | **peça interna**, sem comando próprio; roda automaticamente dentro de `validate` e `publish` |
| **versionador** | Manager → repositório | **peça interna**, exposta por um comando (§5); materializa a árvore de arquivos |

Onde a D-005 §8 e a V-22 §5 dizem "import … gerar YAML", leia-se **versionador**.

---

## 2. O ciclo completo

```
                      ┌──────────────────────────────────┐
                      │        Sensedia API Manager      │
                      └───────┬──────────────────┬───────┘
                        GET   │                  │  GET + PUT
                              ▼                  ▲
                   ┌─────────────────┐   ┌───────┴─────────┐
                   │   VERSIONADOR   │   │    PUBLISHER    │
                   │ (Manager → repo)│   │  (repo → Manager)│
                   └────────┬────────┘   └───────▲─────────┘
                            │ escreve            │ consome
                            ▼                    │
                   ┌─────────────────────────────┴───────┐
                   │        REPOSITÓRIO DA API (git)      │
                   │  api-basic-info.yaml · all-all.yaml  │
                   │  resources/<slug>/resource.yaml      │
                   │  resources/<slug>/<método>_<path>.yaml│
                   └────────┬─────────────────────────────┘
                            │ lê
                            ▼
                   ┌─────────────────┐       ┌──────────────────┐
                   │    IMPORTER     │──────▶│  VALIDATOR       │
                   │ (repo → memória)│       │ schema + régua   │
                   └─────────────────┘       └──────────────────┘
                                                      │ GET
                                                      ▼
                                              régua = API 414
```

---

## 3. Peça interna — `importer`

**Responsabilidade:** carregar o repositório para a memória do orquestrador, produzindo o modelo de
domínio. Não faz rede. Não escreve arquivos.

### 3.1 Comportamento esperado

1. Descobre a árvore a partir da raiz: `api-basic-info.yaml`, `all-all.yaml` e `resources/*/`.
2. Em cada `resources/<slug>/`: lê `resource.yaml` e todos os `*.yaml` restantes como operações.
3. **Não usa índice** — não existe `resources.yaml`. A descoberta é por varredura de diretório.
4. A identidade de uma operação é `(método, path)` lida do conteúdo, **não do nome do arquivo**.
5. O nome do arquivo é consequência da regra de nomenclatura, nunca fonte de verdade.
6. Converte `content` de objeto YAML tipado para o modelo; a serialização para string JSON é do adapter.

### 3.2 Fluxo feliz

```
CENÁRIO  Carregar um repositório bem formado
DADO     um repositório com api-basic-info.yaml, all-all.yaml e 2 pastas em resources/
E        cada pasta com resource.yaml e ao menos um arquivo de operação
QUANDO   o importer carrega o repositório
ENTÃO    devolve 1 basic info, 1 escopo all, 2 recursos e N operações
E        cada operação traz (método, path, destination, inherit, listas de interceptors)
E        nenhuma chamada de rede foi feita
```

### 3.3 Exceções

| # | Cenário | Comportamento esperado |
|---|---|---|
| I-1 | `api-basic-info.yaml` ausente na raiz | erro de estrutura, exit `1`, aponta o caminho esperado |
| I-2 | `resources/` ausente ou vazio | erro de estrutura — uma API sem operação não é publicável |
| I-3 | pasta em `resources/` sem `resource.yaml` | erro nomeando a pasta |
| I-4 | pasta em `resources/` só com `resource.yaml`, sem operação | erro — recurso é identificado pelo conjunto de operações (V-12a) |
| I-5 | YAML sintaticamente inválido | erro com arquivo, linha e coluna; **não** prossegue para schema |
| I-6 | duas operações com o mesmo `(método, path)` | erro de colisão nomeando os dois arquivos |
| I-7 | arquivo `.yaml` solto fora de `resources/<slug>/` | ignorado com `INFO`, ou erro — ⚠️ depende de V-18 |

---

## 4. Peça interna — `versionador`

**Responsabilidade:** materializar o repositório a partir do estado remoto da API.

**Estado atual:** `ApiRepoAdapter` funciona e é agnóstico de layout (preservar). `VersionerService`
é esqueleto com um buraco — o `# Create files` nunca foi implementado. `JsonToYamlService` e
`RevisionFileGenerator` existem para o layout antigo. Falta o elo `GET → ApiFull`.

### 4.1 Comportamento esperado

1. `GET /apis/{spec.id}` → a revision alvo com `interceptors`, `resources`, `destination`, `timeout`.
2. **Particiona** cada lista de interceptors (V-22):
   `GOVERNED_EXECUTION_POINTS = {"FIRST", "SECOND"}`. Só o governado vira YAML; o preservado não
   chega ao repositório.
3. Classifica o fluxo de cada escopo contra o escopo acima → `inherit: true` (herança ou append) ou
   `inherit: false` (quebra). A classificação compara **sequência e `content`**, nunca só o tipo.
4. Gera a árvore com nomes determinísticos (D-005 §4): slug do recurso, desambiguação legível,
   marca `sha1(operações)[:6]` quando houver colisão **ou truncamento**.
5. Escreve sob diretório temporário e só promove ao final (`.lock` + `.tmp_*` → rename).
6. **Estabilidade:** não renomeia pasta existente que já contenha as mesmas operações.

### 4.2 Fluxo feliz

```
CENÁRIO  Materializar uma API existente
DADO     a API 417 no Manager, revision 2, com 4 recursos e 7 operações
E        um diretório de destino limpo
QUANDO   o versionador roda
ENTÃO    cria .lock e um diretório .tmp_<n>_<timestamp>
E        escreve api-basic-info.yaml com spec.id=417 e spec.template declarado
E        escreve all-all.yaml com destination, timeout e as duas listas de interceptors
E        escreve resources/<slug>/resource.yaml para cada recurso
E        escreve um arquivo por operação, nomeado <método>_<path>.yaml
E        NÃO escreve nenhum interceptor com executionPoint fora de FIRST/SECOND
E        promove .tmp_* para o nome final e remove o .lock
E        reexecutar produz exatamente os mesmos bytes
```

```
CENÁRIO  Determinismo sob colisão de nome
DADO     uma API com dois recursos de mesmo name ("Letras")
QUANDO   o versionador roda
ENTÃO    desambigua primeiro pelo sufixo legível (slug do path da 1ª operação)
E        se ainda colidir, usa a marca sha1 das OPERAÇÕES (nunca do name)
E        as duas pastas existem, distintas, sem perda de operação
```

### 4.3 Exceções

| # | Cenário | Comportamento esperado |
|---|---|---|
| V-1 | `.lock` já existe | erro — outra execução em curso ou resíduo; não prossegue |
| V-2 | diretório da revision alvo já existe | erro explícito, sem sobrescrever |
| V-3 | falha no meio da escrita | o `.tmp_*` **não** é promovido; repositório fica intacto; `.lock` é removido |
| V-4 | **item governado não representável** no YAML | **falha alta e explícita** (V-22 §4.1) — perda silenciosa é o único desfecho inaceitável |
| V-5 | caminho excederia o limite do SO | trunca pela regra e aplica a marca; se ainda exceder, erro nomeando o recurso |
| V-6 | nome de pasta reservado no Windows (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`) | sufixa `-recurso` |
| V-7 | escalar que começa com indicador YAML (`*`, `&`, `!`, `|`, `>`, `%`, `@`, `` ` ``, `[`, `{`, `,`, `?`) | **cita a string** — defeito real já observado em `replaceChar: *****` |
| V-8 | valor string que parece número (`"1000"`) | **preserva como string citada** — o wire traz `"quota": "1000"` e o round-trip não pode convertê-lo para inteiro |
| V-9 | API sem nenhum recurso | gera basic info + `all-all.yaml`, `resources/` vazia, com `WARNING` |
| V-10 | tombstone no fluxo remoto | ⚠️ depende de **V-25**; hoje só há comentário, e o round-trip **não fecha** |

---

## 5. Comando — expõe o versionador

> ⚠️ **Decisão aberta (§9, D-1):** o catálogo canônico lista `sen version sync` como
> "compara/reconcilia a revision canônica, PRD como alvo padrão, sem alterar o Git remoto". Não há
> comando que **materialize** a árvore pela primeira vez. O plano assume que `sen version sync`
> ganha os dois modos abaixo; confirmar antes de virar spec.

| Modo | Efeito |
|---|---|
| **materializar** | repositório novo/vazio → escreve a árvore completa |
| **reconciliar** | repositório existente → compara com o remoto e **relata** divergências, sem alterar o Git remoto |

### 5.1 Fluxo feliz (reconciliar)

```
CENÁRIO  Reconciliar repositório em dia
DADO     um repositório materializado da revision alvo
E        nenhuma alteração no Manager desde então
QUANDO   sen version sync roda em modo reconciliar
ENTÃO    reporta "sem divergências"
E        exit code 0
E        nenhum arquivo é alterado
```

```
CENÁRIO  Reconciliar com divergência
DADO     que alguém alterou o destination de uma operação pela UI do Manager
QUANDO   sen version sync roda
ENTÃO    lista a divergência (escopo, campo, valor local, valor remoto)
E        NÃO altera o repositório automaticamente
E        exit code 0 — divergência é informação, não falha
```

### 5.2 Exceções

| # | Cenário | Comportamento |
|---|---|---|
| S-1 | `spec.id` local ≠ API alvo | erro — indício de repositório apontado para outra API (D-001) |
| S-2 | API inexistente no Manager (404) | erro técnico, exit `1`, mensagem humana |
| S-3 | sessão expirada | mensagem orientando `sen login`, exit `1`, sem stacktrace |
| S-4 | repositório existe e o modo é materializar | erro — exigir modo reconciliar ou destino limpo |

---

## 6. Comando — `sen validate`

**Responsabilidade:** dar ao developer **e** à esteira a visão completa da API antes do merge —
gramática local, conformidade com a régua, **publicação de prova no Draft** e o veredito do Adaptive
Governance, tudo num relatório único que serve também ao code review.

> **Revisão de 2026-10-15.** A versão anterior deste plano modelava o `validate` como diagnóstico
> read-only. **Errado.** O comando **escreve** na revisão 1 (Draft) da própria API. Isso não contraria
> o canônico: o P9 registra que *"validate síncrono e **sobrescrita da revision Draft** já
> confirmados — reunião 17/08"*. O que o developer não faz é **promover** (revisions 2/3/4); o Draft
> é o banco de provas dele.

### 6.1 As quatro etapas

```
E1  CARGA LOCAL      importer: repositório → memória                   sem rede
E2  RÉGUA            GET /apis/{template} + conformidade               GET
E3  PROVA NO DRAFT   publica na revisão 1, sem deploy                  GET + PUT   ← ESCRITA
E4  GOVERNANÇA       completeness + lista de ajustes necessários       GET
                              │
                              ▼
          RELATÓRIO CONSOLIDADO — console com tabelas e cores,
          e `--output json|yaml` para automação e code review
```

### 6.1.1 Modelo de relatório — tudo ou nada (D-18, fechada em 2026-10-15)

**O valor do comando está no quadro completo**, não nas partes. Ver só a conformidade com o template,
ou só o completeness, não dá ao developer — nem ao code review — a visão que justifica o comando.
Por isso:

| Desfecho | O que o developer vê |
|---|---|
| **cascata completa** | **relatório único no fim**: achados do template **+** completeness e ajustes do AG, em tela, com tabelas e cores |
| **falha antes da E3** (gramática, template ausente, guarda) | **só o erro que impediu** — sem relatório |
| **falha na publicação (E3)** | **só o erro que o Manager informou.** Nada dos achados de E1/E2, e **nada do AG** — a API não chegou a ser publicada, então não há completeness a buscar |

> A razão de descartar o parcial: um relatório que mostra doze warnings de template **e** um erro de
> publicação convida o developer a corrigir os warnings, quando o que o bloqueia é o erro. O
> bloqueador vem sozinho, para não competir com ruído.

Isso fecha o **C-6** — a premissa anterior deste plano ("o que já foi coletado é reportado") estava
**errada** e foi substituída por esta.

### 6.2 As duas guardas — antes de qualquer escrita

> **Decisão (2026-10-15):** não existe `--dry-run` que valide de verdade. O AG e as demais regras da
> plataforma **só se pronunciam sobre o que foi publicado**, então a escrita no Draft é inerente ao
> comando. Em vez de evitá-la, protege-se com duas guardas em sequência.

**Guarda 1 — identidade (automática, aborta).** D-11, fechada em 2026-10-15. Separa duas coisas que
não são a mesma:

| Campo | Regime no contrato | Papel na guarda |
|---|---|---|
| `spec.id` | **readOnly** (D-001) | **endereço do GET** — não é critério de abort |
| `spec.version` | **readOnly** — muda a D-003 §3, que o classificava como editável | comparado com o Manager — **diverge, aborta** |
| `spec.basePath` | readOnly (D-003 §3) | comparado com o Manager — **diverge, aborta** |

**O que constitui risco:** sobrescrever um Draft cuja `version` ou `basePath` sejam diferentes dos do
repositório — isso é escrever por cima de **outra API**. Um `spec.id` que aponte para lugar diferente
**não é risco por si**: se o `GET` por aquele id devolver a mesma `version` e o mesmo `basePath`,
materialmente é a mesma API, e gravar no Draft dela não causa dano.

Daí a assimetria: os três campos são readOnly no contrato (ninguém os edita no YAML), mas **só dois
abortam**. O id erra para um alvo com outra identidade funcional — e aí quem pega é a comparação de
`version`/`basePath`, que é o que importa materialmente.

A mensagem não tenta corrigir: orienta o developer a **procurar o administrador do sistema**.

> **Nuance com a D-001:** ela previa bloquear a alteração de `spec.id` por representar "tentativa de
> redirecionar o repositório para outra API". A intenção se mantém — o campo segue readOnly —, mas o
> **bloqueio efetivo** passa a ser por `version`/`basePath`, que é onde o dano existe de fato.

> **Consequência a registrar:** com `version` readOnly, **não há caminho pelo repositório para mudar
> a versão de uma API**. Isso passa a ser ato administrativo na plataforma. É o preço consciente da
> proteção, e precisa estar no `--help` e na mensagem de erro.
>
> `readOnly` em JSON Schema **não bloqueia nada sozinho** (a própria D-001 registra isso). Esta
> guarda **é** a implementação da imutabilidade dos três campos.

**Guarda 2 — consentimento explícito (interativa).** Passada a guarda 1, antes do PUT:

```
Para validar a estrutura completa da API, ela será publicada no ambiente Sensedia
na API [Nome da API] [Version]. Deseja prosseguir? (s/n)
```

O nome e a versão aparecem no texto justamente para que o developer reconheça **qual** API vai ser
tocada — é a última chance de perceber que o repositório aponta para o lugar errado, no caso em que
a guarda 1 passou (mesma `version`, mesmo `basePath`, API diferente).

**Quando a guarda 2 não se aplica (D-17, fechada em 2026-10-15):** em execução de **esteira** a
confirmação não é pedida. O discriminador é `EXECUTION_MODE=pipeline` — chave que já existe no
desenho do V-11, sem configuração nova. A guarda 1 continua valendo nos dois modos.

| `EXECUTION_MODE` | Guarda 1 | Guarda 2 |
|---|---|---|
| `local` (default) | sim | **sim** — pergunta `s/n` |
| `pipeline` | sim | não — segue direto |

> ⚠️ **Em aberto (D-11):** a D-001 atribui esse papel a `spec.id` ("alteração representa tentativa de
> redirecionar o repositório e deve ser bloqueada"). O cenário descrito usa `version` + `basePath`.
> Os três juntos, ou só os dois? `version` é campo **editável** pelo contrato da D-003 §3 — travá-lo
> impede o fluxo legítimo de mudar a versão da API.

### 6.3 Etapa E2 — a régua

```
1. id = spec.template  (local)  |  TEMPLATE_API_ID  (pipeline)
2. id ausente/vazio → ERRO: "para executar a validação é necessário informar um template de api"
3. GET /apis/{id} → lastRevision.interceptors          (1 chamada basta)
4. compara o fluxo efetivo de cada caminho de execução
5. resultado vai para o relatório final — não interrompe
```

**D-12 — template é obrigatório (fechada em 2026-10-15).** Sem template não há validação possível:
o comando emite erro e **orienta procurar o administrador do sistema**, mesmo destino da guarda 1.

> **Revoga a V-11 §1** no ponto *"vazio permitido — `template: ''` = esta API não tem régua, a
> validação não roda"*. A chave continua sempre declarada, mas **vazia deixa de ser estado válido**
> para quem quer validar. Precisa virar incremento formal da V-11/D-004 antes do código.

**D-13 — todas as rotas são validadas (fechada em 2026-10-15).** O template é **o default de como a
API deveria ser**, então a comparação percorre **todos os caminhos de execução** — raiz da revision,
cada recurso e cada operação.

O que o orquestrador **não** faz é julgar: não há como distinguir "o developer errou" de "o developer
quis mesmo remover aquele interceptor nesta rota". Por isso a saída é **lista de INFO e WARNING**, em
tela ou na esteira, **para o code review decidir** — exatamente o regime fechado em
[V-11 conformidade](decisoes-refino-409/V-11-conformidade-com-a-regua.md): append = `INFO`,
override/remoção/alteração = `WARNING`, **nunca bloqueia**.

> Isso **confirma** a V-11, não a revoga: "rotas" aqui são os caminhos de execução, e a comparação
> segue sendo de fluxo de interceptors. A API 414 ter 0 recursos não é problema — o template fornece
> o fluxo de referência, não uma lista de rotas.

### 6.4 Etapa E3 — prova no Draft

```
1. GET /apis/{spec.id}  → revisions[], e a revisão de revisionNumber == 1
2. GET da revisão 1     → estado atual, incluindo workflowId e workflowStageId
3. reenvia os MESMOS workflowId/workflowStageId no payload   ← "mantendo o estado do Manager"
4. PUT na revisão 1     → payload denso (mesma mecânica do publish, §7)
5. sem deploy
```

O developer local não sabe qual é o stage do Draft, e não precisa: ele **lê o stage atual e devolve o
mesmo**. A revisão 1 é Draft por convenção em toda API.

> ⚠️ **Em aberto (D-14):** o cenário espera que o AG possa travar aqui (ex.: falta de tag). Mas o
> teste de escrita de 2026-10-14 fez `PUT /revisions/9175` e **passou sem 412**. O 412 do V-23 veio de
> uma tentativa de alterar a **`description`** — ou seja, escrita no nível da **API**, não da revision.
> Hipótese: **o AG intercepta `PUT /apis/{id}` (onde vivem os `apiTags`), não `PUT /revisions/{id}`.**
> Se for isso, a E3 só dispara o AG se também publicar o basic info. Define o escopo da escrita:
> **só revision, ou revision + basic info?**

### 6.5 Etapa E4 — governança

Reaproveita o `sen completeness` já entregue: `get_completeness(api_id, revision_id)` devolve o score
e as `suggestions` (lista de ajustes necessários). O `revision_id` é o da **revisão 1**, resolvido na
E3. Gate de referência: **70%** (P3/P10), informativo no DEV.

### 6.6 Fluxo feliz

```
CENÁRIO  Validação completa e bem-sucedida
DADO     um repositório bem formado, com spec.template preenchido
E        spec.version e spec.basePath iguais aos do Manager
QUANDO   sen validate roda
ENTÃO    E1 carrega o repositório sem erro
E        E2 busca a régua e anexa os achados de conformidade ao relatório
E        a guarda de segurança passa
E        E3 lê a revisão 1, preserva workflowId/workflowStageId e publica via PUT
E        nenhum deploy é feito
E        E4 coleta completeness e as sugestões da revisão 1
E        o console exibe o relatório consolidado em tabelas, com cores por severidade
E        exit code 0
```

```
CENÁRIO  Validação com desvios de régua (oracle real das APIs 409/417)
DADO     o repositório da API 417 e a régua 414
QUANDO   sen validate roda
ENTÃO    o bloco de régua traz exatamente 4 achados:
         WARNING  GET /health-check                 override sem Custom #178
         WARNING  GET /tarefas                      remove XSS threat protection
         WARNING  POST /…/atribuicao-responsavel    Log difere no content
         INFO     resource Atribuicao Responsavel   append de Additional Info
E        a cascata CONTINUA — nenhum deles bloqueia a E3
E        exit code 0
```

### 6.7 Exceções

| # | Etapa | Cenário | Comportamento | Exit |
|---|---|---|---|---|
| T-1 | E1 | YAML inválido | erro de gramática com arquivo/linha; não avança | `1` |
| T-2 | E1 | schema violado | erro apontando o campo; não avança | `1` |
| T-3 | E2 | **`spec.template` ausente ou vazio** | **erro** (D-12, fechada): "para executar a validação é necessário informar um template de api"; orienta procurar o administrador | `1` |
| T-4 | E2 | modo `pipeline` sem `TEMPLATE_API_ID` | falha de configuração | `1` |
| T-5 | E2 | `spec.template` ≠ variável, em pipeline | a variável vence; WARNING da divergência | `0` |
| T-6 | E2 | **régua inalcançável** (sem rede, 401, 404, outro tenant) | ⚠️ **ABERTO — P-2** | ⚠️ |
| T-7 | E2 | append além da régua | `INFO`, cascata continua | `0` |
| T-8 | E2 | override / remoção / alteração | `WARNING` com o que falta e onde falta | `0` |
| T-9 | **guarda** | `version` difere do Manager | **aborta antes de escrever**; orienta procurar o administrador | `1` |
| T-10 | **guarda** | `basePath` difere do Manager | idem | `1` |
| T-11 | **guarda** | `spec.id` não existe no Manager (404) | aborta — repositório apontado para API inexistente | `1` |
| T-12 | E3 | API sem revisão de número 1 | erro — criar revision é ato humano | `1` |
| T-13 | E3 | **HTTP 412 do AG** | coleta o erro do Manager, **calcula** o faltante por GET (nunca parseia `messages[]`), exibe a linha humana da V-23 §5 + JSON | **`3`** |
| T-14 | E3 | erro de sintaxe/semântica recusado pelo Manager (4xx) | coleta e exibe o erro **do Manager** em console, sem reinterpretar | `1` |
| T-15 | E3 | 5xx / timeout | erro técnico, sem retry longo | `1` |
| T-16 | E4 | completeness indisponível para a revisão | WARNING; o relatório sai sem o bloco de governança | `0` |
| T-17 | E4 | completeness abaixo do gate (70%) | informativo no relatório — **não bloqueia** no contexto local | `0` |
| T-18 | — | `null` dentro de `content` | **aceito** — é valor, não regime | `0` |
| T-19 | — | `content` com campo de tipo errado (`quota: "abacaxi"`) | ⚠️ **ABERTO (D-5)** — sem os `*-default-interceptors` ninguém valida shape por tipo localmente; hoje só falharia na E3, pelo Manager | ⚠️ |
| T-20 | E3 | dois developers validando a mesma API ao mesmo tempo | **risco aceito (D-15, fechada)** — sobrescrevem-se, mas a janela é curta. Sem lock, sem aviso. Ver a ressalva da janela E3→E4 abaixo | `0` |
| T-21 | guarda 2 | developer responde `n` à confirmação | encerra sem escrever e **sem relatório** — só "Validação cancelada. Nada foi gravado." (D-18; corrigido em 2026-10-19, a linha anterior dizia "reporta o que E1/E2 já coletaram", premissa que a D-18 revogou) | `0` |
| T-21b | guarda 2 | Ctrl+C (ou fim da entrada) no prompt | interrompe o comando, sem relatório, com a mesma mensagem — não é um "não" | `130` |
| T-22 | guarda 2 | execução em esteira (`EXECUTION_MODE=pipeline`) | **não pergunta** (D-17, fechada); guarda 1 continua valendo | — |
| T-23 | E2/E3/E4 | sessão expirada ou token inválido | mensagem orientando `sen login`, sem stacktrace nem segredo em log | `1` |
| T-24 | guarda 1 | `version` ou `basePath` divergem do Manager | aborta **antes** de qualquer escrita; orienta o administrador (D-11) | `1` |
| T-25 | guarda 1 | `spec.id` aponta para outra API, mas `version` e `basePath` batem | **segue** — materialmente é a mesma API; gravar no Draft dela não causa dano (D-11) | `0` |

### 6.8 Subcomandos

O cenário pede composição: cada etapa roda isolada ou em cascata, como já acontece com
`sen completeness`.

| Subcomando | Etapa | Rede | Escreve? |
|---|---|---|---|
| `sen validate structure` | E1 | não | não |
| `sen validate template` | E1 + E2 | GET | não |
| `sen validate draft` | E1 + guardas + E3 | GET + PUT | **sim** |
| `sen validate` | E1→E4 em cascata | GET + PUT | **sim** |

**Não há `sen validate governance`** (C-3). Quem quer o completeness do que já está publicado usa o
**`sen completeness`**, que já existe. A E4 roda apenas dentro da cascata, sobre a revisão que o
próprio comando acabou de publicar.

**Subcomandos são ocultos (D-19, fechada em 2026-10-15).** Os três existem e funcionam, mas **não
aparecem no `--help`**: servem aos nossos testes e ao desenvolvimento, não ao uso diário. O developer
roda **`sen validate`** e pronto — a superfície pública do comando é uma só.

| Aspecto | Regra |
|---|---|
| listagem em `sen validate --help` | **não aparecem** |
| `sen validate structure --help` (invocado direto) | **funciona** — ajuda própria, para quem já conhece o caminho |
| documentação de usuário | documenta só `sen validate` |

> **As guardas pertencem à etapa E3, não ao comando.** `sen validate draft` é oculto, mas **escreve**
> — então passa pelas mesmas guarda 1 e guarda 2 da §6.2. Qualquer caminho que chegue à E3 as
> atravessa; nenhum atalho escreve sem elas.

**Decisão (D-16, fechada):** o comando sem subcomando **é** a cascata completa e **escreve** no
Manager. Não há `--dry-run` com valor real — validar AG e regras de plataforma exige publicar. A
proteção é a guarda 2 (§6.2), e o `--help` declara a escrita com todas as letras.

Quem quiser só a parte sem escrita tem os subcomandos: `structure` e `template` são read-only e
cobrem gramática e régua.

> **Ressalva da janela E3→E4 (decorrência da D-15).** O `completeness` da E4 é lido da revisão 1 —
> a mesma que outro developer pode ter sobrescrito entre o nosso PUT e o nosso GET. Nessa janela, o
> relatório mostraria o completeness **do repositório alheio**. A janela é de segundos e o risco foi
> aceito; fica registrado porque, se um dia aparecer feedback inexplicável, é aqui que se olha.

### 6.9 Pendências deste cenário — varredura de 2026-10-15

#### A. Correção de classificação: a E3 escreve, então o publish não detém mais estes itens

Eu havia classificado os três abaixo como exclusivos do `sen publish` (onda 3). **Errado** — a E3
monta e envia o mesmo payload denso, logo eles valem aqui, e com uma consequência pior: o alvo é o
**Draft**, o lugar onde o developer confia.

| # | Item | Efeito no `sen validate` se ignorado |
|---|---|---|
| **A-1** | **V-25 — tombstone** (D-2) | a E3 **ressuscita** no Draft o interceptor que a rota removia. O developer valida, vê verde, e o Draft ficou diferente do repositório. **Bloqueante de verdade** |
| **A-2** | **Preservação do não governado** (V-22) | sem `GET` + partição + reanexo, a E3 **apaga** do Draft os interceptors fora de `FIRST`/`SECOND` |
| **A-3** | **`position` no payload** (D-8) | a E3 precisa numerar o que vem do YAML; a regra ainda não está fechada |
| **A-4** | **Hidratação** (D-002) | `visibility`, `apiType`, `creationDate` precisam vir do GET, ou a E3 os zera no Draft |

#### B. Decisões abertas que seguem afetando este comando

| # | Item | Por que trava |
|---|---|---|
| **B-1** | **D-14 — onde o AG intercepta** | o cenário espera bloqueio por falta de tag, mas `apiTags` vivem no **basic info**, e o teste de 14/10 mostrou `PUT /revisions/{id}` passando **sem** 412. Se o AG só atua em `PUT /apis/{id}`, a E3 **precisa publicar o basic info também** — senão a etapa nunca dispara o gate que o cenário pressupõe |
| **B-2** | **D-3 (P-2) — régua inalcançável** | ficou **mais** urgente com a D-12: se o template é obrigatório, falhar ao lê-lo (sem rede, 401, 404, outro tenant) precisa de desfecho definido |
| **B-3** | **D-5 — shape por tipo de interceptor** | sem os `*-default-interceptors`, `quota: "abacaxi"` só falha na E3, pelo Manager — depois de já ter escrito |
| **B-4** | **D-6 (V-18) — nome do arquivo do escopo `all`** | a E1 precisa saber o que descobrir na raiz |
| **B-5** | **D-4 (P-3) — snapshot da régua** | sem id + `revisionNumber` + hash no relatório, um achado de code review não é reproduzível depois |

#### C. Lacunas que a varredura encontrou agora

| # | Lacuna | Observação |
|---|---|---|
| **C-1** | API que ainda não existe no Manager | **FECHADA (2026-10-15): fora de escopo desta versão.** Criação de API não é contemplada; todo repositório parte de uma API que já existe. O `sen validate` sempre tem alvo |
| **C-2** | **Sessão expirada / token inválido** | E2, E3 e E4 exigem token. Não havia cenário de exceção para isso no `validate` — incluído como T-23 |
| **C-3** | `sen validate governance` isolado engana | **FECHADA (2026-10-15):** o subcomando isolado **não existe**. Para ler o que já está publicado já há o **`sen completeness`**, entregue. A E4 passa a existir apenas **dentro da cascata**, onde o `revision_id` é o da revisão que o próprio comando acabou de publicar — sem ambiguidade sobre a origem do dado |
| **C-4** | **GETs repetidos** | guarda 1, E3 e E4 pedem o mesmo `GET /apis/{spec.id}`. Consolidar numa leitura só |
| **C-5** | **Ordem guarda 1 × E2** | hoje a régua roda antes da guarda. Se a guarda aborta, o developer já viu os WARNINGs da régua e leva o abort depois — ruído. Vale abortar cedo, ou é útil mostrar a régua mesmo assim? |
| **C-6** | Relatório em cascata interrompida | **FECHADA (2026-10-15): não é exibido.** Falha na E3 ⇒ **só o erro do Manager**; sem achados de E1/E2 e sem AG, porque a API não chegou a ser publicada. Ver §6.1.1 (D-18) |

### 6.10 Saída

- console humano com **tabelas e cores por severidade**, bloqueantes no topo;
- `--output json|yaml` para automação e code review (JSON no padrão Elastic, P12);
- relatório Markdown local, ignorado pelo Git;
- `--verbose` controla só verbosidade de log, não formato;
- `--help` em todos os níveis (comando e subcomandos), seguindo o padrão de `sen list` e
  `sen completeness`.

---

## 7. Comando — `sen publish`

**Responsabilidade:** gravar o estado do repositório na revision alvo do Manager. Usado pela **CI**.
Não executa reconciliação antes (decisão canônica).

### 7.1 Comportamento esperado (D-005 §9 — **PUT validado empiricamente em 2026-10-14**)

```
1. modo   = EXECUTION_MODE                       (default: local)
2. numero = TARGET_REVISION_NUMBER               (local: só 1 — Draft)
3. GET /apis/{spec.id}                           → revisions[] + estado a preservar
4. id     = revisions[].id onde revisionNumber == numero
5. PUT /api-manager/api/v3/revisions/{id}        → payload denso
```

Mapa de revisões (PRD §3.3): **1 Draft · 2 DEV · 3 HML · 4 PRD**. Criar revision é ato humano — o
orquestrador **nunca** usa `POST /revisions`.

### 7.2 Composição do payload

| Origem | O que entra |
|---|---|
| repositório | basic info, destination/timeout dos 3 escopos, interceptors governados, recursos e operações |
| GET (hidratação) | `visibility` completo, `apiType`, `creationDate`, `workflowId`, `workflowStageId` |
| GET (preservação) | interceptors fora de FIRST/SECOND, com `id`/`idTemp`/`position`/`status`/`parentType` intactos; campos não governados (`async`, `urls`, `instruction`, `certificateId`, `connector`) |

Tradução YAML → wire (D-005 §3): `destination = url or null` · `timeout = destination.timeout or null`
· vazio na raiz da revision ⇒ **chave omitida**.

`content`: objeto YAML → **string JSON** no adapter. **Substituição total, sem merge** — comprovado
por escrita: chave omitida no `content` **remove** o campo.

### 7.3 Fluxo feliz

```
CENÁRIO  Publicar na revision do ambiente
DADO     um repositório válido com spec.id=417
E        TARGET_REVISION_NUMBER=2 e EXECUTION_MODE=pipeline
QUANDO   sen publish roda
ENTÃO    faz GET /apis/417 e resolve revisionNumber 2 → id 9175
E        monta o payload denso com governados do repo + preservados do GET
E        faz PUT /revisions/9175
E        NÃO chama POST /revisions
E        o GET seguinte devolve o estado do repositório
E        os interceptors fora de FIRST/SECOND continuam lá, intactos
E        exit code 0
```

### 7.4 Exceções

| # | Cenário | Comportamento | Exit |
|---|---|---|---|
| P-1 | `TARGET_REVISION_NUMBER` ausente em modo pipeline | falha de configuração | `1` |
| P-2 | modo local com número ≠ 1 | **recusa antes de qualquer escrita** (D-005 §9) | `1` |
| P-3 | número informado não existe em `revisions[]` | erro — criar revision é ato humano | `1` |
| P-4 | `spec.id` não corresponde à API remota | erro, sem escrita | `1` |
| P-5 | **HTTP 412 do Adaptive Governance** | `outcome: governance_blocked` + `workflowId`, `stageId`, `missing[]` calculados por GET (nunca extraídos do texto) | **`3`** |
| P-6 | 401/403 | erro de autenticação orientando `sen login` | `1` |
| P-7 | 5xx / timeout | erro técnico; **sem retry longo** | `1` |
| P-8 | repositório inválido (gramática) | **não publica** — `validate` é pré-condição | `1` |
| P-9 | item governado no remoto que o repo não representa | ⚠️ **V-25** — hoje o publish o ressuscitaria silenciosamente | ⚠️ |
| P-10 | API sem revisions | erro explícito | `1` |

---

## 8. Exit codes consolidados

| Código | Significado |
|---|---|
| `0` | sucesso — inclui WARNING de régua e divergência de reconciliação |
| `1` | falha técnica ou de gramática (schema, estrutura, configuração, rede, auth) |
| `3` | **bloqueio de governança** (HTTP 412 do AG) — canal distinto, decisão da plataforma |

---

## 8.4 Contrato do wire — provado por escrita (2026-10-15)

> Achados obtidos rodando o fluxo completo contra a API 417, com backup e
> restauração entre cada ensaio. Cada linha abaixo é **comportamento observado da
> plataforma**, não inferência — e nenhuma estava em documento algum.

### W-1 · `idTemp` é obrigatório em interceptor novo

Bisseção do `PUT /revisions/9161`, uma variável por vez:

| Payload | HTTP |
|---|---|
| do `GET`, sem alteração (controle) | **200** |
| interceptor novo **sem** `id` e **sem** `idTemp` | **500** |
| interceptor novo com `id=None, idTemp=None` | **500** |
| interceptor novo com `id=idTemp=position` | **200** |
| interceptor novo com `id=None, idTemp=position` | **200** |
| remover um interceptor existente | 200 |
| operação existente sem `id` | 200 |
| recurso novo (sem id) + operação nova (sem id) | 200 |

O 500 vem **sem mensagem** (`{"result":"failure","errors":[],"status":500}`), o
que torna o diagnóstico caro. `id` pode ir nulo; **`idTemp` não**.

É exatamente a convenção que o orquestrador já tem em
`domain/models/interceptors_model.py:17` (`set_ids_from_position` faz
`setdefault("id", position)` e `setdefault("idTemp", position)`) — o modelo estava
certo, e quem reconstrói payload à mão precisa respeitá-la.

### W-2 · O repositório pode referenciar um Custom que não existe mais

| Chamada | Resultado |
|---|---|
| `GET /custom-interceptors/32` | **200** — `Release Notes` |
| `GET /custom-interceptors/33` | **200** — `CyberArk and OAuth Autentication` |
| `GET /custom-interceptors/125` | **404** — "CustomInterceptor with identifier 125 not found!" |
| `GET /custom-interceptors/178` | **404** |
| `GET /custom-interceptors?_limit=500` | 27 itens, ids 1..31 |

> **Correção de um achado anterior.** Eu havia concluído que o `customInterceptorId`
> não era resolvível pelo catálogo. **Errado** — o catálogo funciona. Os ids 125 e
> 178 simplesmente **não existem mais** no tenant: foram apagados depois de terem
> sido usados nas revisions, onde o `content` ficou materializado. O `Custom #178`
> continuava "funcionando" na revision por isso, não por resolução por referência.

O achado que permanece, e que importa para o produto:

1. **O `content` do Custom fica materializado na revision**, não resolvido por
   referência em tempo de execução. Apagar o Custom do catálogo não quebra as
   revisions que já o usam.
2. **Um repositório pode declarar um Custom que não existe mais.** O YAML guarda
   só `type: Custom` + `id`; o script não está nele. Se o id não resolver no
   catálogo **e** o item não estiver no fluxo remoto, ele é **impossível de repor**.
3. Hoje isso só aparece como falha na hora de publicar. **Deveria ser achado da
   camada de gramática do `sen validate`**, antes de qualquer escrita: "o
   repositório referencia o Custom #125, que não existe neste tenant".

Isso dá contorno concreto ao item estacionado da D-003 §1.8 ("Custom referenciado
por ID numérico; portabilidade cross-tenant fica para depois"): além da
portabilidade entre tenants, falta **verificação de existência** dentro do próprio
tenant.

### W-3 · `position` é contínua entre escopos

Leitura da revision 9161:

```
resource 9164    FIRST 2,3,4,5,6,7,8    SECOND 0,1
operation 9172   FIRST 9,10,11,12,13,14 SECOND 15
                       └── continua de onde o resource parou
```

**Responde a dimensão B do P-1**: a numeração **não reinicia por escopo**.
Renumerar `1..N` em cada escopo corromperia a ordem. Some-se ao que a V-22 §2 já
registrava (FIRST e SECOND compartilham a numeração; `THIRD` tem espaço próprio).

### W-4 · O Manager materializa a herança; o repositório guarda o delta

| | |
|---|---|
| wire, resource `Atribuicao Responsavel` | **9 itens** — o fluxo herdado inteiro, materializado |
| repositório, `resource.yaml` | `inherit: true` + **1 item** (`Additional Info`) |

Publicar o delta cru **apaga** os 8 herdados. A tradução YAML → wire precisa
**expandir** a herança — passo que a D-005 §3 não descreve, porque trata a herança
como declarativa quando o armazenamento é resolvido.

### W-5 · Lista vazia significa "herda", não "fluxo vazio"

Um recurso publicado com `interceptors: []` **herda** o fluxo do escopo acima.
Não existe representação para "esta rota não executa nada".

**Consequência direta sobre o V-25:** `inherit: false` só é expressável
**reproduzindo a lista inteira** — que é o que o `GET /health-check` faz com seus 7
itens. A opção (a) do V-25 (lista completa explícita) não é a mais simples: é a
**única possível**. Uma gramática de remoção teria de ser expandida para a lista
completa no publish de qualquer forma.

### W-6 · A operação pertence ao recurso

Enviar uma operação com `id` dentro de um recurso diferente do de origem faz o
Manager **descartá-la**, com HTTP 200. Observado ao fundir os dois `Letras` e os
dois `Tarefas`: recursos novos criados vazios, 4 operações perdidas.

Regra: **operação que muda de recurso é operação nova no destino — vai sem `id`.**
Coerente com a V-12a (o repo não versiona ids), mas com um efeito que ninguém
havia previsto: **reagrupar recursos recria operações**.

### W-7 · O gate do Adaptive Governance está no `PUT /revisions`

| Rota | Com o atributo obrigatório ausente |
|---|---|
| `PUT /apis/{id}` | **200** — grava sem validar |
| `PUT /revisions/{id}` | **412** — `"API must contain attribute ..."` |

Duas consequências:

1. **Fecha a D-14.** Os `apiTags` viajam no `api` aninhado do payload da revision,
   e é ali que o AG atua.
2. **Duas escritas em sequência deixam estado inconsistente.** No ensaio, a API
   ficou sem a tag (5a aceita) e a revision não publicou (5b barrada). A E3 deve
   fazer **um único PUT**, o da revision.

E o gate só dispara se o `workflowStageId` enviado apontar para um stage com
`attributesRequisites` — reenviar o stage atual (1401, sem requisitos) **pula a
validação**. Ver D-20.

### W-9 · `idTemp` é único no payload, não no escopo

Dois itens novos em escopos diferentes receberam o mesmo `idTemp` porque cada
escopo calculava "a próxima posição livre" por conta própria:

```
raiz                 Custom32 -> idTemp 8    Custom33 -> idTemp 9
resource Atribuicao  Custom32 -> idTemp 9 <- COLIDE     Custom33 -> idTemp 10
```

O Manager **deduplica por `idTemp` e descarta um dos itens**, devolvendo HTTP 200.
O `Custom #33` da raiz sumiu assim — e só apareceu porque a conferência
pós-publicação comparou enviado × publicado.

```
position  ->  do ESCOPO   (por escopo e execution point)
idTemp    ->  do PAYLOAD  (único em toda a chamada)
id        ->  pode ser null em item novo
```

Terceiro caso de perda silenciosa sob 200 nesta investigação (ver W-8).

### W-8 · Perda silenciosa sob HTTP 200

Dois casos distintos (operações descartadas no reagrupamento; interceptor
declarado que não subiu) terminaram em **200 com perda**. O `sen publish` e a E3
do `sen validate` **não podem tratar 200 como sucesso**: precisam reler e comparar
o publicado com o enviado, falhando alto na divergência — a salvaguarda da V-22 §4
aplicada à escrita.

---

## 9. Decisões que este plano assume — confirmar antes das specs

| # | Decisão | Estado | Afeta |
|---|---|---|---|
| **D-1** | Qual comando expõe o versionador (`sen version sync` com dois modos?) | **aberta** | §5 inteiro |
| D-2 | **V-25** — gramática do tombstone | **FECHADA (2026-10-15)** — **lista completa explícita**, única forma expressável: o T06 provou que lista vazia **herda**, e uma gramática de remoção teria de ser expandida para a lista completa na publicação de qualquer forma. O importador materializa a lista em vez de gravar comentário, e a deriva de override vira `WARNING`. Ver [V-25](decisoes-refino-409/V-25-tombstone.md) | V-10, P-9 |
| D-3 | **P-2** — desfecho quando a régua está inalcançável | **FECHADA (2026-10-15)** — **aborta nos dois modos de execução**, qualquer que seja a causa (404, 403, rede), e também com `spec.template` vazio (D-12). É falha técnica, não divergência de padrão. Como a plataforma devolve **403** — e não 401 — tanto para sessão expirada quanto para id de outro tenant, a mensagem nomeia as duas causas em vez de escolher uma | T-9 |
| D-4 | **P-3** — gravar snapshot da régua (id + revisionNumber + hash) no relatório | **FECHADA (2026-10-15)** — **grava**. O snapshot entra no contrato `apiops.sen-validate/v1`, para que um achado continue reproduzível depois que a template mudar. Decidido antes de o schema existir, para não custar versão nova | §6.5 |
| D-5 | Validação de shape por tipo de interceptor após remover os `*-default-interceptors` | **FECHADA (2026-10-15)** — **dissolvida na API template**: não existe camada de gramática separada. A template valida tipo e preenchimento no mesmo regime `INFO`/`WARNING` da conformidade, e o dev decide subir fora do padrão. Limite aceito: a template diz o que *ela usa*, não o que *é válido* | T-12 |
| D-6 | **V-18** — nome e gramática do arquivo do escopo `all` | **FECHADA (2026-10-15)** — **`all.yaml`**, aceitando `destination`, `timeout`, `interceptors_request` e `interceptors_response`; `inherit` é inerte na raiz e vira `INFO`. Obrigatório **pelo nome exato**, e a ausência aborta na E1. Fecha também o **I-7**: o typo vira ausência, e ausência aborta. Ver [V-18](decisoes-refino-409/V-18-arquivo-do-escopo-raiz.md) | I-7, §4 |
| D-7 | **T-1 do teste de escrita** — o AG não bloqueou no PUT; confirmar que o gate está no `validate`/deploy | **FECHADA por evidência (§8.4, W-7)** — o gate está no `PUT /revisions/{id}`, que devolve **412**; `PUT /apis/{id}` grava sem validar. Confirmado pelo T03 do caderno | P-5 |
| D-8 | `position` no payload — obrigatória ou decorativa; FIRST/SECOND compartilham; contínua entre escopos | **FECHADA por evidência (§8.4, W-3; P-1 rebaixado)** — no **YAML** a `position` não existe: a ordem da lista é a fonte declarativa (D-003 §4, V-12). No **wire** é obrigatória e **contínua entre escopos**, e não é renumerada nos itens reusados | §7.2 |
| D-9 | Reconciliar o canônico: "o dev não publica via CLI" (17/08) × "local publica na Draft" (D-005 §9) | **FECHADA (2026-10-15)** — **local escreve, sob consentimento explícito**. A exceção da Draft fora concedida à esteira ("uso exclusivo da esteira", Decisão 10 + P1); a reconciliação é a **guarda 2**: em `local` a publicação exige confirmação `s/n`, em `pipeline` não pergunta. A intenção do canônico era impedir publicação *acidental*. Resíduo aceito: dois escritores na mesma Draft (D-15) | P-2 |
| D-14 | O AG intercepta `PUT /apis/{id}` ou também `PUT /revisions/{id}`? Define se a E3 publica só a revision ou também o basic info | **FECHADA por evidência (§8.4, W-7)** — o AG atua no **`PUT /revisions/{id}`**. A E3 faz **um único PUT**, o da revision, com `apiTags`, `name` e `description` no `api` aninhado. Escrever também em `PUT /apis` fura o gate e deixa estado meio-aplicado | §6.4, B-1 |
| D-20 | Stage do Adaptive Governance enviado no payload | **FECHADA (2026-10-15)** — **lido em runtime** da revisão alvo (`workflowId` + `workflowStageId`) e reenviado intacto; nunca configurado, inferido ou avançado. A premissa do §8.4 sobre o stage 1401 estava errada: ele nunca esteve na Draft, e reenviar o stage atual **dispara** o AG. Ver [D-020](d020-stage-do-adaptive-governance.md) | §6.4, §8.4 |
| D-11 | Imutáveis e critério da guarda 1 | **FECHADA (2026-10-15)** — os três são **readOnly** no contrato, mas só **`version` e `basePath` abortam**: são eles que definem a identidade funcional da API. `spec.id` é o **endereço do GET**; apontar para outro id, com mesma version e basePath, não é risco em Draft. Muda a D-003 §3 (`version` era editável) e refina a D-001 | §6.2, T-24, T-25 |
| D-12 | `spec.template` vazio | **FECHADA (2026-10-15)** — sem template **não há validação**: erro + procurar o administrador. **Revoga a V-11 §1** no "vazio permitido" | T-3 |
| D-13 | Escopo da comparação com o template | **FECHADA (2026-10-15)** — **todas as rotas** (todos os caminhos de execução). O template é o default de como a API deveria ser; o orquestrador não julga intenção, emite INFO/WARNING para o **code review**, conforme a V-11 conformidade. **Confirma** a V-11, não a revoga | §6.3 |
| D-15 | Concorrência na revisão 1 | **FECHADA (2026-10-15)** — risco aceito: a janela é curta e sem lock. Ressalva da janela E3→E4 em §6.8 | T-20 |
| D-16 | `sen validate` puro escreve? cabe `--dry-run`? | **FECHADA (2026-10-15)** — é a cascata e **escreve**; `--dry-run` real é impossível (o AG só avalia o publicado). Protegido pelas duas guardas da §6.2 | §6.8 |
| D-17 | Confirmação `s/n` na esteira | **FECHADA (2026-10-15)** — em `EXECUTION_MODE=pipeline` **não pergunta**; guarda 1 permanece nos dois modos | §6.2, T-22 |
| D-19 | Superfície dos subcomandos | **FECHADA (2026-10-15)** — existem, mas **ocultos do `--help`**: servem a teste e desenvolvimento. Uso diário é a cascata. As guardas pertencem à E3, então o `draft` oculto também as atravessa | §6.8 |
| D-18 | Modelo de relatório | **FECHADA (2026-10-15)** — **tudo ou nada**: a cascata completa produz o relatório único (template + AG); falha na E3 devolve **só o erro do Manager**, sem achados anteriores e sem AG | §6.1.1, C-6 |
| D-10 | V-21 — `null` dentro de `content` é valor, não regime | **respondida** por escrita; falta gravar na D-003 §3 | T-18 |

> **Revogações e alterações de contrato produzidas nesta rodada** — precisam virar incremento formal
> nos documentos de decisão **antes** de virar código (regra 1 da feature):
>
> | Decisão | O que muda | Onde gravar |
> |---|---|---|
> | D-11 | `spec.version` passa de **editável** para **readOnly** | D-003 §3 |
> | D-12 | `template: ''` deixa de ser estado válido | V-11 §1 / D-004 §2.1 |
> | D-10 | régua de escalares não alcança o interior de `content` | D-003 §3 |

---

## 10. Matriz de cobertura de teste

| Peça | Fonte de verdade do teste | Rede |
|---|---|---|
| importer | repositórios sintéticos + fixtures regeradas | não |
| versionador | **fixtures douradas** — reexecução byte a byte sobre as 6 APIs reais | GET |
| validate (gramática) | repositórios sintéticos por regra | não |
| validate (régua) | **oracle real**: os 4 achados previstos nas APIs 409 e 417 | GET |
| publish | round-trip com rollback (método validado em 2026-10-14) | GET + PUT |

> **Pré-requisito:** as fixtures em `decisoes-refino-409/exemplos-gerados/saida/` estão incompletas
> (2 APIs de 6) e **2 arquivos não parseiam**. Regerar é pré-condição de qualquer teste do versionador.

---

## 11. Próximo passo

Fechadas as decisões da §9, dividir em changes OpenSpec no repositório do CLI
(`CLI/apiops-orchestrator/openspec/`, que já tem specs e padrão estabelecidos no archive). Corte
proposto:

```
1 · contrato + versionador     schemas, settings, nomenclatura, materialização
2 · sen-validate               gramática + régua 414
3 · sen-publish                PUT em revisão fixa          [depende de D-2]
```
