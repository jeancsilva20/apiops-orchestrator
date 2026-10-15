# Validação da pasta `api-letras-409/` — fila de refino item a item

| Meta | Valor |
|---|---|
| Gerado em | 2026-10-13 |
| Objeto validado | `CLI/apiops-orchestrator/docs/feat-api-estructure/api-letras-409/` (7 arquivos, todos parseiam) |
| Método | Leitura estática dos 7 YAML + diff contra `simulacao-api-409-letras/` e `simulacao-api-417-letras/` + confronto com D-003, D-004 e a série D-a…D-y |
| Escrita na plataforma | Nenhuma. Nenhum arquivo da simulação foi alterado por esta validação |
| Refino | Decisões fechadas ficam em [`decisoes-refino-409/`](decisoes-refino-409/README.md) até a consolidação |
| Procedência | Chamadas usadas na validação: [`decisoes-refino-409/CAMINHOS-DE-VALIDACAO.md`](decisoes-refino-409/CAMINHOS-DE-VALIDACAO.md) |
| Objeto removido | A pasta `api-letras-409/` foi retirada do repositório na consolidação; o conteúdo relevante está absorvido nos documentos de [`decisoes-refino-409/`](decisoes-refino-409/README.md) |
| Consolidação | **2026-10-14** — 20 itens fechados viraram a [D-005](d005-layout-revisado.md). Os itens ainda ABERTOS seguem nesta fila |
| Autoridades citadas | `d003-layout-repo.md`, `d004-template-e-validacao.md`, `simulacao-api-409-letras/README.md` (D-a…D-u), `simulacao-api-417-letras/README.md` (D-v…D-y), `fila-templates-schemas.md` |

> **Como usar:** cada item tem ID próprio, evidência, impacto e a pergunta que o fecha.
> Refine um por vez, preencha a linha **Decisão** e mude o **Status**.
> Item fechado vira incremento da D-003/D-004 (regra 1 da feature) **antes** de virar código (regra 3).

**Régua de status:** `ABERTO` · `EM REFINO` · `FECHADO` · `DESCARTADO`

---

## 0. Índice

