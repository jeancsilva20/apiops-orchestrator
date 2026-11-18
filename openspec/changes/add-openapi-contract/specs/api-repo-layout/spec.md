## ADDED Requirements

### Requirement: Optional components file

O repositório MAY ter `components.yaml` na raiz, com as seções `schemas`, `securitySchemes`,
`responses`, `requestBodies`, `headers` e `examples` do OpenAPI 3. A ausência MUST NOT impedir a
publicação: o arquivo não é obrigatório pelo nome, como `api-basic-info.yaml` e `all.yaml`. Outra
seção (`parameters`, `links`, `callbacks` ou desconhecida) MUST ser erro.

#### Scenario: Repositório sem components
- **WHEN** o repositório não tem `components.yaml` e nenhuma referência
- **THEN** a descoberta não aponta arquivo faltando e o comando segue

#### Scenario: Components reconhecido
- **WHEN** o repositório tem `components.yaml` na raiz
- **THEN** o arquivo é lido e não aparece entre os ignorados

#### Scenario: Seção de parâmetros reutilizáveis
- **WHEN** o `components.yaml` declara `parameters`
- **THEN** o comando sai com exit 1: o parâmetro é escrito por extenso na operação ou no `resource.yaml`

### Requirement: Contract fields per file

Os campos de contrato SHALL ficar no arquivo da sua granularidade, e MUST NOT alterar o que o fluxo de
interceptors, destinos e herança faz:

| Arquivo | Campos |
|---|---|
| `api-basic-info.yaml` (`spec`) | `contact`, `tags`, `security` |
| `resource.yaml` | `parameters` compartilhados por todas as rotas do recurso |
| `<metodo>_<path>.yaml` | `operationId`, `summary`, `tags`, `security`, `parameters`, `requestBody`, `responses` |

#### Scenario: Rota pública
- **WHEN** o arquivo de `GET /health-check` declara `security: []`
- **THEN** a rota é gravada sem requisito de segurança, sobrescrevendo o da raiz

### Requirement: Operation files declare responses

Todo arquivo de operação MUST declarar `responses`. Rota não documentada declara
`responses: {'200': {description: OK}}`, como o importador a puxa.

#### Scenario: Respostas apagadas
- **WHEN** o dev apaga o bloco `responses` de `post_tarefas.yaml`
- **THEN** o comando sai com exit 1 citando o arquivo, e nada é gravado

### Requirement: Platform-owned fields are not declared

`servers` e `info` MUST NOT ser declarados no repositório, e chaves `x-*` MUST NOT aparecer em nenhum
arquivo: vêm do Manager.

#### Scenario: Servidores no basic info
- **WHEN** o `api-basic-info.yaml` declara `spec.servers`
- **THEN** o comando sai com exit 1: `servers` vem do Manager
