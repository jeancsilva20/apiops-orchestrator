## Why

Na API 68, `sen list api --id 68 -r` mostra 68.5 / 68.5 / 66.8 nas revisões 2, 3 e 4, enquanto `sen completeness` (e a interface do Manager) mostra 74.3 / 74.3 / 75.8. A grade lê o score do bloco `completeness[]` do api-finder; os demais comandos leem `GET /api-manager/api/v3/revisions/{id}/completeness`.

A sondagem de 21/10/2026 (40 APIs, 213 revisões, somente GETs) mostrou que o finder diverge do Manager em **164 de 213 revisões (77%)**, para cima (72) e para baixo (92), inclusive na última revisão (10 casos). O bloco do finder traz só `{score, apiRevision}` — sem data, versão de regra ou qualquer marcador que permita saber quais valores estão defasados ou corrigi-los. Não há rota em lote: o swagger do Manager expõe apenas `GET /revisions/{id}/completeness` (`CompletenessBean`).

Consequência prática: a grade pode mostrar uma revisão abaixo do gate de 70% que o `sen deploy` aprova (rev 4 da API 68: grade 66.8, deploy lê 75.8), ou o contrário.

## What Changes

- A célula COMPLETE do drill-down passa a vir de `GET /api-manager/api/v3/revisions/{id}/completeness`, uma chamada por revisão exibida, em paralelo com concorrência limitada.
- Falha ao ler o completeness de uma revisão não derruba a grade: a célula vira `-` e o texto ganha uma nota de rodapé com a contagem de revisões sem leitura. Em `-o json|yaml`, `completeness_score: null`.
- Feedback de espera em modo texto (spinner em terminal, linha única fora dele, nada em `json`/`yaml`) — a rota leva ~2,2 s por chamada.
- A célula COMPLETE passa a exibir uma casa decimal (`75.8%`), como `sen completeness`, `sen validate` e `sen deploy`; o arredondamento para inteiro escondia valores perto do gate (69.6 aparecia como `70%`).
- O adapter deixa de ler o bloco `completeness[]` do frame do api-finder; o campo `CatalogRevision.completeness` sai do modelo.
- Sem mudança em: `sen completeness`, `sen deploy`, `sen validate`, `sen publish` (já usam a rota do Manager ou não leem completeness); contrato JSON do drill-down (mesmo campo `completeness_score`, só muda a origem do valor).

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `sen-list`: o requisito do drill-down passa a exigir a rota do Manager como fonte da coluna COMPLETE, com degradação por célula e feedback de espera.
- `api-catalog`: as regras seladas do frame deixam de correlacionar o bloco `completeness[]` (ignorado por ser defasado); a leitura de completeness passa a existir apenas pela rota do Manager.

## Impact

- Código: `application/services/api_listing_service.py` (busca paralela e degradação), `adapters/outbound/http/manager_api/manager_api_adapter.py` (`_merge_wire_blocks` sem o bloco `completeness`), `domain/models/catalog_revision_model.py` (remove `CatalogRevision.completeness`), `adapters/inbound/cli/cli_adapter.py` (nota de rodapé e feedback de espera na grade).
- Testes: `test_api_listing_service.py`, `test_catalog_translator.py`, `test_api_catalog_model.py`, testes de CLI da grade.
- Rede: o drill-down passa de 1 + W chamadas (W = workflows distintos) para 1 + W + R (R = revisões). Medido na API 341 (55 revisões): ~2 min em sequência, ~21 s com 8 em paralelo.
