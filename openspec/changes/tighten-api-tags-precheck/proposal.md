## Why

O pré-check de `apiTags` (change `handle-manager-rejections-in-validate-publish`, 16/10/2026) só conferia uma coisa: a tag declarada pertencer à lista do atributo no catálogo do Adaptive Governance. Três casos passavam sem aviso e iam para o `PUT`:

- `attributeName` que não existe no catálogo, como um erro de digitação. Não satisfazia requisito nenhum, mas, se o stage não exigisse o atributo, passava calado. O efeito no Manager não foi medido; pode ser o mesmo da tag inválida, que zera todas as `apiTags`.
- Atributo sem tags cadastradas no catálogo (ex.: `CLI`). Qualquer valor era aceito, porque não havia lista contra a qual comparar.
- Atributo declarado sem tag (`tags: []` ou sem a chave). Só contava como ausente na conta da governança, com `exit 3` se fosse exigido; se não fosse, passava.

Decisão do responsável em 05/11/2026: o repositório só carrega pares (atributo, tag) que existam no Manager. Os três casos passam a ser erro do repositório, antes de qualquer escrita.

O `tagId` dos requisitos do stage fica fora: o Manager não oferece a opção de exigir uma tag específica no workflow, então ele é sempre `null`.

## What Changes

- **Pré-check de `apiTags`** (`sen validate` e `sen publish`): cada item é conferido contra o catálogo (`GET /api-governance/api/v3/attributes`) e vira erro quando:
  - o `attributeName` não existe no catálogo;
  - o atributo existe, mas não tem tags cadastradas;
  - o atributo foi declarado sem tag;
  - uma tag não está na lista do atributo (já existia).
- **Um erro só, com todos os problemas** (`InvalidApiTagsError`, `exit 1`, substitui o `InvalidTagError`), antes do bloqueio de governança e terminando em "Nada foi publicado.".
- **Sugestão de nome** para atributo inexistente só quando o nome do catálogo difere do declarado em acentuação e/ou maiúsculas. Qualquer outra diferença fica sem sugestão.
- **Atributo exigido declarado com `tags: []`** sai com `exit 1` (problema no `apiTags`), e não mais com `exit 3`.

## Capabilities

### Modified Capabilities

- `sen-validate`: o requisito "Pré-check confere as tags declaradas em apiTags" passa a cobrir os quatro casos.
- `sen-publish` (spec ainda no change `add-sen-publish`): a lista de pré-condições que abortam antes da escrita passa a citar as `apiTags` inválidas.

## Impact

- **Código**: `application/services/governance_precheck_service.py` (`ApiTagProblem`, `api_tag_problems`), `application/exceptions/validate_exceptions.py` (`InvalidApiTagsError`), `validate_service.py`, `publish_service.py`.
- **`sen deploy`**: sem mudança; ele lê as `apiTags` do Manager e não as grava.
- **APIs existentes**: as que carregam atributo sem tags no catálogo deixam de publicar pelo `sen` até o atributo ganhar tags no Adaptive Governance. No consulting, em 29/09, eram a 189 e a 203 (`CLI: Sensedia`). Confirmado com o responsável.
