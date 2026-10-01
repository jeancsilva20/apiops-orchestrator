## Purpose

Define o contrato do comando `sen login` da CLI: autenticar o executor junto à Orchestrator Auth API usando uma única credencial Basic (`SEN_CREDENTIALS`, enviada intacta) contra um endpoint configurável e persistir a sessão resultante em arquivo oculto local, legível por execuções posteriores da aplicação. É a primeira fase da autenticação — nada do fluxo LEGACY existente é alterado, e guard/autorização por ação ficam para as fases seguintes.

## ADDED Requirements

### Requirement: Comando `sen login`

A CLI SHALL disponibilizar o comando `sen login`, que realiza a autenticação contra a Orchestrator Auth API usando a credencial configurada, persiste a sessão obtida em arquivo local e encerra com exit code `0` em caso de sucesso. Falhas SHALL resultar em erro categorizado com exit code diferente de `0`.

#### Scenario: Login bem-sucedido

- **WHEN** o usuário executa `sen login` com credencial válida e a API de autenticação responde com uma sessão válida
- **THEN** a CLI exibe um resumo da sessão (username, e-mail, grupos e prazo de expiração) sem exibir qualquer valor de token ou segredo, grava a sessão em arquivo local e encerra com exit code `0`

#### Scenario: Credencial não encontrada

- **WHEN** o comando é executado e a credencial Basic não está disponível (variável ausente ou vazia)
- **THEN** o login falha com erro categorizado informando que a credencial não foi encontrada, **antes de qualquer chamada de rede**, e encerra com exit code diferente de `0`

#### Scenario: Falha na chamada de autenticação

- **WHEN** a API de autenticação responde com erro HTTP (ex.: 401/403/5xx) ou a conexão falha
- **THEN** o comando falha com erro categorizado pelo tipo de falha (credencial recusada vs. indisponibilidade), usando o tratamento de erros existente da infraestrutura HTTP com o relato de corpo de resposta **suprimido** (nenhum JSON/corpo cru da resposta é exibido), e encerra com exit code diferente de `0`, sem escrever arquivo de sessão

### Requirement: Credencial Basic como única fonte

A credencial de login SHALL ter como única fonte o valor da variável **`SEN_CREDENTIALS`** (blob `Base64(client_id:secret)`), enviado **intacto** no cabeçalho de autenticação da requisição (decodificação server-side, conforme ADR 0001). Nenhum fallback — inclusive o par legado `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET` — SHALL ser utilizado pelo `sen login`.

#### Scenario: `SEN_CREDENTIALS` definida

- **WHEN** a variável `SEN_CREDENTIALS` possui valor não vazio
- **THEN** seu valor é enviado intacto no cabeçalho da requisição de login

#### Scenario: Ausência de `SEN_CREDENTIALS` com par legado presente

- **WHEN** `SEN_CREDENTIALS` está ausente ou vazia, mesmo que `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET` estejam definidos
- **THEN** o login falha com erro de credencial não encontrada antes de rede — o par legado não é consultado nem montado pela CLI do `sen login` (ele permanece restrito ao fluxo LEGACY existente, que não é tocado por este comando)

#### Scenario: Nenhum valor sensível utilizado além da credencial

- **WHEN** o comando monta a requisição de login
- **THEN** a única origem de dado sensível é `SEN_CREDENTIALS` (mais o endpoint configurável); nenhuma credencial é materializada a partir de outra variável ou armazenamento

### Requirement: Endpoint de autenticação parametrizável

A URL da requisição de login SHALL ser construída exclusivamente a partir das variáveis de configuração `AUTH_HOST` e `AUTH_LOGIN_PATH`, **ambas obrigatórias, sem fallback para o host geral (`HOST`) e sem default de path em código** — nada fixado no código-fonte. Valores de login não configurados SHALL produzir erro antes de qualquer chamada de rede.

#### Scenario: Configuração completa

