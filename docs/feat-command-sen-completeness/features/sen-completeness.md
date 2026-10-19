# Feature — `sen completeness`

| Meta | Valor |
|---|---|
| Ramo | `feat/command-sen-completeness` (incremento sobre `feat/command-sen-list`) |
| Data | 2026-09-24 |
| Estado | **Decisões seladas** (grill 24/09 + bateria de 4 sondas read-only em produção, data única) |
| Autor do documento | Jean Silva |
| Pré-requisito | `sen login` antecede esta feature — **com pendência de emissão de JWT platform-native (ver §5, P-b)** |
| Fontes primárias | Sessão de grill + sondas read-only 24/09/2026 · memory bank APIOps (`knowledge/comandos-cli-sen.md`, `knowledge/adaptive-governance-completeness.md` — P3/P10) · mapeamento APIM `docs-sensedia/05-maturity-score.md` e `12-adaptive-governance.md` |

> **Régua permanente:** este documento é planejamento/documentação. Nenhuma alteração de código foi realizada nesta feature até o momento; todos os pontos técnicos referem-se ao estado observado do código em `src/apiops_orchestrator/` e às sondas de 24/09/2026.

---

## 1. Contexto e autoridade

1. **Comando top-level, família de "valores de plataforma".** `sen completeness` espelha, em leitura pura (read-only), o que a plataforma calcula de maturidade/completude — não avalia nada localmente. A avaliação local é território do `sen validate` (fase 2, não desta fatia).
2. **Fronteira com `sen validate` selada:** o serviço de aquisição de completude desta feature é **compartilhável**; o `sen validate` futuro o reutilizará como bloco (contexto Draft, regras determinísticas). Aqui não há diagnóstico — há espelho.
3. **Correção de escopo (grill 24/09):** o desenho original restringia o comando a "APIs com deploy" (proteção contra a pendência P9 do memory bank). Com a decisão A3 (`--revision` **obrigatório**), essa proteção perde a função: o usuário informa exatamente qual revisão consultar e a plataforma responde ou recusa. A recusa vira **degradação declarada** (ver B2/G), não filtro de entrada.
4. **Cross-produto provado ao vivo (sondas 24/09):** o texto das mensagens de violação do AG corresponde quase 1:1 às `suggestions[]` do Manager (`/revisions/{rid}/completeness`) — mesma engine, dois níveis de zoom. O endpoint do Manager **não** é consumido por este comando (C5).

---

## 2. Decisões seladas (categorias A–G)

### A. Gramática do comando

| # | Decisão | Detalhe |
|---|---|---|
| **A1** | Comando **top-level** `sen completeness` | Irmão de `sen list` (família de valores de plataforma, não catálogo). Recusadas as formas `sen list completeness` e flag `--completeness` dentro de `sen list api` |
| **A2** | `--api-id <id_manager>` **obrigatório** | Vocabulário nativo do dev (inteiro do Manager); tradução interna via `originId` (C4) |
| **A3** | `--revision <id_interno>` **obrigatório** (o `originId` da revisão — o `REV ID` exibido no drill-down `sen list api --id X --revisions`) | **Revogado o default "última revisão"** (voto do grill 24/09): com dezenas de revisions por API, default silencioso = dado visto ≠ dado real. Integridade semântica acima de conveniência |
| **A4** | Ausência de `--revision` ⇒ erro **pré-rede**, `exit 1`, orientando `sen list api --id X --revisions` | Zero chamada HTTP em erro de entrada; UX fecha o loop com o comando irmão |
| **A5** | `--score-only` | Headline + barra de progresso, sem tabela de violações |
| **A6** | `-o text\|json\|yaml` (default `text`) | Mesmo wire de `output_format.py`/`display_output` já adotado pelo `sen list` |
| **A7** | `-v` = verbosidade + coluna `Swagger Loc` | `-v` controla verbosidade, nunca formato (convenção canônica, ADR 0005/padrões §8) |

### B. Escopo

