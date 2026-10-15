# Fila de atualização de templates e schemas (alinhamento D-003)

**Levantado em:** 2026-09-29.  
**Gate (regra 3 da feature):** toda edição de schema/model/código abaixo depende de **change proposal OpenSpec aprovada**. Este documento é o backlog de entrada da proposal — nada dele vira edit antes disso.

## 1. Inventário dos desalinhados

### Schemas da CLI (`src/apiops_orchestrator/domain/schemas/`)

| # | Arquivo | Estado atual | Gap vs. contrato fechado |
|---|---|---|---|
| 1 | `api-basic-info.schema.json` | Vaza `creationDate`, `lastUpdate`, `visibility` reduzida | Falta `template`, `apiTags`; `description` não é required; sem régua de escalares (ausente preserva / `""` limpa / `null` proibido); campos de fundo devem sair |
| 2 | `api-operations.schema.json` | Exige `position`/`executionPoint` | Listas `interceptors_request`/`interceptors_response` + **`inherit`** (nao mais `override`) + `destination` como **objeto `{url, timeout}`** (D-005 §3 e §6) |
| 3 | `api-resource.schema.json` | Contém `flow` completo | `name` + `description` + **`destination` objeto** + `inherit` + listas de interceptors; `name` **nao** precisa casar com a pasta (D-005 §3, §4 e §6) |
| 4 | `api-revision.schema.json` + `api-revision-flow.schema.json` | Representam revisions no repo | **Obsoletos** — revisions saem do repo (D-003 §2); remover |
| 5 | `ecad-*-default-interceptors.schema.json` (6) + `mag-default-interceptors.schema.json` | Templates locais de default interceptors — **4.230 linhas** | **Eliminar, sem reaproveitamento** — confirmado pela D-u (2026-10-13): a régua é a API **414** (`/template/v1`, "Template APIOps") lida por GET. Decisão do usuário: os fluxos ECAD/MAG não são migrados nem comparados; cada cliente novo ganha o seu template como API no Manager do próprio tenant (D-003 §1; impacto §9 item 8) |
| 6 | `catalog.json` | Índice dos schemas | Repontuar/remover referências mortas |
| 7 | `api-environment.schema.json` | Pastas `environments/` | D-003 não aborda environments no repo — decidir dentro da proposal |

### Código/apoio ligado a templates

| # | Arquivo | Problema |
|---|---|---|
| 8 | `domain/services/json_to_yaml_enum.py` (`INTERCEPTORS = "default-interceptors.yaml"`) | Referencia arquivo que deixa de existir no layout final |
| 9 | `application/services/repo_validator.py` + testes (expectativa de pasta `Templates/` com `default-interceptors.yaml`) | Valida o layout antigo |
| 10 | `config/settings.py` (pastas `api-info/`, `revisions/`; env `API_TAGS_*`) | Layout antigo + fonte errada de `apiTags` (deve vir do manifesto, não de variáveis) |
| 11 | `api-gateway/artifacts/Templates/*` | Repo-referência histórico; marcar como superseded pela D-003 ou desligar |
| 12 | `arquetipos/01…04` (`bindings.json`, `revisions/`, `openapi.yaml`) | Histórico de exploração — apenas anotar como tal, não migrar |

## 2. Ordem de execução (dentro da change proposal)

1. **Schema `api-basic-info`** — contrato fechado, risco zero, primeiro movimento do ciclo aprender→aplicar;
2. **Schema de operação** (D-003 §4: listas req/resp + `override` + `destination`/`timeout`);
3. **Schema de resource** (D-003 §5 + **D-005 §3**: `destination` objeto, `timeout`, `inherit`, listas próprias);
4. **Remoção dos default-interceptors** (schemas ECAD/MAG + enum + validador + testes) — maior ganho de simplicidade;
5. **Obsoletos de revision** (2 schemas + settings de pastas antigas);
6. **Models e serviços** (interceptors_model sem `position`/`executionPoint`/`status`; hidratação e preservação do estado não governado no publisher; descoberta por `resources/<slug>/` + diff-vs-**revision** no importer — D-005 §8);
7. **Testes de regressão** — `exemplo-layout-final/` como fixtures douradas + baseline da API 405 (`api-basic-info-criticidade-campos-omitidos.md`).

## 3. Ligação com a D-003 §9

Esta fila é a instanciação concreta dos impactos 1, 2, 5, 6 e 8 de [D-003 §9](d003-layout-repo.md#9-impactos-de-implementação-fila-de-proposta) na granularidade de arquivos. Itens 3 (preservar destination/timeout) e 7 (publisher/revision-alvo) permanecem no escopo da mesma proposal, na fase de models/serviços.


## 4. Incremento da D-005 (refino 409/417, 2026-10-14)

Itens que a [D-005](d005-layout-revisado.md) acrescenta a esta fila:

| # | Alvo | O que fazer |
|---|---|---|
| 13 | `domain/schemas/schema-interceptors.json` | `executionPoint` deixa de ser `const: "FIRST"`; aceitar o conjunto governado (`FIRST`, `SECOND`) e **ignorar** o restante (estado nao governado, D-005 §8) |
| 14 | `domain/models/api_operations_model.py` | `destination` vira objeto `{url, timeout}`; `timeout` sai do nivel da operacao; entra `inherit` |
| 15 | `domain/models/resources_model.py` | `Resource` ganha `destination` e `inherit` |
| 16 | `ApiFull.set_interceptor_positions()` | recalcular **so** sobre os governados; preservados entram intactos, com `position` original |
| 17 | importer | descoberta por `resources/<slug>/`; particionamento governado x preservado; **falhar alto** quando um item governado nao for representavel |
| 18 | publisher | `PUT` em revisao fixa resolvida pelo **numero**; hidratacao e preservacao a partir do GET; traducao YAML <-> wire da D-005 §3 |
| 19 | `config/settings.py` | `EXECUTION_MODE`, `TARGET_REVISION_NUMBER`, `TEMPLATE_API_ID` |
| 20 | tratamento de erro | `GovernanceBlockedError` (HTTP 412 do AG) com saida estruturada e **exit code 3** (D-005 §10) |
| 21 | validador de conformidade | comparacao **efetiva** contra a regua, com `content` e por sequencia; `INFO` para append, `WARNING` para quebra, **sem bloqueio** (D-005 §7) |

Protótipo determinístico das regras de nome e arvore, exercitado em 6 APIs reais:
`decisoes-refino-409/exemplos-gerados/extrair_estrutura.py`.
