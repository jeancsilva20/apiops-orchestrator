# Design — add-sen-completeness

*(pt-BR. Keywords SHALL/MUST em inglês. Complementa o proposal e a spec `sen-completeness`.)*

## Context

- A feature selada do `sen completeness` (`docs/feat-command-sen-completeness/`) definiu o AG (`adaptive-governance`) como fonte primária. As sondas posteriores (`problemas.md`, 24/09) provaram que o AG só mantém report da **última revisão**; nem a UI do Manager expõe histórico de completude por revisão via AG.
- O endpoint do Manager `GET /api-manager/api/v3/revisions/{rid}/completeness` (swagger `swagger-apim-v4/swagger.json`, `CompletenessBean`) aceita **o id da revisão no path** e respondia 200 ao vivo nas mesmas sondas — cobrindo qualquer revisão.
- A spec selada original **não é alterada** (fica como registro histórico/planejamento); esta change estabelece o desvio deliberado e a ADR 0008 receberá nota de supersedência parcial.
- Estado do código: não há implementação do `sen completeness` (nenhum arquivo de comando/port/service dedicado). A infra do `sen list` já possui `get_revision_completeness` esboçado no `ManagerApiAdapter` e `HttpClient` com retries/timeout/RFC 7807 (padrões §7).

## Goals / Non-Goals

**Goals:**
- Entregar `sen completeness` funcional para **qualquer revisão** do histórico, com gramática A1–A7 da feature preservada (`--api-id` e `--revision` obrigatórios, `--score-only`, `-o`, `-v`).
- Contrato JSON versionado `apiops.sen-completeness/v1` **rebocado** ao que o Manager efetivamente entrega (`completenessScore`, `suggestions[]`) — sem campos-fantasma.
- Simplificar o plano de chamadas: 1 GET do Manager + satélite api-finder degradável (contexto/posse).
- Visualização TEXT coerente com o dado disponível: barra/gate + lista integral de `Suggestions` (sem severidade/impacto fabricados client-side).

**Non-Goals:**
- Avaliação local de completude (`sen validate`, fase 2) — apenas garantir reuso do `CompletenessService`.
- Histórico de maturidade estruturado por revisão (depende da Plataforma — P-f permanece aberto para o AG; caso venha, a fonte pode ser reavaliada numa change futura).
- Gate dinâmico via `workflows/{id}/stages` (P-a permanece postergado; gate 70% hardcoded `p10.v1` se mantém na V1).
- Alterar a spec/feature docs originais ou o ADR 0008 além da nota de supersedência.

## Decisions

**D1 — Fonte única: Manager `GET /revisions/{rid}/completeness`.** O path já carrega a revisão pedida, matando o bloqueio do AG. Alternativa (manter AG + aceitar "só última revisão") rejeitada porque invalida a semântica de A3 (`--revision` obrigatório) e derruba o valor do comando a um espelho de uma única revisão. Route/verb/documento confirmados no swagger (`CompletenessBean`).

**D2 — Contrato v1 rebalanceado (subtração assumida).** Campos derivados de violação estruturada do AG são **removidos** da árvore (`violations[]`, `rulesLost[]`, `issues.bySeverity`, `severity`, `impactPoints`, `range`, `classification`, `agCatalogId`, `agId`, `last`): não há como prová-los sem alicerce de dado; nulls-fantasma rompem o princípio "dump honesto" (critério de aceite 4 da feature). Probe adicional (25/09) confirmou o wire real: `{completenessScore, suggestions[]}` — **a plataforma não classifica a partir do Manager**, logo a classificação B/I/A NÃO é derivada client-side (seria invenção de dado; ver Q4). O que permanece: `schema`, `generatedAt`, `api{managerId,name,version,context?}`, `revision{managerId}`, `maturity{score}`, `gate{percent}`, `suggestions[]{text,index}`. Posse (`type/groupName/owner`) mora dentro do bloco `api` — é dado da API; **nenhum bloco de estado-de-coleta existe no contrato** (sem status/source/note: degradação do lookup se expressa só pela ausência dos campos — regra da casa "dado ou nada", que também cortou o `source` do gate/original).

