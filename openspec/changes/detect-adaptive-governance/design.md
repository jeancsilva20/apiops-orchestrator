## Design

### Contexto

As chamadas ao AG estão hoje na `ManagerApiPort`:

- `get_workflow`, `get_workflow_stages` e `list_attributes`, sob `/api-governance/api/v3/`;
- `get_revision_completeness`, sob `/api-manager/api/v3/`. Essa rota é do Manager, mas só responde com o AG ativo: sem AG devolve 403 (medido pelo report-unificado na Supergasbras).

Quem chama essas funções:

- o `GovernancePrecheckService`, usado por `validate`, `publish` e `deploy`;
- o `ApiListingService`, para os nomes de stage e o completeness do `--revisions`;
- o `CompletenessService`;
- a E4 do `validate`;
- o gate de completeness do `deploy`.

Nenhum desses pontos sabe se o tenant tem AG. A E4 e o `--revisions` engolem a falha; o pré-check deixa o 403 subir e o comando quebra.

### Decisões

**D1 — O domínio faz a pergunta e o adapter responde.**

| Peça | Onde |
|---|---|
| `GovernanceAvailability` (`ENABLED`, `DISABLED`, `UNKNOWN`) | `domain/models/governance_model.py` |
| `GovernanceApiPort.availability() -> GovernanceAvailability` | `domain/ports/governance_api_port.py` |
| `GovernanceApiAdapter` | `adapters/outbound/http/governance_api/governance_api_adapter.py` |

A chamada HTTP e a leitura do 403 ficam só no adapter. Se a plataforma mudar o sinal, ou criar um endpoint próprio, só o adapter muda. A porta é separada da `ManagerApiPort` por dois motivos: o padrão do projeto é um pacote por API externa (`padroes-desenvolvimento.md`), e o ADR 0008 já recusou engordar a `ManagerApiPort` com endpoints do AG.

**D2 — Regra de detecção.**

`GET /api-governance/api/v3/attributes`, sem parâmetros de paginação. A sonda de 05/11 mostrou que o endpoint ignora `page`, `size` e `limit` e devolve o catálogo inteiro.

| Resposta | Resultado | Retentativa |
|---|---|---|
| 200 | `ENABLED` | — |
| 403 com "governance module" no `message` (sem diferença de maiúsculas) | `DISABLED` | não |
| 403 sem essa mensagem | `UNKNOWN` | não |
| outro 4xx, 5xx, rede, timeout | `UNKNOWN` se persistir | até 2 |

- Um 403 de permissão não pode ser lido como cliente sem AG. Por isso a mensagem é conferida.
- O 403 é determinístico, então não tem retentativa. Os outros erros têm, a pedido do responsável.
- O `HttpClient` é chamado com `max_retries=0`. Assim a contagem é só do adapter (3 tentativas no máximo), sem somar às 3 retentativas de 5xx do `HttpClient`.
- O intervalo entre tentativas é de 2 s, e cada tentativa tem timeout de 10 s. O pior caso fica em cerca de 34 s, contra cerca de 94 s com o timeout padrão de 30 s.
- O resultado fica guardado na instância do adapter: uma detecção por execução.
- Log em INFO: `governance.availability result=... attempts=... reason=...`. Nunca em WARNING ou acima, para não vazar no stderr pelo `logging.lastResort`.

**D3 — `UNKNOWN` age como hoje.** O `sen` assume que o AG está ativo e deixa o erro real aparecer na chamada seguinte. Pular a governança por causa de uma falha de rede seria pior do que quebrar. A regra fica no domínio: `GovernanceAvailability.absent` só é verdadeira para `DISABLED`, e os serviços (pré-check, listagem e completeness) usam essa propriedade, sem comparar valores do enum.

**D4 — Quem pergunta e quando.** O composition root monta o `GovernanceApiAdapter` com o mesmo token do `ManagerApiAdapter` (um `_build_admin_token` por factory) para `list`, `completeness`, `validate`, `publish` e `deploy`. A pergunta é feita quando o comando chega ao primeiro ponto que depende do AG:

| Comando | Momento da pergunta |
|---|---|
| `validate`, `publish` | antes de montar o payload, porque as `apiTags` dependem da resposta (D6) |
| `deploy` | na avaliação da governança |
| `list api --id X --revisions` | antes de ler os stages e o completeness |
| `completeness` | antes de ler a revisão |
| `list api` sem `--revisions`, `login`, `whoami`, `diag`, `schema` | não perguntam |

**D5 — Pré-check neutro.**

- `GovernancePrecheckService` passa a receber a `GovernanceApiPort`.
- Com `DISABLED`, `evaluate` devolve `PrecheckResult(workflow_id=None, stage_id=None, available=False)`: sem requisitos, sem faltantes, sem avisos, sem problemas de `apiTags` e sem stage.
- O campo novo `available` (padrão `True`) é o que os serviços leem.
- O `deploy` não precisa de regra própria. Sem stage, não há `deployableEnvironments` nem `completenessRequisite`, e os gates não disparam.

**D6 — `apiTags` ignoradas sem AG.**

- `revision_payload.assemble` ganha `include_api_tags` (padrão `True`).
- Com `False`, as `apiTags` do repositório não vão no `PUT`.
- A conferência pós-gravação já pula as `apiTags` quando elas não foram enviadas (`if "apiTags" not in sent_api`).
- Nenhuma mensagem ao usuário, por decisão do responsável. Fica só o log INFO do pré-check, `governanca.precheck.skipped reason=governance_disabled api_tags_ignored=N`.

