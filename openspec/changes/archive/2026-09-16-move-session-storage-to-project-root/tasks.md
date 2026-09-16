## 1. Guard-rail de versionamento (ANTES de qualquer gravaÃ§Ã£o)

- [x] 1.1 Adicionar `.sen_session*` ao `.gitignore`. Verificar: `git check-ignore -v .sen_session` aponta a linha; criaÃ§Ã£o manual de `.sen_session.fake.tmp` nÃ£o aparece em `git status`.
- [x] 1.2 Verificar ausÃªncia de sessÃ£o trackeada no histÃ³rico: `git log --all --oneline -- '*.sen_session*'` vazio. Verificar: comando executado, resultado registrado.

## 2. ComposiÃ§Ã£o e cÃ³digo

- [x] 2.1 `main.py`: `build_login_service_factory` passa `SessionStore(directory=settings.PROJECT_ROOT)`. Verificar: `poetry run python src/apiops_orchestrator/main.py sen login` grava em `<raiz>/.sen_session` mesmo executando a partir de `src/` (cenÃ¡rio "Local independente do diretÃ³rio corrente").
- [x] 2.2 Testes: novo caso afirmando que o caminho do store na composiÃ§Ã£o aponta para `PROJECT_ROOT`; suÃ­te do store inalterada (injeÃ§Ã£o jÃ¡ coberta). Verificar: `poetry run pytest tests/unit -q` verde.

## 3. DocumentaÃ§Ã£o de riscos (requisito do time)

- [x] 3.1 Criar `docs/adr/0006-armazenamento-da-sessao-raiz-do-projeto.md`: contexto, decisÃ£o, tabela risco Ã— mitigaÃ§Ã£o (Git, sync/backup, esteira/artefatos, multiusuÃ¡rio, scanners, `git clean`), alternativas rejeitadas (temp mantido / `~/.sen` adiado), apontamento de supersede do aspecto de storage do ADR 0002. Verificar: revisÃ£o pelo time (regra do projeto: decisÃ£o â†’ validaÃ§Ã£o por segundo agente).
- [x] 3.2 Atualizar `docs/features/sen-login.md` (local da sessÃ£o = raiz), README (trecho de local/privacidade) e `docs/auth/distribuicao-e-fontes-de-credenciais-backlog.md` (link para ADR 0006; `~/.sen` segue como destino na distribuiÃ§Ã£o). Verificar: revisÃ£o textual.

## 4. Qualidade e validaÃ§Ã£o

- [x] 4.1 Suite completa + lint nos arquivos alterados (`pytest -q`, `ruff check`, `black --check`). Verificar: verde.
- [x] 4.2 E2E manual: login feliz â†’ arquivo na raiz; `git status` limpo; re-login substitui sem `.tmp` remanescente. Verificar: execuÃ§Ã£o manual com evidÃªncias na task.
- [x] 4.3 `openspec validate move-session-storage-to-project-root --strict`. Verificar: sem erros; cenÃ¡rios 1:1 com testes/smokes.
