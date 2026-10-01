# Tasks — type-api-catalog-frame

## 1. Models tipados do frame

- [x] 1.1 Criar `domain/models/api_list_model.py` (consolidado — recebe contents do `api_collection_model.py`, que é aposentado no merge do grupo): `ApiCatalogEntry`, `CatalogRevisionRef`, `CatalogScoreRef`, `CatalogEnvironmentRef` — optionals abundant + coerções de wire (`int|str` numéricos, strings vazias → None) em validators `mode="before"`; imports públicos (`ApiCollection`, erros) preservados com novo caminho *[implementado 25/09: frame tipado + CONSOLIDAÇÃO já executada — `ApiCollection`/erros/visibilidade/normalize movidos VERBATIM (utf8-safe), `api_collection_model.py` deletado, 5 imports redirecionados; a troca `items→List[ApiCatalogEntry]` segue no grupo 3]*
- [x] 1.2 Métodos de domínio (verbatim dos helpers existentes): `last_revision_number()`, `completeness_score_for(revision_id)`, `environment_names_for(revision_id)`, contexto de posse (`context_is_known`); unknown-fields descartadas no parse *[implementado]*
- [x] 1.3 Unit tests dos models: frame completo, frame esparsos (faltam blocos), coercões num/str, fallbacks idênticos aos helpers antigos *[implementado: 13 testes]*

## 2. Adapter e port

- [x] 2.1 `ManagerApiAdapter`: absorver `normalize_finder_rows` no parse; `list_catalog_apis` retorna `ApiCatalogPage.rows: List[ApiCatalogEntry]`; `list_api_detail` retorna `Optional[ApiCatalogEntry]`; dict cru restrito ao outbound
- [x] 2.2 Atualizar `domain/ports/manager_api_port.py` (assinaturas e `ApiCatalogPage`) — fluxos legacy (`get_api_by_id`, `publish_api_changes`, conversor) intocados
- [x] 2.3 Unit tests do adapter: fixtures dict → typed; casos esparsos; page-count header

## 3. Collection e service

- [x] 3.1 `ApiCollection`: `items: List[ApiCatalogEntry]`, factory `of_entries`; pipeline filter/sort/window preservado; remover `last_revision_number`/funções livres de dict (viraram métodos); deletar `api_collection_model.py` quando nenhum import apontar mais nele
- [x] 3.2 `ApiListingService`: helpers de chave desaparecem; derivadas passam pelos métodos do entry; drill-down idem
- [x] 3.3 Unit tests do service/collection: fixtures migram para builders tipados; regras de visibilidade/query/order inalteradas

## 4. CLI behavior-neutro

- [x] 4.1 `_listing_cells`/`_revision_cells` consomem tipado; sentinelas `'-'` e textos derivados idênticos (byte-a-byte)
- [x] 4.2 Suite completa verde + golden spot-check das 3 grades canônicas (listagem, drill-down, fallbacks) contra os renders atuais
- [x] 4.3 Varredura dirigida: nenhum `.get("` de chave de finder em service/domain/CLI (grep audit no perímetro)

## 5. Handshake e docs

- [ ] 5.1 `add-sen-completeness`: service consume `ApiCatalogEntry` (tasks 3.1/3.2 da irmã apontam os tipos daqui); cláusulas "gatilho B2" marcadas como fundação realizada (notes em ambos designs)
- [ ] 5.2 CHANGELOG + commit documental separado do código (padrão do repo); segundo agente revisor valida a change antes de `openspec archive`
