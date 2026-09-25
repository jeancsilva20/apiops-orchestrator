# Tasks: store-admin-token-in-sen-session

## 1. Guardas de comportamento (lock-first)

- [x] 1.1 Estender `tests/unit/infrastructure/secure_storage/test_session_store.py`: super-admin salva com `adminAccessToken` no payload gravado e `load()` devolve a sessÃ£o completa; developer salva SEM o campo
- [x] 1.2 Caso de compat legada: arquivo de super-admin sem `adminAccessToken` (formato anterior) carrega sem erro; expirado continua tratado como ausente (incluindo token)

## 2. PersistÃªncia

- [x] 2.1 `SessionStore.save()`: remover `exclude={"adminAccessToken"}` e atualizar comentÃ¡rio inline (motivo do supersede + referÃªncia ao change)
- [x] 2.2 `LoginSession`: ajustar docstring do campo `adminAccessToken` (nÃ£o mais "memory only"); guard `_ensure_guarded_state` inalterado (fonte de verdade do perfil)

## 3. DocumentaÃ§Ã£o e fechamento

- [x] 3.1 Nota de revisÃ£o em `docs/adr/0002-ciclo-de-vida-de-tokens-dev-x-superadmin.md` (seÃ§Ã£o esteira: persistÃªncia autorizada no `.sen_session` com salvaguardas; link para este change) + linha no CHANGELOG
- [x] 3.2 SuÃ­te verde (`pytest`, `ruff` nos arquivos tocados, `mypy`) e nota para o backup do backlog (consumo do token pelo `sen list` â€” change separado)