| ID | Item | Natureza | Bloqueia | Status |
|---|---|---|---|---|
| V-01 | `destination`: sufixo escalar × objeto com URL absoluta (4 formas no mesmo repo) | Contrato | schema de operação e de resource | **FECHADO** → [decisão](decisoes-refino-409/V-01-destination-timeout-escopos.md) · [molde](decisoes-refino-409/V-01-molde-yaml-validado-417.md) |
| V-02 | `timeout` aninhado em `destination` × irmão (como no wire) | Contrato | schema de operação e de resource | **FECHADO** → [molde §1](decisoes-refino-409/V-01-molde-yaml-validado-417.md) · Forma B, com tradução YAML↔wire |
| V-03 | Semântica de `url: ''` (limpa / herda / preserva) | Contrato | publish | **FECHADO** → [molde §1](decisoes-refino-409/V-01-molde-yaml-validado-417.md) · `''` = herda do escopo acima |
| V-04 | `get_atribuicao-responsavel.yaml`: cabeçalho diz `null`, corpo declara URL | Coerência | — | ABERTO |
| V-05 | `api-basic-info.yaml`: comentário cita `My new`, conteúdo é `Time` | Coerência | — | ABERTO |
| V-06 | `get_health_check.yaml` prega sufixo; os irmãos usam URL absoluta | Coerência | depende de V-01 | ABERTO |
| V-07 | `timeout: '30'` nas ops de atribuição × D-m (12 objetos `null` na 409) | Dado a reconfirmar | fixture | **FECHADO** → [V-07…V-10](decisoes-refino-409/V-07-a-V-10-dados-409-reconfirmados.md) |
| V-08 | `destination` do `GET /…/atribuicao-responsavel` (era `null` no wire) | Dado a reconfirmar | fixture | **FECHADO** → [V-07…V-10](decisoes-refino-409/V-07-a-V-10-dados-409-reconfirmados.md) |
| V-09 | `destination` do recurso 9106 = `https://teste.com` (era `null` nos 6) | Dado a reconfirmar | fixture | **FECHADO** → [V-07…V-10](decisoes-refino-409/V-07-a-V-10-dados-409-reconfirmados.md) |
| V-10 | `destination`/`timeout` na raiz da revision 9103 (chave era ausente) | Dado a reconfirmar | fixture | **FECHADO** → [V-07…V-10](decisoes-refino-409/V-07-a-V-10-dados-409-reconfirmados.md) |
| V-11 | `spec.template` ausente × D-004 §2.1 (permanece obrigatório) e D-u | Decisão contrariada | publish, herança | **FECHADO** → [conformidade](decisoes-refino-409/V-11-conformidade-com-a-regua.md) · [binding](decisoes-refino-409/V-11-binding-do-template.md) |
| V-12 | Árvore `resources/<slug>` pasta-por-recurso × `artifacts/Resources/<path>` (D-003 §2 / D-a) | Decisão contrariada | descoberta, importer | **FECHADO** → [identidade](decisoes-refino-409/V-12-identidade-sem-ids.md) · [árvore](decisoes-refino-409/V-12-arvore-por-recurso.md) |
| V-13 | `resource.name` não casa com o nome da pasta (D-003 §5 × D-v) | Decisão contrariada | validador | **FECHADO** → [árvore §1](decisoes-refino-409/V-12-arvore-por-recurso.md) · a correspondência deixa de ser exigida |
| V-14 | Molde da D-003 §4/§5 não prevê o shape novo de `destination`/`timeout` | Spec desatualizada | schemas | **FECHADO** → D-003 §4 e §5 reescritas em 2026-10-14 |
| V-15 | D-f (versionar só o sufixo) revertida em 3 de 4 arquivos | Decisão contrariada | promoção entre ambientes | **FECHADO** → [decisão §5](decisoes-refino-409/V-01-destination-timeout-escopos.md) · D-f revogada na reconstrução; promoção via `$variável` |
| V-16 | Regra de slug da pasta de recurso (path, espaço, `{id}`, colisão) | Lacuna de regra | descoberta | **FECHADO** → [V-16/V-17](decisoes-refino-409/V-16-V-17-nomes-de-pasta-e-arquivo.md) |
| V-17 | Nomenclatura do arquivo de operação (`{metodo}_{parametros}` × slug do recurso) | Lacuna de regra | validador | **FECHADO** → [V-16/V-17](decisoes-refino-409/V-16-V-17-nomes-de-pasta-e-arquivo.md) · `<método>_<path completo>.yaml` |
| V-18 | `all-all.yaml`: papel, nome e gramática do escopo revision sem casa | Lacuna de regra | layout | ABERTO |
| V-19 | Cobertura parcial: 3 de 7 operações, 2 de 6 recursos | Completude | fixtures douradas | ABERTO |
| V-20 | `Additional Info`: tipo sem schema e `content.attributes[].id` versionável? | Contrato | schema de interceptor | ABERTO |
| V-21 | `null` dentro de `content` × régua "`null` proibido" da D-003 §3 | Contrato | schema de interceptor | ABERTO |
| V-22 | Estado não governado: interceptor fora de FIRST/SECOND preservado por GET (achado na validação do V-11) | Contrato | import, publish, schema de interceptor | **FECHADO** → [V-22](decisoes-refino-409/V-22-estado-nao-governado.md) |
| V-23 | Bloqueio do Adaptive Governance (HTTP 412) no publish: como o orquestrador reporta | Observabilidade | publish, esteira CI | **FECHADO** → [V-23](decisoes-refino-409/V-23-bloqueio-do-adaptive-governance.md) |
| V-24 | Revisão alvo do publish: número (não id) por variável de ambiente; local só na Draft | Publish | publisher, esteira | **FECHADO** → [V-24](decisoes-refino-409/V-24-revisao-alvo-do-publish.md) |
| V-25 | Como escrever um **tombstone** (remoção seletiva de item herdado) no YAML — D-003 §4 só tem override total | Contrato | schema de interceptor, import | ABERTO |
| V-26 | `inherit` substitui `override`: herança declarada sempre; ausente ≡ `true` | Contrato | schema, import, publish | **FECHADO** → [V-26](decisoes-refino-409/V-26-inherit.md) |

---

## 1. O que mudou nesta versão (inventário do diff)

