# D-002/D-003 — Evidência empírica de `tags[]` e `apiTags[].attributeName`

> Alinhado à [D-005](d005-layout-revisado.md) em 2026-10-14: as conclusões sobre `apiTags`, `tags[]` e `identityApi` seguem válidas. A governança de atributos pelo Adaptive Governance é tratada na D-005 §10.


**Status:** Varredura read-only concluída em 2026-09-29. Fecha D-002 Q1 (`identityApi`), Q4 (`tags[]`) e Q2 (`attributeName`), conforme refinamento com o responsável.

## Método

- Autenticação pelo fluxo sancionado do CLI: sessão dev (`sen login`) → `POST {AUTH_HOST}/validate` → Bearer `admin_access_token`. Somente GET.
- Listagem `GET /api-manager/api/v3/apis` + **GET individual de cada uma das 110 APIs** do tenant.
- Zero erros de leitura; nenhum write foi executado; nenhum dado bruto versionado (números sanitizados abaixo).
- Script executado a partir do `.venv` do orquestrador; agregados mantidos em área temporária, não no repositório.

## Resultados

### `spec.tags[]` (lista simples)

| Métrica | Valor |
|---|---|
| APIs varridas | 110 |
| APIs com `tags[]` não-vazio | **0** |

Corrobora o ensaio da API 405 (`tags: []` preservado na omissão) e o payload de criação documentado (`"tags": []`). Conclusão: **nenhuma instância de uso real no tenant**.

### `spec.apiTags` (bindings de atributos do Adaptive Governance)

| API | `attributeName` | `tags[]` |
|---|---|---|
| 189 | CLI | Sensedia |
| 203 | CLI | Sensedia |
| 290 | My new | Tag1 |
| 290 | teste giroto | teste giroto |
| 337 | My new | Tag2, Tag1 |
| 400 | My new | Tag1 |
| 405 | My new | Tag1 |

7 bindings em toda a base; uma mesma API pode carregar **mais de um atributo** simultaneamente (caso da 290).

### Catálogo oficial de Attributes (AG) na mesma data

`GET /api-governance/api/v3/attributes` (read-only, token admin):

| id | name | tags declaradas | inUse |
|---|---|---|---|
| 96 | CLI | *(vazio)* | false |
| 149 | My new | Tag1, Tag2 | false |
| 146 | Teste | *(vazio)* | false |
| 231 | teste giroto | teste giroto | false |

Cruzamentos:

- Todos os `attributeName` em uso existem no catálogo — sustenta a regra "nome deve existir no catálogo AG";
- `CLI` tem lista vazia no catálogo e ainda assim as APIs 189/203 portam `Sensedia` — o catálogo orienta o formulário, porém o **runtime não trava os valores** contra ele;
- Todos os atributos retornam `inUse: false` apesar de bindings existentes — `inUse` não reflete binding por revision (provavelmente conta consumo em políticas/workflows do AG).

## Implicações fechadas

1. **`tags[]` simples → suprimir.** Sem uso em 110 APIs e sem evidência em nenhuma outra fonte; o Manager preserva o valor remoto quando o campo é omitido. Sai do YAML e do payload montado.
2. **`attributeName` referencia um namespace externo.** Os três nomes observados (`CLI`, `My new`, `teste giroto`) existem no catálogo de Attributes do Adaptive Governance (`GET /api-governance/api/v3/attributes` — ver `mapeamento APIM/docs-sensedia/12-adaptive-governance.md` §6). A atribuição nasce e é mantida nesse produto; o repo consome os pares `(attributeName, tags[])`.
3. **Valores de `tags[]` não são travados pelo catálogo observado.** Na época do mapeamento, o catálogo registrava `CLI` sem tags; na prática as APIs 189/203 portam `Sensedia`. O runtime não rejeitou a combinação.
4. **Transporte declarativo por lista completa.** O PUT de revisions carregou o conjunto integral de `apiTags` (ensaio 405: omissão apagou; PUT com lista completa restaurou os pares originais). Isso contradiz a nota antiga do mapeamento de que o binding exigiria rota assinada — o PUT público de revisions **efetivamente muta** os bindings. Fica registrado: a fonte do binding é o PUT da revision; rotas `/bindings`, `/attributes`, `/apis/{id}/attributes` continuam 403 (assimétricas), como já anotado em `docs-sensedia/98-erros-e-validacoes.md` #20.
5. **Regime adotado no YAML:** `apiTags` é a lista declarativa completa (ausente preserva; `[]` remove). Editar `tags[]` redefine valores do binding; alterar `attributeName` equivale a replantar o par — tecnicamente viável pelo mesmo PUT, porém o valor novo deve existir no catálogo do AG (nascem lá, nunca no repo). Validação de existência contra o catálogo fica como evolução do validador.

## Limitações

- Catálogo AG consultado em data anterior à varredura; sincronia eventual (API importada ↔ catalogador) não foi re-verificada.
- Nenhum cenário de `identityApi: true` observado em nenhuma fonte (o fechamento desse campo foi por recomendação + prova de preservação na omissão).
- As provas de mutação via PUT continuam restritas à API 405; replicação de changeling de `attributeName` (replantar) ficou como validação opcional em API de descarte, não executada.