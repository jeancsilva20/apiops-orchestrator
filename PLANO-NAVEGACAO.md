# Plano de navegação do ambiente Sensedia pela CLI `sen`

Objetivo: o máximo de comandos **somente leitura**, acionados por parâmetros,
com granularidade crescente e saída máquina (`-o json|yaml`), para que agentes
de código usem a CLI como interface de navegação do ambiente — sem repositório
local e sem tocar o Manager.

Cada área abaixo diz o que a CLI cobre, com qual comando, quais cenários foram
validados contra o mapeamento APIM/AG (`sensedia-documentacao-nexus`) e contra
o tenant de teste (CONSULTING, 125 APIs), e o que ficou fora, com o motivo.

Legenda: ✅ coberto e testado · 🔶 coberto com limite · ⛔ indisponível pela CLI.

## 1. Dados das APIs

| Cenário | Comando | Estado | Validação |
|---|---|---|---|
| Catálogo com janela, busca, todas | `sen list api [--query] [--limit/--offset] [--all]` | ✅ | catálogo `api-finder` (doc 01), visibilidade por sessão |
| Colunas de dono, contexto, time e stage | `sen list api --wide` | ✅ | campos `owner/contextType/contextGroupName/wokflow` do finder (doc 01) |
| Recorte por dono, time, contexto, workflow, stage | `sen list api --all --owner u` / `--team t` / `--context organization|group|me` / `--workflow W` / `--stage S` | ✅ | filtros antes da janela, contam só linhas visíveis |
| Identidade, visibilidade, responsável, tags, planos, ambientes e revisões (com stage) | `sen get api --id N` | ✅ | `GET /apis/{id}` (doc 03 §superfícies: as revisões inline são completas) |
| Revisões com completeness | `sen list api --id N --revisions` | ✅ | `/revisions/{id}/completeness` (doc 05) |
| Forma da revisão: recursos, operações, destino/timeout, herança | `sen get resources --id N [--revision R]` | ✅ | shadow-copy por revisão (doc 03), `destination/timeout` por operação |
| Contrato OpenAPI com `x-*` | `sen get swagger --id N` | ✅ | `GET /revisions/{rid}/swagger` (doc 11) |
| Maturidade e sugestões | `sen completeness --id N --revision REVID` | ✅ | doc 05 |
| Árvore canônica (repositório) | `sen export api --id N [--dir]` | ✅ | round-trip com `sen diag structure` |
| Timeline/auditoria | — | ⛔ | não há endpoint isolado; a UI compõe dos saves (doc 09) |
| Chamadas recentes com filtros (API, ambiente, erros, status, URI, operação, revisão) | `sen list calls [--since 24h] [--errors] …` | ✅ | `GET /calls` (doc 10); janela ≤ 7 dias, datas `yyyy-MM-dd'T'HH:mm:ss` UTC |
| Uma chamada pelo trace id, com o pipeline e headers mascarados | `sen get trace --id` | ✅ | `GET /calls/{id}`; `id == traceId == requestID`; `trace` é string JSON de passos |
| Analytics prontos: volumetria, erros, latência, rankings, por hora | `sen get analytics [--api N] [--since 7d] [--errors]` | 🔶 | amostra até 2000 chamadas; o Query Lab do Analytics (OpenSearch) exige sessão do portal |
| Exportação de alto volume em JSON | — | ⏳ previsto | paginar `/calls` até o fim e gravar em arquivo |

## 2. Donos das APIs

| Cenário | Comando | Estado |
|---|---|---|
| APIs por dono, com contexto e times | `sen list owners` | ✅ |
| APIs de um dono | `sen list api --all --owner <username>` | ✅ |
| Dono, responsável e visibilidade de uma API | `sen get api --id N` (bloco visibilidade/responsável) | ✅ |
| Perfil do dono (times, roles, Super Admin) | `sen get user --username u` | ✅ |

## 3. Teams, roles e Access Control

Vocabulário (doc 14): Team = `groups`, Role = `policies`, serviço `/user-management/v1`.

| Cenário | Comando | Estado | Validação |
|---|---|---|---|
| Usuários com busca | `sen list users [--query]` | ✅ | `GET /users?_keyword` |
| Um usuário: status, MFA, times, roles | `sen get user --username u` | ✅ | `/users/{u}`, `/users/{u}/groups`, `/users/{u}/policies` |
| Times com busca | `sen list teams [--query]` | ✅ | `GET /groups` (sem id; nome é a chave) |
| Um time e os membros | `sen get team --name t` | ✅ | `/groups/{name}`, `/groups/{name}/users` (`pageContent`) |
| Roles e produtos habilitados | `sen list roles [--query]` | ✅ | `GET /policies` (14 no tenant; `sensediaManaged`) |
| Uma role: permissões por produto e usuários | `sen get role --id <uuid ou nome>` | ✅ | `/policies/{id}/permissions`, `/policies/{id}/users` |
| Catálogo de permissões de um produto | `sen list permissions --product "API Platform"` | ✅ | `/account-settings/permissions?productName` (71 códigos API Platform, 47 Access Control, 16 AG…) |
| Federated login, audit logs, client apps | — | ⛔ | sem wire capturado no mapeamento |

## 4. Adaptive Governance