| Item | Antes (`simulacao-api-409-letras`) | Agora (`api-letras-409`) |
|---|---|---|
| Árvore | `artifacts/Resources/<segmentos do path>/` | `resources/<slug do recurso>/` — uma pasta por recurso |
| Arquivo de operação | `get.yaml` / `post.yaml` | `get_health_check.yaml`, `get_atribuicao-responsavel.yaml`, `post_atribuicao-responsavel.yaml` |
| Fluxo herdado | `fluxo-herdado-SEM-CASA.yaml` (só interceptors) | `all-all.yaml` (interceptors **+ `destination`**) |
| `destination` da operação | sufixo escalar (`/health-check`) | objeto `{url, timeout}` com URL absoluta em 2 de 3 |
| `resource.yaml` | `name` + `description` (+ flow no de atribuição) | **+ `destination: {url, timeout}`** (só no de atribuição) |
| `apiTags` | `My new` / `["Tag1"]` | `Time` / `["Arrecadação", "Distribuição"]` |
| `spec.template` | ausente | ausente (a 417, gerada 1h antes, traz `template: 414`) |

**Parse mecânico dos 7 arquivos** (chaves de topo e tipo):

```
all-all.yaml                      destination: dict   interceptors_request: list   interceptors_response: list
api-basic-info.yaml               apiVersion: str     kind: str                    spec: dict
atribuicao/get_…yaml              path: str           destination: dict            description: str
atribuicao/post_…yaml             path: str           destination: dict            description: str   override: bool   interceptors_request: list
atribuicao/resource.yaml          name: str           destination: dict            description: str   interceptors_response: list
health-check/get_health_check     path: str           destination: str             description: str   override: bool   interceptors_request/response: list
health-check/resource.yaml        name: str           description: str
```

---

## 2. Itens de contrato (shape) — bloqueiam schema e conversão

### V-01 · `destination` tem 4 formas no mesmo repositório · Status: **FECHADO** → [decisão](decisoes-refino-409/V-01-destination-timeout-escopos.md)

**Evidência**

| Arquivo | Tipo | Valor |
|---|---|---|
| `health-check/get_health_check.yaml` | `str` | `/health-check` (sufixo) |
| `atribuicao/get_` e `post_` | `dict` | `{url: https://dev-backend…(absoluta), timeout: '30'}` |
| `atribuicao/resource.yaml` | `dict` | `{url: https://teste.com, timeout: '30'}` |
| `all-all.yaml` | `dict` | `{url: '', timeout: '30'}` |

**Impacto** — nenhum parser tipado aceita a chave polimórfica. `Operation.destination: str` (obrigatório) quebra nos 4 casos de `dict`; `Resource` nem tem o campo.

**Histórico** — a **D-f** decidiu versionar **só o sufixo**; a **417 §5** mostrou que, com três bases divergentes (`teste.com` na revision, `google.com` no recurso, `dev-backend…` nas operações), o publish não consegue reconstruir a URL, e listou três saídas: (1) URL absoluta na operação, (2) sufixo + base por escopo, (3) sufixo + variável de ambiente (`$backend_letras/...`, mecanismo nativo já usado por outra API do tenant).

**Pergunta a fechar** — qual das três saídas vale, e o shape é escalar ou objeto?

**Decisão:** _(a preencher)_

---

### V-02 · `timeout` aninhado dentro de `destination` · Status: **FECHADO** → [decisão](decisoes-refino-409/V-01-molde-yaml-validado-417.md)

**Evidência** — no wire `timeout` é **irmão** de `destination` (D-m: chave presente em 12 objetos da 409, todos `null`). Nesta pasta ele aparece **dentro** do objeto `destination`.

**Impacto**

- Operação com `timeout` e **sem** destino fica inexprimível — caso real na 417 (op 9180, `timeout: "55"`).
- `get_health_check.yaml`, que usa a forma escalar, não tem onde colocar timeout.
- A D-m decidiu "não escrever `timeout` por padrão"; o shape novo o torna obrigatório sempre que houver destino.

**Pergunta a fechar** — `timeout` volta a ser chave irmã opcional, ou o objeto `destination` passa a ser o único portador?

**Decisão:** _(a preencher)_

---

### V-03 · Semântica de `url: ''` · Status: **FECHADO** → [decisão](decisoes-refino-409/V-01-molde-yaml-validado-417.md)

**Evidência** — `all-all.yaml` traz `destination: {url: '', timeout: '30'}`.

**Impacto** — a D-003 §3 fechou a régua para escalares do basic info (*ausente preserva · `""` limpa · `null` proibido*), mas **não** para `destination`/`timeout` de resource e operation. A 417 §5 (D-m, pendência 3) mostrou que o regime do wire **muda por escopo**: na raiz da revision a chave só existe quando preenchida; em resource/operation vem sempre presente com `null`. Publicar `""` pode não equivaler a omitir.

