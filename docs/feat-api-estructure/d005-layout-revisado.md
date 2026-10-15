# D-005 — Layout revisado: consolidação do refino das APIs 409/417

**Status:** Fechada em 2026-10-14.
**Natureza:** Spec viva. Revisa a D-003 e a D-004 nos pontos listados em §2; onde não há revisão, a D-003 continua valendo.
**Origem:** refino item a item da pasta `api-letras-409/`, registrado em [`decisoes-refino-409/`](decisoes-refino-409/README.md) — 20 itens fechados (V-01 … V-26).
**Evidência:** leitura ao vivo somente GET do tenant consulting (APIs 2, 5, 17, 409, 414, 417; 118 APIs varridas), documentação oficial Sensedia e materialização de 6 APIs em [`decisoes-refino-409/exemplos-gerados/`](decisoes-refino-409/exemplos-gerados/README.md). Nenhuma escrita na plataforma.

---

## 1. Resumo executivo

| # | Decisão | Itens |
|---|---|---|
| 1 | Árvore passa a ser **uma pasta por recurso**, espelhando o Manager | V-12 |
| 2 | O repo **não versiona id** de recurso nem de operação; chave é `(método, path)` | V-12 (a) |
| 3 | `destination`/`timeout` existem nos **três escopos**, com herança por substituição | V-01, V-02, V-03, V-15 |
| 4 | **`inherit`** substitui `override`; herança declarada sempre, ausente ≡ `true` | V-26 |
| 5 | **Estado não governado** — campos e interceptors fora do YAML, preservados por GET | V-22 |
| 6 | Régua de interceptors é a **API 414**, com binding em `spec.template` e severidades | V-11 |
| 7 | Publish grava em **revisão fixa**, informada pelo **número** via ambiente | V-24 |
| 8 | Bloqueio do **Adaptive Governance** tem canal e exit code próprios | V-23 |
| 9 | Regras determinísticas de **nome de pasta e de arquivo** | V-16, V-17 |

## 2. O que esta decisão revisa

| Documento | Ponto | Situação |
|---|---|---|
| D-003 §1 item 2 | "override total via booleano" | **revisado** — vira `inherit` (§6) |
| D-003 §1 item 3 | herança ascendente até o template canônico | **revisado** — a herança é por escopo (operação → recurso → revision → gateway); o template **não** participa da herança em runtime, só da validação (§7) |
| D-003 §2 | árvore `artifacts/Resources/<segmentos do path>` | **revisado** — `resources/<slug-do-recurso>/` (§4) |
| D-003 §4 | molde do arquivo de operação | **revisado** — `destination` objeto, `inherit`, nome do arquivo (§5, §6) |
| D-003 §5 | `resource.yaml` como mapa leve (`name` + `description`) | **revisado** — ganha `destination`/`timeout` e `inherit`; `name` deixa de precisar casar com a pasta |
| D-003 §6 | ciclo import/publish | **revisado** — publish é `PUT` denso em revisão fixa, com preservação do estado não governado (§8, §9) |
| D-004 §2.1 | `spec.template` obrigatório | **mantido e detalhado** — chave sempre declarada, vazio permitido; na esteira o valor vem de variável de ambiente (§7) |
| D-004 §2.2 | congelamento do ciclo de fluxos | **parcialmente descongelado** — a conformidade com a régua é implementável hoje; o que continua congelado é a remoção seletiva (V-25) |
| D-f (409) | versionar só o sufixo do destino | **revogada na reconstrução** — não existe base derivável (§3) |
| D-m (409) | 3 pendências do `timeout` | **fechadas** — unidade em segundos, precedência do mais específico, regime de omissão (§3) |
| D-e (409) | campos do Resource fora do mapa leve | **resolvida** — parte entra no YAML, parte vira estado não governado (§8) |

## 3. `destination` e `timeout` — escopos e herança

Os dois campos existem em **três escopos**: `all` (raiz da revision), `resource` e `operation`.

```yaml
destination:
  url: <string>        # SEMPRE declarado. '' = herda do escopo acima
  timeout: <string>    # opcional. Ausente = herda. Segundos; teto do gateway: 60
```

- A cadeia é de **substituição**, não de composição: o escopo mais específico troca o de cima por inteiro. Não existe "base + sufixo".
- Sem valor em nenhum escopo, vale o timeout do gateway (**60 s**), que é também o **teto** de qualquer valor cadastrado.
- Portabilidade entre ambientes resolve-se com **variável de ambiente do Manager** (`$var`), mecanismo nativo, válido no Target e no Timeout.
- O nível que a UI chama de "API" é a **revision** no contrato v3: `destination`/`timeout` **não existem** em `GET /apis/{id}`.