**D7 — Saídas: campos do AG vazios, sem trocar a versão do contrato.**

| Comando | JSON sem AG | Texto sem AG |
|---|---|---|
| `validate` | `governance`: `workflowId`/`stageId` `null`, `required`/`missing` `[]`, `blocked: false`; `completeness`: `score`/`gatePercent` `null`, `suggestions: []` | sem o bloco de governança e sem o quality score (a borda já esconde os dois quando `stage_id` e `score` são `None`) |
| `publish` | `governance` vazio como no `validate` | sem o bloco de governança (já é assim com `stage_id` `None`) |
| `deploy` | `governance` com `null` e `[]`, `violations: []` | sem o bloco de governança (já é assim com `stage_id` `None`) |
| `list api --id X --revisions` | `stage_name` e `completeness_score` `null` | sem as colunas STAGE e COMPLETE e sem a nota "N revisões sem completeness" |

Hoje, num cliente sem AG, a coluna STAGE imprime "None": `str(None)`, porque não há nome de stage nem `workflowId` para usar no lugar. Ela some junto com a COMPLETE porque o stage também é do AG.

Também somem sem AG (achados no teste do responsável no ECAD, 11/11/2026):

- da confirmação do `validate`, os avisos do contrato que falam da nota de completeness ("descrições com menos caracteres que o mínimo" e "schemas sem `properties`"). São os únicos avisos que o `ContractWriter.validate` devolve; o `publish` já não os mostrava;
- do progresso, "Verificando a governança" (`validate`, `publish`, `deploy`), e no `--revisions` o rótulo passa a ser "Consultando as revisões..." em vez de "Consultando completeness das revisões...".

**D8 — `sen completeness` sem AG.**

- Com `DISABLED`, o comando não chama o completeness e sai com `exit 3`.
- Mensagem: "A checagem de completude não está disponível: cliente não possui o Adaptive Governance contratado."
- Exceção nova: `CompletenessGovernanceUnavailable` (`exit_code = 3`).
- A pergunta vem antes da conferência de identidade da API. A disponibilidade do AG vale para o tenant inteiro e não revela nada de uma API.
- Com `UNKNOWN`, o fluxo é o de hoje.

**D9 (fase final) — As chamadas ao AG vão para o adapter novo.**

- `get_workflow`, `get_workflow_stages` (com o cache e a degradação para lista vazia) e `list_attributes` saem da `ManagerApiPort`/`ManagerApiAdapter` e vão para a `GovernanceApiPort`/`GovernanceApiAdapter`, junto com `GOVERNANCE_BASE_PATH`.
- Ficam no Manager:
  - `get_revision_completeness`, porque a rota é `/api-manager/...`;
  - a tradução do 412 em `ManagerApiGovernanceBlockedError`, porque o 412 vem do `PUT` da revisão no Manager.
- `WorkflowStage` sai de `domain/models/workflow_stage_model.py` e vai para `domain/models/governance_model.py`, junto com o método que o devolve; o arquivo antigo é apagado.
- Ficam onde estão:
  - `CatalogRevisionCompleteness`, porque é o que a `ManagerApiPort` devolve no `get_revision_completeness`;
  - `completeness_view.py`, que é a resposta do comando `sen completeness` e segue o padrão `*_view.py` de `validate_view` e `publish_view`, que se organizam por comando e não pela API de origem.
- Depois da fase, `GovernancePrecheckService` depende só da `GovernanceApiPort`, e `ApiListingService` recebe as duas portas.
- Ganho: `availability()` e `list_attributes()` usam a mesma resposta do `GET /attributes`, então `validate` e `publish` deixam de fazer uma chamada a mais.
- **Erros:** os métodos movidos levantam os mesmos sinais de hoje (`ManagerApiTransportRejectedError`, `ManagerApiTransportUnavailableError`). Assim os chamadores e o `classify_manager_failure` seguem iguais.
- **Tradução 4xx/5xx:** a tradução que está no `_request` do `ManagerApiAdapter` vai para `adapters/outbound/http/common/`, e os dois adapters passam a usá-la. Renomear os sinais para algo neutro fica fora.

### Fora do escopo

- **O 403 do completeness com `UNKNOWN`:** continua com a mensagem de revisão inexistente.
- **Skills:** voltar a falar de completude e governança quando o JSON trouxer os campos (D12 de 09/11). Fica para depois.
- **Login em cliente sem AG:** depende da Orchestrator Auth API publicada no tenant; é outro assunto.
- **Avisar o dev que as `apiTags` foram ignoradas.**

### Riscos

- **A plataforma muda o texto do 403.** A detecção vira `UNKNOWN` e o `sen` quebra como hoje. O teste do adapter fixa o texto medido, e a correção fica só no adapter.
- **AG instável.** As retentativas somam até ~34 s no pior caso antes de cair em `UNKNOWN`.
- **`apiTags` ignoradas em silêncio.** Quem declarar `apiTags` num cliente sem AG não é avisado. Decisão do responsável.
- **Cliente que contrata o AG depois.** Não é um risco: a detecção roda a cada execução e acompanha a mudança sozinha.
