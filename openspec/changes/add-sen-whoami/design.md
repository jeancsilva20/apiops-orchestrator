## Contexto

A `.sen_session` guarda `accessToken`, `tokenType`, `expiresIn`, `scope`, `profile`, `expiresAt` e, por perfil, `userName`, `userEmail`, `userGroups` (developer) ou `adminAccessToken` (super-admin). O `SessionStore.load()` devolve `None` quando o arquivo não existe, está corrompido ou expirou.

## Decisões

**D1 — Só confere localmente.**
- O `whoami` não pergunta à API de auth se o token ainda vale.
- Se o servidor revogar o token antes do `expiresAt`, o `whoami` continua mostrando a sessão como válida. Quem decide é o servidor (ADR 0003), e o `whoami` não se apresenta como a palavra final.

**D2 — Roda sem `.sen`.**
- O comando não carrega `Settings`, que exige `AUTH_HOST` e `AUTH_LOGIN_PATH`. Assim dá para conferir a sessão com a configuração incompleta.
- A pasta vem de `PACKAGE_ROOT` no ambiente (que já inclui o `.sen` e o `.env` carregados) ou, sem ela, da pasta do pacote. É o mesmo valor que `Settings.PACKAGE_ROOT` resolve para os outros comandos.

**D3 — Expirada e ausente são o mesmo caso.**
- O comando usa o `load()` como está. Mostrar "expirou em X" exigiria um método novo no store.

**D4 — Campos.**

| Campo na sessão | No `whoami` | Motivo |
|---|---|---|
| `accessToken`, `adminAccessToken` | nunca | são tokens |
| `tokenType` | não | descreve o token, não o usuário |
| `expiresIn` | não | é a duração original; o `expiresAt` já diz até quando vale |
| `profile`, `scope`, `expiresAt` | sim | |
| `userName`, `userEmail`, `userGroups` | sim, no developer | o login esconde os grupos, mas é por eles que o `sen` checa o time APIOps |

**D5 — Sem permissões calculadas e sem Manager.**
- O comando não diz se a sessão pertence ao time APIOps nem se pode rodar o `validate`. Mostra só os dados da sessão.
- A sessão não guarda em que Manager foi aberta. Mostrar o `HOST` do `.sen` atual poderia estar errado caso o `.sen` tenha mudado depois do login.

**D6 — Sem sessão é exit `1`.**
- No modo estruturado sai o documento com `authenticated: false`, para quem automatiza ler o mesmo formato nos dois casos.

## Fora do escopo

- As skills usarem o `whoami`.
- Gravar na sessão o Manager em que ela foi aberta.
- Validar o token no servidor.
