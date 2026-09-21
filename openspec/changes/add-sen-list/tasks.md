# Tasks: add-sen-list

## 1. Guardas de comportamento (lock-first, antes de tocar `main.py`)

- [ ] 1.1 Estender `tests/unit/test_main_gate.py`: import de `main` não instancia `Settings`, não faz HTTP, não resolve caminho de disco; `sen --help` e `sen list api --help` respondem sem `.env` (subprocess)
- [ ] 1.2 Testes unitários das regras de listagem contra payload fixture (snapshot real das sondas): filtro `--query` accent-folded, ordenação `id` asc, janela pós-filtro, `--limit ≤ 0` → erro, offset além do total → vazio/`0`

## 2. Composition root lazy (ADR 0006) + entry-point

- [ ] 2.1 Mover `Settings()` para dentro dos builders; `main()` reduzido a dispatch puro; mensagem de degradação educativa (D1-b) quando builder sem chaves falha (`exit 1`, sem stacktrace, ponteiro para sub-help)
- [ ] 2.2 Remover `repo_path` hardcoded e o fluxo `run_bare_pipeline` do `main.py`
- [ ] 2.3 Adicionar `[tool.poetry.scripts] sen = "apiops_orchestrator.main:main"` (e declaração de `packages`) no `pyproject.toml`

## 3. Extração do fluxo legado (D3)

- [ ] 3.1 Criar `scripts/generate_api_json.py` com `--repo`/`--revision` reproduzindo o comportamento antigo (validação de estrutura + schema + conversão `ApiFull`), fora do pacote
- [ ] 3.2 Auditar `pipeline.yaml`/`bitbucket-pipelines.yml` quanto a chamadas `python main.py` peladas e ajustar/checar

## 4. Domínio e aplicação (busca mora aqui)

- [ ] 4.1 Consolidar port `ManagerApiPort` (`get_apis`, `get_api_by_id`, revisões, completeness, stages) e fixtures de mock
- [ ] 4.2 Implementar as regras na `ApiListingService` (filtro `name`+`description` case-insensitive/accent-folded → ordenar `id` asc → janelar), com pipeline explícito filtrar→ordenar→janelar
- [ ] 4.3 Util de normalização Unicode/accent-fold único e reutilizável

## 5. Adapter outbound (novas consultas, sem mudança de contrato)

- [ ] 5.1 `ManagerApiAdapter`: métodos de revisões (`/apis/{id}/revisions`), completeness (`/revisions/{rid}/completeness`) e stages de workflow (`/api-governance/api/v3/workflows/{id}/stages`)
- [ ] 5.2 Cache de catálogo de stages por sessão (1 chamada por workflow distinto); degradação para id quando não resolvível
- [ ] 5.3 Mapear erros RFC7807 → famílias humanas (401/403/404/rede) reutilizando `http_error_mapper.py`, corpo suprimido

## 6. CLI (`sen list api`)

- [ ] 6.1 Flags: `--query` (exclusiva com `--id`, validação pré-rede), `--limit`, `--offset`, `--id`, `--revisions`/`-r`
- [ ] 6.2 Grades canônicas do §3 em `output_display.py`: listagem, 1-linha de drill-down, revisões; rodapé de janela efetiva com default anunciado no caso desnudo
- [ ] 6.3 Mensagens de erro E1 (401 credenciais · 403 permissão · 404 não encontrada · query vazia → dica · rede caída), todos `exit 1`

## 7. Qualidade e fechamento

- [ ] 7.1 Suíte unitária verde (166+ atuais + novos), lint/typecheck (`ruff`, `mypy`) limpos
- [ ] 7.2 Smoke read-only manual (E2): `sen list api` + drill-down API 400, somente GETs, com HOST default do projeto — registrar no CHANGELOG
- [ ] 7.3 Backlog atualizado (`docs/feat-command-sen-list/backlog/`) com o que restou fora da fatia e nota de implementação em `docs/feat-command-sen-list/`
