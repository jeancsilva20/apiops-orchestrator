## 1. Configuração e port

- [x] 1.1 Adicionar `TARGET_ENVIRONMENT_ID: int | None = None` em `config/settings.py` e em `.env.example`
- [x] 1.2 Adicionar `deploy_revision(environment_id, revision_id) -> int` em `ManagerApiPort` e no `ManagerApiAdapter` (`POST /deployments`), com o envelope de erro da plataforma em `messages`
- [x] 1.3 Testes do adapter: 201 devolve o id; 400 e 404 viram `ManagerApiTransportRejectedError` com a `message`; 5xx vira `ManagerApiTransportUnavailableError`

## 2. Serviço e contrato

- [x] 2.0 `PrecheckResultado` passa a expor o stage encontrado pelo `GovernancePrecheckService` (design §6), com as suítes do `validate` e do `publish` passando sem alteração
- [x] 2.1 Criar `application/exceptions/deploy_exceptions.py` (`DeployError` exit 1, `DeployGovernanceBlockedError` exit 3, `DeployFalhouError` com o documento parcial)
- [x] 2.2 Criar `domain/models/deploy_model.py` com `to_document()` emitindo `apiops.sen-deploy/v1`
- [x] 2.3 Criar `application/services/deploy_service.py` com o fluxo do design §1, reusando a regra de `RevisionWriter.guarda_identidade` e o `GovernancePrecheckService`; a resolução da revisão é própria, para listar número e id na mensagem
- [x] 2.4 Gate do AG (design §6), sobre o stage exposto pelo pré-check: `deployableEnvironments` vazio sem restrição, completeness só com requisito > 0, atributos dos `apiTags` do Manager, todas as violações listadas
- [x] 2.5 Testes do serviço: modo local, variáveis ausentes, revisão 1, revisão inexistente, ambiente não ligado, identidade divergente, cada critério do gate e a combinação deles, stage ausente, revisão já no ar, 400/404/5xx no `POST`, conferência divergente, estado anterior nulo e preenchido, ausência de `PUT`/`POST /revisions` e de `GET /environments/{id}`

## 3. Borda

- [x] 3.1 Adicionar `sen deploy` em `cli_adapter.py`, com renderização de texto e `json`/`yaml` da mesma árvore
- [x] 3.2 Registrar `build_deploy_service_factory()` em `main.py`
- [x] 3.3 Testes da CLI: flags, factory ausente, exit 0/1/3, documento com `FAILED` na recusa do `POST`, saída JSON sem progresso

## 4. Documentação

- [x] 4.1 `docs/comandos-cli.md`: `sen deploy`, variáveis e exit codes
- [ ] 4.2 Registrar no memory bank a pendência de rollback (techspec, pergunta sobre publish adicional) com as evidências da sondagem — depende de acesso de escrita ao repositório do memory bank

## 5. Verificação

- [x] 5.1 Suíte unitária sem regressão em relação à linha de base — 778 passam; as mesmas 7 falhas e 2 erros de coleta preexistentes
- [x] 5.2 Sondagem do endpoint contra a API 417 — 2026-10-19, estado restaurado ([sondagem](../../../docs/feat-command-sen-deploy/sondagem-deployments-2026-10-19.md))
- [x] 5.3 Smoke do comando contra a API 417 — 2026-10-19: deploy da revisão 3 no ambiente 7 conferido (deploys 272 e 273, em JSON e texto); recusas reais de ambiente não ligado (9), revisão inexistente (4), modo local e Draft, todas com exit 1 e sem escrita
- [x] 5.3.1 Bateria `tests/integration/test_bateria_deploy_417.py` (exige `APIOPS_BATERIA_417=1`): redeploy conferido, recusas sem criar registro e estado final igual ao inicial — 4/4 em 2026-10-19
- [ ] 5.4 Prova de ponta a ponta: `sen publish` com mudança observável, seguido de `sen deploy` e chamada ao gateway, para provar que o novo deploy serve o conteúdo novo
