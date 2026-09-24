# Feature — `sen login` (Authenticator Module)

> Espelho executável da feature. Fundamentação completa nos [ADRs](../adr/) e em
> [auth/authenticator-module.md](../auth/authenticator-module.md). Última revisão: 2026-09-15.

## Histórias (TDD fornecidas pelo stakeholders)

### TDD 1 — Developer

```gherkin
Eu como developer
Quando for usar o API Ops, quero poder usar o comando `sen login`
Então  a ferramenta deve ler um token Base64 que está no .env da raiz do meu projeto
Então  o CLI deve me autenticar no CLI do APIOps e me autorizar a usar a ferramenta
Então  eu quero poder listar APIs que tenho acesso
E eu NÃO posso editar APIs diretamente fazendo deploys da minha máquina
E eu NÃO devo poder editar/alterar APIs de contexts para os quais não tenho permissão
E eu devo poder rodar o comando `sen validate`
```

### TDD 2 — DevOps / esteira

```gherkin
Eu como DevOps
Quero configurar a esteira do API Ops salvando um token Base64 nas Secrets do GitHub
E   esse token deve ser usado para o login
E   a esteira deve chamar `sen login` enviando esse token
Então o orquestrador deve se autenticar
E   como a esteira é um perfil superadmin, deve conseguir fazer todo o fluxo de desenvolvimento
```

## Decisões travadas

| # | Decisão | ADR |
|---|---|---|
| 1 | CLI repassa `Base64(client_id:secret)` **intacto**; decode server-side | [0001](../adr/0001-autenticacao-cli-base64-passthrough.md) |
| 2 | Dev: token+scopes em **arquivo temporário oculto**; guard local por scopes antes de rede | [0002](../adr/0002-ciclo-de-vida-de-tokens-dev-x-superadmin.md) |
| 3 | Ação autorizada → `/validation` devolve **super admin token efêmero** → usa → **descarta** | [0002](../adr/0002-ciclo-de-vida-de-tokens-dev-x-superadmin.md), [0003](../adr/0003-autorizacao-por-acao-endpoint-validation.md) |
| 4 | Esteira: token **só em memória**; nada persistido/logado | [0002](../adr/0002-ciclo-de-vida-de-tokens-dev-x-superadmin.md) |
| 5 | Entrada via var **`SEN_CREDENTIALS`** (par `OAUTH_*` mantido como legado/transição) | [0004](../adr/0004-variavel-de-ambiente-sen-credentials.md) |
| 6 | Expiração → **re-login orientado**; guard nunca envia token expirado | [0002](../adr/0002-ciclo-de-vida-de-tokens-dev-x-superadmin.md) |
| 7 | Logs de auth no padrão existente de observabilidade + eventos nomeados; zero segredos em log | [0005](../adr/0005-padrao-de-logs-de-autenticacao.md) |
| 8 | Scopes locais são UX; **servidor é autoridade** (recusa invalida cache local) | [0003](../adr/0003-autorizacao-por-acao-endpoint-validation.md) |
| 9 | `.sen` no diretório do pacote abriga o bloco de credenciais (`SEN_CREDENTIALS` + `AUTH_HOST` + `AUTH_LOGIN_PATH`, sem default/fallback); `.sen_session` co-residente; precedência processo > `.sen` > `.env` | [0007](../adr/0007-sen-como-casa-do-bloco-de-credenciais-e-residencia-dos-arquivos-sen.md) |

## Fases

| Fase | Entrega |
|---|---|
| **0 — Âncoras de contrato** | Swagger/definições dos endpoints (quando entregues); até lá, rotas parametrizáveis (`AUTH_LOGIN_PATH`, `AUTH_VALIDATE_ACTION_PATH`) |
| **1 — Settings/storage** | `SEN_CREDENTIALS`; path de storage do token (temp do OS, nome oculto, override opcional) |
| **2 — Domínio** | `LoginSession` (user, profile, scopes, expires_at) e `ActionGrant` (token single-use); mapamento ação×permissão mínimo (`list→read`, `validate→read`) |
| **3 — Adapters outbound** | `OrqAuthApiAdapter.login(credential_b64)` e `authorize(session_token, action)` (nova porta além do `AuthenticationPort`) |
| **4 — Services** | `AuthService` (login/validação/persistência) + `ActionGuardService` (gate local) + `AuthorizedExecutor` (pedir grant → executar → descartar) |
| **5 — Storage seguro** | arquivo oculto temp, ACL restritiva, escrita atômica, `purge()` |
| **6 — CLI** | comando `sen login`; piloto do guard em `sen list`; negação local sem rede |
| **7 — Observabilidade** | `setup_logging()` no entrypoint; eventos `auth.*`; testes de máscara |
| **8 — Qualidade** | unitários novos + suite atual (79) verde; script read-only de E2E p/ Consult |

