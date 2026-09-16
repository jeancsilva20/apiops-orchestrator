## 1. ImplementaÃ§Ã£o

- [x] 1.1 Remover a linha "Grupos:" da saÃ­da de sucesso do comando `login` em `cli_adapter.py`. Verificar: saÃ­da de sucesso exibe apenas usuÃ¡rio, e-mail e expiraÃ§Ã£o.
- [x] 1.2 Atualizar `tests/unit/adapters/inbound/cli/test_login_command.py`: o teste de sucesso afirma que os grupos **nÃ£o aparecem** na saÃ­da, e que a sessÃ£o retornada (persistida) **contÃ©m** `user_groups`. Verificar: `poetry run pytest tests/unit/adapters/inbound/cli -q` verde.

## 2. Qualidade e validaÃ§Ã£o

- [x] 2.1 Suite completa + `ruff`/`black` nos arquivos alterados. Verificar: verde.
- [x] 2.2 `openspec validate omit-groups-from-login-summary --strict`. Verificar: sem erros.
