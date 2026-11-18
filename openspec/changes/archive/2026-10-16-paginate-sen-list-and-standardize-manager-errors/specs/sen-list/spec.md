## RENAMED Requirements

- FROM: `### Requirement: Busca `--query` client-side`
- TO: `### Requirement: Busca `--query` delegada ao Manager`

## MODIFIED Requirements

### Requirement: Comando `sen list api`

A CLI SHALL disponibilizar `sen list api` (substantivo no singular). O comando SHALL ler o catálogo do API Manager **em páginas de no máximo 25 APIs**, aplicando a visibilidade da sessão a cada página, e SHALL **parar de ler assim que a janela solicitada estiver preenchida** ou quando o catálogo terminar. A leitura NUNCA SHALL pedir o catálogo inteiro numa única requisição. Sem flags de janela (`caso desnudo`), o comando SHALL executar com `--limit 10 --offset 0` e exibir rodapé anunciando os padrões usados, nunca aplicando janela silenciosamente.

Quando a plataforma recusar uma página por tamanho de resposta (`413`), o comando SHALL repetir a mesma página com metade do tamanho (25 → 12 → 6 → 3 → 1) e SHALL manter o tamanho reduzido até o fim da leitura. Uma página de tamanho 1 ainda recusada SHALL encerrar o comando com a mensagem padrão de erro interno.

Uma API já recebida SHALL ser descartada se reaparecer em página posterior (deduplicação por id). Uma página não vazia sem nenhuma API nova SHALL interromper a leitura com a mensagem padrão de erro interno, em vez de seguir lendo indefinidamente.

Para sessão super admin (visibilidade total), o `--offset` solicitado SHALL ser aplicado diretamente na leitura do catálogo, sem ler as APIs anteriores a ele.

`sen list api --all` SHALL listar todas as APIs visíveis, lendo o catálogo até o fim em páginas. `--all` SHALL ser mutuamente exclusiva com `--limit`, `--offset` e `--id`: a combinação SHALL falhar imediatamente com erro amigável, sem requisição, e `exit 1`.

#### Scenario: Listagem padrão (desnudo)

- **WHEN** o usuário executa `sen list api` sem flags, com configuração válida
- **THEN** o catálogo é lido em páginas de até 25 APIs só até reunir 10 APIs visíveis (ou o catálogo acabar), a grade exibe até 10 itens ordenados por `id` crescente começando do primeiro, o rodapé `usando padrões: --limit 10 --offset 0 · detalhes: sen list api --help` é exibido, e o exit code é `0`

#### Scenario: Leitura para ao preencher a janela

- **WHEN** o usuário executa `sen list api --limit 5` e a primeira página já contém 5 ou mais APIs visíveis
- **THEN** apenas uma requisição de listagem é feita

#### Scenario: Janela explícita

- **WHEN** o usuário executa `sen list api --offset 90 --limit 5`
- **THEN** a grade exibe a janela exata indicada sobre o universo visível (ordenação `id` asc), com rodapé informativo da janela efetiva, e o exit code é `0`

#### Scenario: Offset além do total

- **WHEN** `--offset` supera a quantidade total de APIs visíveis
- **THEN** o comando exibe grade vazia e encerra com exit code `0`

#### Scenario: Catálogo maior que o limite de resposta da plataforma

- **WHEN** o catálogo tem APIs suficientes para que a resposta única ultrapasse o limite de tamanho do gateway
- **THEN** a listagem conclui normalmente, porque nenhuma requisição pede mais que uma página

#### Scenario: Página recusada por tamanho

- **WHEN** a plataforma responde `413` para uma página de 25 APIs
- **THEN** o comando repete a mesma posição com 12 APIs, segue com 12 nas páginas seguintes e conclui normalmente se a plataforma aceitar

#### Scenario: Página de 1 ainda recusada por tamanho

- **WHEN** a plataforma responde `413` mesmo para uma página de 1 API
- **THEN** o comando exibe a mensagem padrão de erro interno e encerra com `exit 1`, sem omitir a API silenciosamente

