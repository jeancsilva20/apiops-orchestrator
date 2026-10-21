## Why

Todas as chamadas ao Manager usam o token de super admin que o `/orq-auth` devolve, e a rota de validação recebe o corpo vazio, sem a API nem a ação. O servidor, portanto, nunca recusa por visibilidade: quem decide é o CLI, como o spec do `sen list` já registra (*"A visibilidade NUNCA SHALL ser delegada ao servidor"*).

A regra só é aplicada na listagem. A leitura de 21/10/2026 achou, para uma sessão de dev e uma API que ela não enxerga:

- `sen list api --id X` mostra o cabeçalho da API, e `-r` mostra a grade de revisões com stage, ambientes e completeness;
- `sen completeness --id X --revision R` mostra o score e as sugestões; esconde só nome e versão. E como a leitura é feita pelo id da revisão, `--id <API visível> --revision <revisão de outra API>` também passa;
- `sen validate` lê a régua, roda a conformidade e **grava a revisão 1** da API;
- `sen diag draft` (interno, oculto) mostra o estado da revisão alvo.

Duas premissas dos specs não se sustentam com o token de super admin: o cenário do drill-down do `sen list` (*"o servidor pode mascarar ausência e ausência de permissão"*) e a D5 do `add-sen-completeness` (*"a autorização de fato da consulta segue sendo do servidor (403)"*).

O `sen publish` e o `sen deploy` ficam fora: rodam só na esteira (`hide-pipeline-settings-from-dev`), onde a sessão é de super admin.

## What Changes

- Nova capability `api-visibility`: uma regra só, aplicada por todos os comandos, com as duas fontes em que a plataforma entrega a visibilidade (catálogo e `GET /apis/{id}`).
- Na regra `ME`, vale o `owner` **ou** um dos usuários da visibilidade — como o código do `sen list` já faz. O spec dizia que `users[]` era irrelevante.
- Sessão de super admin enxerga tudo. A regra vale pelo perfil da sessão, não pelo modo de execução.
- API invisível responde igual à API inexistente, com a mensagem e o exit code que cada comando já usa para esse caso.
- `sen list api --id X` (com ou sem `-r`): a visibilidade é verificada logo após a leitura do catálogo, antes de stages e completeness. Exit `1`.
- `sen completeness`, para sessão de dev: a consulta da API passa a ser obrigatória e anterior à leitura do completeness; a revisão precisa pertencer à API; falha da consulta encerra com erro. Exit `2`. Para super admin nada muda.
- `sen validate`: a visibilidade é lida do `GET /apis/{id}` que a E2 já faz, antes da guarda de identidade, da régua e de qualquer escrita. Exit `1`, sem chamada nova.
- `sen diag draft`: mesma verificação, mesmo ponto.

## Capabilities

### New Capabilities

- `api-visibility`: regra de visibilidade de uma API para a sessão, fontes, resposta para API invisível e o momento da verificação.

### Modified Capabilities

- `sen-list`: a filtragem da listagem passa a citar a regra de `api-visibility`; o drill-down por `--id` passa a aplicá-la. Depende de `use-manager-completeness-in-sen-list` ser arquivada antes desta change.
- `sen-completeness`: consulta da API obrigatória para dev, pertença da revisão à API e falha da consulta deixam de degradar. Revoga em parte a D5 do `add-sen-completeness`. Os cenários usam `--id`, de `rename-sen-completeness-flag`.
- `sen-validate`: novo requisito de visibilidade da API alvo.

## Impact

- Código novo: `domain/models/api_visibility_model.py`, `domain/services/api_visibility.py` (substitui `catalog_visibility.py`), `application/services/api_access_guard.py`.
- Código alterado: `domain/models/api_catalog_model.py`, `application/services/api_listing_service.py`, `completeness_service.py`, `validate_service.py`, `application/exceptions/manager_failure_messages.py`, `listing_exceptions.py`, `completeness_exceptions.py`, `validate_exceptions.py`, `adapters/inbound/cli/cli_adapter.py` (`diag draft`), `main.py` (factory do `diag draft` monta a guarda), `adapters/outbound/http/manager_api/manager_api_adapter.py` (import do `OwnershipContext`).
- Testes: `test_catalog_visibility.py` vira `test_api_visibility.py`; testes de serviço do list, completeness e validate; teste do `diag draft`.
- Documentação: `comandos-cli.md` (decisão transversal).
- Rede: nenhuma chamada nova. O completeness de dev passa a fazer a consulta do catálogo antes da leitura, e não depois.
