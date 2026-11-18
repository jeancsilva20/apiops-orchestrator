## ADDED Requirements

### Requirement: Contract stage in sen validate

O `sen validate` SHALL validar o contrato declarado antes de qualquer escrita e, depois da gravação e
da conferência do fluxo, gravar o contrato no swagger da mesma revisão — a Draft fora da esteira, a de
`TARGET_REVISION_NUMBER` na esteira. A etapa SHALL rodar antes do completeness.

#### Scenario: Ordem das etapas
- **WHEN** o repositório declara um contrato válido
- **THEN** o comando grava a revisão, confere o fluxo, grava o swagger, confere o contrato e só então calcula o completeness

#### Scenario: Contrato inválido não grava nada
- **WHEN** uma operação referencia um schema inexistente
- **THEN** o comando sai com exit 1 antes da confirmação, sem PUT da revisão nem do swagger

### Requirement: Documentation outcome in the result

O `-o` SHALL trazer `documentation` com `status` (`updated`, `unchanged` ou `not_updated`) e `reason`;
o motivo de não gravar ou de divergir SHALL também aparecer em `achados` como `WARNING`. O texto SHALL
mostrar "Documentação atualizada" com sim, não ou sem mudança, e o motivo. `unchanged` SHALL valer só
quando a documentação lida antes de qualquer gravação é a mesma de depois.

#### Scenario: Contrato igual ao do Manager
- **WHEN** a documentação do repositório já é a do swagger da revisão antes da execução
- **THEN** o swagger não é gravado e o `-o` traz `documentation: {status: unchanged, reason: null}`

#### Scenario: Documentação levada pela gravação da revisão
- **WHEN** o dev muda só a `description` de uma rota sem `summary`, e o PUT da revisão já deixa o swagger igual ao repositório
- **THEN** o swagger não é gravado de novo e o `-o` traz `documentation.status: updated`

#### Scenario: Manager recusa o swagger
- **WHEN** o PUT do swagger é recusado com motivo
- **THEN** o `-o` traz `documentation.status: not_updated` com o motivo em `reason` e em `achados`, e o comando sai com exit 0

### Requirement: Confirmation shows what leaves the documentation

Fora da esteira, a confirmação SHALL dizer que o swagger da revisão também será gravado e SHALL listar
o que sai da documentação do Manager: por operação, por componente e na raiz. SHALL trazer também as
descrições abaixo do mínimo do completeness. Se o swagger estiver em Swagger 2.0, SHALL dizer que o
contrato não será gravado e o fluxo será.

#### Scenario: Respostas que vão sumir
- **WHEN** o Manager documenta respostas em `GET /tarefas` e o repositório não as declara
- **THEN** a confirmação lista `GET /tarefas · responses` entre o que sai do Manager, antes do s/n, e o resultado local não repete o aviso

#### Scenario: Descrição curta avisada antes de gravar
- **WHEN** uma resposta do repositório tem descrição de até 4 caracteres
- **THEN** a confirmação lista o arquivo e a resposta antes do s/n, e nem o resultado nem o `-o` da esteira trazem o aviso

### Requirement: Documentation warnings are not repeated

Os avisos da confirmação MUST NOT se repetir no resultado local. Na esteira, o que sai da documentação
SHALL ir para `achados`; as descrições curtas não, porque as sugestões do completeness já as listam.

#### Scenario: Esteira com descrição curta e documentação removida
- **WHEN** a esteira roda o `sen validate` com uma resposta curta e uma resposta que só o Manager tem
- **THEN** `achados` lista a resposta que sai da documentação e não lista a descrição curta

#### Scenario: Dev cancela
- **WHEN** o dev responde "não" na confirmação
- **THEN** nem a revisão nem o swagger são gravados, e o comando sai com exit 130