**D3 — Sugestões viram entidades de primeira classe com índice.** `suggestions[]` do Manager é `array[string]`; model pydanticembrapa `{index, text}` (ordem do wire preservada = ordem de exibição — determinismo para automação). Alternativa (keyed-map) rejeitada: inventaria chave estável que o backend não garante.

**D4 — Sem port dedicada: a fronteira já existe (evolução do ADR 0008).** Com a fonte voltando a ser o próprio Manager (D1), a port dedicada `CompletenessPort` perdeu a razão de ser: Protocol de 1 método com 1 implementação eterna seria indireção speculative; a fronteira hexagonal real já é detida por `ManagerApiPort`/`ManagerApiAdapter`. A adaptam-se: novo método `get_revision_completeness(revision_id)` no adapter + assinatura correspondente na `ManagerApiPort`. Model e Service permanecem próprios (bloco reutilizável do `sen validate`). Alternativa (manter `CompletenessPort`) rejeitada: outro backend não é a fonte hoje — quando o AG historizar revisões (P-f), a abstração é extraída então (composition root facilita). **Regra de fronteira dura (não-negociável, aprendida do débito consciente do sen list/D3):** o dict cru do wire MORRE DENTRO do adapter — `ManagerApiAdapter.get_revision_completeness` devolve valor tipado de domínio (`CompletionReading{score, suggestions[list[str]]}`, definido junto ao model), nunca `Dict[str, Any]`; quem divide o par de falas wire↔domínio é o outbound, não o service (diferença de qualidade frente ao sen list: lá o dict cru atravessa service e chegou a atingir o CLI; aqui as fronteiras voltam a blindar).

**D4.b — Erros também seguem a casa: exceção única com `exit_code`, sem módulo dedicado.** Convenção vigente (`sen list`) usa ~1 exceção grossa com mensagem PT-BR pronta (`ApiCollectionError`) traduzida em `typer.Exit` pelo CLI; o padrão de transporte de causa é o RFC 7807 do `HttpErrorMapper`. Logo: **não existirá `application/exceptions/completeness_exceptions.py`** — apenas `CompletenessError(message, exit_code=2)` definida junto ao service (espelho de `CliError`). Os dois buckets da matriz G1: `exit 1` é guard pré-rede local do CLI (nem chega ao service); `exit 2` é a exceção única; lookup de identidade caído não é exceção (soft-fail interno). Taxonomia NotFound/Auth/Denied do desenho original morre com a fonte AG — erros são statuses do MESMO backend, distinguíveis pelo `status/detail` do RFC 7807.

**D4.c — Projection vs. reuso: contratos versionados são subconjuntos, nunca inclusões.** O bloco `api` do contrato NÃO referencia `ApiPartialInfo` (domínio do publisher/sen list) porque: (1) ele tem campos mandatórios (`basePath`, `apiResponsible`) que explodiriam o parse no cenário degradação C4; (2) carregaria no JSON dados não provados p/ o relatório; (3) sua evolução acidental alteraria contrato versionado. `ApiInfo`/`RevisionInfo`/`ApiContext` (~10 linhas) são projections locais — regra: **DTO de saída versionado consome projeção mínima; extração de model compartilhado só no 2º consumidor com CONTRATO tipado real**. Precisões: o `sen list` é saída de TERMINAL (grade rica derivada de dicts crus, linha a linha) mas **não** contratu versionado — seu canal JSON tipado é backlog (B2 da fatia sen-list), logo não habilita o gatilho hoje; identidade tipada de entrada já existe (`ApiPartialInfo`, `ApiRevision`, `Interceptor`, `Resource`) — o que esta change inaugura é identidade tipada **de saída** (DTO opcional-friendly para re-eco auditável sob degradação). Incluir entrada na saída (ou vice-versa) confunde ciclos de vida distintos: extração conjunta só quando B2 aterrissar ou `sen validate` surgir. **Fundação em andamento (25/09):** a change irmã [`../type-api-catalog-frame/design.md`](../type-api-catalog-frame/design.md) tipa o frame do api-finder (`ApiCatalogEntry`) e restaura o §9 nas fronteiras — o SATÉLITE desta fatia passa a consumir os tipos da fundação (identidade/contexto lidos de `ApiCatalogEntry`); o DTO de saída aqui permanece projeção mínima, como decidido acima.

