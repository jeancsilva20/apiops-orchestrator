## MODIFIED Requirements

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

## ADDED Requirements

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
