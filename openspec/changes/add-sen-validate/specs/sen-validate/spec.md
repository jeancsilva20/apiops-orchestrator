## ADDED Requirements

### Requirement: Grammar of the sen validate command

A CLI SHALL expor o comando `sen validate`. O comando MUST aceitar `--repo <path>` (opcional, default
`Path.cwd()`), `--output text|json|yaml` (default `text`) e `--verbose` (verbosidade de log apenas,
nunca formato). O serviço MUST ser obtido por factory no contexto do Typer, montada no composition
root de forma preguiçosa, de modo que `Settings` só seja lida quando o comando roda. `typer.Exit`
MUST ser repassado antes de qualquer captura genérica. Subcomandos de diagnóstico (`structure`,
`template`, `draft`) MUST ser declarados `hidden=True`.

#### Scenario: Flags aceitas
- **WHEN** o usuário roda `sen validate --repo ./minha-api -o json -v`
- **THEN** o parser aceita todas as flags e o serviço é instanciado pela factory do contexto

#### Scenario: Serviço indisponível no contexto
- **WHEN** a factory `validate_service_factory` não está no contexto do Typer
- **THEN** a CLI imprime erro em PT-BR e encerra com `exit 1`, sem emitir chamada HTTP

### Requirement: Cascade E1 to E4 with guards before any write

O serviço SHALL executar a cascata na ordem E1 → E2 → E3 → E3.1 → E4. A E1 MUST carregar o
repositório sem rede, e a guarda de identidade (`version` e `basePath` divergentes do Manager) MUST
abortar antes de qualquer escrita. O pré-check de governança MUST rodar antes da E3. A confirmação
interativa MUST ser injetada pela CLI como callable: o serviço MUST NOT ler `stdin`. Em
`EXECUTION_MODE=pipeline` a CLI MUST injetar confirmação automática, mantendo a guarda de identidade
nos dois modos.

#### Scenario: basePath divergente aborta antes de escrever
- **WHEN** o `api-basic-info.yaml` declara `basePath: /letras/v9` e o Manager tem `/letras/v2`
- **THEN** o comando aborta na guarda de identidade, com `exit 1`, e nenhum `PUT` é emitido

#### Scenario: Esteira não pergunta
- **WHEN** `EXECUTION_MODE=pipeline` e a cascata chega à E3
- **THEN** nenhuma confirmação interativa é solicitada, e a guarda de identidade permanece ativa

### Requirement: Single PUT on the revision with runtime-resolved stage

A E3 SHALL emitir **um único** `PUT /revisions/{id}`, carregando o objeto `api` aninhado com
`apiTags`, `name` e `description`. O comando MUST NOT emitir `PUT /apis/{id}`. O `workflowId` e o
`workflowStageId` MUST ser lidos do `GET /revisions/{id}` da revisão alvo e reenviados sem alteração;
o comando MUST NOT configurar, inferir ou avançar o stage. O comando MUST NOT emitir
`POST /revisions`: criar revisão é ato humano.

#### Scenario: Stage preservado no payload
- **WHEN** a revisão alvo responde com `workflowId: 500` e `workflowStageId: 1402`
- **THEN** o payload do `PUT` carrega exatamente `500` e `1402`, sem reescrita

#### Scenario: Nenhuma escrita no recurso de API
- **WHEN** o repositório altera `description` e `apiTags`
- **THEN** a alteração viaja no `api` aninhado do `PUT /revisions/{id}`, e nenhuma chamada a
  `PUT /apis/{id}` é emitida

### Requirement: Post-publication verification treats HTTP 200 as inconclusive

Após a E3, o comando SHALL reler o estado publicado por `GET` e compará-lo com o enviado, em
operações (método e path), interceptors por escopo e recursos vazios. Divergência SHALL ser tratada
como **falha** com `exit 1`, ainda que a plataforma tenha respondido `200`. O comando MUST NOT
concluir sucesso apenas pelo código HTTP.

