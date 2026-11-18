## Why

Hoje a única forma de saber quem está logado, com qual escopo e até quando é rodar `sen login` de novo ou abrir o `.sen_session`. O login esconde os grupos, e são os grupos e o escopo que decidem se o `sen` aceita um comando (time APIOps, `write` no `validate`). Abrir o arquivo expõe os tokens e é proibido para os agentes.

## What Changes

- Novo comando `sen whoami`, que lê a `.sen_session` e mostra os dados da sessão, sem tokens.
- Só lê o arquivo local: não chama a API de auth nem o Manager, e não exige o `.sen`.
- A pasta da sessão é a mesma dos outros comandos, inclusive com `PACKAGE_ROOT` sobrescrito por variável.
- `text` (padrão): painel no estilo do `sen login`, sem logo.
  - `developer`: usuário (nome e e-mail), perfil, grupos, escopo e validade.
  - `super-admin`: perfil, escopo e validade.
- `json`/`yaml`: só o documento `apiops.sen-whoami/v1`.
  - `developer`: `schema`, `authenticated`, `profile`, `user.name`, `user.email`, `groups`, `scope`, `expiresAt`.
  - `super-admin`: `schema`, `authenticated`, `profile`, `scope`, `expiresAt`.
- Sem sessão válida (ausente, expirada ou ilegível): "Nenhuma sessão válida: faça `sen login`." no texto, `{schema, authenticated: false}` no modo estruturado, e exit `1`.

## Capabilities

### New Capabilities

- (nenhuma)

### Modified Capabilities

- `cli-auth`: **ADDED** — "Comando `sen whoami`".

## Impact

- **Código**: comando `whoami` em `cli_adapter.py`; `_session_panel` ganha o status e a dica como parâmetros (o login não muda); factory `build_session_store_factory` em `main.py`.
- **Testes**: CLI do whoami por perfil e formato, sem sessão, sem token em nenhuma saída, leitura pelo store real; factory sem carregar `Settings` e respeitando `PACKAGE_ROOT`.
- **Docs**: `docs/comandos-cli.md` ganha a seção `sen whoami`.
