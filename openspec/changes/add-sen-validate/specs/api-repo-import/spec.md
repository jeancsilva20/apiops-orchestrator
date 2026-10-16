## ADDED Requirements

### Requirement: Import materializes the canonical tree from Manager state

O importador SHALL ler o estado da API no Manager e materializar o repositório na árvore canônica,
sem versionar identificadores que a plataforma gera. O resultado MUST ser determinístico: reexecutar
o import sobre o mesmo estado remoto MUST produzir árvore idêntica, byte a byte, para servir de
oracle de regressão.

#### Scenario: Import determinístico
- **WHEN** o importador roda duas vezes sobre o mesmo estado remoto
- **THEN** as duas árvores geradas são idênticas

#### Scenario: Oracle das APIs reais
- **WHEN** o importador roda sobre as seis APIs reais do conjunto de referência
- **THEN** os 155 arquivos YAML resultantes batem com a saída de referência

### Requirement: Folder and file naming with disambiguation and budget

O importador SHALL derivar o nome do diretório do recurso por slug, com limite de 60 caracteres, e o
nome do arquivo da operação por `<método>_<path>`, com limite de 90 caracteres. Colisões SHALL ser
desambiguadas de forma legível, e o truncamento SHALL preservar uma marca determinística derivada das
operações. O importador MUST distinguir, na mensagem, colisão por nome idêntico de colisão por
truncamento.

#### Scenario: Colisão por truncamento é anunciada
- **WHEN** dois recursos produzem o mesmo slug após truncamento
- **THEN** o importador desambigua os diretórios e informa que a colisão veio de truncamento, não de
  nome idêntico

### Requirement: Serialization preserves YAML-hostile scalars

O importador SHALL citar escalares iniciados por indicador YAML (`*`, `&`, `!`, `|`, `>`, `%`, `@`,
crase, `[`, `{`, `,`, `?`), porque valores como `replaceChar: *****` quebram o parse. Strings
numéricas vindas do wire, como `"1000"`, SHALL ser preservadas como string citada, para que o
round-trip não as converta em inteiro.

#### Scenario: Indicador YAML citado
- **WHEN** o wire traz `replaceChar` com valor iniciado por asterisco
- **THEN** o YAML gerado cita o valor, e a releitura do arquivo devolve o mesmo escalar

#### Scenario: String numérica preservada
- **WHEN** o wire traz `quota` como a string `"1000"`
- **THEN** o YAML gerado mantém `"1000"` citado, e não o inteiro `1000`

### Requirement: Import partitions governed from preserved state

O importador SHALL particionar os interceptors remotos entre **governados**, nos execution points
`FIRST` e `SECOND`, e **preservados**, em qualquer outro ponto. O estado preservado MUST retornar
intacto na publicação e MUST NOT ser objeto de conformidade. Estado remoto que o layout não consiga
representar SHALL produzir falha alta no import, em vez de ser gravado de forma aproximada.

#### Scenario: Estado não governado volta intacto
- **WHEN** a revisão remota tem interceptors fora de `FIRST` e `SECOND`
- **THEN** eles não aparecem no YAML, não entram na conformidade, e retornam sem alteração na
  publicação

#### Scenario: Não representável falha alto
- **WHEN** o estado remoto contém construção que o layout não expressa
- **THEN** o import falha com mensagem que nomeia a construção, em vez de gravar aproximação

### Requirement: Import materializes removals as complete explicit lists

Quando o estado remoto indicar que um escopo deixa de executar um item herdado, o importador SHALL
gravar `inherit: false` com **a lista completa** dos itens que valem. O importador MUST NOT registrar
a remoção apenas em comentário, porque comentário não é publicável e a republicação perderia a
remoção.

Pela mesma razão, todo escopo cuja lista remota não seja vazia SHALL ser materializado com
`inherit: false` e a lista completa, mesmo quando ela não reproduza nenhum item herdado. A lista
própria não vazia **é** o fluxo inteiro do escopo (W-4): gravar `inherit: true` ali afirmaria
"herdado + próprio" sobre um escopo que executa só o próprio, e a republicação — que resolve o fluxo
a partir do repositório — mudaria o fluxo sem ninguém ter pedido.

#### Scenario: Remoção vira lista, não comentário
- **WHEN** uma rota remota executa oito dos nove itens herdados
- **THEN** o arquivo da operação declara `inherit: false` com os oito itens, e nenhum comentário é a
  única fonte da remoção

#### Scenario: Lista própria disjunta do herdado não vira append
- **WHEN** uma rota remota tem um item próprio que não existe no fluxo herdado
- **THEN** o arquivo declara `inherit: false` com esse item e nomeia em comentário os herdados que a
  rota não executa, de modo que publicar o repositório de volta seja um no-op
