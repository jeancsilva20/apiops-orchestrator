# Retorno do update de revisão no API Manager bloqueado pelo AG

*(observações empíricas em produção, 2026-09-28)*

## Contexto

Ao **atualizar uma API** via API Manager — request para salvar/cadastrar a revisão:

```
PUT /api-manager/api/v3/revisions/{revisionId}
```

— a operação **falha antes de ser persistida** quando alguma regra do AG não é atendida. Quem executa essa checagem internamente é o gateway de governança (`/api-governance/api/v3/workflows/{workflowId}/validate`, visível apenas no `path` do payload de erro), chamado **server-to-server pelo Manager** durante o update. O cliente recebe status HTTP **412 (PRECONDITION FAILED)** com corpo `"result": "failure"` contendo TODAS as violações.

## Exemplos reais de retorno

Sem violação de completeness:

```json
{
    "result": "failure",
    "errors": [
        {
            "type": "INVALID",
            "message": "{\"timestamp\":1790614509051,\"status\":412,\"error\":\"PRECONDITION_FAILED\",\"messages\":[\"Expected GZip pack Interceptor\",\"Expected Access token metric Interceptor\"],\"path\":\"/api-governance/api/v3/workflows/139/validate\"}"
        }
    ],
    "status": 412
}
```

Com violação de completeness junto (as mensagens são cumulativas):

```json
{
    "result": "failure",
    "errors": [
        {
            "type": "INVALID",
            "message": "{\"timestamp\":1790614548072,\"status\":412,\"error\":\"PRECONDITION_FAILED\",\"messages\":[\"Actual Completeness is 85.0 but expected greater than or equal to 90.0\",\"Expected GZip pack Interceptor\",\"Expected Access token metric Interceptor\"],\"path\":\"/api-governance/api/v3/workflows/139/validate\"}"
        }
    ],
    "status": 412
}
```

## O ponto central

**O próprio retorno já traz TODAS as regras do AG que estão sendo ignoradas.**

- O array interno `messages` (dentro do `message` serializado) lista **uma mensagem por regra violada**, no plural — Nunca só a primeira falha.
- Regras de **interceptor obrigatório**: `Expected <interceptorType> Interceptor` (ex.: `Expected GZip pack Interceptor`).
- Regras de **completeness mínima**: `Actual Completeness is X but expected greater than or equal to Y`.
- **Parse**: `errors[].message` vem como string JSON duplamente serializada — decodificar antes de ler `messages[]`. O campo `path` é a URI interna que o serviço de governança processou (envelope padrão Spring Boot).

## Contrato das rotas de regras do AG (confirmado via network da própria UI)

Autenticação: `Authorization: Bearer <adminAccessToken>` (token super-admin da `.sen_session`).

| Endpoint | Papel |
|---|---|
| `GET /api-governance/api/v3/workflows?_limit=&_offset=` | Lista workflows do tenant (paginado, headers `count`/`content-range`) com **stages e regras embutidas** |
| `GET /api-governance/api/v3/workflows/{workflowId}` | Detalhe de um workflow |
| `GET /api-governance/api/v3/workflows/{workflowId}/stages` | Stages com **todas as regras** |
| `GET /api-governance/api/v3/interceptors` | Taxonomia de ~69 tipos de interceptor (DEFAULT/JAVASCRIPT/JAVA) — vocabulário possível de `interceptorType` |
| `GET /api-governance/api/v3/attributes` | Atributos usáveis como regra |
| `GET /api-governance/api/v3/environments` | Ambientes referenciados pelos requisitos de deploy |
| `GET /api-manager/api/v3/revisions/basic?workflowOnly=true` | Revisões por stage (vínculo Manager→AG) |

Nota: o token de usuário (`accessToken`, escopo `apis/all`) **não** autoriza essas rotas — apenas o `adminAccessToken`.

### Formato da regra (item de `stages[]`)

