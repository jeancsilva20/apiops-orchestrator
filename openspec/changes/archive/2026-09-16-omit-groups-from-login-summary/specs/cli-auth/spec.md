## MODIFIED Requirements

### Requirement: Comando `sen login`

A CLI SHALL disponibilizar o comando `sen login`, que realiza a autenticação contra a Orchestrator Auth API usando a credencial configurada, persiste a sessão obtida em arquivo local e encerra com exit code `0` em caso de sucesso. Falhas SHALL resultar em erro categorizado com exit code diferente de `0`.

#### Scenario: Login bem-sucedido

- **WHEN** o usuário executa `sen login` com credencial válida e a API de autenticação responde com uma sessão válida
- **THEN** a CLI exibe um resumo da sessão (username, e-mail e prazo de expiração) sem exibir grupos, sem exibir qualquer valor de token ou segredo, grava a sessão em arquivo local — incluindo `user_groups` — e encerra com exit code `0`

#### Scenario: Credencial não encontrada

- **WHEN** o comando é executado e a credencial Basic não está disponível (variável ausente ou vazia)
- **THEN** o login falha com erro categorizado informando que a credencial não foi encontrada, **antes de qualquer chamada de rede**, e encerra com exit code diferente de `0`

#### Scenario: Falha na chamada de autenticação

- **WHEN** a API de autenticação responde com erro HTTP (ex.: 401/403/5xx) ou a conexão falha
- **THEN** o comando falha com erro categorizado pelo tipo de falha (credencial recusada vs. indisponibilidade), usando o tratamento de erros existente da infraestrutura HTTP com o relato de corpo de resposta **suprimido** (nenhum JSON/corpo cru da resposta é exibido), e encerra com exit code diferente de `0`, sem escrever arquivo de sessão
