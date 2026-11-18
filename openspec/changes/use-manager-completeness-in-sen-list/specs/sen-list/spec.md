## MODIFIED Requirements

### Requirement: Drill-down por `--id` com revisões opcionais (fonte = catálogo)

`sen list api --id <api_id>` SHALL exibir cabeçalho de 1 linha da API; com `--revisions` (atalho `-r`), SHALL compor a grade de revisões (**REV # · REV ID · STAGE · ENVS · COMPLETE**). As revisões, os ambientes e o vínculo de workflow vêm do **catálogo (api-finder) via `customSearch=(apiId:{id})`**, 1 chamada para todo o drill-down: o frame traz inline `revisions[]` (id, revisionNumber), `environments[]` ({name, apiRevision}) e `wokflow[]`. A célula COMPLETE SHALL vir de `GET /api-manager/api/v3/revisions/{id}/completeness` (`completenessScore`), uma chamada por revisão exibida, com no máximo 8 chamadas simultâneas; o bloco `completeness[]` do frame do catálogo MUST NOT ser usado (está defasado em relação ao Manager — sondagem de 21/10/2026). A coluna LAST REV (do cabeçalho e da listagem) SHALL exibir o **número** da revisão, traduzido pelo próprio `revisions[]` local (o `lastRevision` do frame é o ID); **sem número resolvível, SHALL renderizar `-`** (nunca o ID). O nome do STAGE resolve via catálogo de workflows de governance **cacheado por execução** (uma chamada por workflow distinto, nunca por linha). Quando o nome do stage não puder ser resolvido, SHALL exibir o id do workflow como degradação. Quando a leitura de completeness de uma revisão falhar (recusa ou indisponibilidade do Manager), a célula SHALL renderizar `-`, as demais linhas SHALL seguir normalmente e o comando SHALL encerrar com exit `0`; no formato texto, a grade SHALL terminar com uma nota indicando quantas revisões ficaram sem completeness e apontando `sen completeness --id X --revision <REV ID>`; em `json`/`yaml`, o campo `completeness_score` SHALL vir `null` e nenhuma nota é impressa. Enquanto as leituras de completeness estiverem em curso, o formato texto SHALL exibir feedback de espera (indicador transitório em terminal; uma linha única fora de terminal); `json`/`yaml` MUST NOT imprimir feedback. A coluna LIFE CYCLE está **aposentada da listagem** (fonte entrega `null` — retorno do detail a mantém dormante, reativa quando a plataforma expor `apiLifeCycle`).

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

- **WHEN** `--id` não corresponde a nenhuma API OU a API não está visível para o chamante (catálogo responde vazio — o servidor pode mascarar ausência e ausência de permissão)
- **THEN** o comando falha com mensagem humana "API não encontrada ou sem permissão de acesso" (sem corpo cru JSON) e exit code `1`, sem chamar a rota de completeness

#### Scenario: Revisões sem `--id`

- **WHEN** `--revisions/-r` é usado sem `--id`
- **THEN** o comando falha com erro educativo apontando o vínculo com `--id` e o sub-help, sem realizar requisição, e exit code `1`
