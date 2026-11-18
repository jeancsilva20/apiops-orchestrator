# APIOPS-115 · Cenários de teste — contrato OpenAPI no `publish` e no `validate`

> Aberto em 2026-10-23; **desenho fechado em 2026-10-26** na change `add-openapi-contract`. Cenários marcados com **❓Qn** têm o
> resultado esperado pendente da pergunta *n* (seção final). **🔬** = depende de medição
> na API-lab 425 (consulting); escrita só lá.

## Decisões já fechadas (base dos cenários)

| # | Decisão |
|---|---|
| D1 | A edição do contrato é uma **etapa do `publish` e do `validate`**, depois do PUT de revisão e da E3.1. Não há comando `sen swagger` agora. |
| D2 | Etapa: `GET /revisions/{id}/swagger` → merge → PUT → conferência nova. A E3.1 atual não muda. |
| D3 | **Revista pelo decisor.** Campo de contrato **ausente no repo vai em branco** no Manager. Ex.: `responses` só no Manager → aviso na confirmação; confirmado, sobrescreve. |
| D4 | `components.yaml` é **opcional**. Com a D3, todo `$ref` precisa resolver **no repo** (o que só está no Manager é apagado). |
| D5 | **Revista pelo decisor.** Parâmetros continuam possíveis no `resource.yaml`, com validação local (ex.: `id` que não existe na rota). Regra exata ❓Q9. |
| D6 | `servers` e `info.*` **não entram no repo**: mantidos do GET feito depois da atualização do fluxo. |
| D7 | **Revista pelo decisor.** GET com `swagger: "2.0"` **bloqueia só a etapa de contrato**, com erro ao usuário; o fluxo segue normal. |
| D8 | `x-*` conferidos por **igualdade estrutural**, não byte a byte. |
| D9 | **A etapa roda sempre.** Premissa: o repo é puxado já com os campos de contrato. Repo sem contrato apaga a documentação do Manager — e o `validate` mostra isso antes, para o usuário perceber. |
| D10 | **Sem rollback.** 5xx retenta (o `HttpClient` já retenta); persistindo, avisa e mantém o fluxo gravado. Problema da plataforma (2.0, recusa, falha, conferência divergente) sai como **warning no `-o`** de `validate` e `publish`, exit 0. |
| D12 | **Erro no que o dev declara** (`$ref` inexistente, parâmetro de path fora da rota, exemplo com tipo errado) **aborta o comando antes de qualquer escrita**, como os demais erros do `validate`. |
| D13 | Parâmetro de path no `resource.yaml` precisa existir em **todas** as rotas do recurso, senão erro; o que não é de todas vai na rota. |
| D14 | O `publish` também roda o serviço Swagger validate. Adoção parcial vale para a API toda. `summary` ausente copia a `description`. |
| D15 | `components.yaml` segue o padrão OpenAPI nas seções de reutilização: `schemas`, `securitySchemes`, `responses`, `requestBodies`, `headers`, `examples`. **`parameters` fica de fora** (a I-8 mostrou que o Manager expande o `$ref` de parâmetro; o repo usa o formato que o Manager guarda), assim como `links` e `callbacks` — declará-los é erro (fora do modelo); se existirem no Manager, ficam como vieram do GET. As seções do modelo são governadas pelo repo (D3). Cada `$ref` precisa existir **e** apontar para a seção que a posição pede. Parâmetros são escritos por extenso, na operação ou no `resource.yaml` (copiado para cada operação do recurso, D18); mesmo `name`+`in` nos dois → **a operação sobrescreve**. |
| D16 | O repositório que puxa a API do Manager passa a puxar também o contrato (premissa da D9). |
| D17 | "Em branco" numa operação = estado de rota não documentada que o Manager gera: `parameters: []` e `responses: {'200': {description: OK}}` (o OpenAPI exige ao menos uma resposta). O importador puxa rota não documentada assim. **Revista em 2026-10-26:** na subida, `responses` ausente no arquivo da operação é **erro de validação** (alguém apagou), sempre — opção (a). Consequência: a versão do orquestrador só vai para uso depois que todos os repositórios forem puxados de novo com o importador ajustado. `parameters` ausente = sem parâmetros. |
| D18 | Parâmetros do `resource.yaml` entram em **cada operação** do recurso, não no path item (um path pode ter métodos em recursos diferentes); `parameters` de path item vão em branco. |
| D19 | ~~Guarda de THIRD/ANY~~ — retirada depois da I-2 (2026-10-26): o item vai no documento como veio do GET; sem conferência própria nesta fase (caminho feliz). |