| # | Decisão | Detalhe |
|---|---|---|
| **B1** | **Qualquer revision informada é consultada** — sem restrição "só deploy" | Substitui o desenho original do grill 24/09 (motivação da proteção caiu com A3) |
| **B2** | Recusas da plataforma (ex.: contexto Draft) = **degradação declarada**: `422` (wrapping `403`) → mensagem honesta + `exit 2` | A pendência P9 do memory bank fica fora do caminho deste comando: o espelho reflete o que a plataforma decide |

### C. Fontes de dados

| # | Decisão | Detalhe |
|---|---|---|
| **C1** | **AG primário**: `GET /adaptive-governance/api/v1/search` (envelope `{result, totalizer}`) + `GET /adaptive-governance/api/v1/maturity-reports` (array cru) | Sondeiras 24/09 — shapes vivos; o AG é o provedor exclusivo do dado de maturidade |
| **C2** | `fullReport=true` **ON por padrão**; `--score-only` passa sem a tabela (o custo é a mesma chamada) | Full report entrega `violations[]` estruturadas (code/path/range/severity) |
| **C3** | **Satélite api-finder** (1 chamada): nomes de ambientes + contexto/posse (`contextType`, `contextGroupName`, `owner`) | Informação inexistente no AG (que traz apenas `originId` numérico dos deployments); reusa `list_api_detail` da `ManagerApiPort` |
| **C4** | Satélite **degrada suave**: `exit 0`, IDs crus + `Contexto: -` + nota no banner | Nunca bloqueia o dado principal (espelho do AG) |
| **C5** | Ponte de identificadores bidirecional: `catalog.catalogOriginId` (id da API no Manager) e `revision.originId` (id da revisão no Manager) | Tradução Manager↔AG resolvida em payload, sem guess |
| **C6** | `GET /api-manager/api/v3/revisions/{rid}/completeness` **NÃO é consumido** | Espelho textual 1:1 das mensagens do AG — registrado como opção de *fallback/regressão* futura, não dependência |

### D. Arquitetura

| # | Decisão | Detalhe |
|---|---|---|
| **D1** | Port dedicada `CompletenessPort` (`domain/ports/completeness_port.py`) | Não engorda a `ManagerApiPort` — plano de dados é outro mundo |
| **D2** | Adapter novo `adapters/outbound/http/adaptive_governance/` | Reuso integral do `HttpClient` (retries 5xx, timeout, RFC 7807 — padrões §7) |
| **D3** | `CompletenessService` em `application/services/` — **compartilhável com `sen validate`** | Resolver catálogo→originId, casar revision, normalizar violações + impacto |
| **D4** | Models pydantic em `domain/models/`, camelCase espelhando o wire (padrões §9) | Nunca dict cru atravessa camadas |
| **D5** | Satélite via `ManagerApiPort.list_api_detail` já existente | Zero adapter novo para o api-finder |

### E. Contrato de saída

| # | Decisão | Detalhe |
|---|---|---|
| **E1** | JSON = contrato **versionado** `apiops.sen-completeness/v1` | Nunca dump cru da resposta do AG; stable contract p/ automação (esteira) |
| **E2** | `impactPoints = lostScore ÷ violationCount` (rateio uniforme, auditável) | Comprovado ao vivo: SSD-011 = 0.5/5 = −0.1 por ocorrência; SSD-002 = 15/1 = −15.0 |
| **E3** | `gate: {"percent": 70.0, "source": "hardcoded.p10.v1"}` | Herança P10 do memory bank (threshold fixo 70% configurado no AG). **Pendência registrada** (§5, P-a): tornar dinâmico via `workflows/{id}/stages.completenessRequisite` |
| **E4** | YAML = mesma árvore do JSON serializada | Sem segundo contrato |

### F. Visualização (TEXT)

