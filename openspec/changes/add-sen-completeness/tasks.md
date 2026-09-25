# Tasks — add-sen-completeness

## 1. Domínio

- [ ] 1.1 Estender `domain/ports/manager_api_port.py` com assinatura `get_revision_completeness(revision_id: int) -> CompletionReading` (tipado de domínio — o dict cru do wire morre no adapter; sem port dedicada, ver D4)
- [x] 1.2 Reescrever `domain/models/completeness_model.py` para a árvore v1 rebalanceada (`api`, `revision{managerId}`, `maturity{score}`, `gate{percent}` (sem marcador de source — decisão 25/09), `suggestions[]{index,text}`, `satellite{source,status,context,note}`), sem campos-fantasma do AG; constante `COMPLETENESS_SCHEMA_V1` preservada — [implementado] context/owner moram no nó satellite (alimenta headline TEXT; JSON sem contexto = posse perdida)
- [ ] 1.3 `CompletenessError(message, exit_code=2)` única (seguindo padrão `CliError` do CLI; msgs PT-BR por status: `404`→orientar `sen list api`, `401`→orientar `sen login`) definida junto ao service — sem módulo de exceptions dedicado
- [ ] 1.4 Unit tests de model: `maturity{score}` puro (sem classification); sugestões indexadas em ordem de chegada

## 2. Infraestrutura (adapter Manager)

- [ ] 2.1 Implementar `ManagerApiAdapter.get_revision_completeness(revision_id) -> CompletionReading`: chama `GET /api-manager/api/v3/revisions/{id}/completeness` reusando `_request` (retries 5xx, timeout, RFC 7807), converte `completenessScore`/`suggestions` para o tipado de domínio AQUI (dict cru não atravessa a borda — D4)
- [ ] 2.2 Fixture unit: payload real anonimizado de `CompletenessBean` (`completenessScore`, `suggestions[]`) em `tests/fixtures/`; mocks da port feitos à mão (padrões §10)
- [ ] 2.3 Unit tests do adapter: sucesso 200; 401/403/404/422/5xx-esgotado propagam o RFC 7807 que o service traduz para `CompletenessError(msg, exit_code)`

## 3. Application

- [ ] 3.1 Criar `application/services/completeness_service.py`: recebe `--api-id`/`--revision`, chama Manager via port e satélite `ManagerApiPort.list_api_detail` (degradável, soft-fail), monta `CompletionReport` do modelo v1
- [ ] 3.2 Unit tests do service: satélite caído ⇒ `exit 0` com IDs crus; revisão histórica consultável (nenhuma recusa sintética); nenhuma chamada ao AG/Connect Catalog (double da port garante)

## 4. CLI e apresentação

- [ ] 4.1 Registrar comando top-level `sen completeness` com `--api-id`, `--revision`, `--score-only`, `-o text|json|yaml` (default `text`), `-v`; validação pré-rede (`exit 1`) sem HTTP quando faltar `--api-id`/`--revision`, mensagem orientando `sen list api --id X --revisions`
- [ ] 4.2 Renderer TEXT: headline (nome/versão/API/revision/contexto), barra de 30 glifos com gate 70% + `✖ −X.X pts` abaixo do gate, lista numerada de suggestions com word-wrap integral (sem Sev/Impact/Where, sem classificação/paleta)
- [ ] 4.3 Renderer `--score-only`: headline + barra/gate apenas
- [ ] 4.4 Serializadores JSON/YAML da árvore v1 (YAML = mesma árvore; nunca dump cru do wire)
- [ ] 4.5 Matriz de erros G1 no CLI layer: `exit 1` pré-rede; `exit 2` para 401/403/404/409/422/5xx-esgotado com mensagens PT-BR (`404` orienta `sen list api --id X --revisions`; `401` orienta `sen login`); `exit 0` p/ satélite caído; sem stacktrace; nenhum token na saída
- [ ] 4.6 Unit tests de apresentação: mensagens de UX literais, exit codes como contrato, uso `-v` só altera verbosidade

## 5. Validação e docs

- [ ] 5.1 Rodar suite completa (`pytest`, `ruff`, `mypy`) verde
- [ ] 5.2 Smoke read-only em produção contra revisão histórica + vigente (somente GETs: manager-completeness + api-finder satélite), fixtures atualizadas com shapes reais
- [ ] 5.3 Nota de supersedência parcial no ADR 0008 (fonte primária AG → Manager) + anotação em `docs/feat-command-sen-completeness/problemas.md` (regra "revisão antiga → exit 2" revogada pelo comando; histórico AG segue pendência P-f)
- [ ] 5.4 Segundo agente revisor valida a change (regra de processo do projeto) antes do `openspec archive`
