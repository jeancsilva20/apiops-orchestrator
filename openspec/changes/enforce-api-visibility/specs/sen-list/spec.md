## MODIFIED Requirements

### Requirement: Drill-down por `--id` com revisões opcionais (fonte = catálogo)

`sen list api --id <api_id>` SHALL exibir cabeçalho de 1 linha da API; com `--revisions` (atalho `-r`), SHALL compor a grade de revisões (**REV # · REV ID · STAGE · ENVS · COMPLETE**). As revisões, os ambientes e o vínculo de workflow vêm do **catálogo (api-finder) via `customSearch=(apiId:{id})`**, 1 chamada para todo o drill-down: o frame traz inline `revisions[]` (id, revisionNumber), `environments[]` ({name, apiRevision}) e `wokflow[]`. Logo após essa leitura, o comando SHALL aplicar a regra de `api-visibility` à API, antes de resolver stages e de ler completeness. A célula COMPLETE SHALL vir de `GET /api-manager/api/v3/revisions/{id}/completeness` (`completenessScore`), uma chamada por revisão exibida, com no máximo 8 chamadas simultâneas; o bloco `completeness[]` do frame do catálogo MUST NOT ser usado (está defasado em relação ao Manager — sondagem de 21/10/2026). A coluna LAST REV (do cabeçalho e da listagem) SHALL exibir o **número** da revisão, traduzido pelo próprio `revisions[]` local (o `lastRevision` do frame é o ID); **sem número resolvível, SHALL renderizar `-`** (nunca o ID). O nome do STAGE resolve via catálogo de workflows de governance **cacheado por execução** (uma chamada por workflow distinto, nunca por linha). Quando o nome do stage não puder ser resolvido, SHALL exibir o id do workflow como degradação. Quando a leitura de completeness de uma revisão falhar (recusa ou indisponibilidade do Manager), a célula SHALL renderizar `-`, as demais linhas SHALL seguir normalmente e o comando SHALL encerrar com exit `0`; no formato texto, a grade SHALL terminar com uma nota indicando quantas revisões ficaram sem completeness e apontando `sen completeness --id X --revision <REV ID>`; em `json`/`yaml`, o campo `completeness_score` SHALL vir `null` e nenhuma nota é impressa. Enquanto as leituras de completeness estiverem em curso, o formato texto SHALL exibir feedback de espera (indicador transitório em terminal; uma linha única fora de terminal); `json`/`yaml` MUST NOT imprimir feedback. A coluna LIFE CYCLE está **aposentada da listagem** (fonte entrega `null` — retorno do detail a mantém dormante, reativa quando a plataforma expor `apiLifeCycle`).

Células CREATED/LAST DEPLOY **não existem no frame do catálogo** (sondas r9: `revisions[]` sem creationDate nem histórico de deploys) e por isso NÃO integram a grade — evolução aguarda a plataforma expor esses dados na mesma fonte.

`-r` sem `--id` SHALL falhar imediatamente (erro educativo, pré-rede, exit 1).

#### Scenario: Drill-down com revisões

- **WHEN** o usuário executa `sen list api --id 400 --revisions` para API com revisões válidas
- **THEN** a grade exibe REV # · REV ID · STAGE (nome) · ENVS · COMPLETE (percentual), com 1 chamada ao catálogo + no máximo 1 chamada por workflow distinto (cache válido dentro da mesma execução) + 1 chamada a `/revisions/{id}/completeness` por revisão exibida

#### Scenario: COMPLETE igual ao sen completeness

- **WHEN** o catálogo informa `completeness[]` com `{score: 66.8, apiRevision: 28541}` e `GET /revisions/28541/completeness` responde `completenessScore: 75.8`
- **THEN** a célula COMPLETE da revisão 28541 exibe `76%`, o mesmo valor que `sen completeness --id 68 --revision 28541` exibe

#### Scenario: Falha no completeness de uma revisão

- **WHEN** `GET /revisions/{id}/completeness` falha (4xx ou indisponibilidade) para uma das revisões e responde para as demais
- **THEN** a célula COMPLETE dessa revisão exibe `-`, as demais exibem o percentual, a grade termina com a nota de revisões sem completeness e o exit code é `0`

#### Scenario: Falha no completeness em saída estruturada

- **WHEN** a mesma falha ocorre com `-o json`
- **THEN** a linha da revisão traz `completeness_score: null` e o stdout contém apenas o documento JSON

#### Scenario: API inexistente ou inacessível

- **WHEN** `--id` não corresponde a nenhuma API (catálogo responde vazio) OU a API existe e não é visível para a sessão pela regra de `api-visibility`
- **THEN** o comando falha com mensagem humana "API X não encontrada ou sem permissão de acesso." (sem corpo cru JSON) e exit code `1`, sem chamar o catálogo de workflows nem a rota de completeness

#### Scenario: Revisões sem `--id`

- **WHEN** `--revisions/-r` é usado sem `--id`
- **THEN** o comando falha com erro educativo apontando o vínculo com `--id` e o sub-help, sem realizar requisição, e exit code `1`

### Requirement: Filtragem de visibilidade client-side

A listagem `sen list api` SHALL filtrar, **no cliente e antes da janela (`--limit`/`--offset`)**, as APIs que a regra de `api-visibility` não deixa a sessão ver, a partir dos campos de visibilidade do catálogo e do contexto do `.sen_session` (`userName`, `userGroups`, perfil admin). Sem contador de APIs ocultas na saída — o comando exibe apenas o que o usuário pode ver.

A ordem SHALL ser: `filtered_by(query)` (no Manager, ao ler cada página) → `visible_to` (no cliente, a cada página) → `sorted_by_id` → `window(offset, limit)`. A janela incide sobre o universo já buscado e filtrado.

Sessão **sem grupos legíveis** (`userGroups` ausente/vazio em perfil não admin) SHALL **bloquear** o comando com erro educativo (o piso mínimo é o grupo API Ops): mensagem curta orientando refazer `sen login` ou entrar em contato, `exit 1`, **sem** simular lista vazia. Resultado vazio após o filtro SHALL tratar-se como lista legítima vazia ("No APIs found."), sem erro.

#### Scenario: API de organização aparece para todos

- **WHEN** o filtro avalia uma API com `contextType: ORGANIZATION`
- **THEN** a API compõe o universo visível independentemente de `userGroups`

#### Scenario: API ME restrita ao dono

- **WHEN** o filtro avalia uma API com `contextType: ME` cujo `owner` difere de `userName` da sessão e cujo `contextUserLogins` não traz `userName`
- **THEN** a API é excluída da listagem (exceto para perfil admin); se `contextUserLogins` trouxer `userName`, a API aparece

#### Scenario: API de grupo casa por associação do usuário

- **WHEN** o filtro avalia uma API com `contextType: GROUP` e `contextGroupName` igual (ignorando caixa, acento e espaços) a um grupo de `userGroups` da sessão
- **THEN** a API aparece na listagem mesmo sem usuários na visibilidade

#### Scenario: API de grupo é ocultada quando o nome não casa

- **WHEN** o filtro avalia uma API `GROUP` cujo nome de grupo não consta em `userGroups` da sessão (independente de quem é o `owner`)
- **THEN** a API é excluída silenciosamente da listagem (a página/janela continua coerente com o universo visível)

#### Scenario: Tipo de visibilidade desconhecido é negado

- **WHEN** o filtro encontra `contextType` ausente, vazio ou fora de `ORGANIZATION`/`GROUP`/`ME`
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