| # | Decisão | Detalhe |
|---|---|---|
| **F1** | Tabelas Rich estruturadas (padrão já usado por `_render_grade` do `sen list`): `Sev │ Impact │ Description │ Where` | Inspirado no painel "Top violations" da plataforma |
| **F2** | Cores de severidade: **HIGH=vermelho · MEDIUM=amarelo · LOW=azul** (paleta própria, decisão do grill) | Classificação de maturidade usa a paleta da plataforma (viva): Basic `#D70026`, Intermediate `#FFAD04`, Advanced `#1771C6` |
| **F3** | `ruleId` (SSD-xxx) e `contracts` **FORA da tela** — vivos no JSON | Motivo: irrelevância para o dev final (usuário);auditoria fica no canal de máquina |
| **F4** | `Description` = mensagem AG **integral**, word-wrap — zero abreviação | |
| **F5** | `Where` = dot-path compacta (`paths./orders/get/responses.200`); `-v` adiciona coluna `Swagger Loc` (linha/char do range) | Linha no arquivo em `-v` = rastreabilidade; nunca exibimos o próprio contrato |
| **F6** | **Barra de progresso**: 30 glifos = 100% (com sub-glifos para fração), marcador do gate fixo, legenda `(gate: ≥70%)` + `✖ −X.X pts` quando abaixo | Layout aprovado no grill 24/09 |
| **F7** | Ordenação da tabela: Sev ↓, depois Impact ↓ | |

### G. Erros e códigos de saída

| # | Decisão | Detalhe |
|---|---|---|
| **G1** | Matriz: pré-rede `exit 1` · 401/404/403/422-wrap `exit 2` · vazio real e satélite caído `exit 0` | Mensagens PT-BR orientando a ação (padrões §5); sem stacktrace |
| **G2** | Mensagens/outputs **nunca** carregam tokens, cookies ou blobs de credencial | Padrão de segurança do projeto (§11) |

---

## 3. Grades aprovadas (dados reais das sondas 24/09 — API "Manager Training 1.0", score 70.5%)

**1) Modo completo** — `sen completeness --api-id 375 --revision 5513`

```
┌ API ───────────────────────────────────────────────────────────────────┐
│  Manager Training 1.0 (1.0)        API: 375 · Revision: 5513           │
│  Contexto: ORGANIZATION            Deployed: Development, Homologação  │
│                                                                        │
│  Completeness: 70.5%   ● INTERMEDIATE    Issues: 12                    │
└────────────────────────────────────────────────────────────────────────┘

┌ Violations ────────────────────────────────────────────────────────────┐
│ Sev    │ Impact │ Description                          │ Where         │
├────────┼────────┼──────────────────────────────────────┼───────────────┤
│ HIGH   │ −15.0  │ API description is too short. Use    │ info.         │
│        │  pts   │ more than 15 characters and describe │ description   │
│        │        │ the API objective, endpoints, and    │               │
│        │        │ operations.                          │               │
│ HIGH   │ −5.0   │ No models defined. Define data       │ definitions   │
│        │        │ models with clear attributes, types, │               │
│        │        │ and descriptions.                    │               │
│ MEDIUM │ −0.1   │ Response code 200 of operation GET   │ paths./orders/│
│        │  pt    │ /orders has a description "OK" that  │ get/responses.│
│        │        │ is too short. …                      │ 200           │
└────────┴────────┴──────────────────────────────────────┴───────────────┘

12 issues · -v inclui linha no swagger · --output json para automação
```

**2) `--score-only` (barra com gate)** — aprovada no grill 24/09:

```
┌─ Maturity 87.5% ── ADVANCED ───────────────────────────────┐
│ ██████████████████████████▋░░░░▏░░░ (gate: ≥70%)           │
└─────────────────────────────────────────────────────────────┘
 Issues: 4 · HIGH 1 · MEDIUM 3 · LOW 0        saiba mais: -v · -o json
```

Abaixo do gate:

```
┌─ Maturity 54.2% ── INTERMEDIATE ───────────────────────────┐
│ ████████████████▎░░░░░░░░░░░░░░▏░░░ (gate: ≥70%) ✖ −15.8   │
└─────────────────────────────────────────────────────────────┘
```

**3) Verbose (`-v`)** — apenas acrescenta a coluna `Swagger Loc`:

```
│ HIGH │ −15.0 │ API description is too short… │ info.description │ L2:C5–L4:C31 │
```

