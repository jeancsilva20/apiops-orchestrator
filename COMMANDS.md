# `sen` — guia de navegação do ambiente Sensedia

Referência de todos os comandos da CLI, pensada para quem explora um ambiente
**sem ter o repositório da API localmente**: uma pessoa no terminal ou um agente
de código (Claude Code, por exemplo) que só fala CLI. Cada comando responde a um
nível de detalhe, aponta o próximo passo e tem saída máquina (`-o json`/`-o yaml`).

Convenções:

- Todos os comandos de leitura aceitam `--output/-o text|json|yaml` (`text` é o padrão; `sen get swagger` usa `yaml`).
- `--revision N` é o **número** da revisão como na UI (REV #). `--revision-id` é o id do Manager (REV ID). Sem os dois, vale a revisão corrente (`lastRevision`).
- Ids de interceptor (`[19220]`) são os ids do Manager dentro da revisão; `customInterceptorId` é o id de catálogo usado por `sen get custom`.
- Credenciais nunca aparecem nas listagens: `clientId`, `secret`, código e refresh de token são descartados, e variáveis de ambiente `SECURED` ou que parecem credencial saem mascaradas (`•••••`). O único caminho que escreve um valor sensível na tela é `sen reveal variable`, uma variável por vez e de propósito.
- Erros de negócio saem com mensagem orientada e `exit 1` (ex.: `A API 400 não tem a revisão de número 9. Números disponíveis: 1, 2, 3, 4.`). Sessão expirada pede `sen login`.
- Nada aqui escreve no Manager. Os comandos que escrevem são `validate`, `publish` e `deploy` (ver README).

## Mapa rápido

| Pergunta | Comando |
|---|---|
| Quais APIs existem? | `sen list api [--query x] [--all]` |
| O que é esta API, onde está no ar, que revisões tem? | `sen get api --id 400` |
| Qual a forma da revisão (recursos, operações, destinos)? | `sen get resources --id 400 --revision 4` |
| O que cada escopo executa (interceptors)? | `sen get interceptors --id 400 [--effective] [--content]` |
| Um interceptor inteiro? | `sen get interceptors --id 400 --item 19220` |
| O script de um Custom? | `sen get custom --custom-id 31 [--script-only]` |
| O contrato OpenAPI? | `sen get swagger --id 400 --revision 4` |
| A nota de maturidade e as sugestões? | `sen completeness --id 400 --revision 8948` |
| A revisão passa no stage? O que falta para o próximo? | `sen get governance --id 400 --revision 4` |
| Quem consome a API (planos, apps)? O que quebra se ela mudar? | `sen get impact --id 400 [--env 1]` |
| Os arquivos canônicos da revisão (o que `sen validate` lê)? | `sen export api --id 400 --revision 4 [--dir ./repo]` |
| Quem é dono de cada API? As APIs de um dono, time, contexto ou stage? | `sen list owners` · `sen list api --all --owner u` / `--team t` / `--context me` / `--workflow W --stage S` · `--wide` |
| Só um ponto de execução? E o que está em THIRD? | `sen get interceptors --id 400 --point FIRST|SECOND|THIRD` (THIRD aparece em `outros pontos`) |
| O que o `content` de um tipo de interceptor carrega? | `sen get interceptor-type --type "Rate limit"` (sem `--type`: todos) |
| Quem é este usuário, de que times e roles? Quem está num time? O que uma role permite? | `sen get user --username u` · `sen get team --name t` · `sen list roles` · `sen get role --id <uuid ou nome>` · `sen list permissions --product "API Platform"` |
| O que aconteceu numa chamada (trace id)? | `sen get trace --id <trace id>` |
| Quais chamadas chegaram? Só erros? | `sen list calls [--api N] [--env E] [--since 24h] [--errors] [--uri x]` |
| Volumetria, taxa de erro, latência, top operações/apps/origens? | `sen get analytics [--api N] [--since 7d] [--errors]` |
| Que ambientes, workflows, atributos e tipos de interceptor existem? | `sen list environments` · `sen list workflows` · `sen list attributes` · `sen list interceptors` |
| O que um stage exige? | `sen get workflow --id 327` |
| Variáveis de ambiente? | `sen list variables [--env 1] [--key x]` · `sen get environment --id 1` |
| O valor de uma variável mascarada? | `sen reveal variable --env 1 --key chave [--map M] [--raw]` |
| Apps, planos e tokens? | `sen list apps [--api 400]` · `sen get app --id 42` · `sen list plans [--api 400]` · `sen get plan --id 66` · `sen list tokens [--app 45] [--api 400]` |
| Pessoas e gateway? | `sen list users [--query x]` · `sen list teams` · `sen list inbounds` · `sen list gateway-pools` |

## Trilha típica de um agente

```bash
sen login                                               # uma vez; a sessão fica em .sen_session
sen list api --query letras                             # 0. achar o id
sen get api --id 409                                    # 1. identidade, ambientes, revisões (com o stage de cada uma)
sen get resources --id 409                              # 2. raiz → recursos → operações, contagens por escopo
sen get interceptors --id 409 --resource Letras --effective   # 3. o fluxo que o recurso executa
sen get interceptors --id 409 --item 20111              # 4. um interceptor, conteúdo inteiro
sen get governance --id 409                             # 5. requisitos do stage atual e do próximo
sen get impact --id 409                                 # 6. quem consome
sen export api --id 409 --dir ./letras                  # 7. materializar o repositório e seguir com sen validate
```

---

## Sessão

### `sen login`
Autentica na Orchestrator Auth API e grava a sessão em `.sen_session` (diretório do pacote). Exige `SEN_CREDENTIALS`, `AUTH_HOST` e `AUTH_LOGIN_PATH` (ver README). Todos os outros comandos usam essa sessão.

### `sen --version` · `sen --help` · `sen <grupo> --help`
Respondem sem configuração.

---

## APIs

### `sen list api`
Catálogo de APIs (`api-finder`), respeitando a visibilidade da sessão.

| Opção | Efeito |
|---|---|
| `--id N` | só a API N (uma linha) |
| `--query texto` | busca por nome/descrição, feita pelo Manager |
| `--limit N` / `--offset N` | janela (padrão 10 / 0) |
| `--all` | todas as visíveis (não combina com janela nem `--id`) |
| `--revisions/-r` | com `--id`: tabela REV # · REV ID · STAGE · ENVS · COMPLETE (score de cada revisão) |
| `--owner u` · `--team t` · `--context organization|group|me` · `--workflow W` · `--stage S` | recortam o catálogo **antes** da janela (a janela conta só o que passou); não combinam com `--id`; `--workflow`/`--stage` olham a revisão corrente |
| `--wide/-w` | acrescenta OWNER, CONTEXT, TEAM e STAGE (id do stage e do workflow); em `-o json` acrescenta `owner`, `contextType`, `contextGroupName`, `workflowId`, `workflowStageId` |

### `sen list owners`
Lê o catálogo inteiro e agrupa por dono: quantidade de APIs, contextos usados, times e a lista de APIs (id e nome). Ordem: mais APIs primeiro.

### `sen get api --id N`
Nível 1: nome, versão, basePath, tipo, descrição, visibilidade (tipo, dono, grupo, usuários), responsável, tags, planos; tabela de **ambientes** (inbound URL e qual revisão está no ar); tabela de **revisões** (número, id, ciclo, **stage**, recursos, operações, interceptors na raiz, onde está no ar; `*` marca a corrente). Fecha com os próximos passos.

### `sen get resources --id N [--revision R | --revision-id ID]`
Nível 2: raiz → recursos → operações. Por escopo: destino e timeout (quando declarados), `herda` ou `quebra herança (remove K)`, quantos interceptors são próprios e quantos executa, e quantos ficam fora de FIRST/SECOND (preservados). Mostra o `slug` do recurso (nome da pasta no repositório canônico).

### `sen get interceptors --id N [--revision R | --revision-id ID]`
Nível 3: o fluxo de interceptors por escopo.

| Opção | Efeito |
|---|---|
| `--resource nome|slug|id` | recorta um recurso e as suas operações |
| `--operation "MÉTODO /path"` (ou só o path, ou o id) | recorta uma operação |
| `--effective` | mostra o que o escopo **executa** (herdado − removido + próprio), marcando a origem de cada item |
| `--content` | inclui a configuração decodificada de cada interceptor |
| `--point FIRST|SECOND|THIRD` (ou `request`/`response`/`third`, ou `1`/`2`/`3`) | deixa só esse ponto de execução em cada escopo |
| `--item ID` | nível 4: um interceptor inteiro (escopo, posição, status, `customInterceptorId`, conteúdo; script incluído quando é Custom) e a conferência contra a referência do tipo (campos conhecidos, fora da referência, esperados ausentes). Não combina com as outras opções |

Cada item sai como `[id] posição Tipo resumo`. Marcações `REMOVED` aparecem como `remove ← [id] Tipo (ponto)`; o status de cada item (`REFERENCE`, `CHANGED_VALUE`, `REMOVED`) está no JSON e no `--item`. Itens fora de FIRST/SECOND (por exemplo `THIRD`, visto só em Customs) saem no bloco `outros pontos` de cada escopo (`other` no JSON): não são governados pelo repositório, mas executam.

### `sen get interceptor-type [--type NOME]`
Referência do `content` por tipo de interceptor, montada da tabela do mapeamento (doc 06) e das chaves observadas nas revisões reais do tenant: grupo, pontos de execução, campos com significado, exemplo e observações. Sem `--type`, lista todos os tipos. O catálogo vivo (o que o tenant tem instalado) é `sen list interceptors`.

### `sen get custom --custom-id N [--script-only]`
Nome e script de um Custom do catálogo. `--script-only` escreve só o script, cru, para redirecionar a um arquivo.

### `sen get swagger --id N [--revision R | --revision-id ID] [-o yaml|json]`
Contrato OpenAPI da revisão como o Manager o guarda (com as extensões `x-*`).

### `sen completeness --id N --revision REVID [--score-only]`
Maturidade (completeness) de uma revisão e as sugestões do Manager. **Aqui `--revision` é o REV ID**, não o número.

### `sen get governance --id N [--revision R | --revision-id ID]`
A revisão contra o Adaptive Governance: workflow e stage atual; maturidade; onde está no ar; e, para o **stage atual** e o **próximo**, o veredito de cada requisito:

- `maturidade (completeness) ≥ X%` contra `/completeness`;
- interceptors obrigatórios/proibidos contra o fluxo efetivo de cada escopo (`flowType` API = raiz, RESOURCE = cada recurso, OPERATION = cada operação; `positionType` FIRST/LAST exige a posição), com a lista dos escopos que falham;
- atributos contra os `apiTags` da API (mesma regra do pré-check do publish: atributo com tags cadastradas só conta se declarar ao menos uma; tag inválida não conta e gera aviso);
- deploy obrigatório/proibido por ambiente e deploy fora dos ambientes permitidos pelo stage.

Resumo por stage: `atende` / `não atende` / `não verificável`.

### `sen get impact --id N [--env E]`
Grafo de impacto (`tree-analysis`): rotas com método, id de operação e destino; planos e os apps inscritos (status, `appId`). Sem `--env`, usa o primeiro ambiente onde a API está no ar.

### `sen export api --id N [--revision R | --revision-id ID] [--dir PASTA] [--force]`
Materializa a árvore canônica (`api-basic-info.yaml`, `all.yaml`, `resources/<slug>/resource.yaml`, `resources/<slug>/<método>_<path>.yaml`). Sem `--dir`, imprime cada arquivo precedido de `# ==> caminho`; com `--dir`, grava e recusa sobrescrever sem `--force`. A pasta gerada é lida por `sen validate`.

---

## Catálogos do tenant

### `sen list environments`
Ambientes: id, nome, inbound URL, se aceita deploy, descrição.

### `sen get environment --id E`
Um ambiente: gateway (pool, host, protocolo/TLS), mapas de variáveis com cada chave e valor (mascarado quando sensível), e **todas as APIs/revisões no ar** nele.

### `sen list variables [--env E] [--key texto]`
Variáveis de ambiente achatadas por mapa (ambiente, mapa, chave, tipo, valor). Sem `--env`, percorre todos os ambientes. A listagem é **sempre mascarada**: valor `SECURED`, e valor `DEFAULT` cuja chave ou valor parece credencial (`secret`, `password`, `token`, `auth`, `client_id`, `Basic …`, `Bearer …`), saem como `•••••`.

### `sen reveal variable --env E --key CHAVE [--map MAPA] [--raw]`
Desmascara **uma** variável, pelo nome exato, e mostra o valor como o Manager o devolve (ambiente, mapa, tipo e se é sensível). Se a chave existir em mais de um mapa, o comando pede `--map`. `--raw` escreve só o valor, para redirecionar a um arquivo ou exportar numa variável de shell. Cada revelação vai para o log da CLI (ambiente, mapa e chave; nunca o valor).

### `sen list workflows`
Workflows do Adaptive Governance (categoria, grupo) e os stages em ordem, com um resumo das regras: maturidade mínima, quantidade de interceptors e atributos exigidos, ambientes de deploy.

### `sen get workflow --id W`
Os requisitos de cada stage por extenso, com ids traduzidos para nomes (atributos, ambientes).

### `sen list attributes`
Atributos de governança (id, nome, tags válidas, em uso). São os `attributeName` de `apiTags` em `api-basic-info.yaml`.

### `sen list interceptors [--custom] [--tag T]`
Catálogo de tipos de interceptor: o `type` aceito nos YAML, origem (nativo/custom), id do custom, pontos de execução (request/response), flow e tags.

---

## Consumo

### `sen list apps [--api N] [--query texto]`
Apps (consumidores): id, nome, status, desenvolvedor, APIs assinadas com os planos entre colchetes, quantidade de tokens. `--api` deixa só os apps inscritos num plano daquela API.

### `sen get app --id A`
Um app: status, desenvolvedor, descrição, tokens, e as assinaturas API → planos (marcando o default).

### `sen list plans [--api N] [--query texto]`
Planos: id, nome, se é default, API dona, quantidade de interceptors do plano.

### `sen get plan --id P`
Um plano e os interceptors que ele acrescenta ao fluxo (request/response, com conteúdo).

### `sen list tokens [--app A] [--api N]`
Access tokens emitidos: id, dono, app, status, expiração, APIs alcançadas. O código e o refresh nunca são exibidos.

---

## Trace e analytics

Fonte: `GET /calls` e `GET /calls/{id}` do Manager (doc 10). A plataforma guarda e serve só os **últimos 7 dias**; janelas maiores são encolhidas e o comando avisa. Datas em UTC. Credenciais da chamada (`accessToken`, `appSecret`, `appToken`, `clientId`) são descartadas, e headers de credencial (`authorization`, `cookie`, `set-cookie`, `x-api-key`, `client_id`, `client_secret`, `x-auth-token`…) saem mascarados.

### `sen list calls [--api N] [--env E] [--since 24h] [--until agora] [--errors] [--status-from A --status-to B] [--uri trecho] [--operation-id O] [--revision-id R] [--limit 20] [--page 1]`
Chamadas da janela: trace id, quando, API, método, URI, status, duração, app. `--since`/`--until` aceitam `30m`, `24h`, `7d`, `YYYY-MM-DD` ou ISO. `--errors` é 400–599. O rodapé traz o total da janela e a página.

### `sen get trace --id <trace id> [--no-headers]`
Uma chamada pelo trace id (é o mesmo `x-request-id` que o gateway devolve): método, URI, status e resultado; API, revisão, recurso, operação, ambiente; tempos total/gateway/backend e tamanhos; app, dono do token, origem, cache, billing; os **passos do pipeline** (`timeMillis` e mensagem de cada interceptor/roteamento) e os headers de request e response, mascarados.

### `sen get analytics [--api N] [--env E] [--since 24h] [--until] [--errors] [--uri x] [--sample 500] [--top 5]`
Queries prontas sobre uma amostra das chamadas mais recentes da janela (até `--sample`, teto 2000; o total da janela vem sempre): classes de status e taxa de erro; latência média, p50, p95, máx, gateway e backend; rankings de status, APIs, operações, apps, ambientes e origens; chamadas por hora; erros recentes com trace id. Quando a amostra é parcial, o comando diz e aponta `--sample` ou `sen list calls -o json` por página. Volumes maiores ficam para um modo de exportação em JSON, previsto.

## Pessoas e gateway

### `sen list users [--query texto]`
Usuários do Access Control: username, nome, e-mail, status, provedor.

### `sen get user --username u`
Um usuário: nome, e-mail, status, provedor, MFA, **times** e **roles** (e se é Super Admin). Aponta `sen list api --all --owner u` para as APIs dele.

### `sen list teams [--query texto]`
Times (`groups`): os nomes usados na visibilidade GROUP das APIs e nos workflows de time.

### `sen get team --name t`
Um time: descrição e membros (username, nome, status).

### `sen list roles [--query texto]`
Roles (`policies`) do Access Control: nome, se é gerida pela Sensedia ou do tenant, produtos que habilita, id.

### `sen get role --id <uuid ou nome exato>`
Uma role: permissões agrupadas por produto (código e nome) e os usuários que a têm.

### `sen list permissions [--product "API Platform"]`
Catálogo de códigos de permissão de um produto (`API Platform`, `Access Control`, `Adaptive Governance`, `Analytics`, `Developer Portal`, `Integrations`, `Connect Catalog`, `AI Gateway`, `Observability`), agrupado pelo domínio do código.

### `sen list inbounds`
Endereços de entrada do gateway: host, protocolo/TLS, versões de TLS, tipo de gateway.

### `sen list gateway-pools`
Pools de gateway e quantas rotas cada um serve.

---

## Escrita (fora da navegação)

| Comando | O que faz |
|---|---|
| `sen validate [--repo PASTA]` | valida o repositório e grava na Draft para obter o veredito da governança |
| `sen publish` | publica o repositório na revisão do ambiente (só na esteira, `EXECUTION_MODE=pipeline`) |
| `sen deploy` | faz o deploy da revisão no ambiente (só na esteira) |

## O que não está disponível pela CLI (e por quê)

- **Analytics do produto (OpenSearch, Query Lab)**: o motor `/analytics/internal/search` exige a sessão do portal e devolve a página de login ao token da CLI; a CLI usa `/calls` do Manager (7 dias) para trace e analytics prontos.
- **Trace além de 7 dias**: a plataforma não serve.
- **Binding de atributos feito no painel da UI**: viaja numa rota assinada que a CLI não lê. Só os `apiTags` contam.
- **Relatórios do Adaptive Governance v2** (`maturity-reports`, dashboards, discovery): usam UUIDs próprios dessincronizados do Manager.
- **Criação/edição de apps, planos, tokens, usuários**: fora do escopo (a CLI de navegação é somente leitura).
