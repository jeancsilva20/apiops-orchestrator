# V-23 · Bloqueio do Adaptive Governance no publish — como o orquestrador deve reportar

| Meta | Valor |
|---|---|
| Status | **FECHADO** — decisão de saída registrada em 2026-10-14 (§5) |
| Data | 2026-10-14 |
| Origem | erro real obtido pelo usuário ao tentar atualizar a `description` da API 417 |
| Fonte | payload do erro + `GET /api-governance/api/v3/{workflows,attributes}` (somente leitura) |
| Escopo | **só o reporte do bloqueio**. A validação *antes* de subir fica para a revisão do `validate` |

## 1. O erro real

```json
{
  "result": "failure",
  "errors": [
    { "type": "INVALID",
      "message": "{\"timestamp\":1791976237840,\"status\":412,\"error\":\"PRECONDITION_FAILED\",\"messages\":[\"API must contain attribute CLI\"],\"path\":\"/api-governance/api/v3/workflows/500/validate\"}" }
  ],
  "status": 412
}
```

Anatomia:

| Camada | Conteúdo |
|---|---|
| envelope externo | `result: failure`, `status: 412`, lista `errors[]` com `type: INVALID` |
| `errors[].message` | **string contendo JSON serializado** — precisa de um segundo parse |
| JSON interno | `status: 412`, `error: PRECONDITION_FAILED`, `messages[]` (texto humano), `path` (identifica o workflow: `/workflows/500/validate`) |

## 2. O requisito é legível por GET — o bloqueio não é opaco

| Chamada | Resultado |
|---|---|
| `GET /api-governance/api/v3/workflows/500` | workflow `APiOps`, `workflowCategory: TEAM`, `groupId: APIOps`, 2 stages |
| stage 1401 `Stage One` | `attributesRequisites: []` |
| stage 1402 `Teste` | `attributesRequisites: [{attributeId: 149, tagId: null, mustHave: true}, {attributeId: 96, tagId: null, mustHave: true}]` |
| `GET /api-governance/api/v3/attributes` | `96 = CLI` · `149 = My new` · `146 = Teste` · `231 = teste giroto` |
| `GET /apis/417` → `apiTags` | `My new` (Tag1) · `teste giroto` |

Cruzando: exigidos `{96 CLI, 149 My new}`, presentes `{My new, teste giroto}` ⇒ **falta `CLI` (96)**.
É exatamente o que a mensagem diz. **O faltante é calculável, não precisa ser extraído do texto.**

Notas do contrato:

- `tagId: null` ⇒ exige o **atributo**, com qualquer tag. Com `tagId` preenchido, exigiria uma tag específica.
- O atributo `CLI` (96) tem `tags: []` no catálogo — atributo sem tags cadastradas; basta estar presente na API.
- `inUse` distingue atributo em uso (`96`, `149`, `231`) de atributo ocioso (`146 Teste`).

## 3. ⚠️ O workflow que valida **não** é o que está gravado na revision

| Onde | Valor |
|---|---|
| `GET /revisions/9175` → `workflowId` / `workflowStageId` | **139** / **420** (`Organization Workflow`, categoria ORGANIZATION) |
| `path` do erro | `/workflows/**500**/validate` (`APiOps`, categoria **TEAM**, `groupId: APIOps`) |
| `GET /apis/417` → `visibility` | `GROUP`, `groupVisibility.name: **APIOps**` |

Relido após o erro: a revision **continua** com 139/420. O workflow 500 foi criado às 08:09:45 e o erro
veio às 08:10:37 — a validação usou o workflow do **grupo da API**, não o campo da revision.

**Consequência para o CLI:** ler `revision.workflowId` **não** antecipa o bloqueio. Quem quiser prever
precisa resolver o workflow efetivo pelo grupo da API.

*Hipóteses ainda não confirmadas* (ficam para a revisão do `validate`): que a resolução seja
"TEAM com `groupId` igual ao grupo da API, com fallback para ORGANIZATION"; e que a validação use o
**próximo** stage (o 1402, que tem os requisitos), não todos.

## 4. Como o orquestrador deve tratar

**Princípio: não parsear texto humano.** `"API must contain attribute CLI"` é mensagem livre — extrair
o nome do atributo dali seria heurística frágil, e o item exige comportamento determinístico.

