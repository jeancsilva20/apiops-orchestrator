## MODIFIED Requirements

### Requirement: Post-publication verification treats HTTP 200 as inconclusive

Após a E3, o comando SHALL reler o estado publicado por `GET` e compará-lo com o enviado, em
operações (método e path), interceptors por escopo e recursos vazios. Divergência SHALL ser tratada
como **falha** com `exit 1`, ainda que a plataforma tenha respondido `200`. O comando MUST NOT
concluir sucesso apenas pelo código HTTP.

Os itens próprios de cada escopo, raiz incluída, SHALL ser comparados com o que o repositório declara
para o escopo — sem o herdado —, por tipo, ordem e `content` normalizado. As marcações `REMOVED`
SHALL ser comparadas pelo item herdado que removem, resolvido no fluxo do escopo acima de cada lado,
e MUST NOT ser comparadas pelo `parent.id`, porque a marcação enviada por `idTemp` é gravada com o id
que a plataforma gera.

#### Scenario: Item descartado sob HTTP 200
- **WHEN** o `PUT` responde `200` mas o `GET` posterior mostra um interceptor a menos do que o enviado
- **THEN** o comando reporta divergência de publicação e encerra com `exit 1`

#### Scenario: Marcação por idTemp não diverge
- **WHEN** a publicação marca numa rota um item que entrou no `all.yaml` no mesmo `PUT`, e o `GET`
  mostra a marcação apontando o id gerado para esse item
- **THEN** a conferência não reporta divergência para a marcação

#### Scenario: Marcação descartada pela plataforma
- **WHEN** a plataforma responde `200` e o `GET` não traz uma marcação enviada
- **THEN** o comando reporta que o item herdado continua executando no escopo e encerra com `exit 1`

### Requirement: Acceptance battery reproduces the proven platform behaviour

A implementação SHALL ser validada pela mesma bateria que validou o protótipo, registrada no
[caderno de testes](../../../../docs/feat-api-estructure/prova-fluxo-validate/CADERNO-DE-TESTES.md).
Cada cenário SHALL alterar o repositório, executar o comando, reler o estado por `GET` e restaurar o
baseline. O veredito SHALL vir da releitura, nunca do código HTTP. Ao fim da bateria, o estado da API
MUST ser idêntico ao baseline em nome, descrição, tags, `basePath`, recursos, operações e
interceptors. O que cada escopo executa é provado pela bateria de herança na API-lab; esta confere o
que cada escopo guarda.

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

#### Scenario: T06 - inherit false sem itens é rota sem interceptors
- **WHEN** um recurso e uma operação declaram `inherit: false` sem nenhum item
- **THEN** o recurso sobe com uma marcação para cada item da raiz e nenhum item próprio, a operação
  sobe sem itens próprios e sem marcações (o recurso não executa nada para ela herdar), e o comando
  não reporta remoção não representável

#### Scenario: T07 - interceptors no recurso não são copiados para as rotas
- **WHEN** o `resource.yaml` declara `inherit: false` com dois itens próprios
- **THEN** o recurso sobe com exatamente esses dois itens próprios e uma marcação para cada item da
  raiz, e as operações do recurso seguem com zero itens próprios, herdando por lista vazia

#### Scenario: T08 - interceptors declarados na operação sobem
- **WHEN** o arquivo de uma operação declara `inherit: false` com dois itens
- **THEN** a operação sobe com exatamente esses dois itens próprios e uma marcação para cada item que
  o recurso executa

#### Scenario: T10 - arquivo removido remove a rota
- **WHEN** o arquivo de uma operação é apagado do repositório
- **THEN** a operação deixa de existir na plataforma, e o recurso permanece com as demais

#### Scenario: T11 - append guarda só o item declarado
- **WHEN** uma operação com `inherit: true` que herda N itens ganha um item no repositório
- **THEN** a operação passa a guardar exatamente esse item, sem cópia dos N herdados e sem marcações

#### Scenario: T12 - restaurar a herança e acrescentar na mesma declaração
- **WHEN** uma operação com itens próprios obsoletos passa a declarar `inherit: true` com um item
- **THEN** a releitura mostra a operação guardando só esse item, sem nenhum vestígio dos obsoletos

#### Scenario: Conferência compara contagens por escopo
- **WHEN** a publicação é aceita e a conferência pós-publicação roda
- **THEN** ela compara operações enviadas contra presentes, interceptors da raiz enviados contra
  presentes e recursos enviados contra presentes, e qualquer divergência é tratada como falha

#### Scenario: Baseline restaurado ao fim da bateria
- **WHEN** todos os cenários terminam
- **THEN** o estado da API é idêntico ao baseline capturado antes da primeira escrita

## ADDED Requirements

### Requirement: Inheritance battery measures execution on the lab API

A herança SHALL ser validada também pelo que cada rota **executa**, numa bateria opt-in
(`APIOPS_BATERIA_425=1`) contra a API-lab 425 do consulting, que publica pelo `sen validate` e faz
deploy da Draft no ambiente 7. O veredito MUST vir do trace das chamadas, nunca do código HTTP nem só
do estado gravado.

#### Scenario: Append executa depois do herdado
- **WHEN** a raiz declara R1 e R2 e uma rota declara `inherit: true` com S2
- **THEN** o trace mostra três execuções, na ordem R1, R2, S2

#### Scenario: Quebra executa só o declarado
- **WHEN** uma rota declara `inherit: false` com S5
- **THEN** o trace mostra uma execução, S5

#### Scenario: Rota sem interceptors
- **WHEN** uma rota declara `inherit: false` sem itens
- **THEN** o trace mostra zero execuções

#### Scenario: Rota que quebra sob recurso que quebra
- **WHEN** um recurso declara `inherit: false` com C1, e uma rota dele declara `inherit: false` com C3
- **THEN** a rota executa só C3, e uma rota do mesmo recurso que só herda executa só C1

#### Scenario: Item novo no pai na mesma publicação
- **WHEN** o `all.yaml` ganha R3 e o `resource.yaml` de um recurso ganha C5, numa só publicação, com
  rotas que quebram sob a raiz e sob esse recurso
- **THEN** nenhuma dessas rotas executa o item novo, e uma rota que só herda executa R3

#### Scenario: Voltar a herdar
- **WHEN** uma rota com `inherit: false` passa a declarar `inherit: true` sem itens
- **THEN** a rota volta a executar o fluxo herdado

#### Scenario: Item tirado do pai
- **WHEN** o `all.yaml` deixa de declarar um item que rotas com `inherit: false` marcavam
- **THEN** a publicação é aceita sem divergência na conferência, e essas rotas seguem executando só o
  que declaram

### Requirement: Lab battery reads execution from the gateway trace

Os interceptors da bateria de herança SHALL ser `Header` que injetam `X-Lab-<rótulo>`, com destino
num serviço de eco. Para cada rota, a bateria SHALL ler o trace da última chamada (`GET /calls`,
`GET /calls/{id}`) e tirar dele o número de interceptors executados e a ordem dos rótulos. A bateria
SHALL fazer backup da revisão antes da primeira escrita e restaurá-la ao fim pelo swagger exportado.

#### Scenario: Execução contada pelo trace
- **WHEN** uma rota executa o mesmo interceptor duas vezes
- **THEN** o trace mostra duas execuções, ainda que o header do eco apareça uma vez só

#### Scenario: Revisão restaurada
- **WHEN** a bateria termina, com ou sem falha
- **THEN** a revisão da API-lab volta ao estado do backup
