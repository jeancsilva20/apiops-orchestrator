# Tasks — add-sen-completeness

## 1. Domínio

- [x] 1.1 Co-localizar a completude em `catalog_revision_model.py` (D9): novo `CatalogRevisionCompleteness{score, suggestions[list[str]]}`; `CatalogRevision.completeness: Optional[...]` SUBSTITUI o flat `completenessScore`; port ganha assinatura `get_revision_completeness(revision_id: int) -> CatalogRevisionCompleteness` (tipado de domínio — o dict cru do wire morre no adapter; sem port dedicada, ver D4) — [28/09]
- [x] 1.2 Árvore v1 rebalanceada sem campos-fantasma (`api{managerId,name,version,context?}`, `revision{managerId}`, `maturity{score}`, `gate{percent}`, `suggestions[]{index,text}`); `apiops.sen-completeness/v1` preservada — [implementado; revisado 25/09; REVISÃO 28/09: com o pivot D9, o envelope `SenCompleteness`/`completeness_model.py` foi EXCLUÍDO — a leitura de domínio é `CatalogRevision.completeness` aninhado e a árvore v1 é projeção montada no service; teste órfão `test_completeness_model.py` removido]
- [x] 1.3 Criar `application/exceptions/completeness_exceptions.py` (PADRÃO da casa pós-padronização — peer de `listing_exceptions.py`): `CompletenessNotFound(revision_id)`, `CompletenessUnauthorized`, `CompletenessDenied`, `CompletenessPlatformError(detail)`; CLI mapeia para `exit 2` + mensagens PT-BR por status (`404`→orientar `sen list api --id X --revisions`; `401`→orientar `sen login`)
- [x] 1.4 Unit tests de model: nested `CatalogRevision.completeness` (teaser = score only; mirror = score + suggestions) e aposentadoria do flat `completenessScore` — [28/09; os testes de envelope do `completeness_model.py` precedentes foram absorvidos/removidos com o pivot D9]
- [x] 1.5 Delta MODIFIED de `api-catalog` ("Selado rules of the catalog revision") criado em `specs/api-catalog/spec.md` citando o objeto aninhado — [28/09]

## 2. Infraestrutura (adapter Manager)

- [x] 2.1 Implementar `ManagerApiAdapter.get_revision_completeness(revision_id) -> CatalogRevisionCompleteness`: chama `GET /api-manager/api/v3/revisions/{id}/completeness` reusando `_request` (retries 5xx, timeout, RFC 7807); parse no outbound no ESTILO da padronização (helpers `_wire_*` + tradutor dedicado `_translate_completeness`, à altura de `_translate_row`) — dict cru não atravessa a borda (D4) — [28/09; `CatalogRevisionCompleteness` desde o pivot D9, o antigo `CompletionReading` não chegou a existir]
- [x] 2.2 Fixture unit: payload real anonimizado de `CompletenessBean` (`completenessScore`, `suggestions[]`) em `tests/fixtures/completeness_bean_payload.json`; mocks da port feitos à mão (padrões §10) — [28/09]
- [x] 2.3 Unit tests do adapter: sucesso 200 com fixture; wire anômalo (sugestões None/brancas, score não-numérico → 0.0); 4xx → `ManagerApiTransportRejectedError` (port signal); 5xx esgotado → `ManagerApiTransportUnavailableError` — [28/09; o intermediate `CompletenessError(msg, exit_code)` foi revogado por D4.b — módulo dedicado tipado]

## 3. Application

- [x] 3.1 Criar `application/services/completeness_service.py`: recebe `--api-id`/`--revision`, chama a port (`get_revision_completeness`) e o lookup de identidade (`list_api_detail` do catálogo TIPADO — `ApiCatalogEntry`; degradável, soft-fail), responde com **`CompletenessView` tipado** (D9.b; dict do contrato só em `to_document()`; `contextType` StrEnum → str)
- [x] 3.2 Unit tests do service: lookup de identidade indisponível ⇒ saída crua com IDs e nulls no contrato; revisão histórica consultável (nenhuma recusa sintética); nenhuma chamada ao AG/Connect Catalog (double da port garante); tradução 404/401/403/409/unavailable → exceptions do módulo `completeness_exceptions.py`

## 4. CLI e apresentação

- [x] 4.1 Registrar comando top-level `sen completeness` com `--api-id`, `--revision`, `--score-only`, `-o text|json|yaml` (default `text`), `-v`; validação pré-rede (`exit 1`) sem HTTP quando faltar `--api-id`/`--revision`, mensagem orientando `sen list api --id X --revisions` — [guard ANTES da factory: nem Settings/token são instanciados]
- [x] 4.2 Renderer TEXT: headline (nome/versão/API/revision/contexto), barra de 30 glifos com gate 70% + `faltam X.X pts` abaixo do gate, lista numerada de suggestions com word-wrap integral (glifos ASCII-seguros; sem Sev/Impact/Where, sem classificação/paleta)
- [x] 4.3 Renderer `--score-only`: headline + barra/gate apenas
- [x] 4.4 Serializadores JSON/YAML da projeção v1 (via `display_output`; YAML = mesma árvore; nunca dump cru do wire)
- [x] 4.5 Matriz de erros G1 no CLI: `exit 1` pré-rede; exceptions de `completeness_exceptions.py` → `exit 2` com mensagens PT-BR (`404` orienta `sen list api --id X --revisions`; `401` orienta `sen login`); `exit 0` quando identidade indisponível; sem stacktrace; nenhum token na saída
- [x] 4.6 Unit tests de apresentação: mensagens de UX literais, exit codes como contrato, uso `-v` só altera verbosidade — [+ testes: factory inexistente ⇒ exit 1; score-only suprime sugestões; yaml sem credenciais]

## 5. Validação e docs

- [x] 5.1 Rodar suite completa (`pytest`, `ruff`, `mypy`) verde — [28/09: ruff 0 erros; mypy limpo em TODOS os arquivos desta fatia (27 erros mypy restantes são baseline pré-existente em 18 arquivos fora da fatia; 6 falhas pytest + 2 collection errors igualmente pré-existentes, comprovadas via stash)]
- [x] 5.2 Smoke read-only em produção contra revisão histórica + vigente (somente GETs: manager-completeness + api-finder satélite), fixtures atualizadas com shapes reais — [28/09: smoke REALIZADO pelo usuário; shapes confirmados; incluiu refinamento de exibição `(#N)` para API e revisão]
- [x] 5.3 Nota de supersedência parcial no ADR 0008 (fonte primária AG → Manager) + anotação em `docs/feat-command-sen-completeness/problemas.md` (regra "revisão antiga → exit 2" revogada pelo comando; histórico AG segue pendência P-f) — [28/09: callout no ADR 0008 + status; problemas.md com revogação da regra selada e P-f re-recortado]
- [x] 5.4 Segundo agente revisor valida a change (regra de processo do projeto) antes do `openspec archive` — [28/09: veredicto APPROVE_FOR_ARCHIVE; validação OpenSpec "valid";(api-catalog delta com 3 cenários originais + 1 complementar); fronteiras hexagonais, ausência de leak de credenciais e confinamento das falhas pré-existentes confirmados; advisories registrados para mudanças futuras (echo de exceção genérica no CLI; score anômalo → 0.0; baseline mypy)]
