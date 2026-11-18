## ADDED Requirements

### Requirement: Contract stage in sen publish

O `sen publish` SHALL validar o contrato declarado antes de qualquer escrita e, depois da gravação e
da conferência do fluxo na revisão de `TARGET_REVISION_NUMBER`, gravar o contrato no swagger da mesma
revisão. O que sai da documentação do Manager e os problemas da plataforma SHALL aparecer em `avisos`.
O `-o` SHALL trazer `documentation` com `status` (`updated`, `unchanged` ou `not_updated`) e `reason`,
como no `sen validate`.

#### Scenario: Esteira com contrato válido
- **WHEN** a esteira roda `sen publish` com um contrato válido
- **THEN** a revisão alvo recebe o fluxo e o contrato, e o comando sai com exit 0

#### Scenario: Contrato inválido na esteira
- **WHEN** o repositório declara `requestBody` numa rota GET
- **THEN** o comando sai com exit 1 sem gravar a revisão nem o swagger

#### Scenario: Documentação apagada na esteira
- **WHEN** as rotas do repositório declaram só `responses: {'200': {description: OK}}` e o Manager tem documentação na revisão alvo
- **THEN** a documentação vai em branco e `avisos` lista o que saiu

#### Scenario: Repositório puxado antes do contrato
- **WHEN** o repositório não tem `responses` nas rotas
- **THEN** o comando sai com exit 1 antes de gravar a revisão