Tradução YAML ↔ wire (no Manager os dois são campos irmãos):

| Sentido | Regra |
|---|---|
| import | `destination.url = destination ?? ''` · `destination.timeout = timeout` (omitido quando `null`) |
| publish | `destination = url or null` · `timeout = destination.timeout or null` |
| publish na raiz da revision | vazio ⇒ **chave omitida** no payload |

## 4. Árvore

```text
repositorio-da-api/
├── api-basic-info.yaml
├── all-all.yaml                      ← escopo `all` (raiz da revision)
└── resources/
    └── <slug-do-recurso>/
        ├── resource.yaml
        └── <método>_<path completo>.yaml
```

**Nome da pasta:**

```
slug(texto)  NFKD → ascii · remove '{' '}' · [^A-Za-z0-9] → '-' · colapsa '-'
             minúsculas · trim · trunca no último '-' antes de 60 chars

pasta        resources/<slug(resource.name)>
             colidiu (case-insensitive) OU truncou?
                1. sufixo LEGÍVEL: slug do path da operação de menor (path, método)
                2. ainda colide ou estourou? sufixo MARCA: sha1(operações ordenadas)[:6]
             nome reservado do Windows (CON, PRN, AUX, NUL, COM1..9, LPT1..9) → '-recurso'
```

**Nome do arquivo:** `<método>_<path completo>.yaml` — `/` vira `_`, `{param}` preservado, teto de 90 caracteres (acima disso, trunca no último `_` e acrescenta `sha1(método+path)[:6]`).

```
resources/letras/delete_letras_{id}.yaml
resources/letras/post_tarefas_{id}_letras.yaml
resources/tarefas/get_tarefas.yaml
resources/tarefas/get_tarefas_{id}.yaml
```

**Estabilidade:** o import não renomeia pasta existente que já contenha as mesmas operações, mesmo que a regra gerasse outro nome hoje.

**Orçamento de caminho:** o pior caso do tenant (API 17, FDX) usa 165 caracteres relativos; nenhuma das 118 APIs estoura o limite do Windows, nem em raiz com OneDrive.

## 5. Identidade e correlação

1. O repo **não versiona** `id` de recurso nem de operação. O único id versionado é `spec.id` da API.
2. A chave estável é **`(método, path)`** da operação.
3. `name` do recurso é **dado versionado**, não chave — pode repetir (aconteceu na 417 rev1).
4. O recurso é identificado pelo **conjunto de operações** que agrupa.
5. O publish envia o estado completo; o Manager regenera os ids (shadow-copy por revisão).

## 6. `inherit` — herança declarada

```yaml
inherit: true     # herda o fluxo do escopo acima (default quando ausente)
inherit: false    # herança quebrada: este arquivo declara o fluxo que vale
```

Declarado sempre, nos três casos (herança pura, append e quebra), em `resource.yaml` e nos arquivos de operação. `override: true` deixa de existir.

## 7. Régua de interceptors (template)

- A régua é uma **API designada por convenção** — hoje a **414** (`/template/v1`). A chave `template` **não existe** no contrato da plataforma (8 confirmações de ausência).
- `spec.template` no `api-basic-info.yaml`: **chave sempre declarada, vazio permitido**, valor = id numérico. Em **esteira**, o valor vem de **variável de ambiente** alimentada pelo cofre, e o YAML é ignorado.
- Papel: **validar interceptors**, apenas. Tags são governadas pelo Adaptive Governance.
- Severidades: **append = `INFO`** (permitido em todos os cenários), **override/remoção/alteração = `WARNING`**, com o que falta e onde falta. **Nunca bloqueia** publish ou deploy — o julgamento é do code review.
- A comparação é **efetiva** (percorre cada caminho de execução), compara **`content`** e usa **sequência**, não conjunto.
- `GET /apis/{id}` já devolve `lastRevision` com os interceptors completos: uma chamada basta.

## 8. Estado não governado

> Tudo que o orquestrador lê por `GET` antes de publicar e reenvia **exatamente como estava**. Ausente no remoto ⇒ sobe vazio. Nunca aparece no YAML, nunca entra em diff.

| Família | Itens |
|---|---|
| Campos | `async`, `urls`, `instruction`, `certificateId` (operação); `connector`, `certificateId` (recurso) |
| Interceptors | tudo com `executionPoint` fora de `FIRST` e `SECOND` |

```python
GOVERNED_EXECUTION_POINTS = frozenset({"FIRST", "SECOND"})
```

