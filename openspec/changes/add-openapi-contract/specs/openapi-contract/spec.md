## ADDED Requirements

### Requirement: Declared contract is validated before any write

O contrato declarado no repositório SHALL ser validado sem rede, antes de qualquer escrita, por um
serviço isolado dos comandos (Swagger validate). Erro MUST abortar o comando com exit 1, citando o
arquivo e a posição, e MUST NOT deixar nada gravado — nem o fluxo, nem o swagger.

#### Scenario: Erro no contrato não grava nada
- **WHEN** o contrato declarado tem qualquer erro de validação
- **THEN** o comando sai com exit 1 antes do PUT da revisão e do PUT do swagger

### Requirement: References are checked

Todo `$ref` SHALL existir no `components.yaml`, apontar para a seção que a posição pede
(`responses.<status>` → `responses`; `requestBody` → `requestBodies`; `schema` → `schemas`;
`headers.<nome>` → `headers`; `examples.<nome>` → `examples`) e ser interno (`#/components/...`).
Ciclo de `$ref` fora de `schemas` MUST ser erro. `security` SHALL citar só esquemas de
`securitySchemes`.

#### Scenario: Referência para schema inexistente
- **WHEN** `get_tarefas.yaml` declara `$ref: '#/components/schemas/Tarefa'` e o `components.yaml` não tem `Tarefa`
- **THEN** o comando sai com exit 1 citando `get_tarefas.yaml` e `Tarefa`

#### Scenario: Referência de seção errada
- **WHEN** uma operação declara `'404': $ref: '#/components/requestBodies/NovaTarefa'`
- **THEN** o comando sai com exit 1 dizendo que uma resposta só pode referenciar `#/components/responses/`

#### Scenario: Referência externa
- **WHEN** uma operação declara `$ref: './schemas/tarefa.yaml'` ou `$ref: '#/definitions/Tarefa'`
- **THEN** o comando sai com exit 1

### Requirement: Parameters are checked

Parâmetro de path do `resource.yaml` SHALL existir no template de todas as rotas do recurso. Cada
`{param}` da rota SHALL ter parâmetro `in: path`, e todo `in: path` da operação SHALL existir no
template. Parâmetro de path MUST ter `required: true`. `name`+`in` repetido no mesmo arquivo MUST ser
erro.

#### Scenario: Parâmetro de path do recurso que não vale para todas as rotas
- **WHEN** o `resource.yaml` de `Tarefas`, com as rotas `/tarefas` e `/tarefas/{id}`, declara `id` em `path`
- **THEN** o comando sai com exit 1 citando `/tarefas`

#### Scenario: Parâmetro de path não declarado
- **WHEN** a rota `/tarefas/{id}` não declara o parâmetro `id` nem no recurso nem na operação
- **THEN** o comando sai com exit 1 citando a rota e o `{id}`

### Requirement: Operations and examples are checked

Toda operação SHALL declarar `responses`, cada resposta com `description` e status de três dígitos,
`1XX`–`5XX` ou `default`. `operationId` MUST ser único na API. `requestBody` MUST aparecer só em POST,
PUT e PATCH. `example`, `examples` e `default` SHALL ser compatíveis com o schema, e `enum` coerente
com o `type`.

#### Scenario: Rota sem respostas
- **WHEN** `get_tarefas.yaml` não declara `responses`
- **THEN** o comando sai com exit 1 citando `get_tarefas.yaml`

#### Scenario: Exemplo com tipo diferente do schema
- **WHEN** um parâmetro `page` com schema `integer` declara `example: primeira`
- **THEN** o comando sai com exit 1 citando o parâmetro e o tipo esperado

#### Scenario: Corpo em GET
- **WHEN** `get_tarefas.yaml` declara `requestBody`
- **THEN** o comando sai com exit 1

### Requirement: Fields outside the model are rejected

Chave `x-*` em qualquer arquivo do repositório, `servers` ou `info` no `api-basic-info.yaml`, seção
de `components` fora do modelo e `components.yml` na raiz MUST ser erro de validação.

#### Scenario: Extensão no YAML
- **WHEN** um arquivo de operação declara uma chave `x-qualquer`
- **THEN** o comando sai com exit 1: as extensões são do Manager

### Requirement: Repository governs the contract fields