**Desenho fechado em 2026-10-26** na change [`add-openapi-contract`](../../openspec/changes/add-openapi-contract/) (D1–D14 do `design.md` consolidam as decisões acima).
| D11 | Validações locais num **serviço isolado ("Swagger validate")**: chamado hoje pelo `validate`, reutilizável por um comando futuro. Também compara o swagger do Manager com o repo e avisa o que vai sumir, na confirmação — por isso o swagger é lido **antes** do PUT da revisão. |

Com o decisor: **T2** (falha depois do runtime gravado) respondida pela D10. **T1**
(conferência nova diverge) presumida igual à D10 — ❓Q11.

---

## A · Sem contrato no repositório (regressão — "sem impacto")

| ID | Cenário | Esperado |
|---|---|---|
| A1 | Repo sem nenhum campo de contrato, Manager também sem documentação | Fluxo idêntico a hoje; a etapa roda, o merge não muda nada e **não há PUT do swagger** (Q2) |
| A2 | API com documentação feita à mão no Manager, repo sem contrato | A documentação vai em branco (D3/D9); o `validate` lista na confirmação o que some; o `publish` leva o mesmo aviso no `-o` |
| A3 | Suíte unitária atual | Passa sem alteração de teste existente (salvo as falhas pré-existentes da linha de base) |
| A4 | Repo com `components.yaml` e nenhuma operação o referencia | Os schemas entram em `components` |
| A5 | Fluxo (interceptors, destinos, recursos, rotas) de qualquer repo | Gravado e conferido exatamente como hoje, com ou sem contrato |

## B · Leitura do repositório (E1)

| ID | Cenário | Esperado |
|---|---|---|
| B1 | `components.yaml` na raiz | Reconhecido; não vai para `ignorados` |
| B2 | `components.yml` (extensão `.yml`) | ❓Q5 — hoje cairia em `ignorados` e o `$ref` falharia sem pista |
| B3 | `components.yaml` com YAML inválido | `ArquivoIlegivelError`, exit 1, antes de qualquer escrita (mecanismo atual) |
| B4 | `components.yaml` vazio | Sem efeito; não conta como campo de contrato para D9 |
| B5 | `components.yaml` dentro de `resources/<slug>/` | Ignorado (não nomeia método); ❓Q5 se avisa |
| B6 | `components.yaml` com `responses`, `requestBodies`, `headers`, `examples` | Aceito, mesma regra dos `schemas` (D15) |
| B6b | `components.yaml` com `parameters`, `links` ou `callbacks` | Erro, antes de qualquer escrita (D15) |
| B7 | `servers` no `api-basic-info.yaml` (seguindo o doc 4 antigo) | ❓Q5 (D6: não entra) |
| B8 | `parameters` no `resource.yaml` | Aceito (D5); entra no path item de cada rota do recurso |
| B10 | Parâmetro de path no `resource.yaml` que não existe em alguma rota do recurso (ex.: `id` em `Tarefas`, que tem `/tarefas` e `/tarefas/{id}`) | Erro, antes de qualquer escrita (D12, D13) |
| B11 | Mesmo `name`+`in` no `resource.yaml` e na operação | A operação sobrescreve (D15) |
| B12 | `$ref: '#/components/parameters/X'` na lista `parameters` da operação ou do `resource.yaml` | Erro, antes de qualquer escrita (D15) |
| B13 | Swagger do Manager tem `components.responses`/`schemas`… que o repo não declara | Vão em branco, com aviso (D3 + D15) |
| B14 | Swagger do Manager tem `components.parameters`/`links`/`callbacks` | Mantidos do GET (fora do modelo, não governados) |
| B9 | Chave `x-*` num YAML do repo | ❓Q5 (`x-*` são do Manager) |