**D5 — Enriquecimento de identidade permanece degradável COMO CHAMADA, e é invisível como contrato (C3/C4 reenquadradas).** Posse/Contexto (`contextType`, `contextGroupName`, `owner`) só existem no api-finder: a chamada permanece soft-fail (`exit 0`, `managerId` garantido, campos `null` quando falha). **Bloco `satellite` eliminado do contrato** (revisão 25/09): o output exibe dados de completeness + dados da API; estado de coleta é ruído — ausência fala por si. Alternativa (manter `satellite{status,note}`) rejeitada: mesma categoria de auto-explicação cortada do gate. A conecta Connect Catalog também morre aqui (era subsídio da ponte AG).

**D6 — Aritmética perdida vira design de tela, não invenção de dado.** Com `severity` indisponível, a tabela `Sev │ Impact │ Where` (F1/F5/F7) é aposentada; lista `Suggestions` numerada + word-wrap integral substitui. `--score-only` mantém headline + barra/gate (F6). `-v` permanece só verbosidade. A paleta colorida de classificação (F2) **morre junto**: sem classificação no wire (probe 25/09), o headline exibe apenas o percentual neutro + barra/gate — cores ficam reservadas para quando a plataforma expor bucket/classification (P-f/Q4).

**D7 — Erros (G1 reajustado).** Matriz: ausência de `--api-id`/`--revision` ⇒ `exit 1` pré-rede (A4 mantido); 401/403/404/409/422 e 5xx esgotado do Manager ⇒ `exit 2`; vazios reais/satélite caído ⇒ `exit 0`. Novo cenário específico: revisão inexistentetingível (`404` do path) → mensagem PT-BR orientando `sen list api --id X --revisions`. Fim da recusa sintética "revisão antiga" (regra selada dos problemas revogada — qualquer revisão alcançável é respondida).

**D8 — Autenticação e moeda de token (herdado).** O comando requer a sessão válida via `sen login`; jwt plataforma-native (P-b) continua pré-condição de produção. Nada de tokens na saída (G2 padronizado).

## Risks / Trade-offs

- [Perda de granularidade: sem `ruleId/severity/range`] → Mitigado com lista simples de suggestions e gate por headline; granularidade fica documentada como retrocompatibilidade com o AG (tabelas possíveis se/quando fonte AG historizar revisões).
- [`suggestions[]` sem ordenação lógica documentada pelo backend] → Ordem de chegada usada como contrato de exibição (index crescente); automação que reordene faz por conta própria.
- [Duplicidade conceitual com `sen list` (completeness por revision no drill-down)] → Fazendas distintas: lá é teaser por linha (frame do catálogo); aqui é espelho integral por revisão — nenhum requisito novo altera a spec `sen-list`.
- [Pendência P-b (JWT platform-native)] → Bloqueio de produção independente; smokes/documentação assumem sessão válida no ambiente de testes.

## Migration Plan

Sem código legado a migrar (nenhuma impl anterior). Rollout = implementação nova sobre a branch base (`feat/command-sen-completeness`). Rollback trivial (ramo não mergeado). ADR 0008 recebe nota de supersedência parcial (fonte primária); docs de problemas mantidos e anotados.

## Open Questions

- Q1 (para plataforma): `suggestions[]` tem ordem estável/peso associado? Hoje tratamos como string list sem ranking.
- Q2: revisões de APIs do modo revisão (draft/non-deployed) retornam 200 igual? (herda P9/P-b; guardado para smoke.)
- Q3: campo `gate` — deve somir no contrato enquanto P-a não avança? Decidido: permanecer (valor fixo do P10) para estabilidade do contrato v1.
- Q4: classificação (Basic/Intermediate/Advanced) — aguardar a Plataforma expor o bucket no wire (Manager ou AG); enquanto não vier, headline exibe apenas o percentual (derivação client-side rejeitada em D2).
