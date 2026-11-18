## 1. Implementação

- [x] 1.1 Comando `whoami` em `cli_adapter.py`, com `--output` / `-o` (`text|json|yaml`, padrão `text`)
- [x] 1.2 Documento `apiops.sen-whoami/v1` por perfil, na ordem de campos da proposta; `authenticated: false` sem sessão
- [x] 1.3 `_session_panel` com o status e a dica como parâmetros, sem mudar o painel do login
- [x] 1.4 `build_session_store_factory` em `main.py`, sem carregar `Settings` e respeitando `PACKAGE_ROOT`

## 2. Testes

- [x] 2.1 Painel por perfil (developer com grupos; super-admin sem identidade)
- [x] 2.2 `json` e `yaml` por perfil, com a ordem de campos do contrato
- [x] 2.3 Sem sessão: mensagem, documento `authenticated: false` e exit `1`
- [x] 2.4 Nenhum token, `tokenType` ou `expiresIn` em nenhum formato
- [x] 2.5 Leitura da sessão gravada pelo `SessionStore` real
- [x] 2.6 Factory sem `Settings`, com e sem `PACKAGE_ROOT` no ambiente

## 3. Docs e validação

- [x] 3.1 `docs/comandos-cli.md`: seção `sen whoami`
- [x] 3.2 Suíte unitária sem regressão: 1152 passam, as mesmas 10 falhas antigas; `sen whoami` real conferido sem sessão e com sessões falsas de developer e super-admin numa pasta temporária