## C · Merge

| ID | Cenário | Esperado |
|---|---|---|
| C1 | `responses` declarado numa operação que já tem `responses` no Manager | O do repo substitui o campo inteiro |
| C2 | Operação sem `responses` no repo | **Erro de validação**, exit 1, antes de qualquer escrita (D17 revista) |
| C2b | Operação com `responses: {'200': {description: OK}}` no repo e respostas documentadas no Manager | O Manager fica com o estado não documentado; aviso na confirmação (local) ou nos avisos (esteira) |
| C15 | Revisão com interceptor em `THIRD` | Vai no documento como veio (I-2); sem conferência própria nesta fase (caminho feliz) |
| C3 | Schema com o mesmo nome no repo e no Manager | O do repo substitui o schema inteiro |
| C4 | Schema só no Manager | Removido (D3), com aviso |
| C14 | Repo declara contrato só em parte das operações | As demais vão em branco, com aviso listando cada uma (D14) |
| C5 | Schema só no repo | Adicionado |
| C6 | Parâmetro do repo com o mesmo `name`+`in` de um do Manager que tem `x-example` | Repo prevalece nos campos; o `x-example` é mantido. Implementado em 2026-10-26 (antes o `parameters` era trocado inteiro e o `x-example` se perdia, visto na rev 1 da 426); medido na Draft da 425: mantido no `validate` sem mudança e na regravação com descrição mudada |
| C7 | Operação com `description` no YAML e `summary` ausente | `summary` = `description` (D14) |
| C8 | `security: []` numa operação (rota pública, ex. health-check) | Vai explícito; `[]` ≠ ausente |
| C9 | Campo com valor `null` / `~` no YAML (`responses: ~`) | Igual a ausente: vai em branco (D3) |
| C10 | Dev quer **remover** do Manager algo que só existe lá | Basta não declarar (D3) |
| C11 | `x-interceptors`, `x-resource-name`, `x-destination` da operação | Intactos, mesmo com campos G substituídos na mesma operação |
| C12 | `tags` de operação sem declaração em `tags` da raiz | Aceito (OpenAPI permite) |
| C13 | Merge produz documento igual ao GET (contrato sem mudança) | ❓Q2 |

## D · Validação do contrato antes de escrever

| ID | Cenário | Esperado |
|---|---|---|
| D-1 | `$ref` para schema que não existe no repo | Aborta antes de qualquer escrita, exit 1, citando o arquivo e o schema (D12) |
| D-2 | `$ref` para schema que só existe no Manager | Erro como D-1 (o schema seria apagado pela D3) |
| D-14 | `example` com tipo diferente do `schema` do parâmetro/propriedade | Aborta antes de qualquer escrita (D12) |
| D-19 | Propriedade, schema, parâmetro, resposta ou `summary` com descrição abaixo do mínimo do completeness | Warning, segue (I-7) |
| D-20 | Schema primitivo com `enum` (ex.: `StatusTarefa`) | Warning: o completeness acusa "sem propriedades" (I-7) |
| D-15 | `$ref` que existe, mas de seção errada para a posição (ex.: `'404': $ref: '#/components/parameters/Page'`) | Aborta antes de qualquer escrita, citando arquivo, posição e a seção esperada (D15) |
| D-16 | Componente que referencia outro (`responses.NaoEncontrado` → `schemas.Erro`) | Resolvido; a mesma regra vale dentro do `components.yaml` |
| D-17 | Cadeia de `$ref` em ciclo fora de `schemas` (`responses.A` → `responses.B` → `responses.A`) | Aborta antes de qualquer escrita; ciclo em `schemas` é permitido (estrutura recursiva) |
| D-3 | Schema do repo referencia outro schema inexistente | Aborta como D-1 |
| D-4 | `$ref` externo (`./schemas/x.yaml`, URL) | ❓Q4 |
| D-5 | `$ref` no formato do Swagger 2.0 (`#/definitions/X`) | ❓Q4 |
| D-6 | `security` global aponta para esquema não definido em lugar nenhum | Aborta como D-1 |
| D-7 | Status declarado como número (`200:`) | Normalizado para `'200'` |
| D-8 | `example: 2024-01-01`, `on`/`off`/`yes`/`no` no YAML | Normalizados para o tipo que o autor quis (string ISO, string) |
| D-9 | `requestBody` em `GET`/`DELETE` | ❓Q4 |
| D-10 | `operationId` repetido entre operações | ❓Q4 |
| D-11 | Response sem `description` | ❓Q4 |
| D-12 | Parâmetro de path declarado que não está no template da rota (ou o inverso) | ❓Q4 |
| D-13 | Erro de OpenAPI que já existia no swagger do Manager (não vem do repo) | ❓Q4 |