**Pergunta a fechar** — `url: ''` limpa o destino no Manager, herda do escopo acima, ou é proibido no schema?

**Decisão:** _(a preencher)_

---

### V-20 · `Additional Info` sem schema e `attributes[].id` · Status: ABERTO

**Evidência** — `atribuicao/resource.yaml` declara `type: Additional Info` com `content.attributes[]` contendo `expression`, `name`, `type`, `id: 1`. O `schema-interceptors.json` existente só conhece Custom, Rate limit, Transaction ID, Log obfuscation, Log, Payload size, XSS threat protection e Client ID validation.

**Impacto** — tipo novo sem cobertura de schema. E o `id: 1` dentro de `attributes[]` parece índice interno: a **D-q** já provou que **id de interceptor não é estável** (os 9 itens foram recriados com ids novos a cada gravação); se o mesmo valer aqui, versionar o `id` gera diff fantasma.

**Pergunta a fechar** — o catálogo de tipos vira enum fechado ou aberto? `attributes[].id` é versionado ou descartado no import?

**Decisão:** _(a preencher)_

---

### V-21 · `null` dentro de `content` · Status: ABERTO

**Evidência** — o `Rate limit` dos 3 arquivos traz `noHeaderBehavior: null` e `headerKey: null`.

**Impacto** — a D-003 §3 item 17 proíbe `null` no schema, mas a regra foi escrita para **escalares do basic info**. O `content` tipado carrega `null` nativamente, vindo do wire. A D-004 §4 item 6 ("`null` dentro de `content` tipado") está marcada como **pendente** — este é o caso concreto dela.

**Pergunta a fechar** — o import preserva `null` no `content` (fidelidade) ou poda a chave?

**Decisão:** _(a preencher)_

---

## 3. Coerência interna dos arquivos

### V-04 · `get_atribuicao-responsavel.yaml` contradiz o próprio cabeçalho · Status: ABERTO

O cabeçalho afirma *"`destination: null` … Omitido pelo regime 2 (D-m)"* e, logo abaixo, *"destination ausente — ver cabeçalho"*. O corpo **declara** `destination: {url: https://dev-backend…, timeout: '30'}`.
Qual é a verdade: o cabeçalho (wire `null`) ou o corpo (URL preenchida)? Ver V-08.

**Decisão:** _(a preencher)_

### V-05 · `api-basic-info.yaml`, comentário × conteúdo em `apiTags` · Status: ABERTO

Comentário: *"Par 1 — atributo **My new** com um valor"*. Conteúdo: `attributeName: "Time"` com **dois** valores (`Arrecadação`, `Distribuição`). O comentário sobrou da versão anterior.

**Decisão:** _(a preencher)_

### V-06 · `get_health_check.yaml` prega regra que os irmãos não seguem · Status: ABERTO

Cabeçalho: *"Aqui versionamos só o sufixo; o publish reconstrói a URL completa"*. Os dois arquivos de atribuição versionam URL absoluta. Consequência de V-01 — fecha junto.

**Decisão:** _(a preencher)_

---

## 4. Dados a reconfirmar no wire (releitura somente GET)

> Hipótese a testar: `https://teste.com` e `'30'` são **exatamente** os valores da revision 9175 da **417**. Ou a 409 foi editada depois das 16:45 de 2026-10-13, ou esses quatro valores vieram da outra simulação.
> Chamadas necessárias: `GET /api-manager/api/v3/apis/409` e `GET /api-manager/api/v3/revisions/9103`. Somente leitura (mais o POST de token).

| ID | Campo | Último dado registrado da 409 | Nesta pasta | Status |
|---|---|---|---|---|
| V-07 | `timeout` de operação e de recurso | `null` nos 12 objetos (D-m) | `'30'` nas duas ops de atribuição | ABERTO |
| V-08 | `destination` do `GET /tarefas/{id}/atribuicao-responsavel` | `null` (rota recém-criada) | URL absoluta | ABERTO |
| V-09 | `destination` do recurso 9106 | `null` nos 6 recursos (D-e) | `https://teste.com` | ABERTO |
| V-10 | `destination`/`timeout` da raiz da revision 9103 | **chave ausente** (417 §4, achado 4) | `{url: '', timeout: '30'}` | ABERTO |

