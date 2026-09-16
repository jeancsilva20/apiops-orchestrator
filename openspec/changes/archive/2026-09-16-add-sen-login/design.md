## Context

O `main.py` é hoje um *composition root com side-effects no import*: instancia `Settings`, valida estrutura do repo, autentica contra a API LEGACY e imprime o JSON da API montada — tudo antes de despachar o Typer (`sen list api`). A autenticação atual (`SensediaAuthenticationAdapter`, porta `AuthenticationPort`) usa `HTTPBasicAuth` contra `{HOST}/user-management/v1/oauth2/token` e mantém o token só em memória. Esta fase entrega **apenas o `sen login`**: ler a credencial Basic de `SEN_CREDENTIALS` (única fonte, já normalizada pelo dev), chamar o endpoint configurável da Orchestrator Auth API e persistir a sessão em arquivo local que execuções posteriores da aplicação consigam ler. O fluxo LEGACY e os demais padrões (infraestrutura HTTP compartilhada, observabilidade, Rich) permanecem intocados e devem ser reutilizados. Restrições: Py3.12, sem novas dependências.

## Goals / Non-Goals

**Goals:**

- `sen login` executável standalone, sem disparar o preprocessamento do `main.py`.
- Adapter outbound dedicado à Orchestrator Auth API, URL 100% parametrizável (`AUTH_HOST`/`AUTH_LOGIN_PATH`), reusando `HttpClient`.
- Sessão tipada (`LoginSession`) persistida em arquivo oculto com escrita atômica + leitor para execuções futuras (com validação de expiração).
- Erros categorizados com saída Rich e exit codes determinísticos.
- Logs `auth.*` no padrão de observabilidade existente, sem segredos.

**Non-Goals:**

- Qualquer fallback de credencial: `sen login` usa **somente** `SEN_CREDENTIALS` (o par `OAUTH_*` continua usado apenas pelo fluxo LEGACY, que não é tocado).
- Grant efêmero via `/oauth2/token/validation` e guard local por scopes (fase seguinte).
- Logout, chaveiro/keyring, refresh token, multi-perfil/multi-host.
- Migração da esteira de `OAUTH_*` para `SEN_CREDENTIALS`.

## Decisions

**D1 — Gate mínimo por argv no `main.py`.** Em `main()`: (a) *bare* (`sys.argv` sem comando → esteira): repete integralmente o fluxo atual; (b) *invoked* (`sen <cmd>`): pula o preprocessamento e despacha direto ao Typer, construindo apenas o que o comando pede. Motivação: `sen login` standalone sem reordenar todo o boot do app; esteira imune. Alternativa rejeitada: extrair toda a lógica de conversão para use cases agora (item 02.01.02 — ampliaria o escopo desta fase).

**D2 — Porta nova para o novo fluxo.** `OrchestratorAuthPort` + adapter `adapters/outbound/http/orchestrator_auth_api/` (`login(credential_b64) -> dict bruto`), deixando `AuthenticationPort`/adapter legado intocados. O mapeamento para `LoginSession` fica no serviço de aplicação (anti-corrupção na borda do domínio).

**D3 — Modelo `LoginSession` no domínio.** `domain/models/login_session_model.py` (Pydantic): campos do contrato + `expires_at: datetime` (UTC) calculado a partir de `expires_in`; serialização via `model_dump_json` para o arquivo de sessão.

**D4 — Credencial única, sem construção local.** Header `Authorization: Basic {SEN_CREDENTIALS}` com o valor repassado **intacto** — nenhuma combinação/montagem de credencial na CLI. Sem `SEN_CREDENTIALS`: erro categorizado "credencial não encontrada" **antes de rede** (a esteira e o fluxo LEGACY seguem com `OAUTH_*` em seu próprio caminho, fora do alcance deste comando). Payload inicial `{"grantType": "client_credentials", "scope": "apis/all"}` (mesmo esquema vigente), ajustável quando o swagger formal chegar — isolado no adapter.

**D5 — Storage: módulo em `infrastructure/secure_storage/`.** Path `tempfile.gettempdir() / ".sen_session"`. Escrita atômica (arquivo provisório no mesmo diretório + `os.replace`); `chmod 0o600` no POSIX; no Windows o `%TEMP%` do usuário já restringe acesso + atributo oculto via `FILE_ATTRIBUTE_HIDDEN` (*best effort*). A mesma infraestrutura expõe a **leitura** (com validação de expiração por `expires_at`) para execuções futuras — não há mutação de nenhum consumidor atual nesta fase.

**D6 — Serviço de login + categorias de erro.** `application/services/login_service.py`: valida entrada (pré-rede) → chama porta → valida campos obrigatórios (protocolo) → persiste → retorna sessão sanitizada. Exit codes: `1` genérico, `2` credencial não encontrada, `3` credencial recusada (401/403), `4` protocolo (campo faltante), `5` persistência. A CLI apenas traduz categoria → texto Rich/exit.

**D7 — Observabilidade.** Eventos `auth.login.started|success|failure` e `auth.credentials.source=env` via `infrastructure/observability/logging` (integrando `set_status`/`log_duration` já usados no `HttpClient`); nunca interpolando credencial/token — só metadados (etapa, status HTTP).

## Risks / Trade-offs

- [Esteira regredir se o gate por argv fora mal computado] → unitários cobrindo `argv` vazio vs `["sen", "login"]` vs `["sen", "list", "api"]`; smoke no pipeline `release` (roda `main.py` bare) antes do merge.
- [Permissões Windows best-effort] → teste afirma apenas leitura/escrita pelo usuário corrente; cenário POSIX verifica modo 0o600.
- [Contrato da API de auth em evolução (swagger pendente)] → payload/header isolados no adapter + constantes em `Settings`; ajustes futuros ficam confinados.
- [Blob inválido ( espaços, wrapper de aspas)] → sem interpretar/normalizar (pass-through); qualquer falha de credencial vira erro categorizado do servidor, nunca ecoando o valor.

## Migration Plan

1. Land como adição pura (comportamento do modo bare e dos comandos existentes inalterado); sem feature flag.
2. `.env.example` recebe `SEN_CREDENTIALS`, `AUTH_HOST`, `AUTH_LOGIN_PATH` comentados + instrução de geração do blob.
3. Rollback: reversão do commit (não há estado externo; arquivo de sessão fica no temp do SO).
4. Smoke: pipeline `release` (modo bare) + `sen login` manual em DEV-APIOPS.

## Open Questions

- Formato definitivo do corpo de login e catálogo de erros RFC 7807 da `/orq-auth/v1` (time de auth) — assunto isolado no adapter.
- Política de `token_type`: aceitar apenas `Bearer` hoje (registrada na implementação) ou tolerância a outros valores.
- Nome final do arquivo de sessão (`.sen_session` vs convenção corporativa) — decisão cosmética adiável.
