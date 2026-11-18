## Why

O `sen` quebra em cliente que não contratou o Adaptive Governance (AG). Pontos que dependem do AG hoje:

- pré-check de `validate`, `publish` e `deploy`: catálogo de atributos, workflow e stage;
- gates do `deploy`: ambientes permitidos e completeness mínima do stage;
- completeness: `sen completeness`, a E4 do `validate`, a coluna COMPLETE do `sen list api --id X --revisions` e o gate do `deploy`;
- nome do stage na coluna STAGE do `--revisions`;
- `apiTags` no `api-basic-info.yaml` gerado pelo `sen sync` e comparado pelo `--check` (incluído em 18/11, depois da mesclagem com `add-sen-sync`).

O responsável recusou uma variável de configuração (tipo `GOVERNANCE_ENABLED`): o `sen` vai direto ao usuário final, que não deve ter de saber o que contratou. A detecção precisa ser automática.

Sondas somente leitura com o admin token do `sen`:

| Tenant | Chamada | Resposta |
|---|---|---|
| consulting (com AG), 10/11/2026 | `GET /api-governance/api/v3/attributes` | 200, catálogo |
| Superbras (sem AG), 10/11/2026 | `GET /api-governance/api/v3/attributes` | 403 `{"result":"failure","message":"In order to use this resource you must have Governance module enabled."}` |
| consulting, 10/11/2026 | `GET /api-manager/api/v3/config?keys=showMenuGovernance` | 200 `[{"id":"showMenuGovernance","value":"true",...}]` |

O 403 do `/attributes` traz uma mensagem própria para o módulo ausente, e por isso é o sinal escolhido. Já no `/config`, uma chave não cadastrada simplesmente não vem na resposta (`cliEnabled` não veio no consulting), e a ausência fica ambígua.

## What Changes

- **Porta e adapter próprios para o AG.** `GovernanceApiPort` no domínio, `GovernanceApiAdapter` em `adapters/outbound/http/governance_api/`. O domínio define a pergunta ("este Manager tem AG?") e o tipo da resposta. Só o adapter sabe como descobrir: trocar o sinal no futuro mexe só nele.
- **Três respostas.** O AG está ativo, não foi contratado, ou não deu para saber. Um erro que não seja 403 tem 2 retentativas. Se ainda assim não der para saber, o `sen` age como hoje.
- **Sem AG, nada trava e o que é do AG some:**
  - o pré-check devolve resultado neutro: sem requisitos, sem gates do `deploy` e sem o aviso "o Adaptive Governance não pode ser antecipado";
  - as `apiTags` do repositório são ignoradas: não são conferidas, não vão no `PUT` e não entram na conferência pós-gravação;
  - o completeness não é consultado;
  - no JSON, os campos do AG saem vazios (`null` e `[]`), sem mudar a versão dos contratos;
  - no texto, os blocos de governança e de quality score não aparecem, e o `--revisions` perde as colunas STAGE e COMPLETE.
- **`sen completeness` sem AG** sai com `exit 3` e a mensagem "A checagem de completude não está disponível: cliente não possui o Adaptive Governance contratado.".
- **Por último, mudança das chamadas ao AG para o adapter novo.** `get_workflow`, `get_workflow_stages` e `list_attributes` saem da `ManagerApiPort` e vão para a `GovernanceApiPort`. A detecção e o catálogo de atributos passam a usar a mesma chamada.

## Capabilities

### Modified Capabilities

- `sen-validate`: cliente sem AG não trava; `apiTags` ignoradas; governança e completeness vazias.
- `sen-list`: o `--revisions` sem AG não mostra STAGE nem COMPLETE.
- `sen-completeness`: `exit 3` para cliente sem AG.
- `sen-deploy`: sem AG, os gates do stage não se aplicam.
- `sen-publish` (spec ainda no change `add-sen-publish`): mesmas regras do `validate` para `apiTags` e governança.

## Impact

- **Código novo**:
  - `domain/models/governance_model.py`;
  - `domain/ports/governance_api_port.py`;
  - `adapters/outbound/http/governance_api/governance_api_adapter.py`.
- **Código alterado**:
  - `main.py`;
  - `governance_precheck_service.py`;
  - `validate_service.py`, `publish_service.py` e `deploy_service.py`;
  - `api_listing_service.py` e `completeness_service.py`;
  - `revision_payload.py` (envio das `apiTags`);
  - `completeness_exceptions.py`;
  - `cli_adapter.py` (colunas do `--revisions`).
- **Fase final**: `manager_api_port.py` e `manager_api_adapter.py` perdem os três métodos do AG.
- **Custo**: até a fase final, uma chamada a mais por execução dos comandos que tocam o AG. Depois dela, `validate` e `publish` usam a mesma chamada para a detecção e para o catálogo.
- **Contratos JSON**: mesma forma e mesma versão; num cliente sem AG, os campos do AG chegam vazios.
