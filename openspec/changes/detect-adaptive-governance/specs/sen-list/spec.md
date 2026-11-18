## ADDED Requirements

### Requirement: Revisões em cliente sem Adaptive Governance

Em `sen list api --id X --revisions`, o comando SHALL verificar se o Manager tem o Adaptive Governance antes de ler stages e completeness. Sem o AG:

- o comando SHALL NOT consultar stages nem completeness;
- a tabela de texto SHALL omitir as colunas STAGE e COMPLETE e a nota de revisões sem completeness;
- no JSON, `stage_name` e `completeness_score` SHALL sair `null`.

Quando não for possível saber se o AG está ativo, o comando SHALL agir como hoje.

#### Scenario: Tabela sem AG
- **WHEN** o Manager responde 403 "Governance module enabled" ao catálogo de atributos
- **THEN** a tabela mostra só REV #, REV ID e ENVS, nenhuma chamada de completeness é feita, e o comando sai com `exit 0`

#### Scenario: JSON sem AG
- **WHEN** o mesmo caso é pedido com `-o json`
- **THEN** cada revisão traz `stage_name` e `completeness_score` `null`, com as demais chaves inalteradas
