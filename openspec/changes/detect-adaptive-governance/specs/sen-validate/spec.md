## ADDED Requirements

### Requirement: Cliente sem Adaptive Governance

Antes de montar o payload, o comando SHALL verificar se o Manager tem o Adaptive Governance. Sem o AG, o comando SHALL seguir sem travar:

- o pré-check SHALL devolver resultado neutro, sem requisitos, sem faltantes e sem avisos de governança;
- as `apiTags` do repositório SHALL ser ignoradas: não são conferidas contra o catálogo, não vão no `PUT` e não entram na conferência pós-gravação;
- o completeness SHALL NOT ser consultado;
- no JSON, os campos `governance` e `completeness` SHALL sair vazios (`null` e `[]`), sem mudar a versão do contrato;
- no texto, os blocos de governança e de quality score SHALL NOT aparecer.

Quando não for possível saber se o AG está ativo, o comando SHALL agir como se estivesse.

#### Scenario: Cliente sem AG com apiTags declaradas
- **WHEN** o Manager responde 403 "Governance module enabled" ao catálogo de atributos e o repositório declara `apiTags`, inclusive uma tag fora do catálogo
- **THEN** o comando não aborta por causa das `apiTags`, o `PUT` sai sem `apiTags`, e a conferência pós-gravação não acusa divergência nelas

#### Scenario: Saída sem AG
- **WHEN** o rascunho é gravado num cliente sem AG
- **THEN** o JSON traz `governance.workflowId` e `governance.stageId` `null`, `required` e `missing` vazios, `completeness.score` e `completeness.gatePercent` `null`, e o texto não mostra governança nem quality score

#### Scenario: Detecção inconclusiva
- **WHEN** o catálogo de atributos falha com erro que não é 403 nas três tentativas
- **THEN** o comando segue como se o AG estivesse ativo
