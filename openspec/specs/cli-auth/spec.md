# cli-auth Specification

## Purpose
Define o contrato do comando `sen login` da CLI: autenticar o executor junto à Orchestrator Auth API usando uma única credencial Basic (`SEN_CREDENTIALS`, enviada intacta) contra um endpoint configurável e persistir a sessão resultante em arquivo oculto local, legível por execuções posteriores da aplicação. É a primeira fase da autenticação — nada do fluxo LEGACY existente é alterado, e guard/autorização por ação ficam para as fases seguintes.
## Requirements
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

### Requirement: Credencial Basic como única fonte

A credencial de login SHALL ter como fontes permitidas a variável de ambiente **`SEN_CREDENTIALS`** ou a entrada equivalente no **arquivo `.sen`** (blob `Base64(client_id:secret)`), enviado **intacto** no cabeçalho de autenticação da requisição (decodificação server-side, conforme ADR 0001). Nenhum fallback — inclusive o par legado `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET` — SHALL ser utilizado pelo `sen login`. Quando a mesma chave for provista por mais de uma fonte, valem as regras de precedência da requirement "Arquivo `.sen` como configuração da CLI".

#### Scenario: `SEN_CREDENTIALS` definida

- **WHEN** a variável `SEN_CREDENTIALS` possui valor não vazio (via processo ou arquivo `.sen`)
- **THEN** seu valor é enviado intacto no cabeçalho da requisição de login

#### Scenario: `SEN_CREDENTIALS` proveniente apenas do arquivo `.sen`

- **WHEN** a variável não existe no processo, mas o arquivo `.sen` do pacote declara `SEN_CREDENTIALS` com valor não vazio
- **THEN** o valor do arquivo é adotado como credencial e enviado intacto no cabeçalho da requisição de login

#### Scenario: Ausência de `SEN_CREDENTIALS` com par legado presente

- **WHEN** `SEN_CREDENTIALS` está ausente ou vazia (processo e `.sen`), mesmo que `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET` estejam definidos
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

A sessão SHALL ser persistida em um **arquivo oculto** (nome iniciado por ponto) no **diretório do pacote** (`PACKAGE_ROOT` — no modo dev, `src/apiops_orchestrator/`; é o mesmo diretório que hospeda o arquivo `.sen`), determinado pela configuração da aplicação e não pelo diretório corrente do shell. A escrita SHALL ser atômica (arquivo provisório + renomeação) com permissões restritivas ao usuário corrente. O arquivo SHALL estar **excluído do rastreamento de versionamento** (ver requirement "Sessão excluída do rastreamento de versionamento"). O arquivo SHALL conter `accessToken`, `tokenType`, `expiresAt` (calculado a partir de `expiresIn` no momento da recepção), `profile`, `scope` e os campos condicionais do perfil (`userName`, `userEmail`, `userGroups` para `developer`) — mas **SHALL NOT conter `adminAccessToken`**, que permanece disponível apenas em memória durante a execução corrente do perfil `super-admin`, de modo que execuções subsequentes da aplicação consigam carregar e avaliar a sessão.

#### Scenario: Escrita segura com conteúdo completo

- **WHEN** o login é concluído com sucesso
- **THEN** o arquivo de sessão é criado no diretório do pacote via escrita atômica (não é possível observar arquivo parcialmente escrito), o nome inicia com ponto, as permissões restringem leitura ao usuário corrente e o conteúdo contém todos os campos listados, incluindo `expiresAt`, `profile` e `scope` — e **não contém** `adminAccessToken`

#### Scenario: Local independente do diretório corrente

- **WHEN** o usuário executa `sen login` a partir de qualquer subdiretório do projeto (ex.: `src/`) ou de fora dele
- **THEN** a sessão é gravada no **diretório do pacote** (`PACKAGE_ROOT`, configuração da aplicação), e não no diretório corrente

#### Scenario: Convivência com o `.sen` no mesmo diretório

- **WHEN** o login é concluído e o diretório do pacote já contém um arquivo `.sen`
- **THEN** ambos os arquivos convivem no mesmo diretório (`.sen` de credencial, `.sen_session` de sessão), sem interferência de um sobre o outro

#### Scenario: Leitura por execução posterior

- **WHEN** a aplicação inicia uma execução subsequente e existe arquivo de sessão com `expiresAt` maior que o instante atual
- **THEN** a sessão é carregável pelo mecanismo de persistência fornecido por esta mudança (contendo os mesmos campos gravados); para a sessão `super-admin` o `adminAccessToken` não está disponível nesse carregamento, apenas os campos persistidos

#### Scenario: Sessão expirada tratada como ausente

- **WHEN** uma execução subsequente lê o arquivo e `expiresAt` ≤ instante atual
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

### Requirement: Logs e saídas no padrão existente, sem segredos

O `sen login` SHALL seguir os padrões atuais da aplicação: tratamento de requisições via infraestrutura HTTP compartilhada (retries, RFC 7807), logs no padrão de observabilidade existente e saída Rich. Em todas as fases (montagem, requisição, persistência, relato final e erros), nenhum fragmento da credencial ou do token SHALL aparecer na saída padrão, saída de erro ou logs — inclusive em modo `--verbose`.