#### Scenario: Plataforma ignora o deslocamento

- **WHEN** uma página não vazia devolve apenas APIs já recebidas em páginas anteriores
- **THEN** a leitura é interrompida e o comando exibe a mensagem padrão de erro interno com `exit 1`

#### Scenario: Super admin com offset

- **WHEN** uma sessão super admin executa `sen list api --offset 50 --limit 10`
- **THEN** a leitura começa na posição 50 do catálogo, sem ler as 50 APIs anteriores

#### Scenario: Listar tudo

- **WHEN** o usuário executa `sen list api --all`
- **THEN** o catálogo é lido em páginas até o fim e a grade exibe todas as APIs visíveis à sessão, ordenadas por `id` crescente, com exit code `0`

#### Scenario: `--all` combinado com janela ou drill-down

- **WHEN** o usuário executa `sen list api --all` junto com `--limit`, `--offset` ou `--id`
- **THEN** o comando falha imediatamente com erro amigável sobre a exclusividade, sem realizar requisição, e exit code `1`

#### Scenario: Limit inválido

- **WHEN** `--limit` recebe valor igual ou inferior a zero
- **THEN** o comando falha com erro amigável (sem stacktrace) e exit code `1`, sem realizar requisição

#### Scenario: Offset inválido

- **WHEN** `--offset` recebe valor negativo
- **THEN** o comando falha com erro amigável (sem stacktrace) e exit code `1`, sem realizar requisição — simétrico ao `--limit ≤ 0`; `--offset 0` permanece válido (início da página)

### Requirement: Busca `--query` delegada ao Manager

`sen list api --query <texto>` SHALL delegar a busca ao Manager, restringindo o catálogo lido às APIs cujo **nome ou descrição** casam com o texto. O casamento de caixa e acentuação segue o comportamento da plataforma. A busca é o único filtro aplicado no servidor; a visibilidade continua exclusivamente client-side. A flag SHALL ser **mutuamente exclusiva** com `--id` (erro imediato sem requisição). A janela `--limit`/`--offset` SHALL aplicar-se **após** a busca e a visibilidade. Quando a busca não produz resultados, SHALL exibir dica útil e encerrar `0`.

#### Scenario: Busca por termo do nome

- **WHEN** o usuário executa `sen list api --query pagamentos` e existe API visível cujo nome ou descrição contém `pagamentos`
- **THEN** a API aparece na grade respeitando a janela aplicada

#### Scenario: Busca com acentuação invertida

- **WHEN** o usuário executa `sen list api --query autenticacao` e existe API cujo nome/descrição contém `Autenticação`
- **THEN** a CLI não aplica casamento próprio de acento ou caixa sobre o resultado: a API aparece se, e somente se, a plataforma a devolver para o termo informado

#### Scenario: Busca combinada com `--id`

- **WHEN** o usuário executa `sen list api --query auth --id 400`
- **THEN** o comando falha imediatamente com erro amigável sobre a exclusividade, sem realizar requisição, e exit code `1`

#### Scenario: Busca sem resultados

- **WHEN** o texto de `--query` não casa com nenhuma API
- **THEN** o comando informa que não encontrou resultados com dica (revisar o termo), sem erro e sem stacktrace

### Requirement: Erros HTTP mapeados para humanos (E1)

Falhas SHALL ser convertidas em mensagens humanas curtas conforme a família do erro, com a mesma classificação em todos os comandos que consultam o Manager:

