## ADDED Requirements

### Requirement: Grammar of the sen deploy command

A CLI SHALL expor o comando `sen deploy`. O comando MUST aceitar `--repo <path>` (opcional, default
`Path.cwd()`), `--output text|json|yaml` (default `text`) e `--verbose`. O serviço MUST ser obtido
por factory no contexto do Typer, montada no composition root de forma preguiçosa.

#### Scenario: Flags aceitas
- **WHEN** a esteira roda `sen deploy --repo ./minha-api -o json -v`
- **THEN** o parser aceita todas as flags e o serviço é instanciado pela factory do contexto

#### Scenario: Serviço indisponível no contexto
- **WHEN** a factory `deploy_service_factory` não está no contexto do Typer
- **THEN** a CLI imprime erro em PT-BR e encerra com `exit 1`, sem emitir chamada HTTP

### Requirement: Deploy runs only in the pipeline

O comando SHALL rodar apenas com `EXECUTION_MODE=pipeline`. Em `local` ele MUST abortar com `exit 1`
antes de autenticar e de qualquer chamada HTTP. O comando MUST NOT pedir confirmação interativa.

#### Scenario: Dev tenta deployar da máquina
- **WHEN** o comando roda com `EXECUTION_MODE=local`
- **THEN** encerra com `exit 1`, explicando que o deploy é feito pela esteira, sem chamada HTTP

### Requirement: Target revision and environment from configuration

A revisão alvo SHALL ser lida de `TARGET_REVISION_NUMBER` e o ambiente alvo de
`TARGET_ENVIRONMENT_ID`; as duas MUST estar definidas. `TARGET_REVISION_NUMBER=1` MUST ser recusado.
O `revisionId` MUST ser resolvido pelo `revisionNumber` em `revisions[]` do `GET /apis/{spec.id}` e
MUST NOT vir de nenhuma outra fonte. O ambiente MUST estar em `environments[]` da mesma resposta.
Falhas desta etapa MUST encerrar com `exit 1` sem escrita.

#### Scenario: Esteira deploya a revisão do ambiente
- **WHEN** `TARGET_REVISION_NUMBER=3`, `TARGET_ENVIRONMENT_ID=7`, a API 417 tem a revisão 3 com id 9327 e o ambiente 7 está em `environments[]`
- **THEN** o comando emite `POST /deployments` com `revisionId: 9327` e `environmentId: 7`

#### Scenario: Variável ausente
- **WHEN** `TARGET_ENVIRONMENT_ID` não está definida
- **THEN** o comando aborta com `exit 1` antes de qualquer chamada HTTP, nomeando a variável

#### Scenario: Draft como alvo
- **WHEN** `TARGET_REVISION_NUMBER=1`
- **THEN** o comando aborta com `exit 1` antes de qualquer chamada HTTP, explicando que a Draft não tem deploy

#### Scenario: Revisão inexistente na API
- **WHEN** a API não tem revisão de número 4
- **THEN** o comando aborta com `exit 1`, nomeando as revisões disponíveis (número e id), sem escrever

#### Scenario: Ambiente não ligado à API
- **WHEN** `TARGET_ENVIRONMENT_ID=9` e a API só está ligada ao ambiente 7
- **THEN** o comando aborta com `exit 1`, listando os ambientes ligados com id e nome, sem escrever

### Requirement: API identity is checked before the write

O comando SHALL ler `spec.id`, `version` e `basePath` do manifesto do repositório e abortar com
`exit 1` quando o manifesto faltar, quando `spec.id` faltar ou quando `version` ou `basePath`
divergirem do Manager. O comando MUST NOT gravar conteúdo da revisão.

#### Scenario: spec.id aponta outra API
- **WHEN** o manifesto declara `basePath: /letras/v2` e a API de `spec.id` tem `/pedidos/v1`
- **THEN** o comando aborta com `exit 1` e nenhum `POST` é emitido

#### Scenario: Nenhuma escrita de conteúdo
- **WHEN** o comando roda com sucesso
- **THEN** nenhum `PUT` ou `POST` em `/revisions` é emitido

### Requirement: Governance gate reads the stage of the target revision

Antes da escrita, o comando SHALL avaliar o stage da revisão alvo, identificado por `workflowId` e
`workflowStageId` em `revisions[]`. Qualquer critério de governança violado MUST encerrar com `exit 3`
sem escrita, listando todos os critérios violados. Revisão sem stage, ou stage inexistente no
workflow, MUST gerar aviso em `warnings[]` e não bloquear.

#### Scenario: Dois critérios violados
- **WHEN** o ambiente não é permitido pelo stage e falta um atributo exigido
- **THEN** o comando aborta com `exit 3` e o resultado lista as duas violações

#### Scenario: Revisão sem stage
- **WHEN** a revisão alvo não declara `workflowId`
- **THEN** o comando segue para a escrita, com aviso em `warnings[]`

### Requirement: Target environment allowed by the stage

O ambiente alvo SHALL estar em `deployableEnvironments` do stage. Lista vazia MUST ser tratada como
sem restrição.

#### Scenario: Ambiente fora do permitido pelo stage
- **WHEN** o stage tem `deployableEnvironments: [7]` e o alvo é o ambiente 9, ligado à API
- **THEN** o comando aborta com `exit 3`, nomeando o stage e os ambientes permitidos, sem escrever