## E · GET do swagger

| ID | Cenário | Esperado |
|---|---|---|
| E-1 | GET responde `swagger: "2.0"` | Etapa de contrato bloqueada; o fluxo é gravado normalmente (D7); warning no `-o`, exit 0 (D10) |
| E-2 | GET responde `openapi: 3.1.x` | ❓Q4 |
| E-3 | GET responde corpo não JSON (YAML em texto) | 🔬 formato; o adapter trata ou falha com mensagem clara |
| E-4 | GET 403/404/5xx | Mensagem da família, como os demais GETs |
| E-5 | Rota do repo ausente no GET depois da E3.1 | Aborta: o swagger não cria rota |
| E-6 | Path do GET com `basePath` embutido ou barra final, diferente do `path` do repo | 🔬 casamento por (método, path) |

## F · PUT do swagger

| ID | Cenário | Esperado |
|---|---|---|
| F-1 | PUT 400/422 com motivos | Warning no `-o` com os motivos da plataforma; fluxo mantido; exit 0 (D10) |
| F-2 | PUT 412 do Adaptive Governance | 🔬 E-3; se roda, mesmo tratamento do bloqueio atual (exit 3) |
| F-3 | PUT 200 mas o contrato não foi gravado (perda silenciosa) | Pego pela conferência nova (G) |
| F-4 | 5xx/timeout depois do envio | Retry do `HttpClient` é seguro (o corpo é o documento inteiro); esgotou → aviso, fluxo mantido (D10) |
| F-5 | Documento grande (413) | Mensagem da família |

## G · Conferência nova (depois do PUT do swagger)

| ID | Cenário | Esperado |
|---|---|---|
| G-1 | Contrato gravado como declarado, `x-*` e runtime iguais | Sucesso |
| G-2 | Campo de contrato declarado ausente ou diferente no GET de conferência | Divergência ❓Q11 |
| G-3 | `x-*` diferentes do GET anterior | Divergência ❓Q11 |
| G-4 | Runtime diferente do que a E3.1 aprovou (fluxo, ordem, `content`, marcações, destinos, operações) | Divergência ❓Q11 |
| G-5 | `workflowId`/`workflowStageId`, `apiTags`, `apiResponsible` mudaram | Divergência ❓Q11 — 🔬 se o PUT preserva |
| G-6 | Ids dos interceptors mudaram | **Não** é divergência (o Manager recria a cada PUT) |
| G-7 | Chaves locais dos `x-interceptors` renumeradas | **Não** é divergência (D8) |
| G-8 | Manager explicita `style`/`explode`/`required: false` em parâmetros e headers | **Não** é divergência (medido na I-8) |
| G-9 | Manager reordena o `required` de um schema | **Não** é divergência (medido na I-8) |
| G-10 | Manager expande o `$ref` de parâmetro da operação | **Não** é divergência: compara resolvido (medido na I-8) |

## H · Fluxo nos comandos

