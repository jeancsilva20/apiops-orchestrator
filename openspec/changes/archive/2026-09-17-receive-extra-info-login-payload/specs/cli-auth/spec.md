# cli-auth — Delta (receive-extra-info-login-payload)

## MODIFIED Requirements

### Requirement: Comando `sen login`

A CLI SHALL disponibilizar o comando `sen login`, que realiza a autenticação contra a Orchestrator Auth API usando a credencial configurada, valida a resposta de acordo com o perfil devolvido pela rota, persiste a sessão obtida em arquivo local e encerra com exit code `0` em caso de sucesso. Falhas SHALL resultar em erro categorizado com exit code diferente de `0`.

#### Scenario: Login bem-sucedido

- **WHEN** o usuário executa `sen login` com credencial válida e a API de autenticação responde com uma sessão válida para o perfil autenticado (`developer` ou `super-admin`)
- **THEN** a CLI exibe um resumo da sessão adequado ao perfil — para `developer`: username, e-mail e prazo de expiração, sem exibir grupos; para `super-admin`: perfil e escopo — sem exibir qualquer valor de token ou segredo (incluindo `admin_access_token`), grava a sessão em arquivo local — incluindo `profile` e `scope` — e encerra com exit code `0`

#### Scenario: Credencial não encontrada

- **WHEN** o comando é executado e a credencial Basic não está disponível (variável ausente ou vazia)
- **THEN** o login falha com erro categorizado informando que a credencial não foi encontrada, **antes de qualquer chamada de rede**, e encerra com exit code diferente de `0`

#### Scenario: Falha na chamada de autenticação

- **WHEN** a API de autenticação responde com erro HTTP (ex.: 401/403/5xx) ou a conexão falha
- **THEN** o comando falha com erro categorizado pelo tipo de falha (credencial recusada vs. indisponibilidade), usando o tratamento de erros existente da infraestrutura HTTP com o relato de corpo de resposta **suprimido** (nenhum JSON/corpo cru da resposta é exibido), e encerra com exit code diferente de `0`, sem escrever arquivo de sessão

### Requirement: Sessão persistida em arquivo e legível por execuções posteriores

A sessão SHALL ser persistida em um **arquivo oculto** (nome iniciado por ponto) na **raiz do projeto** — o diretório raiz do repositório sobre o qual a aplicação está executando, derivado da configuração da aplicação (e não do diretório corrente do shell) —, com escrita atômica (arquivo provisório + renomeação) e permissões restritivas ao usuário corrente. O arquivo SHALL estar **excluído do rastreamento de versionamento** (ver requirement "Sessão excluída do rastreamento de versionamento"). O arquivo SHALL conter `access_token`, `token_type`, `expires_at` (calculado a partir de `expires_in` no momento da recepção), `profile`, `scope` e os campos condicionais do perfil (`user_groups`, `user_email`, `username` para `developer`) — mas **SHALL NOT conter `admin_access_token`**, que permanece disponível apenas em memória durante a execução corrente do perfil `super-admin`, de modo que execuções subsequentes da aplicação consigam carregar e avaliar a sessão.

#### Scenario: Escrita segura com conteúdo completo

- **WHEN** o login é concluído com sucesso
- **THEN** o arquivo de sessão é criado na raiz do projeto via escrita atômica (não é possível observar arquivo parcialmente escrito), o nome inicia com ponto, as permissões restringem leitura ao usuário corrente e o conteúdo contém todos os campos listados, incluindo `expires_at`, `profile` e `scope` — e **não contém** `admin_access_token`

#### Scenario: Local independente do diretório corrente

- **WHEN** o usuário executa `sen login` a partir de qualquer subdiretório do projeto (ex.: `src/`) ou de fora dele
- **THEN** a sessão é gravada na mesma **raiz do projeto** (configuração da aplicação), e não no diretório corrente

#### Scenario: Leitura por execução posterior

