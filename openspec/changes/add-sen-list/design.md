# Design: add-sen-list

Referência de análise completa: `docs/feat-command-sen-list/features/sen-list.md` (decisões A1–E3, selas Paulo) e `docs/feat-command-sen-list/adr/0006-composition-root-lazy-cli.md`.

## Context

- `main.py` é um composition root *semi-ansioso*: os builders de service já são lazy (fatorados pelos comandos, `cli_adapter.py:47-52, 85-91`), mas `Settings()` ainda é construído antes de qualquer dispatch (`main.py:160`), exigindo `.env` completo até para `--help` — atropela o requisito D1-a.
- `repo_path` hardcoded (`main.py:42-44`) alimenta apenas o fluxo legacy `run_bare_pipeline()`, que mistura composição da CLI com pipeline de conversão `ApiFull`.
- `pyproject.toml` não registra `[tool.poetry.scripts]` — não existe binário `sen` instalável.
- `ApiListingService` é pass-through (`manager_api.get_apis()`); nenhuma regra de listagem existe ainda.
- Servidor não provê paginação nem busca (comprovado em sondas 15/09: `?offset/limit/_limit` ignorados, 107/107/107) — tudo client-side é obrigação, não escolha.
- Fontes vivas dos dados (sondas read-only validadas): mapa da §4 da feature — listagem/drill-down via `/api-manager/api/v3/apis[...]`, completeness, stages de workflow, tudo GET.

## Goals / Non-Goals

**Goals:**
- `sen` como entry-point real (`[tool.poetry.scripts]`), metadados sem `.env` (D1-a), degradação educativa sem chaves (D1-b).
- `sen list api` com as grades canônicas da §3: listagem, busca `--query`, drill-down `--id [--revisions]`.
- Regras seladas centralizadas em uma camada de aplicação pura, testável com mocks na port (E3).
- Fluxo legacy fora do pacote (D3), desobstruindo o composition root.

**Non-Goals:**
- Gate de escopo `list→read` (ADR 0003) — fase 2, quando a integração com o login ocorrer.
- Troca da fonte do token para `.sen_session` — hoje mantém-se a injeção atual; o seam (`ManagerApiAdapter(token=...)`) já reserva o ponto.
- Canal de máquina `-o json`/YAML (B2/C3 — backlog `sen-list-despriorizacoes.md`), filtros server-side, `--domain`/`--tag`, `sen audit`.
- Alteração do `sen login` (spec `cli-auth` intocada).

## Decisions

**D1 — Composition root lazy via builders por comando.** `main()` só faz dispatch; `Settings()` é instanciado dentro dos builders no momento em que o comando exige configuração. Alternativa descartada: `Settings(lazy=True)` com proxy global — introduz semântica especial em todo consumers sem necessidade. Esteira PoC ganha falha rápida e o `--help` não paga configuração.

**D2 — Fluxo legacy → `scripts/generate_api_json.py` (fora do pacote).** `python main.py` pelado deixa de existir na CLI (bare `sen` = `no_args_is_help`, já comportamento do `sen_app`); o script recebe `--repo`/`--revision` e reproduz o comportamento atual (validação de estrutura + schema + conversão `ApiFull`). Alternativa descartada: manter como sub-comando interno — perpetuaria o acoplamento e traria o pipeline para dentro do exe entregue ao dev. *(D3 era "pendente de placa"; realizado neste passo porque a migração do composition root o torna morto — não dá para migrar sem extrair ou duplicar.)*

**D3 — Regras de listagem na camada de aplicação, comando como adapter burro.** Pipeline: `filtrar (--query) → ordenar (id asc) → janelar (offset/limit)`. A CLI apenas traduz flags; a `ApiListingService` (ou `ListApisUseCase` sob `use_cases/`) recebe o dataset bruto via `ManagerApiPort` e aplica as micro-regras A3-1a/1b/1c e A3-3. Alternativa descartada: regras no adapter HTTP — impossibilitaria mocks limpos e duplicaria a lógica no futuro drill-down. Ordenação no client compensa a ausência de paginação server-side (única ordem estável para diffs).

**D4 — Janela sempre explícita com default anunciado.** Qualquer saída divulga a janela efetiva; o caso desnudo (`sen list api`) executa `--limit 10 --offset 0` com rodapé `usando padrões: --limit 10 --offset 0 · detalhes: sen list api --help` (selo Paulo-5 — revogou o default silencioso). `--limit ≤ 0` → erro amigável, exit 1; `--offset` além do total → lista vazia, exit 0.

**D5 — Busca `--query` client-side, campos `name`+`description`, case-insensitive + accent-folded.** Normalização Unicode (fold de diacríticos) centralizada em util único para reuso. Mutuamente exclusiva com `--id` (validação na CLI, erro imediato). Janela aplica-se após o filtro. Server-side e `--domain`/`--tag` → backlog (A3-4).

**D6 — Drill-down de revisões com catálogo de stages cacheado por sessão.** Grade de revisões compõe: detail da API + `/apis/{id}/revisions` + `/revisions/{rid}/completeness` (1 chamada por revisão exibida) + nome do stage de `workflows/{workflowId}/stages` cacheado (1 chamada por workflow distinto, não por linha). Economia de chamadas alinhada à feature §4.

**D7 — Erros RFC7807→humano (E1).** Mapper curto sobre o `http_error_mapper.py` existente: 401 credenciais · 403 sem permissão · 404 não encontrada · `--query` sem resultados → dica útil · rede caída; `exit 1`, sem stacktrace, seguindo padrão git/npm.

**D8 — Swagger-fonte única para o shape de saída.** Campos mínimos das grades 100% respaldados pelo mapa de fontes da feature (§4) — nada exibido sem payload real ter comprovado a chave (regra C2).

## Risks / Trade-offs

- [Baixar dataset completo (107+ APIs) por chamada] → aceito e mitigável adiante com `filter=BASIC_INFO` (backlog §6); volume atual comprovado desprezível (~107 itens).
- [Extract do legacy pode quebrar scripts/CI que chamavam `python main.py` pelado] → pipeline `pipeline.yaml`/`bitbucket-pipelines.yml` auditado no passo; entrada antiga mantém mensagem de migração apontando para o script novo.
- [Catálogo de stages invalidado entre sessões] → cache vive só em memória da execução (sem staleness cross-run); nome do stage é cosmético, degrada para o id.
- [Composição lazy invisível ao gate] → `test_main_gate.py` estendido como guarda de regressão antes de qualquer refactor (lock-first).
- [Scope creep via `--revisions` no drill-down] → revisões entram nesta fatia porque a grade é canonizada (§3-3); completeness `suggestions[]` segue backlog.

## Migration Plan

1. Congelar comportamento com testes de gate e unitários da camada de aplicação (mocks na port) — antes de tocar `main.py`.
2. Extrair legacy para `scripts/generate_api_json.py`; rewire `main.py` (sem bare-flow); registrar `[tool.poetry.scripts]`.
3. Implementar port/service/adapter + CLI `sen list api` com grades e flags.
4. Smoke read-only real (E2: `sen list api` + drill-down API 400, somente GETs) — doc no changelog/CHANGELOG.
5. Rollback: branch isolada (`feat/command-sen-list`); nenhum contrato público existente muda (sem breaking).

## Open Questions

- Nenhuma bloqueante. Pendências de placa registradas na feature (D2 selado aqui implicitamente; E2 smoke aguarda token real da máquina no dia da integração).
