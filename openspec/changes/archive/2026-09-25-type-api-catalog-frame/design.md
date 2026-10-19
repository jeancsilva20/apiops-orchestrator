# Design — type-api-catalog-frame

*(pt-BR. Keywords SHALL/MUST em inglês.)*

## Context

- Frame vivo do api-finder (`customSearch=(apiId:X)`): `id, name, description[, version?]`, `revisions[] {id, revisionNumber, workflowId, workflowStageId, creationDate...}`, `completeness[] {score, apiRevision}`, `environments[] {name, apiRevision}`, `lastRevision {id, revisionNumber}`, `contextType/contextGroupName/owner`. Frame **real é esparsos e irregular** — nem toda API traz todos os blocos.
- Débito consciente (D3 fatia `sen list` arquivada): dicts crus atravessam service → `ApiCollection` → CLI; helpers de domínio acoplados a chaves de wire; padrões §9 suspensa na fatia com gatilho de evolução explícito.
- `add-sen-completeness` está em fila e consumirá o mesmo frame para identidade/contexto (regra D4.c: projeção mínima no DTO de saída, mas alimentada por tipos de entrada que ainda não existem).
- Rede de proteção: 261 tests verdes (suite atual), cobertura ampla de `_render_grade`, revisões e erros.

## Goals / Non-Goals

**Goals:**
- Frame tipado em `domain/models/`, parseado **exclusivamente no adapter outbound** (dict cru morre lá — mesma régua do `CompletionReading`).
- Regras de domínio migram para métodos do entry, verbatim (zero mudança de decisão, só de residência).
- **Behavior-neutro:** grade de terminal, exit codes e mensagens idênticos; provado pela suíte existente + golden spot-checks.
- Preparar superfície de consumo para `add-sen-completeness` (identidade via `ApiCatalogEntry`) sem implementar B2.

**Non-Goals:**
- Canal JSON do `sen list` (B2) — fica desbloqueado, não implementado.
- Refatorar fluxo publisher/conversor/`ApiPartialInfo`/`ApiFull` — outro ciclo de vida (decisão D4.c da change irmã: não fundir entrada/saída).
- Tornar campos mandatórios ou endurecer validação — o frame é irregular por natureza; rigidez aqui quebra degradação.

## Decisions

**D1 — Granularidade do model: entry espelhando o frame, sub-objetos só onde a grade realmente navega.** `ApiCatalogEntry{managerId?→id, name?, description?, version?, contextType?, contextGroupName?, owner?, lastRevision? (número já resolvido), revisions: List[CatalogRevisionRef], completeness: List[CatalogScoreRef], environments: List[CatalogEnvironmentRef]}`. Os aninhados são `CatalogRevisionRef{id, revisionNumber, workflowId, workflowStageId, creationDate?}`, `CatalogScoreRef{score?, apiRevision?}`, `CatalogEnvironmentRef{name?, apiRevision?}`. Não tipar além do que list/consumers navegam (não embrulhar `revisions[i].deployments/resources/interceptors` — ruído do wire fica fora do model: campos desconhecidos são descartados no parse, e o caster any-future pede expansão local). **Consolidação de módulo (revisão 25/09):** os types novos + `ApiCollection` + seus erros convivem num único arquivo `domain/models/api_list_model.py` (sucessor do `api_collection_model.py`, que é aposentado) — é o agregado "listagem/catálogo de APIs": entry e coleção pertencem ao mesmo boceto de domínio, e há exatamente 1 casa para consumidores futuros importarem. Nomes PÚBLICOS de classe/errors preservados; só o caminho de import muda (service + cli + testes).

**D2 — Parse concentrado no outbound; tolerância por coercão.** Adapter realiza: fetch → `ApiCatalogEntry.model_validate` (ou classmethod `from_wire(dict)` que absorve o papel de `normalize_finder_rows`) → tipado na borda. Toda flexibilização (None-safe, cast num/str) vive em validators do entry. Port refletida: `ApiCatalogPage.rows: List[ApiCatalogEntry]` (dataclass existente ganha tipo nos items) e `list_api_detail -> Optional[ApiCatalogEntry]`. `get_api_by_id`/`publish_api_changes` (fluxo legacy) permanecem dict — fora do perímetro.

**D3 — Regras de wire→domínio viram métodos do entry, verbatim.** `last_revision_number()` (ordem: `lastRevision` dedicado → última de `revisions[]` → `None`), `completeness_score_for(revision_id)` (float? | None → `'-'` na render), `environment_names_for(revision_id)` (`", ".join` | `''`), contexto de posse (`contextOrNull`). Migração = mover corpo das funções livres (`api_collection_model.py`/service) para os métodos, com testes acompanhando. `ApiCollection.from_raw` passa a consumir `List[ApiCatalogEntry]` (rename honesto p/ `of_entries`; aceita `Optional[...]` para manter folds).

**D4 — CLI com acesso tipado e saída byte-idêntica.** `_listing_cells(entry)/_revision_cells(entry)` passam a projetar de atributos; quaisquer mutações de strings derivadas continuam nos mesmos pontos (o que hoje é `item.get(...)` vira propriedade que devolve o mesmo literal, incluindo sentinela `'-'`). Garantia: golden spot-check por amostragem dos renders contra a suíte atual (pytest protege tanto quanto o snapshot manual de cabos: as fixtures viram objetos, e as asserts sobre linhas renderizadas continuam inchaveadas).

**D5 — Cerca de escopo do perímetro finder.** Somente o caminho finder (listagem/catálogo/detail de contexto) migra. `ApiPartialInfo`/publisher/conversor é um circuito autônomo, mandatório-intenso e sem laço com esta fronteira — tocar nele é trocar digrama sem apelo. Justificativa: ciclos de vida distintos já argüidos no D4.c da change irmã.

**D6 — Handshake com `add-sen-completeness`.** Após merge: service da irmã consome `ApiCatalogEntry` para montar `api{name,version,context}` do contrato; a cláusula "gatilho B2" em ambas designs atinge o estado "fundação realizada". Nada muda no bloco `api` do DTO de saída da irmã (projeção segue mínima).

## Risks / Trade-offs

- [Chaves cruas ocultas em ramo não-top de fixture] → varredura dirigida: grep por `.get("` nos arquivos do perímetro + suíte verde depois da migração.
- [Volume de fixtures testes (dicts → objetos)] → churn mecânico; helpers de fábrica de fixture (uma função builder por shape) reduzem duplicação.
- [Divergência visual inadvertida] → renders byte-identics: asserts existentes de linha/listing preservadas; golden manual nas 3 grades canônicas (listagem, drill-down, fallbacks).
- [Tentação de aproveitar p/ refatorar mais] → cerca D5; escopo congela.

## Migration Plan

Ordem de fusão = tasks 1→5 (model → adapter/port → service/collection → CLI → handshake/docs). Cada task deixa a suíte verde (commits atômicos por grupo). Rollback = branch isolada sem merge; sen list em produção não é afetado até merge final.

## Open Questions

- Q1: `version` presente no frame finder? Smoke definirá (hoje o detail do Manager tem; o frame pode não trazer — model nasce `Optional` e o headline degrada a `'-'`).
- Q2: port `list_api_detail` assinatura — retorna `Optional[ApiCatalogEntry]` ou levanta? Alinhado ao soft-fail C4: `Optional` + sentinelas (service decide).
