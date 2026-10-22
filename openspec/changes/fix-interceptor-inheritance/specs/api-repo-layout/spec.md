## MODIFIED Requirements

### Requirement: Inheritance regime of interceptor flows

Os fluxos SHALL ser declarados em `interceptors_request` e `interceptors_response`, cuja ordem na
lista é a fonte declarativa da ordem de execução dentro do escopo. As chaves `position`,
`executionPoint` e `status` MUST NOT aparecer no YAML. Um interceptor `Custom` SHALL ser referenciado
por `id` numérico.

O que cada escopo executa SHALL ser decidido pelo **repositório**, descendo `all.yaml` →
`resource.yaml` → arquivo de operação, e MUST NOT depender do que a plataforma guardava no escopo. A
publicação SHALL seguir o modelo da plataforma: cada escopo guarda só os itens próprios e as
marcações `REMOVED` do que deixa de herdar, e executa o que o escopo acima executa, menos o marcado,
mais o próprio, com o herdado antes do próprio.

Com `inherit: true`, o escopo SHALL guardar só os itens declarados, sem cópia do herdado. Com
`inherit: false`, SHALL guardar os itens declarados e uma marcação para cada item que o escopo acima
executa, calculado a partir do próprio payload. A marcação de item que entra no escopo acima na mesma
publicação SHALL apontá-lo pelo número temporário do item, enviado em `id` e em `idTemp` como a UI
faz; esse número MUST ficar acima de qualquer id que a plataforma gere. Interceptors fora de `FIRST` e
`SECOND` MUST NOT receber marcação.

#### Scenario: Append guarda só o declarado
- **WHEN** uma rota que herda nove itens declara `inherit: true` e um item próprio
- **THEN** a rota é publicada com um item próprio e nenhuma marcação, e executa os nove herdados e
  depois o declarado

#### Scenario: Append nunca intercala com o herdado
- **WHEN** uma rota declara `inherit: true` com um item
- **THEN** o item executa depois de todo o fluxo herdado, qualquer que seja a sua `position`

#### Scenario: Restaurar a herança e acrescentar na mesma declaração
- **WHEN** uma rota com itens próprios e marcações obsoletas passa a declarar `inherit: true` com um item
- **THEN** a rota é publicada só com esse item, sem as marcações, e volta a executar o herdado

#### Scenario: Herança pura vai vazia no wire
- **WHEN** uma rota declara `inherit: true` sem itens
- **THEN** a lista publicada é vazia, de modo que uma mudança posterior no `all.yaml` a alcance

#### Scenario: Quebrar a herança marca o que o escopo acima executa
- **WHEN** um recurso marca dois itens da raiz e tem um item próprio, e uma rota dele declara
  `inherit: false` com outro item
- **THEN** a rota é publicada com o item declarado e uma marcação só, para o item do recurso, e
  executa só o declarado

#### Scenario: Item novo no all.yaml sob escopo que quebra
- **WHEN** o `all.yaml` ganha um item e uma rota declara `inherit: false`
- **THEN** a mesma publicação leva a marcação desse item na rota, apontando-o pelo `idTemp`, e a rota
  não o executa

#### Scenario: Ordem vem da lista
- **WHEN** a lista declara `Log` antes de `Payload size`
- **THEN** a ordem de execução publicada respeita a sequência da lista, sem `position` no YAML

### Requirement: Tombstone is expressed as the complete explicit list

A remoção de um item herdado SHALL ser expressa reproduzindo no YAML **o fluxo completo que vale**,
com `inherit: false`. O layout MUST NOT depender de comentário para expressar remoção, porque
comentário não é publicável e o round-trip se perde. Uma lista vazia com `inherit: true` MUST ser
entendida como herança. Uma lista vazia com `inherit: false` MUST ser entendida como escopo que não
executa nenhum interceptor, e SHALL ser publicada como uma marcação para cada item herdado, sem itens
próprios.

#### Scenario: Remover um item herdado
- **WHEN** a rota herda nove itens e precisa deixar de executar um deles
- **THEN** o YAML declara `inherit: false` com os oito itens restantes, e a rota executa exatamente
  esses oito

#### Scenario: Rota sem interceptors
- **WHEN** uma rota declara `inherit: false` sem nenhum item
- **THEN** a rota é publicada com uma marcação para cada item herdado e nenhum item próprio, não
  executa nenhum interceptor, e o comando não emite aviso de remoção não representável

### Requirement: Flow removals caused by the repository are reported

O comando SHALL emitir `WARNING` nomeando o fluxo que sai sempre que a publicação **remover** fluxo
que existe na plataforma, e MUST NOT fazê-lo em silêncio. São três os casos: itens próprios de um
escopo que passa a só herdar; herdado que um escopo executa hoje e deixa de executar porque o arquivo
declara `inherit: false`; e `all.yaml` sem interceptors com a raiz remota populada — este último
porque a raiz não herda de nenhum escopo acima, de modo que esvaziá-la remove o fluxo de que todos os
outros escopos dependem.

O segundo caso MUST considerar só o escopo que existe no Manager e só o item herdado que continua no
escopo acima depois da publicação. Item que sai do próprio escopo acima MUST NOT ser reportado nos
escopos que o herdam. O comando MUST NOT avisar quando marcações saem e o herdado volta a executar.

#### Scenario: Lista própria cede lugar à herança
- **WHEN** uma rota com itens próprios passa a declarar `inherit: true` sem itens
- **THEN** o comando avisa que os itens próprios serão removidos, nomeia-os e sugere listá-los no
  arquivo para mantê-los

#### Scenario: Escopo deixa de executar herdado
- **WHEN** uma rota que hoje executa dois itens herdados, sem marcação, passa a declarar
  `inherit: false` com um item próprio
- **THEN** o comando avisa que a rota deixa de executar esses dois itens, nomeando-os

#### Scenario: Repositório importado com a regra antiga
- **WHEN** o arquivo de uma rota foi importado com `inherit: false` e os itens próprios, e no Manager
  a rota executa o herdado mais esses itens
- **THEN** o comando avisa quais itens herdados a rota deixa de executar ao publicar

#### Scenario: Item tirado do all.yaml não é reportado nas rotas
- **WHEN** o `all.yaml` deixa de declarar um item e uma rota com `inherit: false` o marcava
- **THEN** o comando não emite o aviso de herdado cortado para essa rota

#### Scenario: Raiz esvaziada é avisada
- **WHEN** o `all.yaml` não declara interceptors e a raiz remota tem itens
- **THEN** o comando avisa que o fluxo raiz será removido, com ele o que todo escopo herdava
