## ADDED Requirements

### Requirement: Grammar of the sen publish command

A CLI SHALL expor o comando `sen publish`. O comando MUST aceitar `--repo <path>` (opcional, default
`Path.cwd()`), `--output text|json|yaml` (default `text`) e `--verbose`. O serviço MUST ser obtido
por factory no contexto do Typer, montada no composition root de forma preguiçosa.

#### Scenario: Flags aceitas
- **WHEN** o usuário roda `sen publish --repo ./minha-api -o json -v`
- **THEN** o parser aceita todas as flags e o serviço é instanciado pela factory do contexto

#### Scenario: Serviço indisponível no contexto
- **WHEN** a factory `publish_service_factory` não está no contexto do Typer
- **THEN** a CLI imprime erro em PT-BR e encerra com `exit 1`, sem emitir chamada HTTP

### Requirement: Target revision resolved by number from configuration

A revisão alvo SHALL ser lida de `TARGET_REVISION_NUMBER` e resolvida pelo `revisionNumber` em
`revisions[]` do `GET /apis/{spec.id}`. Em `EXECUTION_MODE=pipeline` a variável MUST estar definida.
Em `EXECUTION_MODE=local` ela MUST ser `1` ou ausente. O comando MUST NOT chamar `POST /revisions`.

#### Scenario: Esteira publica na revisão do ambiente
- **WHEN** `EXECUTION_MODE=pipeline`, `TARGET_REVISION_NUMBER=2` e a API tem a revisão 2 com id 9175
- **THEN** o comando lê e grava `PUT /revisions/9175`, e nenhuma outra revisão é escrita

#### Scenario: Variável ausente na esteira
- **WHEN** `EXECUTION_MODE=pipeline` e `TARGET_REVISION_NUMBER` não está definida
- **THEN** o comando aborta com `exit 1` antes de qualquer chamada HTTP, nomeando a variável

#### Scenario: Local fora da Draft
- **WHEN** `EXECUTION_MODE=local` e `TARGET_REVISION_NUMBER=3`
- **THEN** o comando recusa com `exit 1` antes de qualquer chamada HTTP

#### Scenario: Revisão inexistente
- **WHEN** a API não tem revisão de número 4
- **THEN** o comando aborta com `exit 1`, nomeando as revisões disponíveis, sem escrever

#### Scenario: API sem revisões
- **WHEN** `revisions[]` vem vazio
- **THEN** o comando aborta com `exit 1`, sem escrever

### Requirement: Preconditions abort before any write

Antes do `PUT`, o comando SHALL carregar o repositório e abortar com `exit 1` em erro de layout,
divergência de `version` ou `basePath` com o Manager, `Custom` referenciado inexistente ou tag
declarada fora da lista do atributo. O pré-check de governança SHALL abortar com `exit 3` quando um
atributo exigido pelo stage faltar, com `missing[]` calculado e nunca extraído de texto. O comando
MUST NOT executar a comparação com a API-template nem o completeness.

#### Scenario: basePath divergente
- **WHEN** o repositório declara `basePath: /letras/v9` e o Manager tem `/letras/v2`
- **THEN** o comando aborta com `exit 1` e nenhum `PUT` é emitido

#### Scenario: Atributo exigido faltando
- **WHEN** o stage da revisão alvo exige o atributo `My new` e o repositório não o declara
- **THEN** o comando aborta com `exit 3`, nomeando `My new`, e nenhum `PUT` é emitido

#### Scenario: Régua não é lida
- **WHEN** o comando roda com sucesso
- **THEN** nenhuma leitura da API-template nem do completeness é feita

### Requirement: Local publish requires explicit consent

Em `EXECUTION_MODE=local` o comando SHALL pedir confirmação antes do `PUT`, por callable injetado pela
CLI. Recusa MUST encerrar sem escrita e com `exit 0`. Em `pipeline` nenhuma confirmação é pedida.

#### Scenario: Dev recusa
- **WHEN** o comando roda em local e o dev responde `N`
- **THEN** nenhum `PUT` é emitido, nenhum relatório é exibido e a saída é só
  "Publicação cancelada. Nada foi gravado.", com `exit 0`

#### Scenario: Dev interrompe no prompt
- **WHEN** o dev pressiona Ctrl+C na confirmação
- **THEN** o comando é interrompido sem `PUT` e sem relatório, com a mesma mensagem e `exit 130`

### Requirement: Single PUT followed by verification

