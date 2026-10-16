# ADR 0005 — Padrão de logs de autenticação herdado da observabilidade

| | |
|---|---|
| **Status** | Aceito |
| **Data** | 2026-09-15 |
| **Supersede** | Logs pontuais ad-hoc (`rich.print`/`logger` soltos) para eventos de autenticação |
| **Correlatos** | [ADR 0001](0001-autenticacao-cli-base64-passthrough.md), [ADR 0002](0002-ciclo-de-vida-de-tokens-dev-x-superadmin.md) |

## Contexto

Requisito do stakeholders: **"logs de autenticação devem ser um padrão"** — uniforme, correlacionável e sem
exposição de segredos.

Diagnóstico do código na branch `develop` (15/09/2026):

- Já existe infraestrutura madura em `src/apiops_orchestrator/infrastructure/observability/`:
  - `JsonFormatter` → NDJSON com `timestamp`, `trace_id`, `level`, `service`, `message`, `duration` (ms),
    `status` (`IN PROGRESS | SUCCESS | FAILURE`) e `context{api_id, customer, span_id}`;
  - `ContextFilter` (thread-local), `log_duration()`, enums `Level` e `Status`;
  - `SimpleFormatter` com cores para console;
  - `LOG_LEVEL`/`LOG_FORMAT` (`SIMPLE|FILE|BOTH`) controláveis por ambiente;
- `HttpClient` já integra o padrão (`set_span_id`, `set_status`, `log_duration`) e **não imprime headers/auth**;
- porém **`setup_logging()` nunca é chamado** (função órfã) e `set_default_data()` (trace_id) idem —
  a fundação existe, a ligação não.

## Decisão

1. **Herdar** o padrão existente — nenhum esquema novo de log para autenticação;
2. **wire obrigatório:** `setup_logging()` chamado uma única vez no entrypoint da aplicação/CLI;
3. eventos de autenticação com semântica padronizada (nomes estáveis, no campo `message`):

| Evento | Nível típico | Observação |
|---|---|---|
| `auth.login.success` | INFO | perfil e escopos resumidos; nunca o token |
| `auth.login.failure` | WARNING/ERROR | motivo categorizado; nunca o Base64 |
| `auth.denied_local` | WARNING | guard local bloqueou ação sem chamada de rede |
| `auth.grant_issued` | INFO | super admin token emitido **sem valor** |
| `auth.grant_discarded` | INFO | grant descartado após uso único |
| `auth.session.expired` | WARNING | orienta re-login |

4. **proibição absoluta** de registrar token, Base64 ou segredo — em qualquer nível, incluindo `--verbose`
   (que controla somente verbosidade, não formato — conforme documentação canônica);
5. proibições verificadas por **teste automatizado** (assertivas sobre outputs de log).

## Alternativas consideradas e rejeitadas

| Alternativa | Motivo da rejeição |
|---|---|
| Criar esquema de log novo/paralelo para auth | Fragmenta observabilidade; duplica `JsonFormatter`/contexto |
| Depender apenas dos logs genéricos de `HttpClient` ("Requesting POST url") | Não carrega semântica de autenticação (perfil, scopes, negações) |
| Logar tokens mascarados em DEBUG | Mesmo mascarado, aumenta superfície de risco; TDD exige zero rastro |

## Consequências

**Positivas**
- Observabilidade consistente com o resto do orquestrador e pronta para ingestão (Elastic / relatórios —
  Épico 07 do backlog);
- eventos audíveis da jornada de auth sem custo adicional de infraestrutura.

**Negativas / pontos de atenção**
- Wire no entrypoint torna-se obrigatório — testses de regressão devem cobrir isso;
- **correlationId ponta a ponta (`APIOPS_CORRELATION_ID`, run id) fica fora do escopo desta feature**
  (backlog — Story 07.01.02), mantendo o padrão atual de `trace_id` local até lá.

## Fontes

- `src/apiops_orchestrator/infrastructure/observability/logging.py`, `logging_level_enum.py`,
  `logging_status_enum.py` (branch `develop` — leitura 15/09/2026).
- `src/apiops_orchestrator/infrastructure/utils/http_client.py` (integração atual com observabilidade).
- Documentação canônica — `Docs revisados/knowledge/comandos-cli-sen.md` (`--verbose` só verbosidade;
  saída JSON para automação via `--output json`), backlog 07.01.02.
- Requisito "logs de autenticação devem ser um padrão" — stakeholders (chat, 15/09/2026).
