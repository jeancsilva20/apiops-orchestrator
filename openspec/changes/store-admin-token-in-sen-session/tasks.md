# Tasks: store-admin-token-in-sen-session

## 1. Guardas de comportamento (lock-first)

- [ ] 1.1 Estender `tests/unit/infrastructure/secure_storage/test_session_store.py`: super-admin salva com `adminAccessToken` no payload gravado e `load()` devolve a sessão completa; developer salva SEM o campo
- [ ] 1.2 Caso de compat legada: arquivo de super-admin sem `adminAccessToken` (formato anterior) carrega sem erro; expirado continua tratado como ausente (incluindo token)

## 2. Persistência

- [ ] 2.1 `SessionStore.save()`: remover `exclude={"adminAccessToken"}` e atualizar comentário inline (motivo do supersede + referência ao change)
- [ ] 2.2 `LoginSession`: ajustar docstring do campo `adminAccessToken` (não mais "memory only"); guard `_ensure_guarded_state` inalterado (fonte de verdade do perfil)

## 3. Documentação e fechamento

- [ ] 3.1 Nota de revisão em `docs/adr/0002-ciclo-de-vida-de-tokens-dev-x-superadmin.md` (seção esteira: persistência autorizada no `.sen_session` com salvaguardas; link para este change) + linha no CHANGELOG
- [ ] 3.2 Suíte verde (`pytest`, `ruff` nos arquivos tocados, `mypy`) e nota para o backup do backlog (consumo do token pelo `sen list` — change separado)