#### Scenario: Item descartado sob HTTP 200
- **WHEN** o `PUT` responde `200` mas o `GET` posterior mostra um interceptor a menos do que o enviado
- **THEN** o comando reporta divergência de publicação e encerra com `exit 1`

### Requirement: Governance pre-check computes the missing attributes

O pré-check SHALL resolver o workflow e o stage a partir da revisão alvo, ler
`attributesRequisites` do stage e o catálogo de atributos, e calcular
`exigidos(mustHave) - presentes(apiTags do repositório)`. O comando MUST NOT extrair o atributo
faltante do texto de `messages[]`. Havendo faltantes, o comando SHALL abortar com `exit 3`, **sem
escrever**. Nenhum identificador de atributo ou requisito pode ser fixado em código: todos MUST ser
lidos da plataforma a cada execução.

#### Scenario: Atributo obrigatório ausente bloqueia antes da escrita
- **WHEN** o stage exige os atributos `149` e `231` e o repositório declara apenas `231`
- **THEN** o comando reporta `149` como faltante pelo nome do catálogo e encerra com `exit 3`, sem
  emitir `PUT`

#### Scenario: Requisitos mudam entre execuções
- **WHEN** o stage passa a exigir um atributo diferente do exigido na execução anterior
- **THEN** o cálculo reflete o novo requisito, porque é lido da plataforma e não de valor em código

### Requirement: Versioned JSON contract apiops.sen-validate/v1 with ruler snapshot

A saída `json` e `yaml` SHALL serializar a mesma árvore sob o contrato `apiops.sen-validate/v1`,
contendo `schema`, `generatedAt`, identidade da API, revisão alvo, achados de conformidade com
severidade, resultado do pré-check de governança, resultado da conferência pós-publicação e
completeness. A árvore MUST conter o **snapshot da régua** com o `id` do template, o
`revisionNumber` usado e um hash do fluxo comparado, de modo que um achado seja reproduzível depois
que a template mudar. Nenhuma saída MUST conter token, cookie, material de credencial ou dump cru de
wire.

#### Scenario: Esteira consome o id do template
- **WHEN** o comando roda com `-o json` e a régua foi lida
- **THEN** o JSON contém o snapshot com `id`, `revisionNumber` e hash do fluxo do template

#### Scenario: Saída livre de credencial
- **WHEN** qualquer formato de saída é gerado
- **THEN** nenhum campo contém token, cookie ou cabeçalho de autorização

### Requirement: Exit codes separate technical failure from governance blocking

O comando SHALL usar `0` para sucesso, incluindo achados `INFO`/`WARNING` de conformidade e
completeness abaixo do gate de 70%; `1` para falha técnica ou de gramática; e `3` exclusivamente para
bloqueio do Adaptive Governance. As exceções de negócio MUST herdar de um erro base que carrega
`message` e `exit_code`, e a CLI MUST apenas traduzi-las, sem decidir severidade.

#### Scenario: Divergência de régua não bloqueia
- **WHEN** a conformidade produz três achados `WARNING` e a publicação é aceita
- **THEN** o comando encerra com `exit 0` e os achados aparecem na saída

#### Scenario: Governança tem canal próprio
- **WHEN** o Adaptive Governance bloqueia a publicação
- **THEN** o comando encerra com `exit 3`, distinto de qualquer falha técnica

### Requirement: Acceptance battery reproduces the proven platform behaviour

A implementação SHALL ser validada pela mesma bateria que validou o protótipo, registrada no
[caderno de testes](../../../../docs/feat-api-estructure/prova-fluxo-validate/CADERNO-DE-TESTES.md).
Cada cenário SHALL alterar o repositório, executar o comando, reler o estado por `GET` e restaurar o
baseline. O veredito SHALL vir da releitura, nunca do código HTTP. Ao fim da bateria, o estado da API
MUST ser idêntico ao baseline em nome, descrição, tags, `basePath`, recursos, operações e
interceptors.

