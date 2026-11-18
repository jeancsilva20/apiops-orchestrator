## ADDED Requirements

### Requirement: Ruler resolution depends on execution mode

O id da régua SHALL vir de `spec.template` no `api-basic-info.yaml` quando `EXECUTION_MODE=local`, e
de variável de ambiente alimentada pelo cofre quando `EXECUTION_MODE=pipeline`, de modo que o valor
fique fora do alcance de um commit. Em modo `pipeline`, divergência entre a variável e `spec.template`
SHALL fazer a variável vencer, com `WARNING` apontando a divergência. A leitura da régua SHALL custar
**um único** `GET /apis/{id}`, porque `lastRevision` já devolve o fluxo completo com `content`.

#### Scenario: Esteira ignora o manifesto
- **WHEN** `EXECUTION_MODE=pipeline`, a variável aponta para `414` e o YAML declara `999`
- **THEN** a régua lida é a `414` e um `WARNING` registra a divergência

#### Scenario: Uma chamada basta
- **WHEN** a régua é resolvida
- **THEN** o comando emite `GET /apis/{id}` e NÃO emite `GET /revisions/{id}` para obter o fluxo

### Requirement: Unreachable or absent ruler aborts

A régua inalcançável SHALL abortar a operação, nos dois modos de execução, qualquer que seja a causa:
`404` de id inexistente, `403` de permissão ou sessão, ou falha de rede. `spec.template` vazio SHALL
igualmente abortar, com orientação de procurar o administrador. Como a plataforma devolve `403` tanto
para sessão expirada quanto para id de outro tenant, a mensagem MUST nomear as duas possibilidades em
vez de escolher uma.

#### Scenario: Id inexistente aborta
- **WHEN** a régua configurada aponta para um id que responde `404`
- **THEN** o comando aborta com `exit 1`, sem prosseguir para a publicação

#### Scenario: Mensagem do 403 não escolhe causa
- **WHEN** o `GET` da régua responde `403`
- **THEN** a mensagem cita tanto sessão expirada quanto id fora do tenant como causas possíveis

### Requirement: Conformance compares sequence and content

O comparador SHALL percorrer todos os caminhos de execução e comparar o fluxo efetivo com a régua por
**sequência**, não por conjunto, de modo que um item acrescentado de tipo já existente na régua seja
detectado. Para tipos nativos, o comparador MUST comparar o `content`, normalizando previamente
escalar numérico, já que o wire devolve valores como `"1000"` em string. Para interceptors `Custom`,
o casamento MUST ser por `customInterceptorId`, e o `content` MUST NOT ser comparado, porque o mesmo
id designa o mesmo objeto no tenant. Interceptors fora de `FIRST` e `SECOND` MUST ser ignorados.

#### Scenario: Diferença só no content é detectada
- **WHEN** a rota tem um `Log` com `encryptContent: true` e a régua tem o mesmo `Log` com `false`
- **THEN** o comparador produz um achado para esse item

#### Scenario: Custom casa por id
- **WHEN** a rota e a régua referenciam o mesmo `customInterceptorId`
- **THEN** os itens são considerados equivalentes, sem comparar o script

#### Scenario: Normalização evita falso achado
- **WHEN** a régua traz `quota` como `"1000"` e o repositório traz `1000`
- **THEN** nenhum achado é produzido para esse campo

### Requirement: Conformance findings inform and never block

Os achados SHALL ser classificados como `INFO` para acréscimo ao fluxo e `WARNING` para override,
remoção ou alteração, e MUST NOT bloquear a publicação: o dev decide subir algo fora do padrão. A
raiz da revision MUST ser comparada item a item com a régua, nunca tratada como acréscimo, porque não
herda de nenhum escopo. O comparador também SHALL validar tipo e preenchimento do interceptor contra
a régua, pelo mesmo regime de severidade.

#### Scenario: Achados não derrubam o comando
- **WHEN** o comparador produz um `INFO` e três `WARNING`
- **THEN** os achados aparecem na saída e o comando segue para a publicação

#### Scenario: Raiz não é tratada como append
- **WHEN** a raiz da revision difere da régua
- **THEN** a diferença é reportada como alteração, e não como acréscimo

### Requirement: Override drift is reported

Quando um escopo reproduz o fluxo do pai para suprimir itens, o comparador SHALL compará-lo também
com o fluxo do pai e emitir `WARNING` quando a diferença for maior do que a supressão declarada, de
modo que a cópia congelada não derive em silêncio à medida que o fluxo do pai evolui.

#### Scenario: Pai evoluiu e o override ficou para trás
- **WHEN** a rota declara `inherit: false` com oito itens para suprimir um, e o pai passou a ter dez
- **THEN** o comparador emite `WARNING` informando que o override omite mais itens do que a supressão
  declarada

### Requirement: Referenced Custom interceptor must exist in the tenant

O comando SHALL verificar que todo `Custom` referenciado pelo repositório existe no tenant. Id
inexistente SHALL abortar a operação, nomeando o id. O comando MUST NOT repor o conteúdo do
interceptor a partir de outra revisão da própria API, e MUST NOT descartar o item em silêncio.

#### Scenario: Custom apagado aborta
- **WHEN** o repositório referencia um `Custom` cujo `GET` responde `404`
- **THEN** o comando aborta com `exit 1`, nomeando o id, sem publicar

#### Scenario: Nenhuma ressurreição
- **WHEN** o conteúdo do `Custom` apagado existe em uma revisão antiga da mesma API
- **THEN** o comando ainda assim aborta, em vez de republicar o conteúdo recuperado
