# Proposal — type-api-catalog-frame

*(pt-BR. Keywords SHALL/MUST em inglês conforme padrão OpenSpec do projeto.)*

## Why

A fatia `sen list` (arquivada, 25/09) assumiu conscientemente um débito de forma: o frame do api-finder circula como `List[Dict[str, Any]]` **cru** através de service, `ApiCollection` e CLI — violando o padrão §9 da casa (*"nunca dict cru atravessa camadas"*), com regras de domínio (`last_revision_number`, `_complete_cell`, `_env_names`) devendo as chaves do wire externo. O design arquivado predisse o desfazimento ("quando os dois mundos colapsam — canal JSON/B2"). A change irmã `add-sen-completeness` vai consumir o **mesmo frame** (identidade/contexto da API), e tipar antes evita que a nova fatia herde o dict cru ou replique o problema em seu plano de dados. Pagar a fundação agora é barato: 261 testes verdes travam o comportamento visível.

## What Changes

- **Novo model de domínio** `ApiCatalogEntry` (+ registros aninhados mínimos: revision/env/score refs, `context` de posse) representando o frame do api-finder — optionais abundantes para degradação graciosa.
- **`ManagerApiAdapter` passa a parsear e devolver tipado**: `list_catalog_apis` → `ApiCatalogPage.rows: List[ApiCatalogEntry]`; `list_api_detail` → `ApiCatalogEntry`. **O dict cru morre no outbound** (regra já selada no D4 de `add-sen-completeness` para o `CompletionReading`).
- **`ApiCollection` migra de `List[dict]` para `List[ApiCatalogEntry]**`; pipeline (filtro/query/sort/window) intacto.
- **Helpers de dict viram métodos do model** (`last_revision_number`, score por revisão, nomes de env) — regras preservadas verbatim, só mudam de casa; `normalize_finder_rows` é absorvido pelo parse do adapter/entry.
- **CLI (celulas `_listing_cells`/`_revision_cells`) consome tipado** — **zero mudança visual** (grade, cabeçalhos, footers e exit codes idênticos).
- **FORA de escopo:** fluxo legacy publisher/conversor (`ApiPartialInfo`, `ApiFull`, revisão/publish) — outro ciclo de vida; canal JSON do `sen list` (B2) fica **desbloqueado mas não implementado**.

## Capabilities

### New Capabilities
- `api-catalog`: leitura tipada do catálogo do api-finder — frame representado por modelos de domínio parseados exclusivamente no adapter outbound, tolerantes a frames esparsos, consumíveis por qualquer comando (sen list hoje; completeness/validate no futuro) sem dict cru entre camadas.

### Modified Capabilities

*Nenhuma.* A fatia `sen-list` é behavior-neutra (saída de terminal, exit codes e semântica da listagem não mudam) — requisitos existentes não são alterados.

## Impact

- **Código:** `domain/models/api_list_model.py` (NOME consolidado, decisão 25/09 — arquivo novo que RECEBE os contents de `api_collection_model.py` e abriga também os models tipados do frame: `ApiCatalogEntry` + aninhados; `api_collection_model.py` é aposentado no move); `adapters/outbound/http/manager_api/manager_api_adapter.py` (parse + assinaturas); `domain/ports/manager_api_port.py` (`ApiCatalogPage.rows`, `list_api_detail` retornado tipado); `application/services/api_listing_service.py` (helpers removidos, consome métodos do entry); `adapters/inbound/cli/cli_adapter.py` (celulas). Imports das 3 casas que referenciam `api_collection_model` apontam para o novo módulo (Git rastreia como rename por similaridade).
- **Testes:** maior churn = fixtures de dict → objetos tipados; assertions de chaves `.get(...)` viram atributos; golden/spot-check de render sem alteração.
- **Cross-change:** `add-sen-completeness` passa a consumir os tipos daqui (port `get_revision_completeness` já selada tipada; service monta identidade a partir de `ApiCatalogEntry`); destrava B2 (JSON de máquina do sen list) sem implementá-la.