## Fora de escopo (backlog explícito)

- CorrelationId/run id ponta a ponta (07.01.02) e logs decorrentes do PoC de esteira;
- Migração da esteira de `OAUTH_CLIENT_ID/SECRET` para `SEN_CREDENTIALS` Base64;
- D2 (enforcement Draft) e D4 (política de criação de Apps);
- deprecação formal do par `OAUTH_*` e do fluxo LEGACY/M2M.

## Pré-requisitos externos

Ver [auth/divergencias-abertas.md](../auth/divergencias-abertas.md) (endpoint `/validation`, apps, swagger,
interceptor Consult, migração da esteira).

## Critérios de aceite (proposta — validar com o time)

1. Com `SEN_CREDENTIALS` válida, `sen login` retorna exit **0**, exibe perfil + scopes **sem qualquer valor de
   token/segredo** e grava session segura;
2. Sem/valor inválido: erro categorizado **antes de rede** + exit ≠0;
3. Ação com scope insuficiente: mensagem de negação **sem chamada** à API de auth;
4. Ação autorizada: fluxo `/validation` → uso único do grant → descarte demonstrável (nada em log/arquivo);
5. Token expirado: guard interpoe re-login orientado;
6. Logs seguem padrão JSON da observabilidade com eventos `auth.*` (`--verbose` não muda formato);
7. Suite `pytest` existente permanece 100% verde + novos testes unitários de guard/storage/adapters/CLI.

## Implantação da fase 1 (implementada 16/09/2026 — change `add-sen-login`)

Uso:

```powershell
# credencial: APENAS o blob Base64(client_id:secret), sem prefixo "Basic"
[Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("<client_id>:<secret>"))

# variáveis obrigatórias no .env da raiz (ver .env.example):
SEN_CREDENTIALS="<blob>"
AUTH_HOST="https://api-consulting.sensedia.com"      # sem fallback para HOST
AUTH_LOGIN_PATH="/cli-2/orq-auth/v1/oauth2/token"    # sem default em código

# execução local (venv criado por scripts\setup.ps1, sem Poetry):
.\.venv\Scripts\python.exe src\apiops_orchestrator\main.py sen login
```

Comportamentos entregues:

| Aspecto | Comportamento |
|---|---|
| Credencial | única fonte `SEN_CREDENTIALS` (sem fallback legado); ausente → erro pré-rede, exit **2** |
| Endpoint | `AUTH_HOST` + `AUTH_LOGIN_PATH` obrigatórios; não configurados → erro antes de rede |
| Exit codes | `0` sucesso · `1` indisponibilidade/genérica · `2` credencial não encontrada · `3` recusada (4xx) · `4` protocolo · `5` persistência |
| Erro HTTP 4xx | **sem corpo cru/JSON** na tela (HttpClient com `report_client_errors=False`); mensagem única categorizada |
| Sessão | JSON em `<raiz do projeto>/.sen_session` (arquivo oculto, escrita atômica, permissões de dono; fora do Git via `.gitignore` — ADR 0006) com `expires_at` |
| Consumo futuro | `SessionStore().load()` → `LoginSession` \| `None` (ausente/expirada) |
| Logs | eventos `auth.login.started/success/failure` no padrão de observabilidade; nenhum segredo impresso |
| Esteira | modo bare (`python main.py`) preservado via gate por argv em `main.py` |

## Implantação 1.1 (implementada 17/09/2026 — change `migrate-sen-files-to-package-root`)

Migração de residência (ADR 0007):

```powershell
# No pacote (dev: src/apiops_orchestrator/), copie o gabarito e preencha:
Copy-Item src\apiops_orchestrator\.sen.example src\apiops_orchestrator\.sen
# .sen recebe as tres chaves do bloco: SEN_CREDENTIALS, AUTH_HOST, AUTH_LOGIN_PATH
```

| Aspecto | Comportamento novo |
|---|---|
| Fontes | precedência **processo > `.sen` (pacote) > `.env` (raiz)** — abaixo do detalhe no ADR 0007; esteira sem `.sen` não muda nada |
| `.sen` | dotenv no `PACKAGE_ROOT` com o bloco de credenciais (3 chaves, todas obrigatórias, **sem default/fallback em código**); chaves extras ignoradas; git-ignored (match exato) com gabarito `.sen.example` trackeado |
| `.sen_session` | movida para o `PACKAGE_ROOT` (co-residente do `.sen`); sessão de tempdir/raiz antiga é tratada como ausente (re-login) |
| Erro de credencial | mensagem orienta **somente** o `.sen` do diretório do aplicativo |
| Visibilidade | log `config.sources.active sen_file=%s env_file=%s process=%s` (booleans, sem valores) no início do login |
| `.env.example` | restaurado ao estado anterior ao `sen login` (o `.env` tende a deixar de existir) |
