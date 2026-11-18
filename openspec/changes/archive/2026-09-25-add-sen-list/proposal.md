# Proposal: add-sen-list

## Why

A CLI `sen` do apiops-orchestrator ainda não expõe comando de listagem: o desenvolvedor e a esteira não conseguem consultar quais APIs estão disponíveis a eles via interface de linha de comando (hoje a única alternativa é inspecionar o API Manager manualmente ou rodar scripts avulsos). Esta é a fatia sequenciada após o `sen login` (branch `feat/command-sen-list`), cujas decisões estão seladas em `docs/feat-command-sen-list/features/sen-list.md` (grill 15/09 + 5 votos do Paulo em 16/09). Além disso, o composition root atual (`main.py`) ainda impede o uso da CLI como executável distribuído: `Settings()` é instanciado antecipadamente em *toda* invocação, exigindo `.env` completo até para `sen --help`, e o pacote não registra o entry-point `sen`.

## What Changes

- **Composition root lazy (ADR 0006)**: construção de `Settings()` e demais dependências migra para builders invocados sob demanda — metadados da CLI (`sen`, `sen --help`, `sen list --help`) respondem instantaneamente com ou sem `.env` (D1-a). O fluxo bare (`python main.py` pelado) **permanece inalterado** — sua extração é o D3, pendência de placa fora desta leva.
- **Degradacão educativa (D1-b)**: comando que exige rede, executado sem chaves, produz erro curto orientando como resolver (ponteiro para o sub-help) e `exit 1` — sem stacktrace.
- **Entry-point registrado**: `[tool.poetry.scripts] sen = "apiops_orchestrator.main:main"` — `sen` vira executável próprio, pré-requisito para o exe distribuído ao dev e para a esteira.
- **Comando `sen list api`** (substantivo no singular, escola gh): listagem com conjunto completo por padrão, `--limit`/`--offset` sempre explícitos (desnudo executa `--limit 10 --offset 0` com rodapé de default anunciado), ordenação client-side por `id` asc, busca `--query` client-side (name+description, case-insensitive + accent-folded, exclusiva com `--id`), drill-down `--id <api_id>` com `--revisions` (`-r`).
- **Erros RFC7807 → humano (E1)**: mapa de mensagens curtas (401 credenciais · 403 sem permissão · 404 não encontrada · `--query` vazio → dica · rede caída), todos com `exit 1` e sem stacktrace.
- **Segurança da sessão afetada**: nenhuma credencial/token é ecoada em saídas (herda padrão ADR 0005 / requirement "Logs e saídas no padrão existente, sem segredos").
- Integração com o token da sessão do `sen login` (gate de escopo `list→read`, ADR 0003) fica **fora** desta fatia — o ponto de injeção de token (`ManagerApiAdapter(token=...)`) é o seam de troca futura.

## Capabilities

### New Capabilities
- `sen-list`: contrato do comando `sen list` (listagem, busca client-side, janelamento explícito, drill-down de revisões, tratamento de erros) e dos requisitos estruturais de composição lazy da CLI (help sem `.env`, degradação educativa, entry-point `sen`).

### Modified Capabilities

## Impact

- `src/apiops_orchestrator/main.py` — composition root lazy: `Settings()` migram para builders; fluxo bare (`run_bare_pipeline`) preservado sem alteração de comportamento.
- `src/apiops_orchestrator/adapters/inbound/cli/cli_adapter.py` — comando `sen list api` com novas flags (`--query`, `--limit`, `--offset`, `--revisions`).
- `src/apiops_orchestrator/application/services/api_listing_service.py` — ganha as regras de negócio (filtro/ordenação/janela) sobre dados vindos da `ManagerApiPort`.
- `src/apiops_orchestrator/adapters/outbound/http/manager_api/manager_api_adapter.py` — sem mudança de contrato (`token` permanece injetado; a fonte futura é a sessão do login).
- `pyproject.toml` — entrada `[tool.poetry.scripts]`.
- `tests/unit/test_main_gate.py` — estendido para proteger o gate lazy (help sem `.env`, degradação sem chaves).
- Endpoints consumidos (somente GET): `GET /api-manager/api/v3/apis`, `GET /api-manager/api/v3/apis/{id}`, `GET /api-manager/api/v3/apis/{id}/revisions`, `GET /api-manager/api/v3/revisions/{rid}/completeness`, `GET /api-governance/api/v3/workflows/{id}/stages`.

**Fora desta leva (registrados no backlog):** extração do fluxo legacy para `scripts/generate_api_json.py` (D3, pendência de placa); gate de escopo `list→read` (ADR 0003, fase 2); troca da fonte do token para `.sen_session` (dia da integração do login).
