# Sondagem do deploy no API Manager — 2026-10-19

| Meta | Valor |
|---|---|
| Status | **CONCLUÍDA** — base empírica do change `add-sen-deploy` |
| Alvo | API **417** ("Serviço de Letras 2.0.0"), tenant `consulting`, `platform-production.sensedia.com` |
| Credencial | token de superadmin do `.sen_session` (`sen login --service`), nunca impresso |
| Autorização | explícita do responsável, para leituras e escritas na 417 |
| Estado final | **restaurado**: revisão 9327 (nº 3) no ar só no ambiente 7 (deploy 269) |
| Origem do endpoint | curl da UI do Manager (`.../revisions/9327/edit/environments/7/confirm`) |

## 1. Estado de partida

| Revisão | id | Stage (AG) | No ar |
|---|---|---|---|
| 1 | 9161 | 1402 | — |
| 2 | 9175 | 1402 | — |
| 3 | 9327 | 1402 | ambiente 7 (`DEV-APIOPS`), deploy 266 |

Workflow 500, stage 1402 "Teste": `completenessRequisite: 0.0`, `attributesRequisites` 149 e 231
(`mustHave`), `deployableEnvironments: [7]`. Completeness da 9327: 77,5.

## 2. Leituras

| # | Chamada | Resultado |
|---|---|---|
| L-1 | `GET /apis/417` | 200. `environments[]` e `revisions[].deployments` (formato na §4) |
| L-2 | `GET /revisions/9327` | 200, **`deployments: []` com a revisão no ar** — o campo não é preenchido nesta rota |
| L-4 | `GET /deployments` (com e sem `apiId`/`environmentId`) | **403** — não há listagem de deploys |
| L-5 | `GET /environments` | 200. Lista do tenant: `{id, name, description, inboundUrl, tlsType, isDeployable}` |
| L-5b | `GET /environments/7` | 200, com `revisionsDeployed[]` **e `mapVars[]` com os valores das variáveis do ambiente em claro, incluindo uma credencial `Basic`** |
| L-6 | `GET /revisions/{id}/completeness` · `GET /api-governance/api/v3/workflows/500` | 200. `completenessScore` na escala 0–100; o stage traz `deployableEnvironments` e `completenessRequisite` |

## 3. Escritas

| # | Teste | Resultado |
|---|---|---|
| E-1 | `POST /deployments` da 9327 no 7, onde ela **já estava** | **201 `{"id": 267}`**, ~4 s, síncrono. O 266 passa a `UNDEPLOYED`; o 267 é `DEPLOYED` |
| E-2 | Deploy da 9175 no 7, depois volta da 9327 | 201 nos dois. A revisão anterior vira `UNDEPLOYED` — **substitui, sem conflito e sem undeploy prévio** |
| E-3 | Deploy da 9327 no 9 (`HMG-APIOPS`), **fora** de `deployableEnvironments` e **não ligado** à API | **201** — nem o Manager nem o AG barram. O 9 **não aparece** em `environments[]` da API, mesmo 20 s depois; aparece em `revisions[].deployments` e em `GET /environments/9` |
| E-5 | `revisionId: 1` | **400** "Environment Variable '$destinationAuthorization/...' have not found". O id 1 é revisão da **API 1 "oAuth - RFC"**: o endpoint **não confere a API da revisão**, e só recusou por falta da variável |
| E-6 | `environmentId: 99999` | **404** "Environment not found." |
| E-6b | `revisionId: null` | **500**, `errors: []` |
| U-1 | `POST /deployments` com `status: "UNDEPLOYED"` | **201 e novo deploy `DEPLOYED`** — o campo `status` é ignorado |
| U-2 | `DELETE /deployments/{id}` | **403** |
| U-3 | `PUT /deployments/{id}` com `status: "UNDEPLOYED"` | **200** `{"result": "success", "id": null}` — é o undeploy |

## 4. Contratos

**Deploy**

```
POST /api-manager/api/v3/deployments
→ { "environmentId": 7, "revisionId": 9327, "status": "DEPLOYED" }    # status ignorado
← 201 { "id": 267 }                                                   # id do registro de deploy
```

**Erros** — envelope `{ "result": "failure", "errors": [{ "path", "type", "message" }], "status" }`

| Caso | HTTP | `errors[0]` |
|---|---|---|
| Ambiente inexistente | 404 | `environment` · `INVALID` · "Environment not found." |
| Variável da revisão ausente no ambiente | 400 | `environment` · `INVALID` · "Environment Variable '$…' have not found" |
| `revisionId` nulo | 500 | — |

**Undeploy** (fora do `sen deploy`)

```
PUT /api-manager/api/v3/deployments/{id}
→ { "id": 271, "environmentId": 9, "revisionId": 9327, "status": "UNDEPLOYED" }
← 200 { "result": "success", "id": null }
```

**Estado, em `GET /apis/{id}`**

```
environments[]          { id, name, inboundUrl,
                          revisionDeployed { id, apiId, revisionId, revisionNumber, apiVersion },
                          visibility, showTrace }                      ← ligação API × ambiente
revisions[]             { id, revisionNumber, workflowId, workflowStageId, apiBroken, …,
                          deployments[] { id, revisionId, revisionNumber, environmentId,
                                          status: DEPLOYED | UNDEPLOYED, deployDate (epoch ms) } }
apiTags[]               { attributeName, tags[] }
```

## 5. Consequências para o comando

1. A **única** escrita do deploy é o `POST /deployments`; refazer o deploy da mesma revisão é
   aceito e é o caso normal com revisões fixas (E-1).
2. O `revisionId` **só** pode vir de `revisions[]` da API resolvida (E-5).
3. Ambiente fora de `environments[]` é recusado pelo CLI, porque a plataforma aceita (E-3).
4. O gate do AG precisa ser aplicado pelo CLI: o `POST` não o aplica (E-3).
5. Estado anterior e conferência vêm de `revisions[].deployments`; `GET /revisions/{id}` não serve
   (L-2) e `GET /environments/{id}` **não deve ser chamado**, porque expõe segredos (L-5b).
6. Não provado: que o novo deploy leva ao gateway o conteúdo alterado por um `sen publish` (exige
   escrita na revisão e tráfego real).