**Observação já verificada:** a URL absoluta do `post_atribuicao-responsavel.yaml` **confere** com o wire — a D-f registrou `https://dev-backend.ecad.org.br/app-demo/servico-letras/v1/{path}` repetida nas 6 operações da 409. O que está em dúvida é só o `timeout` que a acompanha.

**Decisão / resultado da releitura:** _(a preencher)_

---

## 5. Decisões fechadas que a pasta contraria

### V-11 · `spec.template` ausente · Status: **FECHADO** → [decisão](decisoes-refino-409/V-11-binding-do-template.md)

A **D-004 §2.1** decidiu que `spec.template` **permanece obrigatório** no contrato do manifesto, mesmo sem a plataforma expor a chave; a **D-u** reenquadrou o Golden Path: a régua tem lastro real e é a **API 414** (`/template/v1`, "Template APIOps"), lida por GET. A `simulacao-api-417-letras/api-basic-info.yaml` traz `template: 414`.
Aqui o campo está ausente e o cabeçalho declara a chave inexistente no contrato da plataforma — correto quanto ao GET de `/apis/{id}`, mas é o binding à régua que se perde.

**Pergunta a fechar** — o manifesto da 409 passa a declarar `template: 414` como a 417, ou a D-004 §2.1 é revista?

**Decisão:** _(a preencher)_

### V-12 · Árvore pasta-por-recurso · Status: **FECHADO** → [decisão](decisoes-refino-409/V-12-arvore-por-recurso.md)

`resources/<slug>` com uma pasta por recurso, no lugar de `artifacts/Resources/<segmentos do path>` (D-003 §2 + D-a opção 1).
**Isto é ganho, não regressão:** resolve a **D-y** (o recurso "Letras", cujas duas operações não compartilham prefixo, não tinha onde morar) e dispensa a regra de ancestralidade da **D-x**. Era a alternativa (2) listada na D-y.
**Custo:** perde-se a leitura da hierarquia de paths na árvore; a correlação repo ↔ Manager passa a depender do conjunto de `path:` (417, impacto 6), nunca do nome da pasta nem de `resource.name` (D-v).

**Pergunta a fechar** — promover a pasta-por-recurso a layout canônico (incremento da D-003 §2, revogando a D-a opção 1)? Mantém-se o prefixo `artifacts/`?

**Decisão:** _(a preencher)_

### V-13 · `resource.name` × nome da pasta · Status: **FECHADO** → [decisão](decisoes-refino-409/V-12-arvore-por-recurso.md)

A D-003 §5 manda o validador conferir que `name:` casa com o nome da pasta. Aqui: `name: /tarefas/{id}/atribuicao-responsavel` na pasta `atribuicao-responsavel`, e `name: /health-check` na pasta `health-check`. A **D-v** já havia derrubado a premissa (na 417 os nomes viraram rótulos livres: "Tarefas", "Atribuicao Responsavel").

**Pergunta a fechar** — remover a regra da D-003 §5 e declarar `name` como dado livre do usuário, versionado e sem papel de chave?

**Decisão:** _(a preencher)_

### V-14 · Molde da D-003 §4/§5 desatualizado · Status: **FECHADO** → spec reescrita (D-003 §4 e §5, 2026-10-14)

§4 lista `destination: <backend>` e `timeout: <segundos>` como escalares irmãos; §5 define `resource.yaml` como mapa leve de `name` + `description`. A pasta usa objeto em ambos e o `resource.yaml` ganhou `destination`. A 417 §5 (D-e) já havia registrado que um mapa leve **perde dado do Manager** quando o recurso tem destino preenchido.

**Pergunta a fechar** — reescrever §4 e §5 depois de V-01/V-02, num único incremento.

**Decisão:** _(a preencher)_

### V-15 · D-f revertida em 3 de 4 arquivos · Status: **FECHADO** → [decisão](decisoes-refino-409/V-01-destination-timeout-escopos.md)

Decorrência de V-01. A D-f foi tomada para **viabilizar promoção entre os 3 ambientes** (Default, DEV-APIOPS, HMG-APIOPS); URL absoluta no YAML mata esse motivo. Fechar junto com V-01 e registrar explicitamente se a promoção deixa de ser requisito do MVP.

**Decisão:** _(a preencher)_

---

## 6. Lacunas de regra criadas pela versão nova

### V-16 · Regra de slug da pasta de recurso · Status: **FECHADO** → [decisão](decisoes-refino-409/V-16-V-17-nomes-de-pasta-e-arquivo.md)

