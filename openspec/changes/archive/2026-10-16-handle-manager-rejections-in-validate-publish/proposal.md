## Why

Depois de `paginate-sen-list-and-standardize-manager-errors` (16/10/2026), dois caminhos ainda escondiam o motivo real de uma falha do Manager:

- O fallback de erro inesperado da CLI tratava como "erro interno" qualquer sinal do Manager que nenhum caso de uso traduziu. Um 401 numa chamada não envolvida (ex.: o `PUT` do rascunho no `sen validate`) deixava de orientar `sen login`.
- O `PUT` da revisão no `sen validate` não tratava recusas. Um `412` do Adaptive Governance que o pré-check não antecipou saía com `exit 1` e sem motivo, violando o spec do comando ("`exit 3` exclusivamente para bloqueio do Adaptive Governance"; cenário T03: "a plataforma responde `412`, o comando encerra com `exit 3`") e a decisão V-23 §5 ("nunca engole o erro").

Testes na API 417 do consulting (Draft 9161, 16/10/2026) mostraram mais dois buracos:

- **Tag que não pertence ao atributo** (`My new: [TagInexistente]`, válidas `Tag1`/`Tag2`): o Manager aceitou com `200` e **apagou todas as `apiTags`** da Draft e da API; a governança não barrou e o `validate` reportou sucesso, porque a conferência pós-gravação não olha o `api` aninhado.
- **Atributo obrigatório sem tag** (`My new: []`): o pré-check o considerou presente; o Manager recusou com `412` ("API must contain attribute My new").

## What Changes

- **Fallback da CLI**: um sinal do Manager não traduzido recebe a mensagem da família pela classificação compartilhada (sessão, acesso negado, indisponível, erro interno), mantendo o `exit_code` do comando.
- **Motivos da plataforma no sinal do port**: o adapter desembrulha o envelope de erro do Manager (`errors[].message` com JSON serializado dentro de string — V-23 §1) e entrega os motivos em texto humano no sinal de recusa.
- **Sinal de bloqueio de governança**: `412` com `path` `/api-governance/.../workflows/{id}/validate` vira um sinal próprio, com o workflow lido do `path` e o envelope original.
- **`sen validate`, recusa do `PUT` do rascunho**:
  - bloqueio de governança → `exit 3`, com o motivo literal da plataforma (o faltante não é calculável quando o workflow que valida não é o gravado na revisão — V-23 §3);
  - `400`/`409`/`412`/`422` fora da governança → `exit 1`, com o motivo da plataforma;
  - demais recusas → mensagem da família, `exit 1`;
  - todas terminam com "Nada foi publicado.".
- **Pré-check confere as tags**: tag fora da lista do atributo no catálogo aborta antes da escrita (`exit 1`); atributo com tags cadastradas declarado sem tag conta como ausente (`exit 3` pelo cálculo do faltante). Os avisos do pré-check, antes descartados, passam a aparecer como achados `WARNING`.
- **Conferência pós-gravação inclui o basic info**: `name`, `description` e `apiTags` enviados são comparados com a releitura; diferença é divergência (`exit 1`).

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `sen-validate`: novo requisito sobre a recusa da gravação do rascunho. A capability ainda não está em `openspec/specs/` (vive no change `add-sen-validate`, não arquivado), por isso o delta é `ADDED`.

O comportamento do fallback já está previsto em `sen-list` (E1: 401 → sessão; 403 → acesso negado) e `sen-completeness`; a mudança corrige a implementação para cumpri-los, sem delta de spec.

## Impact

- **Código**:
  - `domain/ports/manager_api_port.py`: `messages` no sinal de recusa e o novo `ManagerApiGovernanceBlockedError`.
  - `adapters/outbound/http/manager_api/manager_api_adapter.py`: leitura do envelope.
  - `http_error_mapper.py` / `http_client.py` / `http_client_exceptions.py`: corpo parseado no erro 4xx.
  - `application/exceptions/validate_exceptions.py`: motivos no `GovernanceBlockedError` e o novo `PublicacaoRecusadaError`.
  - `application/services/validate_service.py`: recusa do `PUT`.
  - `adapters/inbound/cli/cli_adapter.py`: fallback.
- **Testes**: `test_manager_api_adapter.py`, `test_validate_service.py`, `test_cli_adapter.py`.
- **Fora do escopo**: calcular o faltante quando o bloqueio só aparece no `PUT`. Exige resolver o workflow e o stage efetivos pelo grupo da API, hipótese ainda não confirmada na V-23 §3.
