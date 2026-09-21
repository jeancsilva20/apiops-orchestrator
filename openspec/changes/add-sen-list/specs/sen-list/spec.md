# sen-list Delta

## ADDED Requirements

### Requirement: Entry-point `sen` registrado e metadados sem configuração

O pacote SHALL registrar o entry-point `[tool.poetry.scripts] sen = "apiops_orchestrator.main:main"` de modo que, instalado, exponha o comando `sen`. Comandos de metadado (`sen`, `sen --help`, `sen list`, `sen list api --help`) SHALL responder instantaneamente **sem** carregar configuração (nenhuma leitura de `.env`, nenhuma autenticação, nenhum efeito colateral de rede ou sistema de arquivos durante o import/dispatch) — requisito D1-a (ADR 0006).

#### Scenario: Ajuda responde sem `.env`

- **WHEN** a CLI é invocada em máquina sem `.env` configurado (nenhuma variável presente)
- **THEN** `sen --help` e `sen list api --help` exibem a ajuda completa e encerram com exit code `0`, sem qualquer mensagem de configuração ausente

#### Scenario: Invocação sem argumentos

- **WHEN** o binário `sen` é executado sem argumentos
- **THEN** a ajuda é exibida (`no_args_is_help`), nenhum pipeline de conversão é executado e nenhum caminho de disco absoluto é consultado

#### Scenario: Import sem efeitos colaterais

- **WHEN** o módulo `main` é importado (ex.: durante coleta de testes)
- **THEN** nenhuma instância de `Settings` é criada, nenhuma chamada HTTP é realizada e nenhum caminho de disco é resolvido

### Requirement: Degradacão educativa em comando de rede sem chaves (D1-b)

Um comando que exige rede, executado sem as chaves de configuração necessárias, SHALL produzir erro curto e educativo contendo (i) o que está faltando, (ii) como resolver (ponteiro para a configuração/arquivo `.sen`) e (iii) referência ao sub-help relevante, encerrando com `exit 1` — sem stacktrace e sem segredos na saída (herda padrão ADR 0005).

#### Scenario: Listagem sem configuração

- **WHEN** `sen list api` roda sem as chaves obrigatórias (`.env`/`.sen` ausentes ou incompletos)
- **THEN** a CLI exibe mensagem curta indicando a chave faltante e `sen list api --help` como próximo passo, sem stacktrace, e encerra com `exit 1`

### Requirement: Comando `sen list api`

A CLI SHALL disponibilizar `sen list api` (substantivo no singular). Em condições normais SHALL chamar o endpoint de listagem do API Manager uma única vez e compor a grade de listagem com a janela efetiva solicitada. Sem flags de janela (`caso desnudo`), o comando SHALL executar com `--limit 10 --offset 0` e exibir rodapé anunciando os padrões usados — nunca aplicar janela silenciosamente.

#### Scenario: Listagem padrão (desnudo)

- **WHEN** o usuário executa `sen list api` sem flags, com configuração válida
- **THEN** uma única requisição de listagem é feita, a grade exibe até 10 itens ordenados por `id` crescente começando do primeiro, o rodapé `usando padrões: --limit 10 --offset 0 · detalhes: sen list api --help` é exibido, e o exit code é `0`

#### Scenario: Janela explícita

- **WHEN** o usuário executa `sen list api --offset 90 --limit 5`
- **THEN** a grade exibe a janela exata indicada (ordenação `id` asc client-side), com rodapé informativo da janela efetiva, e o exit code é `0`

#### Scenario: Offset além do total

- **WHEN** `--offset` supera a quantidade total de APIs
- **THEN** o comando exibe grade vazia e encerra com exit code `0`

#### Scenario: Limit inválido

- **WHEN** `--limit` recebe valor igual ou inferior a zero
- **THEN** o comando falha com erro amigável (sem stacktrace) e exit code `1`, sem realizar requisição

### Requirement: Busca `--query` client-side

