# Observações — identificação do catálogo (Connect Catalog)

*(observações empíricas em produção, 2026-09-24)*

## O problema

No retorno do `GET /adaptive-governance/api/v1/search` não há um identificador confiável da API do Manager (não se pode apontar qual item do catálogo corresponde à API pesquisada). Por isso, a ponte `--api-id` (Manager) → `catalog.catalogOriginId` precisa ser feita consultando diretamente o Connect Catalog, evitando depender da busca do AG.

## O catálogo

Ao consultar `GET /connect-catalog/api/v1/catalogs`, atenção: **o mesmo `originId` pode aparecer em mais de um item**, pois cada manager conectado (integração) tem sua própria numeração — pode até haver APIs diferentes com mesmo número em managers distintos.

O que se mostrou mais eficaz (e o porquê):

1. **Primeiro consultar `/integrations` e selecionar a integração NATIVE/v5** — é ela que representa o Manager nativo; com o `integrationId` em mãos, qualquer `originId` passa a ser único, eliminando a ambiguidade entre managers.
2. **Depois filtrar `/catalogs` com `integrationIds` (plural) + `name`** — são os únicos filtros que o servidor realmente honra nessa rota (inclusive `originId`, sozinho ou combinado, é ignorado). Resolvendo por nome e conferindo o `originId` client-side, o match fica determinístico: 1 chamada leve, sem paginar o catálogo inteiro.