- **WHEN** a aplicação inicia uma execução subsequente e existe arquivo de sessão com `expires_at` maior que o instante atual
- **THEN** a sessão é carregável pelo mecanismo de persistência fornecido por esta mudança (contendo os mesmos campos gravados); para a sessão `super-admin` o `admin_access_token` não está disponível nesse carregamento, apenas os campos persistidos

#### Scenario: Sessão expirada tratada como ausente

- **WHEN** uma execução subsequente lê o arquivo e `expires_at` ≤ instante atual
- **THEN** a sessão é tratada como ausente (não utilizável), sem ressurreição de token

#### Scenario: Sessão legada ou com perfil desconhecido tratada como ausente

- **WHEN** uma execução subsequente lê um arquivo de sessão que não contém `profile` (formato anterior a este change) ou contém perfil desconhecido
- **THEN** a sessão é tratada como ausente (não utilizável) e o próximo fluxo que a exigir executa o re-login, em vez de transitar sessão malformada

#### Scenario: Substituição de sessão anterior

- **WHEN** já existe arquivo de sessão de um login anterior e um novo `sen login` é concluído com sucesso
- **THEN** o arquivo existente é substituído pela nova sessão sem resíduos de arquivos provisórios

#### Scenario: Falha de escrita

- **WHEN** ocorre erro de I/O ao persistir (diretório inexistente, sem permissão, disco cheio)
- **THEN** o comando falha com erro categorizado indicando o problema de persistência, sem expor o conteúdo da sessão, e encerra com exit code diferente de `0`

## ADDED Requirements

### Requirement: Validação por perfil do payload de login

O serviço de login SHALL validar a resposta de autenticação conforme o envelope `extra_info` publicado pela rota, utilizando o campo `extra_info.profile` como discriminador de perfil (`developer` | `super-admin`). O núcleo de sessão (`access_token`, `token_type` Bearer, `expires_in`, `extra_info` como objeto e `profile` com valor conhecido) SHALL ser exigido para qualquer perfil; adicionalmente SHALL ser exigido, para `developer`: `user_name`, `user_email`, `user_groups` **não-vazio** e `scope`; e, para `super-admin`: `scope` e `admin_access_token`. Falhas de validação SHALL resultar em erro categorizado com mensagem genérica ao usuário — nenhum fragmento de payload é exibido — e em nenhuma sessão persistida.

#### Scenario: Login developer completo

- **WHEN** a resposta contém núcleo válido e `extra_info` com `profile: "developer"`, `user_name`, `user_email`, `user_groups` não-vazio e `scope`
- **THEN** o login conclui com exit code `0` e a sessão gravada carrega `profile`, `scope` e os campos do perfil

#### Scenario: Campo obrigatório ausente para o perfil

- **WHEN** a resposta de um perfil não traz um campo exigido pela matriz (ex.: `developer` sem `user_groups` não-vazio, ou `super-admin` sem `admin_access_token`)
- **THEN** o login falha com erro categorizado de protocolo e mensagem genérica (sem detalhar payload), a causa completa fica restrita ao log interno e nenhum arquivo de sessão é escrito

#### Scenario: Perfil ausente ou desconhecido

- **WHEN** a resposta não contém `extra_info`, contém `extra_info` sem `profile`, ou com `profile` de valor não reconhecido
- **THEN** o login falha fechado com erro categorizado e mensagem genérica, sem escrever sessão — sem inferência de perfil por outros campos

#### Scenario: Token de administração permanece em memória

- **WHEN** o login `super-admin` conclui com sucesso
- **THEN** o `admin_access_token` está acessível aos consumidores da sessão durante a execução corrente (objeto de sessão retornado), não aparece em qualquer saída/log e não é gravado no arquivo de sessão

#### Scenario: Tipo de token não suportado

- **WHEN** a resposta indica `token_type` diferente de Bearer (case-insensitive)
- **THEN** o login falha com erro categorizado de protocolo, mensagem genérica, sem escrever sessão
