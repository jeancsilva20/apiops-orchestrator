## ADDED Requirements

### Requirement: Comando `sen whoami`

A CLI SHALL disponibilizar o comando `sen whoami`, que lê a sessão persistida pelo `sen login` e exibe os dados dela. O comando MUST NOT fazer chamada de rede e MUST NOT exigir o arquivo `.sen` nem as variáveis do bloco de credenciais. Ele SHALL ler a sessão na mesma pasta usada pelos demais comandos. O comando SHALL aceitar `--output` / `-o` com `text` (padrão), `json` e `yaml`. Nenhuma saída MUST conter valor de token, `tokenType` ou `expiresIn`.

#### Scenario: Sessão developer

- **WHEN** o usuário executa `sen whoami` com uma sessão `developer` válida
- **THEN** a CLI exibe um painel com usuário (nome e e-mail), perfil, grupos, escopo e validade em UTC, e encerra com exit code `0`

#### Scenario: Sessão super-admin

- **WHEN** o usuário executa `sen whoami` com uma sessão `super-admin` válida
- **THEN** a CLI exibe perfil, escopo e validade, sem identidade pessoal, e encerra com exit code `0`

#### Scenario: Modo estruturado (developer)

- **WHEN** o usuário executa `sen whoami -o json` com uma sessão `developer` válida
- **THEN** a saída é só o documento com `schema: apiops.sen-whoami/v1`, `authenticated: true`, `profile`, `user.name`, `user.email`, `groups`, `scope` e `expiresAt` em ISO-8601 UTC, nessa ordem, sem elementos visuais

#### Scenario: Modo estruturado (super-admin)

- **WHEN** o usuário executa `sen whoami -o yaml` com uma sessão `super-admin` válida
- **THEN** a saída é só o documento com `schema: apiops.sen-whoami/v1`, `authenticated: true`, `profile`, `scope` e `expiresAt`, sem identidade pessoal

#### Scenario: Sem sessão válida

- **WHEN** o usuário executa `sen whoami` e a sessão não existe, expirou ou não pode ser lida
- **THEN** a CLI informa "Nenhuma sessão válida: faça `sen login`." no modo `text`, ou emite `{schema: apiops.sen-whoami/v1, authenticated: false}` no modo estruturado, e encerra com exit code `1`

#### Scenario: Configuração ausente

- **WHEN** o usuário executa `sen whoami` sem `.sen` e sem as variáveis `AUTH_HOST` e `AUTH_LOGIN_PATH`
- **THEN** o comando lê a sessão normalmente, sem erro de configuração