#### Scenario: Sucesso sem vazamento

- **WHEN** o login é executado com `--verbose` habilitado
- **THEN** nenhuma linha de saída ou de log contém o valor da credencial ou do token; os logs seguem o formato do padrão de observabilidade existente (eventos nomeados de autenticação)

#### Scenario: Erro sem vazamento

- **WHEN** o login falha em qualquer etapa (rede, protocolo, persistência)
- **THEN** as mensagens de erro identificam a categoria e, no máximo, metadados seguros (status HTTP, etapa da falha), nunca o conteúdo do cabeçalho de credencial ou do token

### Requirement: Sessão excluída do rastreamento de versionamento

Por conviver com a árvore do projeto, o arquivo de sessão SHALL estar protegido contra ingresso no versionamento: o repositório SHALL manter um padrão `.sen_session*` no `.gitignore` cobrindo o arquivo e suas variantes provisórias, garantindo que a sessão nunca seja commitada nem propagada por operações Git.

#### Scenario: Estado do Git limpo com sessão presente

- **WHEN** existe arquivo de sessão válido na raiz do projeto e o usuário executa `git status`
- **THEN** o arquivo de sessão (e seus provisórios) não aparecem como modificados/não rastreados

#### Scenario: Cobertura de variantes provisórias

- **WHEN** a pasta raiz contém resíduos de escrita (ex.: `.sen_session.<sufixo>.tmp`)
- **THEN** o padrão de `.gitignore` definido cobre essas variantes, mantendo o repositório limpo

#### Scenario: Repositório livre de sessão histórica

- **WHEN** o repositório é clonado ou navegado em qualquer commit
- **THEN** não existe arquivo de sessão trackeado em nenhuma revisão (a exclusão previne, não exige remoção retroativa)

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

### Requirement: Arquivo `.sen` como configuração da CLI

A aplicação SHALL reconhecer um arquivo **`.sen`** na sintaxe dotenv (pares `CHAVE=valor`), localizado no **diretório do pacote** (`PACKAGE_ROOT`), como arquivo de configuração do executável — contemplando o **bloco de credenciais de login**, composto exatamente por `SEN_CREDENTIALS`, `AUTH_HOST` e `AUTH_LOGIN_PATH`, que migram **juntos** para esse arquivo. **Nenhum dos três SHALL possuir default ou fallback em código**: ausência de qualquer um deles (em todas as fontes) resulta em erro categorizado **antes de qualquer chamada de rede**. Chaves desconhecidas no arquivo SHALL ser ignoradas (sem falha de carga). A precedência SHALL ser: **variáveis de processo > `.sen` > `.env` da raiz do projeto**. A aplicação SHALL fornecer gabarito versionado `.sen.example` contendo comentários de uso e **nenhum valor real de segredo**; o arquivo `.sen` em si SHALL estar excluído do versionamento (match exato no `.gitignore`).

#### Scenario: Carga apenas com `.sen`

- **WHEN** o diretório do pacote contém `.sen` com o bloco de credenciais completo e não existe `.env` (nem variáveis de processo)
- **THEN** a CLI carrega as configurações a partir do `.sen` e o `sen login` conclui normalmente

#### Scenario: Bloco de credenciais incompleto no `.sen`

- **WHEN** o arquivo `.sen` não declara alguma das chaves do bloco (`SEN_CREDENTIALS`, `AUTH_HOST` ou `AUTH_LOGIN_PATH`) e a chave também não existe como variável de processo ou no `.env`
- **THEN** o login falha com erro categorizado **antes de qualquer chamada de rede**, sem aplicar default ou fallback em código para a chave faltante

#### Scenario: Precedência sobre o `.env`

- **WHEN** `.env` e `.sen` definem a mesma chave com valores diferentes
- **THEN** o valor do `.sen` prevalece sobre o do `.env`

#### Scenario: Precedência do processo

- **WHEN** uma chave existe como variável de processo e também em `.sen`/`.env`
- **THEN** a variável de processo vence (allowlist de operadores de esteira intacto)

#### Scenario: Esteira sem `.sen` não quebra

- **WHEN** o processo de esteira roda apenas com `.env` gerado em runtime (sem `.sen`)
- **THEN** o comportamento é idêntico ao atual — a ausência do `.sen` não gera erro nem warning fatal

#### Scenario: Chaves extras ignoradas

- **WHEN** o `.sen` contém chaves além das reconhecidas pelas `Settings`
- **THEN** elas são ignoradas silenciosamente (`extra="ignore"`) e a aplicação inicia normalmente

#### Scenario: Gabarito sem segredo e trackeado

- **WHEN** o repositório é clonado
- **THEN** existe `.sen.example` versionado com comentários e placeholders, e nenhum valor real de credencial em qualquer arquivo versionado

#### Scenario: `.sen` nunca entra no Git

- **WHEN** o dev cria um `.sen` com credencial real no diretório do pacote e executa `git status`
- **THEN** o arquivo não aparece (não rastreado nem modificado), inclusive em operações de add globais

