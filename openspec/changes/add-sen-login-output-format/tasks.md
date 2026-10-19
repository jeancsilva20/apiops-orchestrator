## 1. Implementação

- [x] 1.1 Adicionar `--output` / `-o` (`text|json|yaml`, padrão `text`) ao comando `login` em `cli_adapter.py`
- [x] 1.2 Em `json`/`yaml`, não exibir logo nem animação; emitir só o documento `apiops.sen-login/v1`
- [x] 1.3 Documento por perfil: `developer` com `user.name`/`user.email`; `super-admin` com `profile`/`scope`; ambos com `authenticated` e `expiresAt` (ISO-8601 UTC); nenhum token

## 2. Testes

- [x] 2.1 Saída `text` inalterada
- [x] 2.2 `json` e `yaml` por perfil, com a ordem de campos do contrato
- [x] 2.3 Nenhum valor de token ou segredo em nenhum formato; nenhum elemento visual no modo estruturado
- [x] 2.4 Erro de login com `-o json` mantém a mensagem categorizada e o exit code

## 3. Docs e validação

- [x] 3.1 `docs/comandos-cli.md`: `--output` na seção `sen login`
- [x] 3.2 Suíte completa sem regressão em relação à linha de base — 718 passam, mesmas 8 falhas; `sen login -o json` real conferido (super-admin, sem token)
