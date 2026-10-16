## ADDED Requirements

### Requirement: Canonical repository tree

O repositório de uma API SHALL seguir a árvore canônica: `api-basic-info.yaml` e `all.yaml` na raiz,
e um diretório por recurso em `resources/<slug>/` contendo `resource.yaml` e um arquivo por operação
nomeado `<método>_<path>.yaml`. O método da operação MUST ser derivado do nome do arquivo: o YAML da
operação MUST NOT declarar `method`. O repositório MUST NOT conter `bindings.json`, pastas de
revisions, `resources.yaml` ou OpenAPI versionado.

#### Scenario: Árvore reconhecida
- **WHEN** o importador materializa a API 417
- **THEN** a raiz contém `api-basic-info.yaml` e `all.yaml`, e cada recurso tem `resource.yaml` mais
  um arquivo por operação

#### Scenario: Método vem do nome do arquivo
- **WHEN** o arquivo se chama `get_tarefas_{id}.yaml`
- **THEN** o método resolvido é `GET` e o conteúdo do YAML não declara `method`

### Requirement: Root scope file and grammar

O arquivo do escopo raiz SHALL se chamar `all.yaml` e mapear para a raiz da revision. A gramática da
raiz MUST aceitar `destination`, `timeout`, `interceptors_request` e `interceptors_response`. A chave
`inherit` na raiz SHALL ser reportada como `INFO` e ignorada, porque a raiz não herda de nenhum
escopo. Na raiz, o valor vazio MUST ser expresso por omissão da chave, enquanto em recurso e operação
é expresso por `null`.

#### Scenario: Interceptors de resposta na raiz
- **WHEN** `all.yaml` declara `interceptors_response` com dois itens
- **THEN** os dois itens são reconhecidos no escopo raiz e publicados no execution point `SECOND`

#### Scenario: inherit na raiz é inerte
- **WHEN** `all.yaml` declara `inherit: true`
- **THEN** o comando emite `INFO` informando que a chave não se aplica à raiz e prossegue

### Requirement: Base files are mandatory by exact name

Os arquivos base `all.yaml`, na raiz, e `resource.yaml`, em cada diretório de recurso, SHALL ser
obrigatórios pelo nome exato. A ausência de qualquer um deles MUST abortar a operação na E1, antes de
qualquer chamada de rede. Arquivos `.yaml` não reconhecidos que convivam no repositório MUST NOT
derrubar a operação por si: a proteção vem da obrigatoriedade do nome, de modo que um erro de
digitação produz ausência, e ausência aborta.

#### Scenario: Erro de digitação aborta
- **WHEN** a raiz contém `alll.yaml` em vez de `all.yaml`
- **THEN** o comando aborta na E1, com `exit 1`, sem emitir chamada HTTP

#### Scenario: Arquivo não relacionado é tolerado
- **WHEN** a raiz contém `all.yaml` válido e também um `notas.yaml` de outra ferramenta
- **THEN** a descoberta prossegue normalmente

### Requirement: Inheritance regime of interceptor flows

Os fluxos SHALL ser declarados em `interceptors_request` e `interceptors_response`, cuja ordem na
lista é a fonte declarativa da ordem de execução. As chaves `position`, `executionPoint` e `status`
MUST NOT aparecer no YAML. Um interceptor `Custom` SHALL ser referenciado por `id` numérico.

O fluxo efetivo de um escopo SHALL ser resolvido a partir do **repositório**, descendo `all.yaml` →
`resource.yaml` → arquivo de operação, e MUST NOT depender do que a plataforma guardava no escopo.
Com `inherit: true`, o efetivo SHALL ser o fluxo do escopo acima **mais** os itens declarados. Com
`inherit: false`, SHALL ser exatamente o declarado. Quando o efetivo for idêntico ao do escopo acima,
a lista SHALL ir vazia no wire, preservando a propagação; nos demais casos SHALL ir completa.

#### Scenario: Append soma ao fluxo do pai segundo o repositório
- **WHEN** uma rota que herda nove itens declara `inherit: true` e um item próprio
- **THEN** o fluxo publicado tem os dez — os nove herdados, materializados a partir do repositório,
  mais o declarado ao final

#### Scenario: Restaurar a herança e acrescentar na mesma declaração
- **WHEN** uma rota com lista própria obsoleta passa a declarar `inherit: true` com um item
- **THEN** a lista obsoleta é descartada e o fluxo publicado é o do escopo acima mais o item

#### Scenario: Herança pura vai vazia no wire
- **WHEN** uma rota declara `inherit: true` sem itens
- **THEN** a lista publicada é vazia, de modo que uma mudança posterior no `all.yaml` a alcance

#### Scenario: Ordem vem da lista
- **WHEN** a lista declara `Log` antes de `Payload size`
- **THEN** a ordem de execução publicada respeita a sequência da lista, sem `position` no YAML

### Requirement: Tombstone is expressed as the complete explicit list

A remoção de um item herdado SHALL ser expressa reproduzindo no YAML **o fluxo completo que vale**,
com `inherit: false`. O layout MUST NOT depender de comentário para expressar remoção, porque
comentário não é publicável e o round-trip se perde. Uma lista vazia MUST ser entendida como herança,
nunca como ausência de fluxo: a plataforma não representa "rota que não executa nada".

#### Scenario: Remover um item herdado
- **WHEN** a rota herda nove itens e precisa deixar de executar um deles
- **THEN** o YAML declara `inherit: false` com os oito itens restantes, e a publicação reproduz
  exatamente esses oito

#### Scenario: Lista vazia herda
- **WHEN** uma rota declara `inherit: false` sem nenhum item
- **THEN** a plataforma mantém a herança, e o comando reporta a situação como remoção não
  representável em vez de tratar como fluxo vazio

### Requirement: Flow removals caused by the repository are reported

O comando SHALL emitir `WARNING` nomeando o fluxo que sai sempre que a resolução a partir do
repositório **remover** fluxo que existe na plataforma, e MUST NOT fazê-lo em silêncio. São três os casos: lista
própria substituída por herança pura, `inherit: false` sem itens, e `all.yaml` sem interceptors com a
raiz remota populada — este último porque a raiz não herda de nenhum escopo acima, de modo que
esvaziá-la remove o fluxo de que todos os outros escopos dependem.

#### Scenario: Lista própria cede lugar à herança
- **WHEN** uma rota com lista própria passa a declarar `inherit: true` sem itens
- **THEN** o comando avisa que a lista própria será removida e nomeia os itens que saem

#### Scenario: Raiz esvaziada é avisada
- **WHEN** o `all.yaml` não declara interceptors e a raiz remota tem itens
- **THEN** o comando avisa que o fluxo raiz será removido, com ele o que todo escopo herdava
