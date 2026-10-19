## MODIFIED Requirements

### Requirement: Comando `sen login`

A CLI SHALL disponibilizar o comando `sen login`, que realiza a autenticação contra a Orchestrator Auth API usando a credencial configurada, valida a resposta de acordo com o perfil devolvido pela rota, persiste a sessão obtida em arquivo local e encerra com exit code `0` em caso de sucesso. Falhas SHALL resultar em erro categorizado com exit code diferente de `0`. O comando SHALL aceitar `--output` / `-o` com `text` (padrão), `json` e `yaml`. Em `json`/`yaml` a saída MUST conter só o documento `apiops.sen-login/v1`, sem logo, animação ou painel, e MUST NOT conter valor de token ou segredo.

#### Scenario: Login bem-sucedido

- **WHEN** o usuário executa `sen login` com credencial válida e a API de autenticação responde com uma sessão válida para o perfil autenticado (`developer` ou `super-admin`)
- **THEN** a CLI exibe um resumo da sessão adequado ao perfil — para `developer`: username, e-mail e prazo de expiração, sem exibir grupos; para `super-admin`: perfil e escopo — sem exibir qualquer valor de token ou segredo (incluindo `admin_access_token`), grava a sessão em arquivo local — incluindo `profile` e `scope` — e encerra com exit code `0`

#### Scenario: Login em modo estruturado (developer)

- **WHEN** o usuário executa `sen login -o json` com credencial válida e o perfil autenticado é `developer`
- **THEN** a saída é só o documento com `schema: apiops.sen-login/v1`, `authenticated: true`, `user.name`, `user.email` e `expiresAt` em ISO-8601 UTC, sem grupos, sem token e sem elementos visuais, e o comando encerra com exit code `0`

#### Scenario: Login em modo estruturado (super-admin)

- **WHEN** o usuário executa `sen login -o yaml` com credencial válida e o perfil autenticado é `super-admin`
- **THEN** a saída é só o documento com `schema: apiops.sen-login/v1`, `authenticated: true`, `profile`, `scope` e `expiresAt`, sem identidade pessoal, sem token e sem elementos visuais

#### Scenario: Credencial não encontrada

- **WHEN** o comando é executado e a credencial Basic não está disponível (variável ausente ou vazia)
- **THEN** o login falha com erro categorizado informando que a credencial não foi encontrada, **antes de qualquer chamada de rede**, e encerra com exit code diferente de `0`

#### Scenario: Falha na chamada de autenticação

- **WHEN** a API de autenticação responde com erro HTTP (ex.: 401/403/5xx) ou a conexão falha
- **THEN** o comando falha com erro categorizado pelo tipo de falha (credencial recusada vs. indisponibilidade), usando o tratamento de erros existente da infraestrutura HTTP com o relato de corpo de resposta **suprimido** (nenhum JSON/corpo cru da resposta é exibido), e encerra com exit code diferente de `0`, sem escrever arquivo de sessão
