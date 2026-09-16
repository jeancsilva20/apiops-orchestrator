## Why

Os grupos aparecem na saída de sucesso do `sen login`, mas não têm valor de decisão imediata para o dev — o consumo real deles é o guard por scopes (fase 2). O resumo de login fica mais enxuto sem a linha; os dados de grupo continuam **persistidos** na sessão (contrato de armazenamento inalterado).

## What Changes

- Saída de sucesso do `sen login` passa a exibir apenas: username, e-mail e prazo de expiração. A linha de grupos é removida.
- **Persistência inalterada**: `user_groups` continua no `.sen_session` (e seguindo para o guard futuro).

## Capabilities

### New Capabilities
- (nenhuma)

### Modified Capabilities
- `cli-auth`: **MODIFIED** — "Comando `sen login`": cenário "Login bem-sucedido" deixa de listar grupos na exibição (bloco copiado integralmente no delta).

## Impact

- **Código**: remoção de 1 linha de saída no comando de login (`cli_adapter.py`).
- **Testes**: caso de CLI atualizado — grupos NÃO aparecem na saída; sessão persistida CONTÉM `user_groups` (ambas as afirmações).
- **Docs**: nenhum lugar citava grupos na exibição (README/features não mudam).