Salvaguarda obrigatória: se o import encontrar um item **governado** que não consiga representar, deve **falhar explicitamente** — perda silenciosa é o único desfecho inaceitável.

## 9. Publish

```
1. modo   = EXECUTION_MODE                  (default: local)
2. numero = TARGET_REVISION_NUMBER          (local: só 1 — Draft)
3. GET /apis/{spec.id}                      → revisions[] + estado para hidratar/preservar
4. id = revisions[].id onde revisionNumber == numero
5. PUT /api-manager/api/v3/revisions/{id}   → payload denso, estado completo do repo
```

- A revisão alvo é informada pelo **número**, não pelo id — 1 Draft, 2 DEV, 3 HML, 4 PRD (PRD §3.3 da arquitetura).
- **Local só publica na Revision 1 (Draft)**; número diferente é recusado antes de qualquer escrita.
- Criar revisão é ato humano: o orquestrador nunca usa `POST /revisions`.
- A tradução número → id não custa chamada extra.

## 10. Bloqueio do Adaptive Governance

HTTP **412** vindo de `/api-governance/.../validate` é **falha de governança**, não de transporte:

- mensagem humana no stderr + JSON (`outcome: governance_blocked`, `workflowId`, `stageId`, `missing[]`, `raw`);
- **exit code `3`**, distinto do `1` técnico;
- o faltante é **calculado** por GET (`workflows/{id}` + `attributes` + `apiTags`), nunca extraído do texto de `messages[]`;
- o workflow que valida é resolvido pelo **grupo da API**, não pelo `workflowId` gravado na revision.

## 11. Impactos de implementação

Soma-se à fila da D-003 §9 e de [`fila-templates-schemas.md`](fila-templates-schemas.md):

| Peça | O que muda |
|---|---|
| `domain/models/api_operations_model.py` | `destination` vira objeto `{url, timeout}`; `timeout` sai do nível da operação; entra `inherit` |
| `domain/models/resources_model.py` | `Resource` ganha `destination` e `inherit`; perde a exigência de casar `name` com pasta |
| `domain/models/interceptors_model.py` | sem `id`/`idTemp`/`position`/`executionPoint`/`status`; listas `interceptors_request`/`interceptors_response` |
| `domain/schemas/*.json` | `executionPoint` deixa de ser `const: "FIRST"`; schemas aceitam o enum governado |
| `ApiFull.set_interceptor_positions()` | recalcula **só** sobre os governados; preservados entram intactos |
| importer | descoberta por `resources/<slug>/`; particionamento governado × preservado; falha alta no caso não representável |
| publisher | `PUT` em revisão fixa; hidratação e preservação a partir do GET; tradução YAML ↔ wire do §3 |
| `config/settings.py` | `EXECUTION_MODE`, `TARGET_REVISION_NUMBER`, `TEMPLATE_API_ID` |
| erros | `GovernanceBlockedError` com exit code próprio |

## 12. O que fica aberto

> **V-14 fechado em 2026-10-14:** a D-003 §2, §4, §5, §6, §7 e §9 foram reescritas; toda a pasta
> `feat-api-estructure/` foi alinhada a esta decisão (14 documentos, 0 links quebrados).

| Item | Pergunta |
|---|---|
| **V-25** | gramática do **tombstone** (remoção seletiva) no YAML — `inherit: false` sinaliza, mas não expressa o item removido |
| **V-18** | nome e gramática do arquivo do escopo `all` (o conteúdo está decidido) |
| **V-19** | regerar `api-letras-409/` como fixture — 4 valores vieram da 417 (V-07…V-10) |
| **V-20** | `Additional Info`: tipo sem schema; `content.attributes[].id` é versionável? |
| **V-21** | `null` dentro de `content` × a régua "`null` proibido" da D-003 §3 |
| V-04, V-05, V-06 | correções de comentário na pasta `api-letras-409/` |

Sem prova possível por GET, para fechar quando houver ambiente de escrita: herança em runtime, equivalência `''` ↔ `null` na publicação, e as duas inferências sobre resolução de workflow e stage no Adaptive Governance.

## 13. Referências

- Decisões item a item: [`decisoes-refino-409/README.md`](decisoes-refino-409/README.md)
- Procedência das chamadas: [`decisoes-refino-409/CAMINHOS-DE-VALIDACAO.md`](decisoes-refino-409/CAMINHOS-DE-VALIDACAO.md)
- Layout materializado em 6 APIs reais: [`decisoes-refino-409/exemplos-gerados/`](decisoes-refino-409/exemplos-gerados/README.md)
- Extrator determinístico (protótipo, só GET): `decisoes-refino-409/exemplos-gerados/extrair_estrutura.py`