`atribuicao-responsavel` veio do último segmento do path. Com os 6 recursos reais da 409 a regra não fecha:

- `/tarefas` e `/tarefas/{id}` — o último segmento do segundo é `{id}`;
- a 417 mostrou nomes com espaço ("Atribuicao Responsavel") e rótulos que não são path ("Tarefas", "Letras");
- a D-004 §4 item 4 ("nome de pasta de resource com espaço") está **pendente** desde o grill.

**Pergunta a fechar** — slug derivado de quê (path completo? `name`? ordinal?), com que transliteração, e qual é o erro de colisão?

**Decisão:** _(a preencher)_

### V-17 · Nomenclatura do arquivo de operação · Status: **FECHADO** → [decisão](decisoes-refino-409/V-16-V-17-nomes-de-pasta-e-arquivo.md)

D-003 §2/§7 item 3: `{metodo}_{parametros}_{chaves}.yaml` (ex.: `get_endereco_{cep}.yaml`, como em `exemplo-layout-final/`). Aqui: `get_health_check.yaml` (hífen do recurso virou `_`) e `get_atribuicao-responsavel.yaml` (hífen preservado) — **duas transliterações na mesma pasta**, e o nome não codifica `tarefas` nem `{id}`.
Como `path:` é a fonte da verdade (D-a opção A), o nome do arquivo só precisa (a) entregar o método e (b) ser único. Falta declarar isso: *prefixo até o primeiro `_` = método; o resto é rótulo livre; colisão de método+path no mesmo recurso é erro*.

**Decisão:** _(a preencher)_

### V-18 · `all-all.yaml` — papel e gramática · Status: ABERTO

O arquivo cumpre o mesmo papel do `fluxo-herdado-SEM-CASA.yaml` (409) e do `escopo-revision-SEM-CASA.yaml` (417): **marcar o gap**, não propô-lo como solução — e o próprio cabeçalho diz isso. Mas agora ele acumula **duas coisas**: o fluxo base herdado (que a D-u atribuiu à régua 414) e o `destination`/`timeout` do escopo revision (que a 417 §5 declarou **decisão nova**, candidata a `spec.destination`/`spec.timeout` no basic info ou a um arquivo de defaults).
O nome `all-all` sugere uma convenção de layout (`{recurso}-{metodo}`?) que não está declarada em lugar nenhum.

**Pergunta a fechar** — (a) o fluxo base fica na régua 414 (V-11) e sai daqui? (b) onde moram `destination`/`timeout` de revision? (c) se o arquivo permanecer, qual é o nome e a gramática canônicos?

**Decisão:** _(a preencher)_

### V-19 · Cobertura parcial · Status: ABERTO

3 de 7 operações e 2 de 6 recursos da API 409. A simulação anterior cobria 7/7 e 6/6, conferidos contra o wire. A `fila-templates-schemas.md` §2 item 7 prevê o exemplo como **fixture dourada** dos testes de regressão — nesse papel, a cobertura precisa ser total (inclui o tombstone de `GET /tarefas`, que é o único caso de supressão com `parent: {id}`).

**Pergunta a fechar** — esta pasta é recorte de demonstração (e o exemplo normativo segue em `exemplo-layout-final/`), ou é a nova fixture e precisa dos 7 arquivos?

**Decisão:** _(a preencher)_

---

## 7. Acessibilidade dos campos (não é decisão — é inventário)

**Acessível por GET hoje**

| Campo | Fonte |
|---|---|
| `id`, `name`, `version`, `basePath`, `description`, `apiResponsible`, `apiTags` | `GET /apis/{id}` |
| `visibility`, `apiType`, `creationDate` (hidratação) | `GET /apis/{id}` |
| interceptors dos 3 escopos (revision, resource, operation) | `GET /revisions/{id}` |
| `resource.name/description/destination/timeout/connector/certificateId` | `GET /revisions/{id}` |
| `operation.path/method/description/destination/timeout` | `GET /revisions/{id}` |
| conteúdo do Custom por id | `GET /custom-interceptors/{id}` (já implementado no adapter) |
| catálogo de `attributeName` | Attributes do Adaptive Governance (`evidencia-tags-e-atributos.md`) |

**Sem fonte no contrato**

