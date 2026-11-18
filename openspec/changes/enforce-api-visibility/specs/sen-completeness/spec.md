## MODIFIED Requirements

### Requirement: Fetch completeness for any revision from the Manager

The command SHALL fetch the completeness report of the informed revision exclusively from the Manager endpoint `GET /api-manager/api/v3/revisions/{rid}/completeness`, whose response carries `{completenessScore: number, suggestions: string[]}`. Any revision reachable in the platform SHALL be consultable: historical revisions MUST NOT be refused by the command itself. The command SHALL NOT call Adaptive Governance routes (`search`, `maturity-reports`) nor Connect Catalog routes. The ownership displayed belongs to the API (catalog frame), not to the queried revision.

Para sessão que não é de super admin, a consulta de identidade (`ManagerApiPort.list_api_detail`, catálogo api-finder) SHALL acontecer **antes** da leitura de completeness e é obrigatória:

- API inexistente ou invisível pela regra de `api-visibility` MUST encerrar com `exit 2` e a mensagem "API X não encontrada ou sem permissão de acesso.", sem chamar `/revisions/{rid}/completeness`;
- revisão que não está em `revisions[]` da API MUST encerrar com `exit 2` e a mesma mensagem de revisão não encontrada do `404`, sem chamar `/revisions/{rid}/completeness`;
- falha da consulta (recusa, rede ou 5xx) MUST encerrar com `exit 2` e a mensagem da família da falha, pela classificação compartilhada do Manager (`404` conta como API inexistente), sem exibir completeness.

Para sessão de super admin, a consulta de identidade MAY degrade softly: when it fails, the command SHALL still succeed with `exit 0` and the absence itself is the signal — API `name`/`version`/`context` fields render as `-` (no narrator block, no collect-state in any output).

#### Scenario: Historical revision is consultable
- **WHEN** user runs `sen completeness --id 375 --revision 5501` (a non-last revision of API 375, visible to the session)
- **THEN** the CLI performs `GET /api-manager/api/v3/revisions/5501/completeness` and renders the returned completeness for that revision (no synthetic refusal, no exit 2 for being an old revision)

#### Scenario: Identity lookup degrades softly
- **WHEN** the session is super admin, the api-finder lookup fails and the Manager call succeeds
- **THEN** the output renders the raw manager id (e.g. `API: 375`) with name/version/context as `-`, and the process exits with code 0

#### Scenario: Dev consulta API invisível
- **WHEN** a sessão de dev roda `sen completeness --id 375 --revision 5501` e a API 375 é `GROUP` de um grupo que ela não tem
- **THEN** o comando encerra com `exit 2` e "API 375 não encontrada ou sem permissão de acesso.", sem chamar `/revisions/5501/completeness`

#### Scenario: Dev aponta revisão de outra API
- **WHEN** a sessão de dev roda `sen completeness --id 400 --revision 9175`, a API 400 é visível e a revisão 9175 não está em `revisions[]` dela
- **THEN** o comando encerra com `exit 2` e a mensagem de revisão não encontrada, sem chamar `/revisions/9175/completeness`

#### Scenario: Consulta da API falha para dev
- **WHEN** a sessão é de dev e a consulta ao catálogo falha por indisponibilidade
- **THEN** o comando encerra com `exit 2` e a mensagem padrão de Manager indisponível, sem exibir completeness