O comando SHALL emitir um único `PUT /revisions/{id}`, com `workflowId` e `workflowStageId` lidos da
revisão alvo e reenviados intactos, e SHALL reler a revisão e comparar o publicado com o enviado.
Divergência MUST encerrar com `exit 1`. HTTP 412 do Adaptive Governance MUST encerrar com `exit 3`,
repassando o motivo da plataforma. Outras recusas MUST encerrar com `exit 1`, nomeando a revisão
alvo.

#### Scenario: Publicação conferida
- **WHEN** o `PUT` responde 200 e a releitura corresponde ao enviado
- **THEN** o comando encerra com `exit 0` e `publication.verified = true`

#### Scenario: 200 com perda
- **WHEN** o `PUT` responde 200 e a releitura não corresponde ao enviado
- **THEN** o comando encerra com `exit 1`, listando as divergências

#### Scenario: Governança recusa no PUT
- **WHEN** o `PUT` responde 412 com o motivo `Actual Completeness is 50.0 but expected greater than or equal to 70.0`
- **THEN** o comando encerra com `exit 3` e exibe o motivo literal

### Requirement: Machine-readable output contract

Com `--output json|yaml`, o comando SHALL emitir o documento `apiops.sen-publish/v1` com `schema`,
`generatedAt`, `executionMode`, `api`, `revision`, `governance`, `publication` e `warnings`. O
documento MUST NOT conter token nem dump cru do wire. Em `json`/`yaml` nenhum progresso é impresso.

#### Scenario: Esteira consome o resultado
- **WHEN** a esteira roda `sen publish -o json` e a publicação é conferida
- **THEN** o stdout contém só o documento, com `revision.revisionNumber` igual ao alvo e `publication.verified = true`

### Requirement: Target revision deploy status is reported

O resultado SHALL listar em `revision.deployments[]` os ambientes em que a revisão alvo está no ar
(`deploymentId`, `environment { managerId, name }`, `deployedAt`), lidos de
`revisions[].deployments` do `GET /apis/{id}` já feito, sem chamada nova. Sem deploy, a lista MUST
ser `[]`. A informação MUST NOT bloquear nem alterar o exit code. O comando MUST NOT chamar
`GET /environments/{id}`.

#### Scenario: Revisão deployada
- **WHEN** a revisão 3 está `DEPLOYED` no ambiente 7 (`DEV-APIOPS`) e a publicação é conferida
- **THEN** `revision.deployments` traz o ambiente 7 com o id do deploy e a data, e o texto mostra
  `deployada em DEV-APIOPS (id 7) · deploy em <data>` abaixo de "gravada"

#### Scenario: Revisão fora do ar
- **WHEN** a revisão alvo não tem registro `DEPLOYED`
- **THEN** `revision.deployments` é `[]` e o texto mostra "não está deployada em nenhum ambiente"

### Requirement: Repository prevails on declared interceptors

Para interceptors de request e response, o payload SHALL usar o `content` declarado no repositório
nos tipos nativos e a ordem declarada em cada execution point. Do item que já existe no Manager MUST
ser reaproveitada só a identidade técnica (`id`, `idTemp`, `status`, `parentType`); o `content` de
`Custom` MUST continuar o do Manager. As `position` MUST NOT ser renumeradas 1..N. A conferência SHALL
comparar o publicado com o fluxo declarado — tipo, ordem e `content` normalizado.

#### Scenario: Alterar content de interceptor existente
- **WHEN** o repositório muda o `quota` de um Rate limit que já existe de `1000` para `500`
- **THEN** o `PUT` leva `500`, reaproveitando o `id` do item, e a releitura mostra `500`

#### Scenario: Reordenar interceptors
- **WHEN** o repositório inverte a ordem de Log e Rate limit no request da raiz
- **THEN** a releitura, por `position`, mostra Rate limit antes de Log

#### Scenario: Conteúdo perdido sob HTTP 200
- **WHEN** o `PUT` responde 200 e a releitura mostra o `content` antigo
- **THEN** o comando encerra com `exit 1`, nomeando o campo que não foi gravado

### Requirement: Removal is warned before the write

Recurso, rota ou interceptor presente no Manager e ausente do repositório SHALL gerar aviso que nomeie
o que será apagado. O aviso MUST NOT bloquear. Em `local` ele MUST aparecer na confirmação, antes do
`s/n`, e MUST NOT se repetir no resultado; em `pipeline` ele MUST sair no resultado.

#### Scenario: Rota removida em modo local
- **WHEN** a rota `DELETE /letras/{id}` existe no Manager e não no repositório, em `EXECUTION_MODE=local`
- **THEN** a confirmação lista a rota em "Atenção:" antes do `s/n`, e o resultado não repete o aviso
