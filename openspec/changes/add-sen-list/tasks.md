# Tasks: add-sen-list

## 1. Guardas de comportamento (lock-first, antes de tocar `main.py`)

- [x] 1.1 Estender `tests/unit/test_main_gate.py`: import de `main` não instancia `Settings`, não faz HTTP, não resolve caminho de disco; `sen --help` e `sen list api --help` respondem sem `.env` (subprocess) *(purity test ativo e verde; os subprocess-help ficam parkados com `@ETAPA3_SKIP` — exigem a Etapa 3 do ADR 0006, ativam na task 2.1)*
- [x] 1.2 Testes unitários das regras de listagem contra payload fixture (snapshot real das sondas): filtro `--query` accent-folded, ordenação `id` asc, janela pós-filtro, `--limit ≤ 0` → erro, offset além do total → vazio/`0` *(cobertos por `ApiCollection` + `test_api_collection_model.py`; + regra nova: `--offset < 0` → erro, simétrico ao limit)*

## 2. Composition root lazy (ADR 0006) + entry-point

- [x] 2.1 Mover `Settings()` para dentro dos builders; `main()` reduzido a dispatch puro; mensagem de degradação educativa (D1-b) quando builder sem chaves falha (`exit 1`, sem stacktrace, ponteiro para sub-help) *(helper único `_load_settings()` nos builders; bifurcação argv e fluxo bare PRESERVADOS — decisão; prova D1-a via snippet "BOOM" com Settings venenada antes do import, pois env zerada não é discriminante com dotenv absoluto)*
- [x] 2.2 Remover `repo_path` hardcoded e o fluxo `run_bare_pipeline` do `main.py` *(PARKED por decisão — `repo_path`/`run_bare_pipeline` permanecem; extração real vira o corpo da task 3/D3)*
- [x] 2.3 Adicionar `[tool.poetry.scripts] sen = "apiops_orchestrator.main:main"` (e declaração de `packages`) no `pyproject.toml` *(REMANEJADA para o change add-sen-entrypoint, onde o shim e seus smokes vivem)*

## 3. Extração do fluxo legado (D3)

- [ ] 3.1 Criar `scripts/generate_api_json.py` com `--repo`/`--revision` reproduzindo o comportamento antigo (validação de estrutura + schema + conversão `ApiFull`), fora do pacote
- [ ] 3.2 Auditar `pipeline.yaml`/`bitbucket-pipelines.yml` quanto a chamadas `python main.py` peladas e ajustar/checar

## 4. Domínio e aplicação (busca mora aqui)

- [x] 4.1 Consolidar port `ManagerApiPort` (`get_apis`, `get_api_by_id`, `list_catalog_apis`, revisões, completeness, stages) e fixtures de mock *(REWIRE FINDER: + `list_catalog_apis(limit, order_by, sort) -> ApiCatalogPage` (catálogo api-finder, header `count` = total do universo); adaptação por base path opcional no adapter; listagem migrada do manager cru para o finder — `/revisions/basic` fora do fluxo; contratos do drill-down entregues na task 5)*
- [x] 4.2 Implementar as regras na `ApiListingService` (filtro `name`+`description` case-insensitive/accent-folded → ordenar `id` asc → janelar), com pipeline explícito filtrar→ordenar→janelar *(entregue e provado pelos testes da task 1.2 + testes de visibilidade; ordenação `apiId asc` passou a ser também SERVER-side no finder, determinismo preservado; smoke E2E real: janelas sem overlap, offset-beyond-total vazio, query accent-fold ✓)*
- [x] 4.3 Util de normalização Unicode/accent-fold único e reutilizável *(+ teste direto `test_text_normalizer.py`: acentos, casefold (ß/İ), None, escalares, simetria payload×query)*

## 5. Adapter outbound (novas consultas, sem mudança de contrato)

- [x] 5.1 `ManagerApiAdapter`: métodos de revisões (`/apis/{id}/revisions`), completeness (`/revisions/{rid}/completeness`) e stages de workflow (`/api-governance/api/v3/workflows/{id}/stages`) *(SONDAS r1-r4 revogaram o desenho original: drill-down fonte única = `GET /apis/{id}` (revisions[]+lastRevision+environments já vivem lá); adapter entrega completeness (degradação `{}`) + stages (base path governance) + CATÁLOGO api-finder (`list_catalog_apis`, header `count`); `/revisions/{rid}` foi contratado e PODADO no mesmo commit; `/revisions/basic` ficou fora da listagem nova — enrich morto com o finder)*
- [x] 5.2 Cache de catálogo de stages por sessão (1 chamada por workflow distinto); degradação para id quando não resolvível *(cache de instância = por execução/processo; falha nunca cacheia; `[]` → CLI mostra id do workflow; 3 testes provando HIT/MISS/fail-through/isolamento entre instâncias)*
- [x] 5.3 Mapear erros RFC7807 → famílias humanas (401/403/404/rede) reutilizando `http_error_mapper.py`, corpo suprimido *(supressão de corpo já vigente no HttpClient/existing mapper; o CATÁLOGO E1 de mensagens materializa na CLI — task 6.3, onde reside a última milha da tradução)*

## 6. CLI (`sen list api`)

- [x] 6.1 Flags: `--query` (exclusiva com `--id`, validação pré-rede), `--limit`, `--offset`, `--id`, `--revisions`/`-r` *(-r exige --id: erro pré-rede; offsets negativos rejeitados — guarda da task 1)*
- [x] 6.2 Grades canônicas do §3 em `output_display.py`: listagem, 1-linha de drill-down, revisões; rodapé de janela efetiva com default anunciado no caso desnudo *(REWIRE FINDER: fonte única das grades = catálogo; grade de revisões 5 colunas (REV ID · REV # · STAGE · ENVS · COMPLETE) — opção A, células CREATED/LAST DEPLOY descartadas por ausência no frame; `_render_grade` parametrizável por header; smoke real rc 0 nas duas faces)*
- [ ] 6.3 Mensagens de erro E1 (401 credenciais · 403 permissão · 404 não encontrada · query vazia → dica · rede caída), todos `exit 1` *(ervas: 404 fundido educativo já live no drill-down; 401/403/rede seguem com catch genérico da CLI — catálogo humano pendente, exige infra de `HttpCallError` resgatada da leva descartada)*

## 7. Qualidade e fechamento

- [ ] 7.1 Suíte unitária verde (166+ atuais + novos), lint/typecheck (`ruff`, `mypy`) limpos
- [ ] 7.2 Smoke read-only manual (E2): `sen list api` + drill-down API 400, somente GETs, com HOST default do projeto — registrar no CHANGELOG
- [ ] 7.3 Backlog atualizado (`docs/feat-command-sen-list/backlog/`) com o que restou fora da fatia e nota de implementação em `docs/feat-command-sen-list/`