`sen list api --query <texto>` SHALL filtrar o conjunto retornado client-side pelos campos `name` e `description`, comparando de forma case-insensitive e accent-folded (ex.: `autenticacao` casa `Autenticação`). A flag SHALL ser **mutuamente exclusiva** com `--id` (erro imediato sem requisição). A janela `--limit`/`--offset` SHALL aplicar-se **após** o filtro. Quando a busca não produz resultados, SHALL exibir dica útil e encerrar `0`.

#### Scenario: Busca com acentuação invertida

- **WHEN** o usuário executa `sen list api --query autenticacao` e existe API cujo nome/descrição contém `Autenticacão`
- **THEN** a API aparece na grade respeitando a janela aplicada

#### Scenario: Busca combinada com `--id`

- **WHEN** o usuário executa `sen list api --query auth --id 400`
- **THEN** o comando falha imediatamente com erro amigável sobre a exclusividade, sem realizar requisição, e exit code `1`

#### Scenario: Busca sem resultados

- **WHEN** o texto de `--query` não casa com nenhuma API
- **THEN** o comando informa que não encontrou resultados com dica (revisar o termo), sem erro e sem stacktrace

### Requirement: Drill-down por `--id` com revisões opcionais

`sen list api --id <api_id>` SHALL exibir cabeçalho de 1 linha da API; com `--revisions` (atalho `-r`), SHALL compor a grade de revisões (REV ID · REV # · STAGE · CREATED · LAST DEPLOY · ENVS · COMPLETE) usando: revisions da API, completeness por revisão exibida e nome do stage via catálogo de workflows **cacheado por sessão** (uma chamada por workflow distinto, não por linha). Quando o nome do stage não puder ser resolvido, SHALL exibir o id do workflow como degradação.

#### Scenario: Drill-down com revisões

- **WHEN** o usuário executa `sen list api --id 400 --revisions` para API com revisões válidas
- **THEN** a grade exibe as revisões com número, stage (nome), datas e percentual de completeness, realizando no máximo 1 chamada por revisão exibida + 1 por workflow distinto (cache válido dentro da mesma execução)

#### Scenario: API inexistente ou inacessível

- **WHEN** `--id` não corresponde a nenhuma API OU a API não está visível para o chamante (404 do servidor — o servidor pode mascarar ausência e ausência de permissão na mesma resposta)
- **THEN** o comando falha com mensagem humana "API não encontrada ou sem permissão de acesso" (sem corpo cru JSON) e exit code `1`

### Requirement: Erros HTTP mapeados para humanos (E1)

Falhas SHALL ser convertidas em mensagens humanas curtas conforme a família do erro — `401`: problema de credenciais · `403`: sem permissão · `404` no drill-down: "API não encontrada ou sem permissão de acesso" (mensagens fundidas, pois o servidor pode mascarar as duas situações na mesma resposta) · falha de conexão: rede indisponível — todas com `exit 1`, sem stacktrace e **sem ecoar corpos brutos de resposta** (padrão de supressão existente da infraestrutura HTTP).

#### Scenario: Credencial recusada

- **WHEN** o servidor responde 401/403 durante a listagem
- **THEN** a CLI exibe mensagem humana adequada à família (401 → credenciais; 403 → permissão) e encerra com exit code `1`, sem mostrar corpo da resposta

#### Scenario: Rede caída

- **WHEN** a conexão com o host falha (timeout/DNS/refused)
- **THEN** a CLI exibe mensagem de indisponibilidade com dica (host/rede) e encerra com exit code `1`

### Requirement: Segurança de saídas e segredos

Todas as saídas do `sen list` SHALL seguir o padrão de logs existente (ADR 0005): nenhum token, credencial ou valor de segredo SHALL aparecer em stdout/stderr, exceptions ou testes; corpos de resposta com credenciais SHALL ser suprimidos (relato de corpo suprimido).

#### Scenario: Nenhum segredo na saída

- **WHEN** qualquer comando da fatia executa (sucesso ou falha)
- **THEN** nenhuma linha de saída contém valores de token, credencial Basic ou segredo; falhas exibem apenas descrições e categorias
