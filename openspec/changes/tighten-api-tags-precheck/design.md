## Design

### Contexto

O pré-check lê o catálogo de atributos uma vez por execução. Ele já servia a duas coisas: traduzir os `attributeId` dos requisitos do stage em nomes, e conferir se as tags declaradas pertencem ao atributo. As `apiTags` do repositório falam em nomes (`attributeName`, `tags[]`), e o catálogo também.

Sonda somente leitura no consulting em 05/11/2026: `GET /api-governance/api/v3/attributes` devolve uma lista simples e ignora `page`, `size` e `limit`, sem cabeçalhos de paginação. A lista é o catálogo inteiro, então "não está no catálogo" não corre o risco de vir de uma página truncada. Estado do catálogo nessa data: `CLI []`, `My new [Tag1, Tag2]`, `Teste []`, `teste giroto [teste giroto]`.

### Decisões

**D1 — Quatro problemas, conferidos em ordem, um veredito por atributo.**

| Caso | Problema |
|---|---|
| `attributeName` fora do catálogo | `unknown_attribute` |
| atributo sem tags cadastradas, com ou sem tag declarada | `attribute_without_catalog_tags` |
| atributo declarado com `tags: []` ou sem a chave | `missing_tag` |
| tag fora da lista do atributo | `invalid_tag`, um por tag |

Um atributo sem tags no catálogo gera um problema só, qualquer que seja o número de tags declaradas: o que o dev precisa corrigir é o atributo.

**D2 — Um erro só, com a lista inteira.** `InvalidApiTagsError` (`exit 1`) substitui o `InvalidTagError` e lista todos os problemas, para o dev corrigir tudo numa rodada. É erro de conteúdo do repositório, então vem antes do bloqueio de governança (`exit 3`). Por isso, um atributo exigido declarado com `tags: []` passa a sair com `exit 1`.

**D3 — Sugestão só para acento e maiúscula.** O nome do catálogo é sugerido quando fica igual ao declarado depois de tirar os acentos (NFKD sem marcas combinantes) e passar para minúsculas (`casefold`). Letras diferentes, espaço a mais ou plural ficam sem sugestão. Se mais de um nome do catálogo bater, todos são sugeridos.

**D4 — A conferência fica no pré-check, não no JSON Schema.** Os schemas dos YAML (`domain/schemas/`) não são aplicados pelo `validate` nem pelo `publish`; o `CatalogSchemaValidator` só roda nos testes. O pré-check já tem o catálogo e reúne os quatro casos numa mensagem.

**D5 — A conta da governança não muda.** `_present` continua tratando atributo com tags cadastradas e `tags: []` como ausente. No `validate` e no `publish` esse caso já aborta antes, pela D2; a regra continua valendo para o `sen deploy`, que avalia as `apiTags` do Manager.

**D6 — `tagId` não é tratado.** O Manager não deixa exigir tag específica no workflow; o campo é sempre `null`.

### Fora do escopo

- `apiTags` ausente no `api-basic-info.yaml`: continua sem envio e sem conferência, e o pré-check segue contando todos os atributos exigidos como faltantes.
- Aplicar os JSON Schemas dos YAML no `validate`/`publish`.
- Remover `tagId` da saída JSON.

### Riscos

- **APIs com atributo sem tags no catálogo** (ex.: `CLI: Sensedia` nas 189 e 203 do consulting) deixam de publicar pelo `sen` até o atributo ganhar tags no Adaptive Governance. Aceito pelo responsável.
- **Catálogo muda entre a leitura e o `PUT`**: janela de segundos; a conferência pós-publicação acusa a perda.