| ID | Cenário | Esperado |
|---|---|---|
| H-1 | `validate` local: confirmação | O texto avisa que o swagger também será gravado e lista o que some da documentação do Manager (D3, D11) |
| H-11 | `publish` (sem confirmação) com contrato que apaga documentação do Manager | Os mesmos avisos vão para a saída, como os do fluxo hoje |
| H-12 | `publish` com erro no contrato declarado | Aborta antes de qualquer escrita, como o `validate` (D12, D14) |
| H-2 | `validate` local: dev responde "não" | Nenhum dos dois PUTs; exit 130 (atual) |
| H-3 | Pré-check de governança bloqueia | Nada gravado, swagger incluso; exit 3 (atual) |
| H-4 | PUT da revisão recusado | Etapa de contrato não roda (atual) |
| H-5 | E3.1 diverge | Etapa de contrato não roda; exit 1 (atual) |
| H-6 | `validate`: etapa de contrato antes do completeness | O score já reflete a documentação 🔬 (se considera) |
| H-7 | `validate` na esteira | Grava na revisão de `TARGET_REVISION_NUMBER`, como o PUT da revisão |
| H-8 | Saída `-o` quando o contrato não sobe | Warning em `achados` (`validate`) e em `avisos` (`publish`); exit 0 (D10) |
| H-9 | Dois `publish` seguidos com o mesmo repo | ❓Q2 |
| H-10 | `deploy` depois do `publish` | A revisão no ar carrega o contrato 🔬 |

## I · Medições na 425 (viram testes de integração opt-in)