#### Scenario: Lista de ambientes vazia
- **WHEN** o stage tem `deployableEnvironments: []`
- **THEN** o critério de ambiente não bloqueia

### Requirement: Completeness meets the stage requirement

O `completenessScore` da revisão alvo SHALL ser maior ou igual ao `completenessRequisite` do stage.
Com requisito igual a 0, o completeness MUST NOT ser lido.

#### Scenario: Completeness abaixo do exigido
- **WHEN** o stage exige `completenessRequisite: 70.0` e a revisão tem `completenessScore: 65.0`
- **THEN** o comando aborta com `exit 3`, mostrando 65,0 contra 70,0, sem escrever

#### Scenario: Stage sem exigência de completeness
- **WHEN** o stage tem `completenessRequisite: 0.0`
- **THEN** `GET /revisions/{id}/completeness` não é chamado

### Requirement: Required attributes present in the Manager

Todo atributo `mustHave` do stage SHALL estar presente nos `apiTags` da API **no Manager**, e não nos
do repositório: o deploy coloca no ar o que já foi gravado.

#### Scenario: Atributo exigido ausente no Manager
- **WHEN** o stage exige o atributo `teste giroto` e os `apiTags` da API no Manager não o têm
- **THEN** o comando aborta com `exit 3`, nomeando o atributo, sem escrever

### Requirement: Single deployment write

O comando SHALL emitir um único `POST /deployments` com `environmentId`, `revisionId` e `status:
"DEPLOYED"`, mesmo quando a revisão alvo já estiver no ar no ambiente. Recusa do `POST` MUST encerrar
com `exit 1`, repassando a `message` da plataforma quando houver. O comando MUST NOT chamar `GET
/environments/{id}`, `PUT /deployments/{id}` nem `DELETE /deployments/{id}`.

#### Scenario: Revisão já no ar
- **WHEN** a revisão 9327 já está `DEPLOYED` no ambiente 7
- **THEN** o comando emite o `POST` mesmo assim

#### Scenario: Variável ausente no ambiente alvo
- **WHEN** o `POST` responde 400 com "Environment Variable '$backend' have not found"
- **THEN** o comando encerra com `exit 1` e exibe a mensagem da plataforma

### Requirement: Deployment verified after the write

Depois do `POST`, o comando SHALL reler `GET /apis/{id}` e confirmar, em `revisions[].deployments`,
o registro com o id devolvido, `status: DEPLOYED`, o ambiente e a revisão alvo. Divergência MUST
encerrar com `exit 1`.

#### Scenario: Deploy conferido
- **WHEN** o `POST` responde 201 `{"id": 269}` e a releitura mostra o 269 `DEPLOYED` no ambiente 7 com a revisão 9327
- **THEN** o comando encerra com `exit 0` e `deployment.verified = true`

#### Scenario: 201 sem efeito na releitura
- **WHEN** o `POST` responde 201 e a releitura não mostra o registro `DEPLOYED`
- **THEN** o comando encerra com `exit 1`, com o id do deploy para investigação

### Requirement: Previous and new state are reported

O resultado SHALL conter o estado anterior do ambiente (o deploy `DEPLOYED` no ambiente alvo antes
do `POST`, ou nulo) e o novo estado (o deploy conferido), cada um com `deploymentId`, `revisionId`,
`revisionNumber` e `deployedAt`.

#### Scenario: Troca de revisão no ambiente
- **WHEN** o ambiente 7 tinha a revisão 2 no ar e o comando deploya a revisão 3
- **THEN** `previousState.revisionNumber = 2` e `newState.revisionNumber = 3`

#### Scenario: Primeiro deploy no ambiente
- **WHEN** nenhuma revisão da API estava no ar no ambiente alvo
- **THEN** `previousState` é nulo

### Requirement: Machine-readable output contract

Com `--output json|yaml`, o comando SHALL emitir o documento `apiops.sen-deploy/v1` com `schema`,
`generatedAt`, `executionMode`, `api`, `revision`, `environment`, `governance`, `previousState`,
`newState`, `deployment` e `warnings`. O documento MUST NOT conter token, variáveis de ambiente nem
dump cru do wire. Em `json`/`yaml` nenhum progresso é impresso.

#### Scenario: Esteira consome o resultado
- **WHEN** a esteira roda `sen deploy -o json` e o deploy é conferido
- **THEN** o stdout contém só o documento, com `deployment.status = "SUCCESS"` e `environment.managerId` igual ao alvo

### Requirement: Failed deployment still produces the document

Recusa do `POST` ou divergência na conferência SHALL produzir o documento completo com
`deployment.status = "FAILED"` e o motivo, além do `exit 1`. Falhas anteriores à escrita MUST
produzir só a mensagem e o exit code.

#### Scenario: Falha antes da escrita
- **WHEN** o ambiente alvo não está ligado à API, com `-o json`
- **THEN** o comando encerra com `exit 1` e não emite o documento

#### Scenario: Deploy recusado ainda gera documento
- **WHEN** o `POST` responde 400 com `-o json`
- **THEN** o stdout contém o documento com `deployment.status = "FAILED"` e o motivo, e o exit é 1
