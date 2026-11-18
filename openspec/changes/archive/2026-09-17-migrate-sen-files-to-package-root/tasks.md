## 1. Settings â€” `PACKAGE_ROOT` e fonte dupla

- [x] 1.1 Derivar e expor `PACKAGE_ROOT` no `Settings` (`Path(__file__).resolve().parents[1]`) e compor `env_file=(ENV_PATH, SEN_PATH)` nas `SettingsConfigDict` â€” `.env` da raiz, `.sen` do pacote, respeitando precedÃªncia nativa (processo > `.sen` > `.env`)
- [x] 1.2 Adicionar/atualizar teste de contrato de settings para a tupla de fontes: carrega sÃ³ `.env`; sÃ³ `.sen`; overlap `.sen` vence `.env`; variÃ¡vel de processo vence ambas; chaves extras ignoradas

## 2. Store â€” `.sen_session` no diretÃ³rio do pacote

- [x] 2.1 Default de `SessionStore` deixa de ser `tempfile.gettempdir()` e passa a `settings.PACKAGE_ROOT` (composition root injeta; `directory=` de testes preservado); docstrings/logs refletem o novo destino
- [x] 2.2 Testes de store: arquivo criado no diretÃ³rio informado (comportamento atual jÃ¡ validado com `tmp_path` â€” acrescentar cenÃ¡rio "default do pacote" via instÃ¢ncia sem argumento com monkeypatch de `PACKAGE_ROOT`)

## 3. Mensagens e UX mÃ­nimas

- [x] 3.1 `CredentialNotFoundError` orienta as duas fontes (`SEN_CREDENTIALS` na variÃ¡vel **ou** bloco `SEN_CREDENTIALS` no `.sen`) â€” texto PT-BR acionÃ¡vel, sem mencionar `OAUTH_*`
- [x] 3.2 Ajustar asserÃ§Ãµes de mensagem nos testes do service/CLI que enxergam o texto da credencial

## 4. Config de repositÃ³rio e gabarito

- [x] 4.1 `.gitignore`: adicionar match exato `.sen` (+ garantir `.sen_session*` cobre o novo diretÃ³rio; incluir provisÃ³rios `.sen_session.*.tmp`)
- [x] 4.2 Criar `.sen.example` (mesmo padrÃ£o de comentÃ¡rios do `.env.example`; placeholders, zero segredo real) â€” VERSIONADO
- [x] 4.3 Restaurar `.env.example` ao estado anterior ao `sen login` (remover o bloco AUTH da CLI) â€” o `.env` tende a deixar de existir; a esteira deverÃ¡ injetar as credenciais por variÃ¡veis de ambiente quando isso amadurecer

## 5. DocumentaÃ§Ã£o e ADR

- [x] 5.1 Novo ADR (fontes de credencial e residÃªncia de arquivos `.sen`/`.sen_session`, precedÃªncia e limitaÃ§Ã£o de executÃ¡vel congelado) em `docs/adr/`, formato MADR
- [x] 5.2 Atualizar `docs/features/sen-login.md` e Â§4.2/Â§4.3 da doc de padrÃµes (cadastro dos lugares + tabela de perfis)

## 6. ConsistÃªncia e fechamento

- [x] 6.1 Suite completa verde (`poetry run pytest`) + `black`/`ruff` nos arquivos tocados
- [x] 6.2 `npx openspec validate migrate-sen-files-to-package-root` e registro no CHANGELOG
