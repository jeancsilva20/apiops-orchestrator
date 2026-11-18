## Why

Uma API que já existe no Manager precisa entrar no APIOps com cada branch de ambiente carregando o
código da sua revisão (`main` ← 4, `develop` ← 2, `release` ← 3), antes de as proteções de branch
serem ativadas. Hoje isso é feito pelo protótipo `extrair_estrutura.py` (repositório
`apiops-versioner`), configurado por constantes no código e com um token de super admin em texto.
Depois da carga, ninguém tem como saber se o Manager e o Git deixaram de ser espelho um do outro:
o `sen version sync` do memory bank (Story 06.03) nunca foi implementado, e o `VersionerService`
do orquestrador é um esqueleto do layout antigo, sem comando ligado a ele.

A especificação completa está em
[`docs/feat-command-sen-sync/sen-sync.md`](../../../docs/feat-command-sen-sync/sen-sync.md).
Este change é a **fase 1** dela: a carga e a verificação passando o id e a revisão, sem nenhuma
consulta ao Git. A parte de Git (branch atual, aviso de revisão inesperada, recusa de carga já
publicada) fica para um change próprio, inclusive a definição de como a branch é identificada na
esteira.

## What Changes

- Novo comando `sen sync --id <api-id> --revision <n> [--repo <pasta>] [--check]`, que roda na raiz do repositório da
  API.
- **Carga** (sem `--check`): lê a API e a revisão pelo `revisionNumber`, gera a área gerenciada
  (`api-basic-info.yaml`, `all.yaml`, `resources/`) e a grava de forma atômica, preservando o
  `spec.template` do arquivo existente e gravando o `spec.id`.
- **Verificação** (`--check`): compara o repositório com a revisão informada por conteúdo, não por
  texto, e lista as diferenças por arquivo e campo; exit `8` quando há diferença, `0` quando não há.
- **Contrato OpenAPI** na carga: `GET /revisions/{id}/swagger`, só OpenAPI 3 (Swagger 2.0 aborta);
  `components.yaml` sempre, `contact`/`tags`/`security` no `api-basic-info.yaml` e os campos de
  contrato em cada arquivo de operação. O `--check` compara o contrato também.
- Só `GET` no Manager; nenhuma escrita no Git. Token só da sessão do `sen login`, como nos outros
  comandos; regra de visibilidade da API aplicada antes de qualquer leitura da revisão.
- Exit codes por categoria (1 a 8), conforme a tabela da especificação; os da parte de Git (`5`
  por branch ou carga publicada, `7` por remoto inacessível) ficam reservados.
- Novo módulo **Sincronizador**: `SyncService` na aplicação, a porta `RepoWriterPort` com adapter
  de filesystem, e um diff semântico de revisões no domínio.
- O sentido Manager → arquivos do Conversor é o `repo_materializer` que já existe: ele passa a
  receber o `template` a preservar e a emitir os avisos que o script emite.
- **Remoção do versionador legado**: `VersionerService`, `ApiRepoPort`/`ApiRepoAdapter`,
  `Settings.API_REPO_FOLDER`, o `api_id` fixo do `ManagerApiAdapter` e as operações legadas do port
  que nenhum comando usa (`publish_api_changes`, `get_apis`).

## Capabilities

### New Capabilities

- `sen-sync`: gramática do comando, carga atômica, verificação semântica, exit codes, só leitura na
  plataforma.

### Modified Capabilities

- (nenhuma) — a regra de `api-visibility` é reusada como está.

## Impact

**Código novo** — `domain/models/api_model.py` (modelos do Manager, tipados e tolerantes),
`application/services/sync_service.py`,
`application/exceptions/sync_exceptions.py`, `domain/models/sync_view.py`,
`domain/ports/repo_writer_port.py`, `domain/services/revision_diff.py`,
`adapters/outbound/filesystem/repo_writer_adapter.py`.

**Código alterado** — `domain/services/repo_materializer.py` (`template`, avisos e contrato),
`domain/services/openapi_contract.py` (sentido swagger → repositório), `openapi_contract_validator.py`
(conjuntos de nomes passam a vir do `openapi_contract`),
`cli_adapter.py` (comando `sync`), `main.py` (factory), `manager_api_port.py` e
`manager_api_adapter.py` (remoção do legado; `get_api_by_id` e `get_revision` devolvem os modelos),
`validate`, `publish`, `deploy`, `ruler_service` e `contract_writer` (ponte `as_wire` até migrarem).

**Código removido** — `application/services/versioner_service.py`, `domain/ports/api_repo_port.py`,
`adapters/outbound/template_repo/`, `adapters/outbound/diff_engine/.keep`,
`tests/unit/application/services/test_versioner_service.py`.

**Reuso** — `AdminTokenProvider` (sessão, time APIOps, token), `ApiAccessGuard` + `api_visible`
(visibilidade), `ManagerApiPort.get_api_by_id` e `get_revision` (as mesmas leituras do script),
`RepoCanonicalReader` + `revision_payload.assemble` (sentido arquivos → modelo do Manager no
`--check`), `repo_materializer` (sentido Manager → arquivos).

**Rede** — `GET /apis/{id}`, `GET /revisions/{id}` e `GET /revisions/{id}/swagger`. Nunca `PUT` nem
`POST`.

**Fora deste change** — a parte de Git da especificação (fase 2), aplicar
no Git as diferenças do `--check`, `--check` na esteira, 4º ambiente, padronização geral dos exit
codes da CLI, criação do repositório da API.
