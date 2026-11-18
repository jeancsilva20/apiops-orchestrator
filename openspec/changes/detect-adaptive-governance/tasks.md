## 1. Sondas

- [x] 1.1 consulting (com AG), 10/11/2026: `GET /api-governance/api/v3/attributes` → 200; `config?keys=showMenuGovernance` → `"true"`
- [x] 1.2 Superbras (sem AG), 10/11/2026: `GET /api-governance/api/v3/attributes` → 403 "In order to use this resource you must have Governance module enabled."

## 2. Domínio

- [x] 2.1 `GovernanceAvailability` em `domain/models/governance_model.py`
- [x] 2.2 `GovernanceApiPort.availability()` em `domain/ports/governance_api_port.py`

## 3. Adapter

- [x] 3.1 `GovernanceApiAdapter`: regra da D2, `max_retries=0` no `HttpClient`, 3 tentativas, 2 s de intervalo, timeout de 10 s, resultado guardado na instância
- [x] 3.2 Testes: 200; 403 com a mensagem; 403 sem ela, sem retentativa; 5xx e depois 200; três falhas (rede, 5xx, 404) viram `UNKNOWN`; número de chamadas; segunda pergunta sem nova chamada

## 4. Montagem

- [x] 4.1 `main.py`: `_build_platform_adapters` monta os dois adapters com o mesmo token, nas factories de `list`, `completeness`, `validate`, `publish` e `deploy`

## 5. Comandos

- [x] 5.1 `GovernancePrecheckService`: recebe a porta; `PrecheckResult.available`; resultado neutro com `DISABLED`
- [x] 5.2 `revision_payload.assemble(include_api_tags=...)`; `validate` e `publish` perguntam antes de montar o payload; o log fica no pré-check (`api_tags_ignored=N`)
- [x] 5.3 `validate`: sem E4 com `DISABLED`; governança e completeness vazias
- [x] 5.4 `deploy`: gates não disparam com o pré-check neutro (só testado, sem mudança de regra)
- [x] 5.5 `ApiListingService.api_revisions`: sem stages e sem completeness com `DISABLED`; `governance_available()` para a borda, que tira STAGE, COMPLETE e a nota
- [x] 5.6 `CompletenessService`: `CompletenessGovernanceUnavailable` (`exit 3`) antes de qualquer leitura

## 6. Testes

- [x] 6.1 Cada serviço com `ENABLED`, `DISABLED` e `UNKNOWN` (`UNKNOWN` igual a hoje)
- [x] 6.2 `validate` e `publish` sem AG: `PUT` sem as `apiTags` do repositório, sem erro de `apiTags` mesmo com tag inválida, JSON com os campos do AG vazios
- [x] 6.3 `--revisions` sem AG: texto sem STAGE e COMPLETE; JSON com `null`; `completeness` com `exit 3` na borda
- [x] 6.4 Suíte de unidade (10/11/2026): 10 falhas, as mesmas da linha de base; 1162 passam (eram 1133)
- [x] 6.6 Varredura depois do teste no ECAD com 403 simulado (11/11/2026): sem AG, a confirmação do `validate` não mostra os avisos da nota de completeness, o progresso não narra a governança, e o `--revisions` troca o rótulo de espera
- [x] 6.5 Revisão contra o `padroes-desenvolvimento.md` (11/11/2026): `GovernanceAvailability(str, Enum)` com a propriedade `absent` usada pelos três serviços; `_get_headers()` no adapter do AG; suíte com 1166 passando e as mesmas 10 falhas

## 7. Verificação real

- [x] 7.1 consulting, só leitura (10/11/2026): `sen list api --id 425 --revisions` com STAGE e COMPLETE; `sen completeness --id 425 --revision 9769` com 87,5%
- [x] 7.2 consulting, API-lab 425, com o `HttpClient` embrulhado: todo `/api-governance/` devolve o 403 medido e toda escrita na plataforma é recusada antes da rede (10/11/2026):
  - `--revisions`: só REV #, REV ID e ENVS; duas chamadas (catálogo e o 403); JSON com `stage_name` `null`
  - `completeness`: `exit 3` com a mensagem, uma chamada (o 403)
  - `validate` na revisão 13 (a 425 não tem mais a revisão 1), repositório materializado com `apiTags` inválidas e a confirmação respondendo "não": chegou à confirmação sem erro de `apiTags`, governança e completeness vazias, nenhuma chamada além do 403 ao AG
  - o mesmo `validate` com o AG real: uma só chamada ao `/attributes` (detecção e catálogo) e `InvalidApiTagsError`, como hoje
- [x] 7.4 Bateria depois da varredura (11/11/2026), consulting, 425 revisão 13, mesmo embrulho da 7.2: `list api` (catálogo, `--id`, `--revisions` texto e JSON), `completeness` texto e JSON (`exit 3`), `validate` texto e JSON até a confirmação, `diag draft|structure|template`, `publish` local e na esteira e `deploy` na esteira até a escrita (recusada pelo embrulho). Sem AG: uma chamada ao AG por comando, nenhuma ao completeness, nenhum texto de governança ou completeness; o `diag draft` mostra workflow e stage porque a revisão do consulting os tem (decisão do responsável: fica assim, a linha descreve o dado reenviado no PUT, não o AG). Com AG, `--revisions` e `validate` iguais a antes
- [ ] 7.3 (opcional, pelo responsável) um tenant sem AG, se o `sen login` funcionar lá

## 8. Docs

- [x] 8.1 Deltas de `sen-validate`, `sen-list`, `sen-completeness` e `sen-deploy`
- [x] 8.2 Spec do `sen-publish` no change `add-sen-publish`: pré-condição e cenário sem AG
- [x] 8.3 `docs/comandos-cli.md`: decisão transversal, `exit 3` do `completeness`, colunas do `--revisions` e gates do `deploy`
- [x] 8.4 O `sen schema` e as skills (`feat/skills`) não citam os exit codes do `completeness`; a `sen-explore` já trata `stage_name` e `completeness_score` nulos

## 9. Chamadas ao AG no adapter novo (fase final)

- [x] 9.1 Tradução 4xx/5xx do `_request` para `adapters/outbound/http/common/platform_request.py`, usada pelos dois adapters
- [x] 9.2 `get_workflow`, `get_workflow_stages` (com cache e degradação) e `list_attributes` para a `GovernanceApiPort` e o `GovernanceApiAdapter`, com os mesmos sinais de erro
- [x] 9.2.1 `WorkflowStage` para `domain/models/governance_model.py`; `workflow_stage_model.py` apagado e imports ajustados
- [x] 9.3 `availability()` e `list_attributes()` usando a mesma resposta do `GET /attributes`
- [x] 9.4 `GovernancePrecheckService` só com a `GovernanceApiPort`; `ApiListingService` com as duas portas; três métodos removidos da `ManagerApiPort`
- [x] 9.5 Testes de stages movidos para `test_governance_api_adapter.py`; fakes dos serviços respondem pelas duas portas; baterias de integração montam o adapter do AG
- [x] 9.6 7.1 e 7.2 rodados já com a fase final
- [x] 9.7 (18/11) `sen sync` com a `GovernanceApiPort`: sem AG, carga sem `apiTags` e `--check` sem comparar o campo (detalhe em `add-sen-sync`, D17)