```json
{
  "workflowStageId": 420,
  "workflowStageName": "Stage One",
  "completenessRequisite": 90.0,
  "position": 1,
  "interceptorsRequisites": [{
    "interceptorType": "GZip pack",
    "mustHave": true,
    "executionPoint": "FIRST",
    "positionType": "ANY",
    "flowType": "API",
    "operationType": "ALL",
    "resourceType": null,
    "resourceId": null,
    "operationId": null
  }],
  "attributesRequisites": [],
  "environmentsRequisites": [],
  "deployableEnvironments": [1, 7, 9],
  "environments": [{ "id": 1, "deployableApiManager": true, "mandatoryDeployment": null }]
}
```

Mapeamento regra → mensagem do 412:

| Regra no stage | Mensagem de violação |
|---|---|
| `interceptorsRequisites[].interceptorType` | `Expected <interceptorType> Interceptor` |
| `completenessRequisite` (> 0) | `Actual Completeness is <score> but expected greater than or equal to <threshold>` |
| `attributesRequisites` / ambientes | (analogamente, quando presentes) |

Isso permite **mapear cada mensagem de volta à regra de origem** lendo `GET /workflows/{id}/stages` — inclusive pra sugerir correção automática (qual interceptor aplicar, em qual flowType/executionPoint).

## Prevenção: o que dá para validar ANTES do PUT

Comparando o payload local da revisão com `GET /workflows/{id}/stages`:

| Tipo de regra | Comparável localmente (preventivo)? |
|---|---|
| `interceptorsRequisites` (tipo + flowType + executionPoint) | **Sim** — comparar flow da revisão local com a regra |
| `attributesRequisites` / `deployableEnvironments` | **Sim** — metadata estática |
| `completenessRequisite` | **NÃO** — ver limitação abaixo |

### Limitação estrutural da completeness (importante!)

A completeness **só existe depois que o Manager a calcula a partir da revisão registrada** (`GET /api-manager/api/v3/revisions/{id}/completeness`). Provas:

1. O AG **não recalcula** completeness do payload recebido no validate — ele só faz **lookup** num índice próprio do que já existe.
2. Simulação do `POST /workflows/139/validate` com o payload integral da revisão (e variantes com identificadores/beams injetados) retornou sempre `"Cannot find completeness for this API / Revision"`.
3. No fluxo real, o Manager **computa a completeness da nova revisão dentro do próprio update** e aí sim o AG compara — por isso o 412 real vem com `Actual Completeness is 85.0...`.

Consequências para o desenho do orchestrator:

- Validação **preventiva** deve cobrir somente regras estáticas (interceptores, atributos, ambientes) — abortar com clareza nessas falhas.
- A verificação de completeness **depende do PUT** (o Manager calcula na hora); o 412 embutido continua sendo a fonte de verdade final. Replicar o motor de scoring do Manager localmente é over-engineering (heurísticas reinventadas e sujeitas a drift).

## Sobre chamar o `/validate` diretamente

O endpoint **existe e é operacional** (responde com schema-feedback), mas o contrato de request completo não está documentado publicamente e o modo como o AG resolve a completeness ficou obscuro. Comportamentos observados:

- `POST` com body `{}` → 412 `"Workflow Stage Id is required"`
- `POST` com `{"workflowStageId":420}` → 400 sobre `workflowCategory` (valores aceitos: `ORGANIZATION`/`TEAM`)
- `POST` com `{"workflowStageId":420,"workflowCategory":"ORGANIZATION"}` → 500 (schema incompleto)
- `GET` na rota → 403 (método não permitido)
- Payload integral da revisão (+ variantes) → 412 `"Cannot find completeness..."`

Para contrato byte-a-byte, o caminho é **ticket no Support** — a chamada do Manager é server-to-server na rede interna, invisível de fora.

## Histórico / armadilhas

- `errors[].message` às vezes aparece vazio no corpo repassado (streaming/encoding) — validar tolerância no parser.
- Correlação com comandos locais: ver [`../feat-command-sen-completeness/`](../feat-command-sen-completeness/) para o mapeamento das violações nos comandos `sen completeness`.