**4) JSON (`-o json`)** — envelope do contrato `v1` (ver §6/ADR e payload de referência abaixo):

```json
{
  "schema": "apiops.sen-completeness/v1",
  "generatedAt": "2026-09-24T12:40:00Z",
  "api": {"managerId": 375, "name": "Manager Training 1.0", "version": "1.0",
           "agCatalogId": "7259b213-…",
           "context": {"type": "ORGANIZATION", "groupName": null, "owner": "…"}},
  "revision": {"managerId": 5513, "agId": "87e1bab3-…", "last": true,
                "deployedEnvironments": [{"originId": "17", "name": "Development"}]},
  "maturity": {"score": 70.5, "totalLossPoints": 29.5,
                "classification": {"name": "Intermediate", "color": "#FFAD04"}},
  "gate": {"percent": 70.0, "source": "hardcoded.p10.v1"},
  "issues": {"total": 12, "bySeverity": {"HIGH": 7, "MEDIUM": 5, "LOW": 0}},
  "violations": [{"ruleId": "SSD-011", "severity": "MEDIUM", "impactPoints": 0.1,
                   "code": "operations_responses_codes_description_is_less_than_4",
                   "message": "Response code 200 of operation GET /orders …",
                   "path": ["paths", "/orders", "get", "responses", "200"],
                   "range": {"startLine": 14, "startChar": 23, "endLine": 14, "endChar": 27}}],
  "rulesLost": [{"ruleId": "SSD-002", "weight": 15.0, "lost": 15.0, "violations": 1}],
  "satellite": {"source": "api-finder", "status": "ok"}
}
```

---

## 4. Mapa de fontes vivas (sondas read-only, 24/09/2026)

| Fonte | Chamada | Observação |
|---|---|---|
| AG search | `GET /adaptive-governance/api/v1/search?limit=&page=` | Envelope `{result[…], totalizer{…}}`; cada row traz `issues[]` resumidas + `maturity.scoreAverage/classification` + `id` (catalog UUID) |
| AG maturity-reports | `GET /adaptive-governance/api/v1/maturity-reports?catalogIds={uuid}&limit=` | **Array cru**; cada report traz `revision{originId, catalogOriginId, last, contracts, deployedEnvironments[]}` + `classification` + `scoreAverage` + `qualityProfileAnalysis[0].score.details` (17 regras) |
| AG fullReport | idem + `&revisionIds={revUuid}&fullReport=true` | Delta = `violations[]` por regra: `{code, path[], severity, message, range{start/end{line,character}}}` |
| Satélite api-finder | `GET /api-finder/api/v3/apis` (`customSearch=(apiId:X)`) | Frame existente: `environments[{name, apiRevision}]` (nomes p/ deployments) + `contextType/contextGroupName/owner` (posse/na tela do `sen list`) |
| *Não consumido* | `GET /api-manager/api/v3/revisions/{rid}/completeness` | 200 ao vivo com o mesmo JWT; payload `{completenessScore, suggestions[]}` (texto integral, sem estrutura). Registrado como mirror — não-dependência (C6) |

**Conclusões empíricas registradas:**

1. **Autenticação universal:** um único **Bearer JWT do mundo-plataforma** (RS256, emitido pelo portal) abre Manager, api-finder e AG — sem cookie e sem XSRF em leituras. O token opaco do fluxo `orq-auth` atual retorna `401 {"message":"Unauthorized"}` no gateway **inclusive para o Manager e o api-finder** (alerta lateral §5/P-d).
2. **Pontes de ID:** `catalogOriginId` = id da API no Manager; `revision.originId` = id da revisão no Manager. Tradução declarativa em payload.
3. **Aritmética auditada:** `score = 100 − Σ(lostScore)` — provado 3× ao vivo (70.5 = 100 − 29.5). `severityPenalty` por regra confere com a tabela SSD-001..017 do mapeamento APIM.
4. **O gate NÃO está exposto** em nenhum payload sondado (nem search, nem reports) — legitima o hardcode 70% (P10) na V1 e anota a rota futura (workflows).
5. **Divergência de severidade agregada:** a `issues[]` da search rotulou a API de teste como `MEDIUM`, mas o fullReport mostra violações `HIGH` — eleita fonte-display única: **fullReport** (search fica como teaser/contagem).
6. Faixas de classificação vivas: `Basic 0–29.9 (#D70026) · Intermediate 30–79 (#FFAD04) · Advanced 80–94 (#1771C6)`.