- **WHEN** `AUTH_HOST` e `AUTH_LOGIN_PATH` estão configurados
- **THEN** a requisição de login é feita em `{AUTH_HOST}/{AUTH_LOGIN_PATH}` (ex.: `https://api-consulting.sensedia.com/cli-2/orq-auth/v1/oauth2/token`)

#### Scenario: Override por ambiente

- **WHEN** `AUTH_HOST` e/ou `AUTH_LOGIN_PATH` apontam para outro ambiente (QA, HMG)
- **THEN** a requisição utiliza exatamente esses valores, sem nenhum fallback implícito

#### Scenario: Variável de endpoint não configurada

- **WHEN** `AUTH_HOST` (ou `AUTH_LOGIN_PATH`) está ausente ou vazio/em branco
- **THEN** o comando falha com erro antes de qualquer chamada de rede e exit code diferente de `0`

### Requirement: Sessão persistida em arquivo e legível por execuções posteriores

A sessão SHALL ser persistida em um **arquivo oculto** (nome iniciado por ponto) no diretório temporário do sistema operacional, com escrita atômica (arquivo provisório + renomeação) e permissões restritivas ao usuário corrente. O arquivo SHALL conter `access_token`, `token_type`, `expires_at` (calculado a partir de `expires_in` no momento da recepção), `user_groups`, `user_email` e `username`, de modo que execuções subsequentes da aplicação consigam carregar e avaliar a sessão.

#### Scenario: Escrita segura com conteúdo completo

- **WHEN** o login é concluído com sucesso
- **THEN** o arquivo de sessão é criado via escrita atômica (não é possível observar arquivo parcialmente escrito), o nome inicia com ponto, as permissões restringem leitura ao usuário corrente e o conteúdo contém todos os campos listados, incluindo `expires_at`

#### Scenario: Leitura por execução posterior

- **WHEN** a aplicação inicia uma execução subsequente e existe arquivo de sessão com `expires_at` maior que o instante atual
- **THEN** a sessão é carregável pelo mecanismo de persistência fornecido por esta mudança (contendo os mesmos campos gravados)

#### Scenario: Sessão expirada tratada como ausente

- **WHEN** uma execução subsequente lê o arquivo e `expires_at` ≤ instante atual
- **THEN** a sessão é tratada como ausente (não utilizável), sem ressurreição de token

#### Scenario: Substituição de sessão anterior

- **WHEN** já existe arquivo de sessão de um login anterior e um novo `sen login` é concluído com sucesso
- **THEN** o arquivo existente é substituído pela nova sessão sem resíduos de arquivos provisórios

#### Scenario: Falha de escrita

- **WHEN** ocorre erro de I/O ao persistir (diretório inexistente, sem permissão, disco cheio)
- **THEN** o comando falha com erro categorizado indicando o problema de persistência, sem expor o conteúdo da sessão, e encerra com exit code diferente de `0`

### Requirement: Logs e saídas no padrão existente, sem segredos

O `sen login` SHALL seguir os padrões atuais da aplicação: tratamento de requisições via infraestrutura HTTP compartilhada (retries, RFC 7807), logs no padrão de observabilidade existente e saída Rich. Em todas as fases (montagem, requisição, persistência, relato final e erros), nenhum fragmento da credencial ou do token SHALL aparecer na saída padrão, saída de erro ou logs — inclusive em modo `--verbose`.

#### Scenario: Sucesso sem vazamento

- **WHEN** o login é executado com `--verbose` habilitado
- **THEN** nenhuma linha de saída ou de log contém o valor da credencial ou do token; os logs seguem o formato do padrão de observabilidade existente (eventos nomeados de autenticação)

#### Scenario: Erro sem vazamento

- **WHEN** o login falha em qualquer etapa (rede, protocolo, persistência)
- **THEN** as mensagens de erro identificam a categoria e, no máximo, metadados seguros (status HTTP, etapa da falha), nunca o conteúdo do cabeçalho de credencial ou do token