O repositório SHALL ser a verdade em `info.contact`, `tags` e `security` da raiz; nas seções
`schemas`, `securitySchemes`, `responses`, `requestBodies`, `headers` e `examples` de `components`; e
em `operationId`, `summary`, `tags`, `security`, `parameters`, `requestBody` e `responses` de cada
operação. Campo governado ausente MUST ir em branco; `parameters` ausente SHALL ir como `[]`; `summary`
ausente SHALL receber a `description` da operação.

#### Scenario: Resposta só no Manager
- **WHEN** o Manager documenta `404` em `GET /tarefas/{id}` e o arquivo da rota declara só `responses: {'200': {description: OK}}`
- **THEN** a rota é gravada só com o `200`, e o aviso lista o `404` entre o que sai do Manager

#### Scenario: Schema só no Manager
- **WHEN** o swagger do Manager tem o schema `Legado` e o `components.yaml` não o declara
- **THEN** `Legado` sai do swagger, e o aviso o lista

### Requirement: Platform-owned parts come from the revision swagger

O documento gravado SHALL partir do GET do swagger feito depois da gravação do fluxo. `openapi`,
`servers`, `info.title`, `info.version`, `info.description` e as seções de `components` fora do modelo
MUST vir desse GET, intactos. A `description` da operação e os `x-*` MUST vir desse GET quando ele
descreve o fluxo gravado; senão, do fluxo (requisito "Swagger follows the flow").

#### Scenario: Extensões intactas
- **WHEN** o contrato de uma rota é substituído e o GET do swagger descreve o fluxo gravado
- **THEN** `x-interceptors`, `x-resource-name` e `x-api-broken` dessa rota são gravados como vieram do GET

#### Scenario: Servidores e título vêm do Manager
- **WHEN** o contrato é gravado
- **THEN** `servers` e `info.title`, `info.version` e `info.description` são os do GET

### Requirement: Resource parameters are copied into each operation

Os parâmetros do `resource.yaml` SHALL entrar em cada operação do recurso, e não no path item. No
mesmo `name`+`in`, a operação SHALL prevalecer. `parameters` de path item MUST ir em branco.

#### Scenario: Parâmetro do recurso sobrescrito pela rota
- **WHEN** o `resource.yaml` declara `X-Correlation-Id` em `header` com `required: false` e `post_tarefas.yaml` o declara com `required: true`
- **THEN** o POST é gravado com `required: true`, e as demais rotas do recurso com `required: false`

### Requirement: Parameter extensions from the Manager are kept

Cada parâmetro gravado SHALL levar os `x-*` do parâmetro do swagger atual com o mesmo `name`+`in`, da
operação ou, na falta dele, do path item. Os campos declarados no repositório MUST prevalecer; os `x-*`
só preenchem o que o repositório não declara, já que o repositório não aceita `x-*` (C6).

#### Scenario: `x-example` mantido no parâmetro
- **WHEN** o Manager tem `status` em `query` com `x-example: PENDENTE` e o repositório declara `status` em `query` sem `x-*`
- **THEN** o parâmetro é gravado com os campos do repositório e com `x-example: PENDENTE`, e a execução seguinte, sem mudança, não grava o swagger

#### Scenario: Outro `in` não herda
- **WHEN** o Manager tem `id` em `query` com `x-example` e o repositório declara `id` em `path`
- **THEN** o parâmetro `id` em `path` é gravado sem o `x-example`

### Requirement: Swagger follows the flow

Os `x-*` do GET do swagger, a `description` da operação e a do recurso SHALL ser comparados com o fluxo
lido na conferência da gravação do fluxo, sem as chaves locais e com o `parent-id` resolvido para o
item pai. Iguais, o documento MUST partir do GET como veio. Diferentes, o documento SHALL ser alinhado
ao fluxo: rota que falta é criada, rota e recurso que o fluxo não tem saem, e os `x-*` passam a ser os
do fluxo. O `-o` SHALL trazer `documentation.aligned` só quando houve alinhamento.

#### Scenario: Rota que o Manager não levou ao swagger
- **WHEN** o GET do swagger, depois da gravação do fluxo, não traz `POST /tarefas`, que está no fluxo e no repositório
- **THEN** o documento gravado tem `POST /tarefas` com o contrato do repositório e os `x-*` do fluxo, e o `-o` traz `aligned: ["POST /tarefas: criada"]`

#### Scenario: Marcador de herança apontando para o pai errado
- **WHEN** o GET traz, em `GET /tarefas`, um `REMOVED` cujo `x-interceptor-parent-id` aponta para outro item que não o do fluxo
- **THEN** os `x-interceptors` gravados são os do fluxo, e o fluxo depois do PUT do swagger é o da conferência

