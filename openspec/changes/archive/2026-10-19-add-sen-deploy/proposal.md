## Why

O `sen publish` grava o repositório na revisão fixa do ambiente — 2 em `develop`, 3 em `release`, 4
em `main` ([V-24](../../../docs/feat-api-estructure/decisoes-refino-409/V-24-revisao-alvo-do-publish.md)) —,
mas gravar não coloca nada no ar. Pelo memory bank de arquitetura, publicar e deployar são etapas
separadas: "A CI publica; a CD deploya" (`knowledge/mapeamento-branch-ambiente-revision-stage.md`),
e "o caller CD não executa publish; recebe a revision publicada como input"
(`artifacts/tasks/prd-apiops-cicd/adrs/adr-001.md`). Falta o comando que a CD chama.

A mecânica foi sondada contra a API 417 em 2026-10-19
([sondagem](../../../docs/feat-command-sen-deploy/sondagem-deployments-2026-10-19.md)): um único
`POST /deployments` coloca a revisão no ar e substitui a anterior, mas a plataforma **não** confere a
API da revisão, **não** exige que o ambiente esteja ligado à API e **não** aplica o gate do Adaptive
Governance. Essas guardas são do CLI.

## What Changes

- Novo comando `sen deploy`, com a borda do `sen publish`: `--repo`, `--output text|json|yaml`,
  `--verbose`, factory preguiçosa e exceções tipadas que a CLI só traduz em `exit_code`.
- **Só na esteira:** `EXECUTION_MODE=local` é recusado antes de autenticar (decisão de 17/08/2026,
  ADR 0002).
- Revisão alvo por `TARGET_REVISION_NUMBER` (obrigatória, diferente de 1); ambiente alvo por
  `TARGET_ENVIRONMENT_ID` (nova, obrigatória, id numérico do Manager).
- Guardas antes da escrita: identidade da API, revisão da própria API, ambiente ligado à API e gate
  do AG lido do stage da revisão (ambiente permitido, completeness mínima, atributos exigidos).
- Uma única escrita, `POST /deployments`, seguida de conferência por `GET`.
- Saída `apiops.sen-deploy/v1`, com estado anterior e novo do ambiente. Exit `0` sucesso, `1` falha
  técnica ou de configuração, `3` bloqueio de governança.

## Capabilities

### New Capabilities

- `sen-deploy`: gramática do comando, configuração do alvo, guardas, gate do AG, escrita única com
  conferência, contrato `apiops.sen-deploy/v1` e exit codes.

### Modified Capabilities

Nenhuma.

## Impact

**Código novo** — `application/services/deploy_service.py`,
`application/exceptions/deploy_exceptions.py`, `domain/models/deploy_model.py`.

**Código alterado** — `domain/ports/manager_api_port.py` e `manager_api_adapter.py` (`deploy_revision`),
`config/settings.py` (`TARGET_ENVIRONMENT_ID`), `cli_adapter.py` (comando e renderização), `main.py`
(factory), `.env.example`.

**Reuso** — a regra de `RevisionWriter.guarda_identidade`, com mensagem do deploy;
`GovernancePrecheckService` para os atributos exigidos e o stage da revisão.

**Rede** — `GET /apis/{id}`; `GET` do workflow e dos atributos do AG; `GET
/revisions/{id}/completeness` quando o stage exige completeness; um `POST /deployments`; um `GET
/apis/{id}` de conferência. Nunca `PUT`/`POST /revisions`, `PUT /deployments` ou `GET
/environments/{id}`.

**Fora deste change** — rollback (pendência da arquitetura: `techspec.md` "O contrato final de `sen
deploy` aceita rollback pelo checkout da tag sem publish adicional?"), undeploy, smoke test, tag,
pushback, concurrency e gatilhos da esteira, correlation ID.