| Cenário | Comando | Estado | Validação |
|---|---|---|---|
| Workflows e stages | `sen list workflows` | ✅ | `GET /api-governance/api/v3/workflows` (doc 04/12) |
| Requisitos de cada stage (maturidade, interceptors must/must-not, atributos, ambientes) | `sen get workflow --id W` | ✅ | stages reais 139/327/423/500 |
| Revisão contra o stage atual e o próximo | `sen get governance --id N [--revision R]` | ✅ | `positionType` FIRST/LAST, `flowType` API/RESOURCE/OPERATION, `deployableEnvironments`, `mandatoryDeployment` |
| Atributos e tags válidas | `sen list attributes` | ✅ | regra do pré-check: tag inválida apaga `apiTags` (412/200) |
| APIs por workflow/stage | `sen list api --all --workflow W [--stage S] --wide` | ✅ | `wokflow[]` do finder |
| Impacto (rotas, planos, apps) | `sen get impact --id N [--env E]` | ✅ | `tree-analysis` (doc 12 §5) |
| Binding de atributos feito no painel da UI | — | ⛔ | rota assinada (doc 98 #20); só `apiTags` contam |
| Maturity reports / dashboards / discovery do AG v2 | — | ⛔ | UUIDs dessincronizados do Manager (doc 12) |
| Exception Settings (APIs sem restrição temporária) | — | ⛔ | sem endpoint de leitura capturado |

## 5. Apps

| Cenário | Comando | Estado |
|---|---|---|
| Apps e assinaturas API → planos | `sen list apps [--api N] [--query]` | ✅ |
| Um app | `sen get app --id A` | ✅ |
| Tokens de um app | `sen list tokens --app A` | ✅ |
| Credenciais (clientId/secret) | — | ⛔ de propósito: a plataforma mascara e a CLI descarta |
| Criar app | — | ⛔ UI/portal (doc 08) e fora do escopo de navegação |

## 6. Plans

| Cenário | Comando | Estado |
|---|---|---|
| Planos por API, default, interceptors | `sen list plans [--api N] [--query]` | ✅ (paginação até o fim: 50/50) |
| Fluxo de um plano | `sen get plan --id P` | ✅ |
| Quem assina um plano | `sen list apps --api N` | ✅ |

## 7. Environments

| Cenário | Comando | Estado |
|---|---|---|
| Ambientes (ids, inbound, deploy?) | `sen list environments` | ✅ |
| Um ambiente: gateway, variáveis, tudo no ar | `sen get environment --id E` | ✅ |
| Variáveis por mapa, mascaradas | `sen list variables [--env E] [--key]` | ✅ |
| Desmascarar uma variável | `sen reveal variable --env E --key K [--map M] [--raw]` | ✅ (log de auditoria sem o valor) |
| Inbounds e pools | `sen list inbounds` · `sen list gateway-pools` | ✅ |
| Deploy history por revisão | `sen get api --id N` (NO AR) · `sen get environment` (no ar) | 🔶 só o estado atual; `/deployments` responde 403 |

## 8. Interceptors em FIRST, SECOND e THIRD

Varredura do tenant (125 APIs, revisão corrente): 1076 itens em FIRST, 147 em
SECOND, 2 em THIRD (só `Custom`); status `REFERENCE`, `REMOVED` e `CHANGED_VALUE`.

| Cenário | Comando | Estado |
|---|---|---|
| Fluxo próprio por escopo (raiz, recurso, operação) | `sen get interceptors --id N` | ✅ |
| Fluxo efetivo (herdado − removido + próprio) | `--effective` | ✅ |
| Só um ponto | `--point FIRST|request`, `--point SECOND|response`, `--point THIRD` | ✅ |
| THIRD e outros pontos não governados | bloco `outros pontos` em cada escopo (`other` no JSON) | ✅ |
| Marcações REMOVED e status CHANGED_VALUE | `removes` por escopo; `status` em cada item | ✅ |
| Um interceptor inteiro | `--item ID` | ✅ |

## 9. Conteúdo de interceptors custom e nativos

| Cenário | Comando | Estado | Validação |
|---|---|---|---|
| Conteúdo decodificado por item | `sen get interceptors … --content` / `--item ID` | ✅ | `content` é string JSON (doc 06) |
| Script de um Custom | `sen get custom --custom-id C [--script-only]` | ✅ | doc 15 |
| Referência de campos por tipo | `sen get interceptor-type [--type "Rate limit"]` | ✅ | tabela do doc 06 + chaves observadas em 40 tipos do tenant |
| Conferência do item contra a referência | `--item` mostra conhecidos / fora da referência / esperados ausentes | ✅ | |
| Catálogo vivo de tipos | `sen list interceptors [--custom] [--tag]` | ✅ | 81 no tenant |
| Java custom | tipo `Java` na referência; conteúdo por `--item` | 🔶 | sem endpoint de script Java capturado |

Cenários do doc 06 cobertos por teste unitário: Mock, Rate limit, OAuth, Log,
Client ID validation, Custom, JSON schema validation; mais Log obfuscation,
Header, Cache read/write, Service callout e Internal api call pelas chaves do tenant.

## 10. Fora do escopo (escrita)

`validate`, `publish`, `deploy` continuam sendo os únicos comandos que escrevem.
Nenhum comando de navegação muta o Manager.