#### Scenario: T01 - campo simples do basic info replica
- **WHEN** o repositório altera `description` no `api-basic-info.yaml` e o comando publica
- **THEN** a releitura mostra a nova `description`, que viajou no `api` aninhado do payload da revision

#### Scenario: T02 - guarda de identidade impede a escrita
- **WHEN** o repositório declara um `basePath` divergente do Manager
- **THEN** o comando aborta na guarda de identidade, nenhum `PUT` é emitido, e o `basePath` na
  plataforma permanece inalterado

#### Scenario: T03 - bloqueio do AG não deixa estado parcial
- **WHEN** o repositório remove um `apiTag` exigido pelo stage da revisão alvo e o comando tenta publicar
- **THEN** a plataforma responde `412`, o comando encerra com `exit 3`, e a tag continua na API,
  porque houve um único `PUT`

#### Scenario: T04 - destination de operação replica
- **WHEN** o repositório altera `destination.url` no arquivo de uma operação
- **THEN** a releitura mostra o novo destino naquela operação

#### Scenario: T05 - rota nova nasce sem id e herda por lista vazia
- **WHEN** o repositório ganha um diretório de recurso com `resource.yaml` e um arquivo de operação novos
- **THEN** recurso e operação são criados sem `id`, gerados pela plataforma, a operação sobe com zero
  interceptors próprios, e o fluxo da raiz permanece intacto

#### Scenario: T06 - lista vazia herda, não zera
- **WHEN** um recurso e uma operação declaram `inherit: false` sem nenhum item
- **THEN** ambos sobem com lista vazia e seguem executando o fluxo herdado, e o comando reporta a
  situação como remoção não representável, nunca como fluxo vazio

#### Scenario: T07 - interceptors no recurso não são copiados para as rotas
- **WHEN** o `resource.yaml` declara `inherit: false` com dois itens próprios
- **THEN** o recurso sobe com exatamente esses dois, e as operações do recurso seguem com zero itens
  próprios, herdando por lista vazia e não por cópia

#### Scenario: T08 - interceptors declarados na operação sobem
- **WHEN** o arquivo de uma operação declara `inherit: false` com dois itens
- **THEN** a operação sobe com exatamente esses dois itens

#### Scenario: T10 - arquivo removido remove a rota
- **WHEN** o arquivo de uma operação é apagado do repositório
- **THEN** a operação deixa de existir na plataforma, e o recurso permanece com as demais

#### Scenario: T11 - append soma ao herdado em vez de substituí-lo
- **WHEN** uma operação com `inherit: true` que herda N itens ganha um item no repositório
- **THEN** o fluxo próprio da operação passa a ter N+1 itens — os herdados materializados mais o
  declarado ao final — e MUST NOT ficar com apenas o item declarado

#### Scenario: T12 - restaurar a herança e acrescentar na mesma declaração
- **WHEN** uma operação com lista própria obsoleta passa a declarar `inherit: true` com um item
- **THEN** a releitura mostra o fluxo do escopo acima mais esse item, sem nenhum vestígio da lista
  obsoleta

#### Scenario: Conferência compara contagens por escopo
- **WHEN** a publicação é aceita e a conferência pós-publicação roda
- **THEN** ela compara operações enviadas contra presentes, interceptors da raiz enviados contra
  presentes e recursos enviados contra presentes, e qualquer divergência é tratada como falha

#### Scenario: Baseline restaurado ao fim da bateria
- **WHEN** todos os cenários terminam
- **THEN** o estado da API é idêntico ao baseline capturado antes da primeira escrita

### Requirement: Completeness is informational in sen validate

A E4 SHALL reportar o percentual de completeness e a lista de issues da revisão, reusando o serviço
existente. O gate de 70% MUST NOT bloquear o `sen validate`, porque a Draft não é ambiente: a trava
pertence à publicação em DEV ou superior.

#### Scenario: Completeness baixa não derruba o comando
- **WHEN** a revisão alvo tem completeness de 42% e a publicação foi aceita
- **THEN** a saída mostra `42%` com a lista de issues e o comando encerra com `exit 0`
