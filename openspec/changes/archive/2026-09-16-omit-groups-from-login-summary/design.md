## Context

A saída de sucesso do login é composta exclusivamente no comando (`cli_adapter.py`), a partir da `LoginSession` retornada pelo serviço. `user_groups` permanece no modelo e no arquivo persistido (contrato da requisição "Sessão persistida..." inalterado); somente a renderização perde a linha de grupos.

## Goals / Non-Goals

**Goals:** saída minimalista (username, e-mail, expiração).
**Non-Goals:** alterar persistência, alterar modelos/API da Orchestrator Auth, remover grupos de qualquer log de autorização futuro (guard).

## Decisions

**D1 — Edição só na renderização da CLI.** O token de decisão de exibição vive no comando (camada inbound); o serviço continua entregando a sessão completa. Alternativa rejeitada: "esconder" grupos no modelo — quebraria o contrato de armazenamento e o futuro guard.

## Risks / Trade-offs

- [Alguém esperar grupos na tela p/ diagnóstico rápido] → visualização possível via `(Get-Content .sen_session | ConvertFrom-Json).user_groups`; documentado no guia, se necessário.

## Migration Plan / Open Questions

Rollback trivial (reversão de 1 linha). Sem questões abertas.
