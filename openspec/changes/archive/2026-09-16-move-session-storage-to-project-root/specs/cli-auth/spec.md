## MODIFIED Requirements

### Requirement: Sessão persistida em arquivo e legível por execuções posteriores

A sessão SHALL ser persistida em um **arquivo oculto** (nome iniciado por ponto) na **raiz do projeto** — o diretório raiz do repositório sobre o qual a aplicação está executando, derivado da configuração da aplicação (e não do diretório corrente do shell) —, com escrita atômica (arquivo provisório + renomeação) e permissões restritivas ao usuário corrente. O arquivo SHALL estar **excluído do rastreamento de versionamento** (ver requirement "Sessão excluída do rastreamento de versionamento"). O arquivo SHALL conter `access_token`, `token_type`, `expires_at` (calculado a partir de `expires_in` no momento da recepção), `user_groups`, `user_email` e `username`, de modo que execuções subsequentes da aplicação consigam carregar e avaliar a sessão.

#### Scenario: Escrita segura com conteúdo completo

- **WHEN** o login é concluído com sucesso
- **THEN** o arquivo de sessão é criado na raiz do projeto via escrita atômica (não é possível observar arquivo parcialmente escrito), o nome inicia com ponto, as permissões restringem leitura ao usuário corrente e o conteúdo contém todos os campos listados, incluindo `expires_at`

#### Scenario: Local independente do diretório corrente

- **WHEN** o usuário executa `sen login` a partir de qualquer subdiretório do projeto (ex.: `src/`) ou de fora dele
- **THEN** a sessão é gravada na mesma **raiz do projeto** (configuração da aplicação), e não no diretório corrente

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

## ADDED Requirements

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