```
1. HTTP 412 vindo de um path /api-governance/.../validate
   -> classificar como GovernanceBlockedError (categoria própria, não "4xx genérico")
2. parse do envelope: errors[].message -> json.loads (defensivo: se falhar, manter string crua)
3. extrair workflowId do campo `path` do JSON interno
4. GET workflows/{id} + GET attributes + apiTags da API
5. COMPUTAR os faltantes: exigidos(mustHave) - presentes
6. emitir log acionável + payload estruturado + exit code dedicado
```

O passo 5 é o que torna a saída determinística; `messages[]` vira apenas evidência bruta.

Tradução de camadas (fronteira já existente no projeto):

| Hoje | Falta |
|---|---|
| `HttpClient4xxError` → `ManagerApiTransportRejectedError(status_code, title)` | um sinal **de domínio** `GovernanceBlockedError(workflow_id, stage_id, missing[], raw)` — bloqueio de governança não é falha de transporte |

## 5. Decisão — a saída do orquestrador

**Mensagem humana (aprovada textualmente pelo usuário em 2026-10-14):**

```
Adaptive Governance bloqueou a publicação: a API precisa do atributo "CLI" (id 96),
exigido pelo stage "Teste" (1402) do workflow "APiOps" (500). Declare-o em apiTags.
```

Com mais de um faltante, uma linha por atributo, mantendo o mesmo formato.

**O pacote que acompanha a mensagem:**

| # | Decisão |
|---|---|
| 1 | **Formato:** linha humana no stderr **+** JSON estruturado, com `outcome: governance_blocked`, `workflowId`, `stageId`, `missing: [{attributeId, name}]` e `raw` (o envelope original, intacto) |
| 2 | **Exit code dedicado:** `3` para bloqueio de governança, distinto de `1` (falha técnica) — a esteira ramifica sem ler texto |
| 3 | **Enriquecer, não repassar:** o CLI resolve nomes e requisitos por GET antes de emitir. Degradação graciosa: se os GETs falharem, cai no repasse bruto — nunca engole o erro |
| 4 | **Nunca parsear `messages[]`:** o texto humano é evidência, não fonte. O faltante é sempre **calculado** |

> Procedência: o item 4 e a mensagem foram aprovados explicitamente; 1, 2 e 3 seguem a proposta
> apresentada na mesma conversa, sem objeção registrada. Reabrir é barato enquanto não virar código.

**Esboço do JSON:**

```json
{
  "outcome": "governance_blocked",
  "status": 412,
  "workflowId": 500,
  "stageId": 1402,
  "missing": [{ "attributeId": 96, "name": "CLI" }],
  "raw": { "result": "failure", "errors": [{ "type": "INVALID", "message": "…" }], "status": 412 }
}
```

## 6. Caminhos usados para validar este item

Todos somente leitura. Receita completa (token, bases, sessão) em
[CAMINHOS-DE-VALIDACAO.md](CAMINHOS-DE-VALIDACAO.md).

| Chamada | O que entregou |
|---|---|
| `GET /api-governance/api/v3/workflows` | catálogo de workflows do tenant; mostrou o 139 (ORGANIZATION) e o 500 (TEAM / `groupId: APIOps`) |
| `GET /api-governance/api/v3/workflows/500` | os 2 stages e o `attributesRequisites` do 1402 — a origem do bloqueio |
| `GET /api-governance/api/v3/workflows/500/stages` | mesma informação, confirmando por outra rota |
| `GET /api-governance/api/v3/attributes` | catálogo `id ↔ name` (`96 = CLI`), que torna o faltante calculável |
| `GET /api-manager/api/v3/apis/417` | `apiTags` presentes e `visibility` GROUP/`APIOps` (ligação com o workflow TEAM) |
| `GET /api-manager/api/v3/revisions/9175` | `workflowId: 139` — releitura que revelou a divergência do §3 |

Nenhuma escrita foi feita por esta validação. O HTTP 412 do §1 veio de uma tentativa do **usuário**,
colada na conversa.

## 7. Fora de escopo aqui

Validar **antes** de subir (o `sen validate` consultando os requisitos e falhando localmente) — fica
para a revisão dos comandos de validação, conforme decidido. O §2 e o §3 deste documento já entregam
a mecânica que esse comando vai precisar.