| Família | Origem | Mensagem |
|---|---|---|
| sessão | `401` | sessão inválida ou expirada; orienta `sen login` |
| acesso negado | `403` | acesso negado; orienta `sen login` e, se persistir, o time de acesso |
| não encontrado | `404` no drill-down | "API não encontrada ou sem permissão de acesso" (mensagens fundidas, pois o servidor pode mascarar as duas situações na mesma resposta) |
| erro interno | demais `4xx` (ex.: `400`, `413`, `429`) | "ocorreu um erro interno na consulta"; orienta tentar novamente e, se persistir, acionar o suporte. NUNCA SHALL orientar `sen login` |
| indisponível | falha de conexão ou `5xx` após esgotar as tentativas | Manager indisponível; orienta tentar novamente em instantes |
| erro inesperado | qualquer falha não prevista no comando | a mesma mensagem padrão de erro interno |

Todas SHALL encerrar com `exit 1`, sem stacktrace, **sem ecoar corpos brutos de resposta, status ou títulos HTTP crus**, nem texto técnico de exceção. Os dados de diagnóstico (status, código de erro devolvido pela plataforma, identificador da requisição na plataforma e, para erro inesperado, o tipo e o stacktrace) SHALL ser registrados apenas em log, nunca na saída do comando.

#### Scenario: Credencial recusada

- **WHEN** o servidor responde 401/403 durante a listagem
- **THEN** a CLI exibe mensagem humana adequada à família (401 → sessão; 403 → acesso negado) e encerra com exit code `1`, sem mostrar corpo da resposta

#### Scenario: Recusa sem relação com credencial

- **WHEN** o servidor responde um 4xx fora de 401/403/404 (ex.: `413` com `{"code":"BACKEND_RESPONSE_TOO_LARGE"}`) e a falha não é absorvida pela leitura paginada
- **THEN** a CLI exibe a mensagem padrão de erro interno, sem orientar `sen login`, sem exibir status, título ou código da plataforma, e encerra com exit code `1`

#### Scenario: Diagnóstico registrado em log

- **WHEN** qualquer recusa da plataforma é traduzida para mensagem humana
- **THEN** o status, o código de erro do corpo (quando houver) e o identificador da requisição na plataforma (quando houver) são registrados em log, sem valores de token ou credencial

#### Scenario: Erro inesperado

- **WHEN** ocorre uma falha não prevista durante o comando
- **THEN** a CLI exibe a mensagem padrão de erro interno (sem o texto da exceção) e encerra com exit code `1`, e o tipo e o stacktrace vão apenas para o log

#### Scenario: Rede caída

- **WHEN** a conexão com o host falha (timeout/DNS/refused)
- **THEN** a CLI exibe mensagem de indisponibilidade com dica (host/rede) e encerra com exit code `1`

### Requirement: Filtragem de visibilidade client-side

A listagem `sen list api` SHALL filtrar, **no cliente e antes da janela (`--limit`/`--offset`)**, quais APIs são visíveis ao perfil da sessão. A decisão SHALL combinar o objeto `visibility` de cada API (retorno cru do payload de listagem) com o contexto de sessão do `.sen_session` (`userName`, `userGroups`, perfil admin). A visibilidade NUNCA SHALL ser delegada ao servidor: o token das chamadas administrativas é de super admin e compartilhado, então só o cliente conhece o perfil do usuário logado. Comparações de username e de nome de grupo SHALL usar trim + case-insensitive (nomes de grupo sem distinção de acento/caixa). Sem contador de APIs ocultas na saída — o comando exibe apenas o que o usuário pode ver.

Tipos de visibilidade observados em produção (probes read-only 21/09/2026, 110 APIs): `ORGANIZATION` (87) · `GROUP` (10) · `ME` (13). `owner` sempre presente; `groupVisibility` chega como objeto único com `name` inline (sem GET para resolver); `users[]` na lista é irrelevante para a decisão de visibilidade. Valores distintos SHALL ser tratados pela tabela:

| Condicao                                        | Visivel para a sessao                                   |
|-------------------------------------------------|----------------------------------------------------------|
| `super_admin` (perfil/admin token da sessao)     | tudo                                                     |
| `visibilityType == "ORGANIZATION"`               | todos da organizacao                                     |
| `visibilityType == "ME"`                         | somente se `owner == userName`                           |
| `visibilityType == "GROUP"`                      | SOMENTE se `groupVisibility.name` casa com algum `userGroups` da sessao (trim/casefold) — `owner` NAO influi na regra GROUP |
| tipo ausente ou desconhecido                     | NUNCA (deny-by-default)                                  |

