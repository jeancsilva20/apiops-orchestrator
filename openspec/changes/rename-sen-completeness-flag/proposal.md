## Why

O comando `sen completeness` recebe o ID da API via flag `--api-id`, enquanto o comando irmão `sen list api` (que o próprio texto de erro do completeness cita como "como descobrir") usa `--id`. Duas grafias para o mesmo conceito na mesma CLI confundem o usuário e contradizem a mensagem de ajuda que manda rodar `sen list api --id X --revisions`. Padronizar agora, logo após o arquivamento de `add-sen-completeness` (2026-09-28), minimiza o custo de quebra.

## What Changes

- **BREAKING**: flag `--api-id` do `sen completeness` passa a se chamar `--id` (renomeação limpa, SEM alias para `--api-id` — decisão do autor em 29/09/2026).
- Mensagem de erro pré-rede (`MISSING_TARGET_MESSAGE`) atualizada para citar `--id e --revision`.
- Especificação `sen-completeness` atualizada (gramática e cenários) para a nova grafia.
- Sem mudanças em: service/adapter/port (`api_id` continua nome interno do parâmetro), contrato JSON `apiops.sen-completeness/v1`, matriz de exit codes.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `sen-completeness`: o requisito "Grammar of the sen completeness command" passa a exigir `--id <id_manager>` (em vez de `--api-id`) como flag obrigatório do ID da API; cenários refletem a nova grafia.

## Impact

- Código: `adapters/inbound/cli/cli_adapter.py` (assinatura da opção + mensagem de erro).
- Testes: `tests/unit/adapters/inbound/cli/test_cli_adapter.py` (invocações passam a usar `--id`).
- Usuários/scripts que invocam `sen completeness --api-id X` quebram na grafia do flag (única quebra).
