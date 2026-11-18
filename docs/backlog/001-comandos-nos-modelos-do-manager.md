# 001 — Validate, publish e deploy nos modelos do Manager

**Status:** `todo` · **Prioridade sugerida:** média · **Registrado em:** 2026-11-18 · **Base:** `feat/sen-sync` em `3c9ec13`

## Resumo

O adapter do Manager já entrega `Api` e `Revision` (`domain/models/api_model.py`), mas só o `sen sync` lê esses
modelos. Os outros consumidores convertem de volta para dicionário com `as_wire()` e seguem lendo chaves do JSON
do Manager (`api.get("basePath")`, `revision["id"]`, `draft.get("interceptors")`).

O objetivo é que o adapter seja o único lugar que conhece o formato da API: na leitura transforma o JSON em modelo
de domínio; na escrita serializa com `to_wire()`. Serviços de aplicação e de domínio passam a ler atributos.

## Origem

Change `add-sen-sync`, decisão **D13** (16/11, `openspec/changes/add-sen-sync/design.md`). Os modelos entraram com uma
ponte transitória (`as_wire()`) para não migrar os três comandos de escrita no mesmo change. `padroes-desenvolvimento.md`
§2 registra a ponte "até migrar (Story 02.03)".

## Impacto enquanto não for pago

- Dois jeitos de ler o mesmo dado: modelo no sync, dicionário no resto. Uma mudança no formato do Manager precisa ser
  tratada nos dois.
- O `--check` do sync faz ida e volta: `assemble(draft=remote.revision.to_wire())` e, em seguida,
  `Revision.model_validate(assembled.body)`.
- Código repetido: `domain/services/revisions.py` reimplementa `Api.revision_by_number`; `api_visibility` tem
  `from_api` (modelo) e `from_api_payload` (dicionário).
- Campos que o código lê sem tipo, só via `model_extra`: `workflowId`, `workflowStageId` e o `api` aninhado na
  revisão; `revisions[].deployments` e `environments` na API; `stages[].attributesRequisites`,
  `deployableEnvironments` e `completenessRequisite` no workflow.
- As baterias de integração dependem de `tests/integration/_wire.py` para continuar recebendo dicionário.

## Onde a ponte está hoje

| Arquivo | O que volta para dicionário |
|---|---|
| `application/services/validate_service.py` | API em `api_visible` e revisão alvo |
| `application/services/publish_service.py` | API e revisão alvo |
| `application/services/deploy_service.py` | API na leitura e na conferência do deploy |
| `application/services/revision_writer.py` | revisão relida na conferência pós-`PUT` |
| `application/services/contract_writer.py` | revisão relida depois do `PUT` do swagger |
| `application/services/ruler_service.py` | API-template |
| `adapters/inbound/cli/cli_adapter.py` | comando `diag` |
| `application/services/sync_service.py` | `to_wire()` para o `assemble` e volta para `Revision` |
| `tests/integration/_wire.py` | baterias de integração |

Serviços de domínio que trabalham sobre dicionário: `revision_payload` (`assemble`, `verify`), `interceptor_flow`,
`swagger_flow`, `template_conformance`, `deployments` e `revisions`.

Métodos do port que ainda falam dicionário: `get_workflow`, `list_attributes` e `get_custom_interceptor_by_id` na
leitura (o modelo `CustomInterceptor` já existe em `interceptor_model.py` e é usado por `list_custom_interceptors`);
`update_revision` na escrita.

## Plano (um commit por etapa)

1. **Completar os modelos** com os campos listados em "Impacto" e criar `Deployment`, `Environment`, `Workflow`/`Stage`
   e `Attribute`. Os testes de round-trip nas fixtures reais continuam como prova.
2. **Consumidores pequenos:** `deployments` e `deploy_service` nos modelos; remover `revisions.py` (fica
   `Api.revision_by_number`); `api_visible` com `from_api` e remoção de `from_api_payload`; `ruler`/`template_conformance`
   e `diag`. Prova: bateria de deploy.
3. **Governança e custom:** adapter devolve `Workflow`, `Attribute` e `CustomInterceptor` em
   `get_custom_interceptor_by_id`; o pré-check lê atributos.
4. **Montagem e conferência:** `assemble`, `verify`, `interceptor_flow` e `swagger_flow` sobre `Revision`;
   `update_revision` recebe `Revision` e o adapter serializa. Validate, publish, `revision_writer` e `contract_writer`
   sem ponte. Remover `as_wire`, `tests/integration/_wire.py` e a ida e volta do sync. Prova: baterias de escrita
   na API-lab 425.

As etapas 1–3 são mecânicas e podem sair antes da 4.

## Decisões propostas (confirmar ao iniciar)

- Change próprio no openspec, fora do `add-sen-sync`.
- `get_revision_swagger` segue como dicionário: é um documento OpenAPI, tratado como documento pelo `openapi_contract`,
  não uma entidade do Manager.
- `update_revision(revision_id, Revision)`, com o `to_wire()` dentro do adapter.

## Pontos de atenção

- O `assemble` parte de uma cópia profunda do estado remoto e só altera o que o repositório declara. É isso que
  preserva `workflowId`/`workflowStageId` (D-020) e tudo o que o repositório não governa. No modelo, a cópia vira
  `model_copy(deep=True)`, e o round-trip precisa continuar provado.
- `to_wire()` usa `exclude_unset`: um campo com valor padrão que não foi atribuído não vai no corpo. Item de
  interceptor, recurso ou operação criado pela montagem precisa receber explicitamente os campos que o `PUT` espera.
- HTTP 200 não prova a gravação (W-8). A etapa 4 só fica provada com a releitura nas baterias de escrita, e escrita
  só na API-lab 425 — nunca 417, 400 ou ECAD.

## Critério de resolução

- `as_wire` e `tests/integration/_wire.py` removidos.
- Nenhum serviço de aplicação ou de domínio lê chave do JSON do Manager; `to_wire()` aparece só nos adapters.
- O port não devolve nem recebe dicionário para entidade do Manager (o swagger fica de fora, se a decisão acima se
  confirmar).
- `revisions.py` e `from_api_payload` removidos.
- Testes unitários verdes; baterias de escrita na 425 (validate, publish, herança, contrato) e de deploy verdes.

## Referências

- `openspec/changes/add-sen-sync/design.md` — D13
- `docs/padroes-desenvolvimento.md` — §2, "Modelos do Manager"
- `docs/feat-command-sen-sync/sen-sync.md` — dependência da Story 02.03