A ordem SHALL ser: `filtered_by(query)` (no Manager, ao ler cada página) → `visible_to` (no cliente, a cada página) → `sorted_by_id` → `window(offset, limit)`. A janela incide sobre o universo já buscado e filtrado.

Sessão **sem grupos legíveis** (`userGroups` ausente/vazio em perfil não admin) SHALL **bloquear** o comando com erro educativo (o piso mínimo é o grupo API Ops): mensagem curta orientando refazer `sen login` ou entrar em contato, `exit 1`, **sem** simular lista vazia. Resultado vazio após o filtro SHALL tratar-se como lista legítima vazia ("No APIs found."), sem erro.

#### Scenario: API de organização aparece para todos

- **WHEN** o filtro avalia uma API com `visibilityType: ORGANIZATION`
- **THEN** a API compõe o universo visível independentemente de `userGroups`

#### Scenario: API ME restrita ao dono

- **WHEN** o filtro avalia uma API com `visibilityType: ME` cujo `owner` difere de `userName` da sessão
- **THEN** a API é excluída da listagem (exceto para perfil admin)

#### Scenario: API de grupo casa por associação do usuário

- **WHEN** o filtro avalia uma API com `visibilityType: GROUP` e `groupVisibility.name` igual (ignorando caixa/espaços) a um grupo de `userGroups` da sessão
- **THEN** a API aparece na listagem mesmo com `users: []` no payload

#### Scenario: API de grupo é ocultada quando o nome não casa

- **WHEN** o filtro avalia uma API `GROUP` cujo nome de grupo não consta em `userGroups` da sessão (independente de quem é o `owner`)
- **THEN** a API é excluída silenciosamente da listagem (a página/janela continua coerente com o universo visível)

#### Scenario: Tipo de visibilidade desconhecido é negado

- **WHEN** o filtro encontra `visibility` ausente, com `visibilityType` vazio ou com valor fora da tabela (`ORGANIZATION`/`GROUP`/`ME`)
- **THEN** a API é excluída (deny-by-default), independentemente do perfil (exceto super admin)

#### Scenario: Busca e janela aplicadas após a visibilidade

- **WHEN** o usuário combina filtro de visibilidade ativo com `--query`, `--limit` e/ou `--offset`
- **THEN** o pipeline executa na ordem `filtered_by` (Manager) → `visible_to` → `sorted_by_id` → `window`, e a janela incide sobre o conjunto já visível

#### Scenario: Janela preenchida com páginas de baixa visibilidade

- **WHEN** a sessão enxerga poucas APIs e a primeira página não contém APIs visíveis suficientes para a janela
- **THEN** o comando continua lendo as páginas seguintes até preencher a janela ou o catálogo acabar, e a grade exibe apenas APIs visíveis

#### Scenario: Sessão sem grupos bloqueia o comando

- **WHEN** o perfil da sessão é não admin e `userGroups` está ausente ou vazio no `.sen_session`
- **THEN** o comando falha **antes de qualquer cálculo/requisição complementar** com mensagem educativa curta (contexto mínimo de participação no grupo API Ops; sugerir `sen login` novamente ou acionar o time de acesso) e `exit 1`

#### Scenario: Plataforma não retorna APIs

- **WHEN** o endpoint de listagem responde com coleção vazia
- **THEN** o comando informa ausência de APIs (mensagem padrão "No APIs found.") e encerra com `exit code 0`

#### Scenario: Filtro resulta em universo vazio

- **WHEN** a coleção retornada não é vazia, mas nenhuma API passa pelo filtro de visibilidade
- **THEN** o comando exibe a grade vazia sem tratar como erro e encerra com `exit code 0`