| ID | Pergunta |
|---|---|
| I-1 | O Adaptive Governance roda no `PUT /swagger`? (E-3) — **não medida, por decisão** (2026-10-26): o desenho trata os dois desfechos |
| I-2 | Interceptors THIRD/ANY passam inteiros pelo swagger? (E-4) — **medida em 2026-10-26** na Draft da 425 (restaurada): um `Custom` em `THIRD` igual ao da 417 atravessa o PUT de swagger **igual** quando está no documento; um swagger **sem** ele o apaga. `ANY` não medido (nenhuma das 41 APIs lidas tem) |
| I-3 | O PUT preserva `workflowId`/`workflowStageId`, `apiTags`, `apiResponsible`, descrição de recurso, destinos? |
| I-4 | `tags` de operação diferente do `x-resource-name` move a operação de recurso? **Não** — na I-8, `tags: [Tarefas]` em rotas dos recursos `Quebra` e `Heranca` não moveu nada (conferência sem divergência) |
| I-5 | `securitySchemes`/`security` criam ou alteram interceptor? |
| I-6 | Formato do GET em outras APIs do consulting (só leitura): sempre OpenAPI 3? JSON? — **medida em 2026-10-26** (40 APIs): sempre JSON; **11 em Swagger 2.0**, 25 em 3.0.0, 2 em 3.0.3, 2 em 3.0.4; `components` usados: `schemas` (5), `requestBodies` (2), `securitySchemes` (2); nenhum `$ref` de parâmetro; `servers` relativo ou absoluto; nenhum item fora de `FIRST`/`SECOND` |
| I-7 | O completeness considera a documentação? — **sim, medida em 2026-10-26** na Draft da 425: com o contrato da rev 2, a nota foi de 97 para **89,5** (13 → 24 sugestões). Saíram as de `summary` vazio e de resposta "OK" curta; entraram as de descrição vazia ou curta em parâmetro, propriedade e schema (mínimos: `summary` e resposta > 4 caracteres; propriedade ≥ 9; schema > 9 e com propriedades) |
| I-9 | Que schemas o completeness acusa como "has no properties"? — **medido em 2026-10-27** na Draft da 425 (schemas referenciados por uma resposta; Draft restaurada): acusa `string` com e sem `enum`, `object` sem `properties`, `array`, `allOf` e mapa (`additionalProperties`); **não** acusa `object` com `properties` nem com `properties: {}` vazio. O Manager só olha a chave `properties`: com `properties: {}`, mapa e `allOf` também deixam de ser acusados, sem mudar a nota (97,0 → 97,0). `oneOf`/`anyOf` não medidos (mesma regra presumida) |
| I-10 | Rota nova vai ao swagger no PUT da revisão, e o PUT do swagger mexe no fluxo? (chamado ECAD 4058988: rota nova salva na rev 4 da 474 ficou só em `x-resources`) — **medido em 2026-10-27** na 425, rev 1 pelo `validate` e rev 2 pelo `publish`, 9 etapas cada (restauradas do backup): rota nova sempre no swagger logo depois do PUT da revisão, inclusive recurso com nome de path e `{id}` — o caso ECAD **não reproduziu**; o PUT do swagger não mudou o fluxo das rotas do repositório (herda/quebra, item novo, só `description`, rota nova com e sem itens, volta a herdar). **Bug achado:** método removido de um path que mantém outro fica órfão no swagger e o PUT do swagger o devolvia ao fluxo — corrigido pela D15. Detalhe de leitura: o marcador `REMOVED` guarda a `position` do item do pai, então empata com item próprio e a ordem do GET varia |
| I-11 | O swagger pode ser alinhado ao fluxo quando o Manager não o sincroniza? (D16) — **medido em 2026-10-28**. Leitura: a montagem dos `x-*` a partir do GET da revisão bate com o export do Manager em todas as revisões em dia (lab, backups e 16 revisões OpenAPI 3 do consulting, 34 tipos); diverge só nas dessincronizadas — API 200 rev 2 (`POST /teste` e 3 interceptors fora do swagger) e API 3 rev 19 (itens a mais no fluxo). Na 425: `POST /revisions` apagou as revisões 1–3 (a API ficou sempre com 2; sobraram 4 e 5); a rev 5 nasceu com `POST /c1-pura` fora do swagger e marcadores para chaves inexistentes, a rev 6 (salva pela UI) com marcadores apontando para o pai errado, e a rev 8 deixou de atualizar o swagger nos PUTs da revisão. Swagger alinhado e gravado: fluxo idêntico (ids de rota inclusos) na rev 2 (4 cenários simulados), na rev 8 e no `sen publish` real nas revs 5 e 6, com rota nova que o Manager não levou ao swagger; depois de alinhada, a rev 8 voltou a sincronizar nos PUTs seguintes. Tipos `GZip pack`/`unpack`, `Java`, `Cache invalidation`, `Additional Info` medidos na rev 8: a regra erra os três primeiros (`GZIPPACK`, `GZIPUNPACK`, `CUSTOM_JAVA`), e o PUT do swagger com o nome da regra é recusado ("Invalid interceptors") |
| I-8 | O Manager aceita e devolve intactos `components.responses`/`parameters`/`requestBodies`/`headers`/`examples` e os `$ref` para eles? Insumo: `exemplo-components-reutilizaveis.yaml` (válido no Redocly CLI 1.25.0, regra `minimal`). **Medido em 2026-10-23 na revisão 2 (id 9554) da 425 — o estado ficou lá:** ver "Resultado da I-8" abaixo |

### Resultado da I-8 (2026-10-23, API 425, revisão 2, id 9554)

`PUT /swagger` aceito (`{"result": "success"}`). O que o GET devolveu:

| Item | Resultado |
|---|---|
| As 7 seções de `components` | **Mantidas**, inclusive as não referenciadas (`requestBodies`, `parameters.IdTarefa`) |
| `$ref` em `responses.<status>` | **Mantido** |
| `$ref` em `headers` de resposta | **Mantido** |
| `$ref` em `examples` | **Mantido** |
| `$ref` em `requestBody` (I-8b) | **Mantido** |
| `$ref` de schema dentro de parâmetro | **Mantido** |
| `$ref` de **parâmetro** na lista `parameters` da operação | **Expandido**: o Manager troca o `$ref` pelo parâmetro por extenso |
| Parâmetros e headers | O Manager explicita os padrões do OpenAPI: `style`, `explode`, `required: false` |
| `required` dos schemas | Reordenado (alfabético) |
| `info.contact`, `tags`, `security` | Mantidos |
| `info.title`/`version`/`description` | Iguais aos de antes |
| `x-*` | 17 de 17 iguais, sem renumeração |
| Runtime (`revision_payload.conferir` antes × depois) | **Sem divergência** |
| `workflowId`/`workflowStageId`, `apiTags`, `apiResponsible`, nome, descrição, descrição/destino dos recursos | Iguais |
| `security`/`securitySchemes` | Não criaram interceptor (contagem por escopo igual) — responde a **I-5** |
| Ids dos interceptors | Mudaram (recriados), como já medido |