| Campo | Situação |
|---|---|
| `spec.template` | 4 confirmações de ausência (APIs 204, 290, 409); `"template": null` no payload de criação. Ver V-11 e D-004 §2.1 |
| base do backend | A 417 §4 provou que a cadeia é de **substituição**, não composição (recurso aponta `google.com`, operações apontam `dev-backend`): nenhuma base é derivável. Ver V-01 |
| unidade do `timeout` | O payload não informa se é s ou ms (D-m, pendência 1) — só fecha com publish |
| precedência de `timeout` entre escopos | Caso real existe (revision `"30"` × operação `"55"` na 417), nunca resolvido — só fecha com publish |

---

## 8. Impacto no CLI (consequência das decisões acima, não item de refino)

| Peça | Estado atual | O que falta | Resolve-se com |
|---|---|---|---|
| `domain/models/api_operations_model.py` → `Operation.destination: str` **obrigatório** | escalar | aceitar ausência e o shape decidido | V-01, V-02 |
| `Operation.timeout` irmão, `str`, removido quando vazio | — | alinhar ao shape decidido | V-02 |
| `domain/models/resources_model.py` → `Resource` | só `name`, `description`, `operations` | `destination`, `timeout`, `connector`, `certificateId` e flow de resource | V-01, V-14 |
| `domain/models/interceptors_model.py` → `Interceptor` | exige `id`, `idTemp`, `position`, `executionPoint`, `status` | nenhum deles existe no YAML (D-003 §4) | fila §1 item 2 |
| — | não há `override` nem listas request/response nos models | append × override inexprimível | D-003 §4 |
| `api-operations.schema.json`, `schema-interceptors.json` | fixam `position`/`executionPoint`/`status` com `additionalProperties: false` | reprovam todos os 7 arquivos; `Additional Info` não existe em nenhum schema | V-20, fila §1 itens 2 e 3 |
| `domain/services/json_to_yaml_enum.py`, `application/services/repo_validator.py` | esperam `resources.yaml` e `Templates/default-interceptors.yaml` | descoberta recursiva | V-12, fila §1 itens 8 e 9 |
| `ApiFull.set_interceptor_positions()` | contador global sobre revision + operations | não percorre o escopo **resource** (que tem flow real desde a D-q) | V-14 |

O que esta pasta **acrescenta** à `fila-templates-schemas.md`: shape de `destination` (V-01/V-02), `destination`/`timeout` em `resource.yaml` (V-14), tipo `Additional Info` (V-20), `null` em `content` (V-21) e a regra de slug/descoberta (V-12, V-16, V-17).

---

## 9. Pendências de rastreabilidade (menores, mas confundem citação)

1. As séries de letras **colidem**: `d004-template-e-validacao.md` §4 cita D-a (template), D-b (pasta com espaço), D-c (position global), D-d (escalares vazios), D-e (environments); o `simulacao-api-409-letras/README.md` usa os mesmos rótulos com outro sentido (D-a = nome de recurso é o path, D-b = position global, D-c = `workflowId`, D-d = `apiResponsible.groupName`, D-e = campos do Resource). A 417 teve o cuidado de continuar em D-v…D-y; a D-004 não.
2. A D-004 declara como premissa de evidência `simulacao-api-cep-real/README.md` — **essa pasta não existe** em `docs/feat-api-estructure/`.
3. Os cabeçalhos dos arquivos de `api-letras-409/` citam "README §3 D-c/D-e/D-f/D-h/D-q…" sem dizer **qual** README: é o de `simulacao-api-409-letras/`, não o da feature.

---

## 10. Sequência sugerida de refino

1. **V-07 a V-10** — releitura somente GET da 409; separa "dado novo" de "valor herdado da 417". Sem isso, V-01 decide sobre dado possivelmente contaminado.
2. **V-01 → V-02 → V-03** — fecham o shape de `destination`/`timeout`; destravam V-06, V-14, V-15 e os schemas de operação e resource.
3. **V-11** — `spec.template`: alinha a 409 à 417 ou revê a D-004 §2.1.
4. **V-12 → V-16 → V-17 → V-13** — layout e descoberta num bloco só (pasta-por-recurso, slug, nome de arquivo, papel de `name`).
5. **V-18** — casa do escopo revision.
6. **V-20, V-21** — contrato de interceptor.
7. **V-19** — completar a cobertura antes de virar fixture.
8. **V-04, V-05, V-06** — varredura final de comentários (fecham junto com os itens que os originam).

Fechados os itens, o movimento é: incremento na D-003/D-004 → atualização da `fila-templates-schemas.md` → change proposal OpenSpec.
