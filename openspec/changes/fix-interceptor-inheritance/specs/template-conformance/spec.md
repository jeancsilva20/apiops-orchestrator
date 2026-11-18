## MODIFIED Requirements

### Requirement: Conformance compares sequence and content

O comparador SHALL percorrer todos os caminhos de execução e comparar o fluxo efetivo com a régua por
**sequência**, não por conjunto, de modo que um item acrescentado de tipo já existente na régua seja
detectado. O fluxo efetivo de cada escopo SHALL ser composto como a plataforma o executa: o do escopo
acima, menos os itens marcados como removidos no escopo, mais os itens próprios, nessa ordem. A
marcação SHALL ser reconhecida tanto pelo `parent.id` quanto pelo `parent.idTemp`, para que o
payload seja comparado antes de a plataforma gravá-lo.

Para tipos nativos, o comparador MUST comparar o `content`, normalizando previamente escalar
numérico, já que o wire devolve valores como `"1000"` em string. Para interceptors `Custom`, o
casamento MUST ser por `customInterceptorId`, e o `content` MUST NOT ser comparado, porque o mesmo id
designa o mesmo objeto no tenant. Interceptors fora de `FIRST` e `SECOND` MUST ser ignorados.

#### Scenario: Diferença só no content é detectada
- **WHEN** a rota tem um `Log` com `encryptContent: true` e a régua tem o mesmo `Log` com `false`
- **THEN** o comparador produz um achado para esse item

#### Scenario: Custom casa por id
- **WHEN** a rota e a régua referenciam o mesmo `customInterceptorId`
- **THEN** os itens são considerados equivalentes, sem comparar o script

#### Scenario: Normalização evita falso achado
- **WHEN** a régua traz `quota` como `"1000"` e o repositório traz `1000`
- **THEN** nenhum achado é produzido para esse campo

#### Scenario: Append é comparado com o herdado
- **WHEN** a raiz é igual à régua e uma rota declara `inherit: true` com um item a mais
- **THEN** o único achado da rota é o `INFO` de acréscimo desse item

#### Scenario: Rota sem interceptors
- **WHEN** uma rota declara `inherit: false` sem itens
- **THEN** a rota é comparada com fluxo vazio, e cada item da régua gera `WARNING` de ausente

## REMOVED Requirements

### Requirement: Override drift is reported

**Reason**: nunca foi ligado a nenhum comando. A situação que avisaria — escopo com
`inherit: false` que não recebe o que o escopo acima ganhou — é o efeito pedido pela declaração, e o
corte de herdado que o escopo executa hoje passa a ser avisado na publicação
(`api-repo-layout`, "Flow removals caused by the repository are reported").

**Migration**: nenhuma; `comparar_deriva_de_override` é removida junto com os seus testes.
