# V-01 · Molde dos arquivos YAML — validado campo a campo contra a API 417

| Meta | Valor |
|---|---|
| Status | **FECHADO** — shape decidido em 2026-10-14 (Forma B) |
| Data | 2026-10-14 |
| Fonte | `GET /apis/417` + `GET /revisions/9175` (tenant consulting, somente leitura) |
| Regra adotada | **Nenhum campo entra no YAML sem existir no contrato do Manager.** Campo sem lastro no wire é inconsistência, não layout |
| Fecha também | V-02 (`timeout` aninhado) e V-03 (semântica de `url: ''`) |

## 1. Shape decidido — Forma B

```yaml
destination:
  url: <string>        # SEMPRE declarado. '' = herda do escopo acima
  timeout: <string>    # opcional. Ausente = herda. Em segundos, teto 60
```

O objeto `destination` é **sempre declarado** nos três escopos. É isso que torna a forma aninhada
suficiente: o caso "timeout próprio sem destino próprio" se escreve `url: ''` com `timeout` preenchido,
e não fica inexprimível.

**Tradução entre o YAML e o wire** (no Manager os dois são campos irmãos, com heranças independentes):

| Sentido | Regra |
|---|---|
| import (wire → YAML) | `destination.url = destination ?? ''` · `destination.timeout = timeout` (omitido quando `null`) |
| publish (YAML → wire) | `destination = url or null` · `timeout = destination.timeout or null` |
| publish na raiz da revision | vazio ⇒ **chave omitida** no payload (é assim que o Manager representa ausência nesse escopo) |

## 2. Contrato real dos três escopos (varredura do payload)

### Escopo `all` (raiz da revision)

| Campo do wire | No YAML | Regime |
|---|---|---|
| `destination` + `timeout` | **sim**, como objeto `destination` | topo da cadeia: `url: ''` = sem destino, `timeout` ausente = teto do gateway (60 s) |
| `interceptors` | **sim** | fluxo base (listas request/response) |
| `id`, `revisionNumber`, `creationDate`, `api`, `deployments`, `apiBroken` | não | estado operacional / readOnly |
| `workflowId`, `workflowStageId` | não | governança (Adaptive Governance) |
| `resources` | não | é a própria árvore de arquivos |

### Escopo `resource`

| Campo do wire | No YAML | Valor real na 417 | Regime |
|---|---|---|---|
| `name` | **sim** | `/health-check`, `Tarefas`, `Letras`, `Atribuicao Responsavel` | rótulo livre (D-v) |
| `description` | **sim** | 3 textos preenchidos | sempre declarado, mesmo vazio (D-s) |
| `destination` + `timeout` | **sim**, objeto | `google.com`/`30`, `teste.com`/`23`, `null`/`null` | `url: ''` = herda do `all` |
| `connector`, `certificateId` | **não** | `null` nos 4 | preservados por GET (§5) |
| `interceptors` | **sim** | flow próprio do recurso | — |
| `id`, `apiBroken`, `operations` | não | — | readOnly / estrutura |

### Escopo `operation`

| Campo do wire | No YAML | Valor real na 417 | Regime |
|---|---|---|---|
| `method` | **sim** | GET, POST, DELETE | hoje vem do nome do arquivo |
| `path` | **sim** | 6 paths | fonte da verdade (D-a opção A) |
| `description` | **sim** | 6 preenchidas, 1 vazia (`''`) | sempre declarada (D-s) |
| `destination` + `timeout` | **sim**, objeto | 6 com URL, 1 `null` (op 9184); `'55'` na 9180 | `url: ''` = herda do recurso |
| `async`, `urls`, `instruction`, `certificateId` | **não** | `false`, `[]`, `null`, `null` | preservados por GET (§5) |
| `interceptors` | **sim** | — | — |
| `id`, `apiBroken` | não | — | readOnly |

## 3. Escopo `all` — dado real da revision 9175

```yaml
# Escopo `all`: raiz da revision. Topo da cadeia de herança.
# Wire: GET /revisions/9175 -> destination="https://teste.com", timeout="30"
destination:
  url: https://teste.com    # vale para todo recurso/operação que não declarar o seu
  timeout: '30'             # segundos; teto do gateway = 60

interceptors_request: []    # (fluxo base — fora do escopo deste item)
interceptors_response: []
```

## 4. Escopos `resource` e `operation` — os casos reais