#### Scenario: Swagger em dia
- **WHEN** o GET descreve o fluxo, ainda que com outras chaves locais
- **THEN** o documento parte do GET como veio e o `-o` não traz `aligned`

### Requirement: Flow the swagger cannot carry is not aligned

Fluxo com campo que o swagger não carrega (`certificateId`, `connector`, `async`, `urls`,
`instruction`) ou com marcador cujo pai está fora da revisão MUST impedir o alinhamento: o swagger
não é gravado, com warning, e o fluxo gravado fica.

#### Scenario: Fluxo que o swagger não carrega
- **WHEN** o swagger diverge do fluxo e uma rota do fluxo tem `certificateId`
- **THEN** o swagger não é gravado, o warning cita a rota e o campo, e o fluxo gravado fica

### Requirement: Operations outside the repository leave the swagger

Operação que o GET do swagger traz e o repositório não tem SHALL sair do documento gravado, e o path
que ficar sem operação também. O PUT de swagger MUST NOT devolver ao fluxo uma rota que a gravação do
fluxo removeu.

#### Scenario: Método removido de um path que mantém outro
- **WHEN** o repositório tira `POST /tarefas`, mantém `GET /tarefas`, e o Manager deixa o `POST` no swagger depois da gravação do fluxo
- **THEN** o documento gravado não tem o `POST`, e a revisão termina só com o `GET /tarefas`

### Requirement: Unchanged contract is not written

O documento montado SHALL ser comparado, normalizado, com o GET do swagger. Igual, o PUT de swagger
MUST NOT ser feito.

#### Scenario: Segunda execução com o mesmo repositório
- **WHEN** o comando roda de novo sem mudança no contrato
- **THEN** não há PUT de swagger e os ids dos interceptors da revisão não mudam

### Requirement: Contract write is verified, including the runtime

Depois do PUT de swagger, o comando SHALL reler o swagger e a revisão e conferir, com o documento
normalizado (padrões do OpenAPI explicitados, `required` dos schemas como conjunto, `$ref` resolvidos):
o contrato do repositório como declarado; os `x-*` estruturalmente iguais aos enviados; e o runtime
igual ao que a conferência do fluxo aprovou, com `workflowId` e `workflowStageId`. Ids de interceptor e
chaves locais de `x-interceptors` MUST NOT contar como divergência.

#### Scenario: Normalização do Manager não é divergência
- **WHEN** o Manager devolve um parâmetro com `style: form`, `explode: true` e `required: false` que o repositório não declarou
- **THEN** a conferência não aponta divergência

#### Scenario: Runtime alterado pelo PUT de swagger
- **WHEN** a releitura da revisão mostra um escopo com um interceptor a menos do que a conferência do fluxo aprovou
- **THEN** o comando emite warning nomeando o escopo e sai com exit 0

### Requirement: Platform problems become warnings and keep the flow

Swagger 2.0 no GET, GET ou PUT recusado, 5xx que persiste depois dos retries, swagger que não pode
ser alinhado ao fluxo e conferência divergente SHALL virar warning na saída, com exit 0. O fluxo gravado e
conferido MUST ser mantido, e não há rollback.

#### Scenario: Revisão em Swagger 2.0
- **WHEN** o GET do swagger devolve `swagger: "2.0"`
- **THEN** o fluxo é gravado, a etapa de contrato não roda e o `-o` traz o warning

#### Scenario: Plataforma indisponível no PUT de swagger
- **WHEN** o PUT de swagger responde 502 em todas as tentativas
- **THEN** o comando sai com exit 0, com warning, e o fluxo gravado fica

### Requirement: Descriptions below the completeness minimums are warned

O Swagger validate SHALL emitir warning, sem bloquear, para descrição abaixo do mínimo que o
completeness do Manager cobra: `summary` e `description` de resposta com até 4 caracteres;
`description` de parâmetro com até 4; de propriedade com menos de 9; de schema com até 9; schema de
objeto sem propriedades.

#### Scenario: Propriedade sem descrição
- **WHEN** o schema `Tarefa` declara a propriedade `id` sem `description`
- **THEN** o comando avisa que a propriedade baixa a nota de completeness e segue

#### Scenario: Contrato bem descrito
- **WHEN** todas as descrições do contrato atendem aos mínimos
- **THEN** o comando não emite aviso de descrição