**Economia de chamadas (fluxo completo):** `search` (≤2 chamadas paginadas para casar originId) + `maturity-reports` (1) + satélite api-finder (1) ≈ 4 GETs; nenhuma chamada de escrita.

---

## 5. Pendências de placa (não bloqueiam a implementação)

| Selo | Pendência | Valor recomendado aguardando |
|---|---|---|
| **P-a** | Gate **dinâmico** da barra | Ler `completenessRequisite` real via `GET /api-governance/api/v3/workflows/{workflowId}/stages` (cache por workflow — a infra `get_workflow_stages` já existe na port do Manager); substitui o `hardcoded.p10.v1` |
| **P-b** | **JWT platform-native no `sen login`** | O fluxo atual (`orq-auth`, token opaco) retorna 401 em TODAS as rotas de produção sondadas. Emitir/expor JWT RS256 do mundo-plataforma é pré-requisito de runtime (decisão da Plataforma) |
| **P-c** | Divergência de severidade agregada (search × fullReport) | Manter fullReport como fonte-display; reportar divergência à Plataforma se persistir |
| **P-d** | Alerta lateral: saúde do Bearer atual da CLI em produção | Investigação apartada — não é culpa desta feature, mas toca todos os comandos |
| **P-e** | `sen validate` (fase 2) | Reutiliza `CompletenessService`; inclui contexto Draft/estáticos e reabre o tema P9 |

---

## 6. Critérios de aceite

1. Grades/tabelas renderizam com payloads reais das sondas (fixtures anonimizadas em `tests/fixtures/`);
2. Unit tests espelhando a árvore (`tests/unit/…`, doubles feitos à mão na port — padrões §10): mensagens de UX literal na saída, **segredos nunca na saída**, exit codes como contrato;
3. `--api-id` e `--revision` obrigatórios; erro pré-rede (`exit 1`) orientando `sen list api --id X --revisions` quando falta `--revision`;
4. Contrato JSON estável `apiops.sen-completeness/v1` — determinístico para automatização; sem dump cru em nenhuma saída;
5. Matriz de erros (G1) respeitada, incluindo degradação do satélite (`exit 0` com nota) e 422-wrap documentada como "possível contexto Draft";
6. Smoke read-only em produção: somente GETs (search + reports + api-finder), com sessão válida;
7. Segundo agente revisor valida este documento (regra de processo do projeto).

---

## 7. Ligação com o restante da documentação

- ADR da arquitetura desta fatia: [`../adr/0008-completeness-port-dedicada-ag-direto.md`](../adr/0008-completeness-port-dedicada-ag-direto.md)
- Despriorizações/pendências congeladas: [`../backlog/sen-completeness-postergados.md`](../backlog/sen-completeness-postergados.md)
- Fatia irmã (padrões de grade, drill-down, factories): [`../../feat-command-sen-list/features/sen-list.md`](../../feat-command-sen-list/features/sen-list.md)
  - *(no backlog da fatia sen-list, o item 5 — "Visualizador de suggestions / candidato a `sen audit`" — é **supplantado** por este comando)*
- Credenciais do login (`SEN_CREDENTIALS`/`.sen`): [`../../../adr/0007-sen-como-casa-do-bloco-de-credenciais-e-residencia-dos-arquivos-sen.md`](../../adr/0007-sen-como-casa-do-bloco-de-credenciais-e-residencia-dos-arquivos-sen.md)
- Fonte normativa de completude/gate (P3/P10): memory bank APIOps — `arquitetura-apiops-memory-bank/knowledge/adaptive-governance-completeness.md` (canônico)
- Fonte empírica de produto: mapeamento APIM — `docs-sensedia/05-maturity-score.md`, `docs-sensedia/12-adaptive-governance.md`