```yaml
# resource 9177 — destino E timeout próprios (substituem os do `all`)
name: Tarefas
description: Gerenciamento de tarefas de busca de letra de obras musicais
destination:
  url: https://google.com   # wire: "https://google.com"
  timeout: '30'             # wire: "30"
```

```yaml
# resource 9179 — preenchido em 14/10 para exercitar a cadeia
name: Atribuicao Responsavel
description: Gerenciamento de tarefas de busca de letra de obras musicais
destination:
  url: https://teste.com    # wire: "https://teste.com"
  timeout: '23'             # wire: "23"
```

```yaml
# resource 9176 — nada próprio: herda destino e timeout do `all`
name: /health-check
description: Verificação de saúde da aplicação
destination:
  url: ''                   # wire: null -> herda https://teste.com
                            # timeout omitido — wire: null -> herda 30
```

```yaml
# op 9186 — destino próprio, sem timeout (herda o do recurso, que herda do `all`)
path: /health-check
destination:
  url: https://dev-backend.ecad.org.br/app-demo/servico-letras/v1/health-check
description: >-
  Retorna o status de saúde da aplicação. Endpoint público utilizado para
  readiness probes em ambientes Kubernetes e monitoramento do API Gateway.
```

```yaml
# op 9180 — destino próprio E timeout próprio (o mais específico vence)
path: /tarefas/{id}/letras
destination:
  url: https://dev-backend.ecad.org.br/app-demo/servico-letras/v1/tarefas/{id}/letras
  timeout: '55'             # wire: "55" — sobrepõe os 30 do `all`
description: >-
  Cadastra uma nova letra de obra musical vinculada a uma tarefa existente…
```

```yaml
# op 9184 — ⭐ o caso que prova a cadeia: nada próprio
path: /tarefas/{id}/atribuicao-responsavel
destination:
  url: ''                   # wire: null -> herda do recurso 9179 (https://teste.com)
                            # timeout omitido — wire: null -> herda "23" do recurso
description: ''             # wire: "" — declarada mesmo vazia (D-s)
```

```yaml
# caso que a Forma B precisa suportar (não ocorre hoje na 417, mas o modelo permite):
# timeout próprio SEM destino próprio
path: /exemplo
destination:
  url: ''                   # herda o destino do escopo acima
  timeout: '55'             # mas impõe o seu próprio timeout
```

**Cadeia resultante da op 9184, pela regra do mais específico:**
`operação (vazio) → recurso 9179 (teste.com / 23 s) → all (teste.com / 30 s) → gateway (60 s)`.

## 5. Campos fora do YAML, preservados por GET

**Decisão (2026-10-14):** `async`, `urls`, `instruction` e `certificateId` (operação) **não entram no
YAML**. Antes de publicar, o orquestrador faz `GET` da API/revision, recupera esses campos e os reenvia
**exatamente como estavam**. É o princípio já estruturante do projeto — *manifesto versionado + estado
remoto (GET) → payload efetivo* (AGENTS.md) — e o mesmo regime da hidratação de `visibility`, `apiType`
e `creationDate` fechada na D-002.

Por simetria, `connector` e `certificateId` do **recurso** entram na mesma regra. *(Extensão aplicada
aqui por coerência — o usuário nomeou os quatro campos de operação; confirmar na consolidação.)*

Consequências a registrar:

1. **Não há perda de dado no ciclo import → publish**, que era o risco levantado pela D-e.
2. **O repo deixa de ser a fonte completa do objeto**: esses campos existem só no Manager. Mudança
   neles não aparece em diff do git — é consciente e é o preço de mantê-los fora do manifesto.
3. **API nova (sem estado remoto)** não tem de onde hidratar: o publish enviará o default do Manager
   (`false`, `[]`, `null`). A verificar quando houver write.

## 6. O que continua sem validação possível por GET

1. **Herança efetiva em runtime.** A revision 9175 tem `deployments: []` — a API nunca foi implantada,
   não há tráfego para observar. A herança está provada na **documentação** (exemplo oficial com o PUT
   e o `/resource2`), não no comportamento deste tenant.
2. **Equivalência `''` ↔ `null` na escrita.** O mapeamento do §1 é a regra adotada; confirmá-lo exige
   publish (write), fora do escopo atual.
3. **Formato dos campos preservados quando preenchidos.** Só foram vistos vazios; como ficam fora do
   YAML, isso deixou de bloquear o schema.
