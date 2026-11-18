## Why

Os demais comandos (`sen list`, `sen completeness`, `sen validate`, `sen publish`) aceitam `--output
text|json|yaml`, e a decisão transversal da CLI é que o modo estruturado contém só os dados, sem
elementos visuais, num formato versionado. O `sen login` é o único que só tem saída para humanos: uma
esteira ou um script não tem como saber, sem raspar texto, quem autenticou e até quando a sessão vale.

## What Changes

- `sen login` passa a aceitar `--output` / `-o` com `text` (padrão), `json` e `yaml`.
- `text` não muda: logo, animação de autenticação e painel da sessão.
- `json`/`yaml` emitem só o documento `apiops.sen-login/v1` — sem logo e sem animação:
  - `developer`: `schema`, `authenticated`, `user.name`, `user.email`, `expiresAt`;
  - `super-admin`: `schema`, `authenticated`, `profile`, `scope`, `expiresAt` — sem identidade pessoal,
    como no painel.
- Nenhum token ou segredo aparece em nenhum formato (decisão vigente do `sen login`).
- Erros não mudam: mensagem categorizada e exit code diferente de `0`.

## Capabilities

### New Capabilities

- (nenhuma)

### Modified Capabilities

- `cli-auth`: **MODIFIED** — "Comando `sen login`": ganha o `--output` e os cenários do modo
  estruturado (bloco copiado integralmente no delta).

## Impact

- **Código**: comando `login` em `cli_adapter.py` (opção, supressão do visual no modo estruturado,
  montagem do documento).
- **Testes**: CLI do login nos três formatos, por perfil, sem token na saída.
- **Docs**: `docs/comandos-cli.md`, seção `sen login`, passa a listar o `--output`.
