# cli-auth Delta

## MODIFIED Requirements

### Requirement: Sessão persistida em arquivo e legível por execuções posteriores

A sessão SHALL ser persistida em um **arquivo oculto** (nome iniciado por ponto) no **diretório do pacote** (`PACKAGE_ROOT` — no modo dev, `src/apiops_orchestrator/`; é o mesmo diretório que hospeda o arquivo `.sen`), determinado pela configuração da aplicação e não pelo diretório corrente do shell. A escrita SHALL ser atômica (arquivo provisório + renomeação) com permissões restritivas ao usuário corrente. O arquivo SHALL estar **excluído do rastreamento de versionamento** (ver requirement "Sessão excluída do rastreamento de versionamento"). O arquivo SHALL conter `accessToken`, `tokenType`, `expiresAt` (calculado a partir de `expiresIn` no momento da recepção), `profile`, `scope` e os campos condicionais do perfil (`userName`, `userEmail`, `userGroups` para `developer`; **`adminAccessToken` para `super-admin`**, conforme revisão do ADR 0002 registrada neste change — o token privilegiado passa a residir no arquivo de sessão, sujeito às mesmas salvaguardas de escrita, permissões, exclusão de versionamento e expiração da sessão), de modo que execuções subsequentes da aplicação consigam carregar e avaliar a sessão completa. A sessão do perfil `developer` SHALL continuar sem `adminAccessToken` (campo não emitido para o perfil).

#### Scenario: Escrita segura com conteúdo completo

- **WHEN** o login é concluído com sucesso
- **THEN** o arquivo de sessão é criado no diretório do pacote via escrita atômica (não é possível observar arquivo parcialmente escrito), o nome inicia com ponto, as permissões restringem leitura ao usuário corrente e o conteúdo contém todos os campos listados, incluindo `expiresAt`, `profile` e `scope`; para perfil `super-admin` o conteúdo inclui `adminAccessToken`, e para perfil `developer` não o inclui

#### Scenario: Local independente do diretório corrente

- **WHEN** o usuário executa `sen login` a partir de qualquer subdiretório do projeto (ex.: `src/`) ou de fora dele
- **THEN** a sessão é gravada no **diretório do pacote** (`PACKAGE_ROOT`, configuração da aplicação), e não no diretório corrente

#### Scenario: Convivência com o `.sen` no mesmo diretório

- **WHEN** o login é concluído e o diretório do pacote já contém um arquivo `.sen`
- **THEN** ambos os arquivos convivem no mesmo diretório (`.sen` de credencial, `.sen_session` de sessão), sem interferência de um sobre o outro

#### Scenario: Leitura por execução posterior — super-admin com token completo

- **WHEN** a aplicação inicia uma execução subsequente e existe arquivo de sessão de perfil `super-admin` com `expiresAt` maior que o instante atual
- **THEN** a sessão é carregável pelo mecanismo de persistência com TODOS os campos gravados, incluindo `adminAccessToken`

#### Scenario: Leitura por execução posterior — sessão legada de super-admin sem token

- **WHEN** a aplicação carrega um arquivo de sessão de perfil `super-admin` gravado antes deste change (sem `adminAccessToken`) e ainda não expirado
- **THEN** a sessão é carregada sem falha de protocolo; se um fluxo subsequente exigir o token ausente, SHALL orientar re-login em vez de falhar com erro opaco

#### Scenario: Sessão expirada tratada como ausente

- **WHEN** uma execução subsequente lê o arquivo e `expiresAt` = instante atual
- **THEN** a sessão é tratada como ausente (não utilizável), sem ressurreição de token — incluindo o `adminAccessToken`

#### Scenario: Sessão legada ou com perfil desconhecido tratada como ausente

- **WHEN** uma execução subsequente lê um arquivo de sessão que não contém `profile` (formato anterior a este change) ou contém perfil desconhecido
- **THEN** a sessão é tratada como ausente (não utilizável) e o próximo fluxo que a exigir executa o re-login, em vez de transitar sessão malformada

#### Scenario: Substituição de sessão anterior

- **WHEN** já existe arquivo de sessão de um login anterior e um novo `sen login` é concluído com sucesso
- **THEN** o arquivo existente é substituído pela nova sessão sem resíduos de arquivos provisórios

#### Scenario: Falha de escrita

- **WHEN** ocorre erro de I/O ao persistir (diretório inexistente, sem permissão, disco cheio)
- **THEN** o comando falha com erro categorizado indicando o problema de persistência, sem expor o conteúdo da sessão, e encerra com exit code diferente de `0`

#### Scenario: Estados inconsistentes de perfil bloqueados

- **WHEN** o modelo recebe uma tentativa de sessão incoerente (perfil `developer` com `adminAccessToken`, ou perfil `super-admin` sem `adminAccessToken`)
- **THEN** a construção falha conforme o guard existente do modelo — a presença do token no arquivo é consequência do perfil validado, nunca do ponto de gravação