**I-8b (mesmo dia, mesma revisão):** criada `POST /c1-pura` no recurso `Quebra` (`x-resource-name`, `x-interceptors: {}`) com `requestBody: $ref '#/components/requestBodies/NovaTarefa'`. PUT aceito; o **`$ref` em `requestBody` foi mantido**, `responses` iguais, a rota caiu no recurso `Quebra` e a única diferença de runtime foi a própria rota nova; workflow/stage iguais. A rota ficou na revisão 2.

Consequências para o desenho:
- A conferência nova (G) e o "merge sem mudança não faz PUT" (Q2) comparam o documento **normalizado**: `$ref` de parâmetro resolvido, padrões do OpenAPI aplicados e `required` como conjunto. Sem isso, divergem sempre — e o PUT roda sempre.
- O repo que puxa a API recebe os parâmetros por extenso: o `$ref` de parâmetro não volta na ida e volta.

---

## Perguntas em refino (grill)

| Q | Pergunta | Recomendação | Decisão |
|---|---|---|---|
| Q1 | Erro de contrato do repo (D-1, D-14…) bloqueia o comando inteiro ou só a etapa de contrato, como o 2.0? | Só a etapa de contrato, coerente com a D7 | **Comando inteiro, antes de escrever** (D12) |
| Q2 | Merge sem mudança: pula o PUT do swagger? | Sim — evita recriar os interceptors à toa | Assumido, sem objeção |
| Q3 | Como remover do Manager algo que só existe lá? | — | Não declarar (D3) |
| Q4 | Validação do documento final: quais checagens? | 15 checagens, sem validador genérico | Aprovada; virou 16 com `responses` obrigatório, mais avisos de completeness (design D6 da change) |
| Q5 | Coisa fora do modelo no repo (`servers`, `x-*`, `components.yml`): erro ou aviso? | Erro (D12) | Assumido, sem objeção |
| Q6 | `summary` ausente: preserva ou copia a `description`? | | Copia a `description` (D14) |
| Q7 | `components` além de `schemas`/`securitySchemes` (ex.: `parameters`)? E o mesmo `name`+`in` no recurso e na operação? | Seções de reutilização do padrão; repetição = erro | Seções de reutilização do padrão, **sem `parameters`** (I-8), `links` e `callbacks`; a operação sobrescreve (D15) |
| Q8 | Saída JSON: onde entra o resultado da etapa? | | Warning no `-o` (D10) |
| Q9 | Parâmetro de path no `resource.yaml`: todas as rotas ou só as que o têm? | Todas, senão erro | Todas, senão erro (D13) |
| Q10 | A etapa só roda se o repo declarar contrato? | Sim | **Não — roda sempre** (D9) |
| Q11 | Conferência nova diverge: mesmo tratamento da D10? | Sim | Assumido, sem objeção |
| Q12 | Adoção parcial apaga a documentação das demais operações? | Sim, por API | Sim (D14) |
| Q13 | Exit code quando o fluxo sobe e o contrato não | Código próprio | Exit 0 + warning no `-o` (D10) |
| Q14 | O `publish` também roda o serviço Swagger validate? | Sim | Sim (D14) |
| Q15 | Seções de `components` que o repo não pode declarar e existem no Manager | Manter do GET | Com a D15 o repo declara quase todas; só `links`/`callbacks` ficam do GET |
