# Exploração empírica — 2026-09-15 (read-only)

Diário de investigação conduzido na sessão de alinhamento com Jean Carlos da Silva. **Nenhuma alteração de código,
nenhuma publicação e nenhum dado sensível registrado.** Todos os acessos de rede foram `GET`/probe de autenticação
com credenciais fornecidas pela equipe (valores **não reproduzidos** neste documento).

## Cronologia

### 1. Preparação e baseline de testes
- Repositório `apiops-orchestrator` em branch `develop` (`origin = https://github.com/jeancsilva20/apiops-orchestrator`).
- Ambiente local Windows/PowerShell sem Poetry: venv (`python3` 3.13) + deps de teste.
- `.env` local (gitignored) com valores de execução — suíte: **79/79 passed**.

### 2. Driver E2E read-only (executor separado, fora do repo)
Validação da cadeia da pasta → plataforma com o exemplo `main` (API.CEP):
- Estrutura (new-struct) OK no `RepoValidator`;
- import normalizado: 7 documentos;
- 18 arquivos validados contra catálogo de schemas;
- conversão: `ApiFull` para id **290 — API CEP** (`API_CEP`);
- `GET /apis/290` → 4 revisões no Manager. Zero publicações executadas.

### 3. Mistério do 404 — credenciais "novas" × rota LEGACY
- Credenciais do **App Client (M2M)** retornavam `HTTP 404` (corpo vazio) em
  `POST /user-management/v1/oauth2/token` (rota LEGACY/JSON camelCase+scope).
- Credenciais antigas (User Credentials) retornavam `HTTP 200` na mesma rota — comportamento determinístico.

### 4. Probing de rotas candidatas (Basic + `grant_type=client_credentials`, form-urlencoded)

| Rota | Resultado |
|---|---|
| `/oauth2/token` | 200, porém HTML do portal SPA (catch-all) |
| `/access-control/oauth2/token` | 200 — HTML do portal SPA |
| `/access-control/v2/oauth2/token` | **403 vazio** para ambas credenciais (inclui LEGACY) → não era a rota correta |
| `/api/oauth2/token` | 200 — HTML do portal SPA |

### 5. Descoberta da rota M2M correta (HTML da doc oficial)
Inspeção do HTML cru da página *Client Apps* da documentação revelou a rota real:

> **`POST /access-control/api/v1/oauth2/token`** (+ status do token em `/user-management/v1/oauth2/token/status`)

Teste com as credenciais M2M: **HTTP 200** — `access_token` (~839 caracteres), `expires_in: 86400`, `token_type: Bearer`.
Validei o token no Manager: `GET /api-manager/api/v3/apis` → **HTTP 200, 107 APIs**.

### 6. Conclusão intermediária — dois esquemas OAuth2 coexistindo

| | LEGACY (User Credentials) | M2M (Client App) |
|---|---|---|
| Endpoint | `/user-management/v1/oauth2/token` | `/access-control/api/v1/oauth2/token` |
| Content-Type | `application/json` | `application/x-www-form-urlencoded` |
| Body | `{"grantType":"client_credentials","scope":"apis/all"}` | `grant_type=client_credentials` |
| Validade | curta | ~24h |

- Evidence direto para o backlog **03.01.03** (dois perfis de token); adapter atual cobre só o LEGACY.
- Hoje o desenho **canônico** da esteira aponta para a fachada da API 400 (`/orq-auth/v1`) — os endpoints diretos
  acima permanecem como referência operacional (ver [api-orq-auth-contrato.md](api-orq-auth-contrato.md)).

### 7. Deep-dive na API 400 (Orchestrator Auth API)
`GET /api-manager/api/v3/apis/400` — detalhes completos registrados em [contrato](api-orq-auth-contrato.md):
- interceptors de revisão (`Log → Client ID validation → Log → OAuth(CLIENT_CREDENTIALS)` FIRST; `Log` SECOND);
- resources: `Token` (2 operações; `/validation` **Mock/broken**), `Groups` (proxy user-management);
- rev 1 deployada no Default; rev 2 **DRAFT**.

### 8. Prova de listagem com o stack do orquestrador
Script standalone usando exatamente os componentes do projeto
(`SensediaAuthenticationAdapter → ManagerApiAdapter → ApiListingService`):
- **107 APIs listadas**; `sen list api` ainda não roda standalone (side-effects no import de `main.py` — backlog 02.01.02).

### 9. Material de desenho coletado após a exploração
- Confluence `Módulo: Auth` (Nexus) → base para [authenticator-module.md](authenticator-module.md);
- Agenda/transcrição `[ECAD] - API OPS` (15/09/2026) → decisões (Base64, user/senha V1, grupo API Ops,
  apps centralizados, ambiente Consult p/ testes, ECAD/outubro);
- TDDs (dev × devops) → base para [features/sen-login.md](../features/sen-login.md);
- ADRs 0001–0005 consolidando todas as decisões.

## Resultado líquido

1. 404 esclarecido (rota/error-domain errado, não credencial inválida);
2. 3 esquemas OAuth2 mapeados empiricamente (LEGACY ✓, M2M ✓, fachada `/orq-auth` em construção);
3. API 400 caracterizada em detalhe (é o coração do módulo de autenticação);
4. Suíte e E2E read-only verde; nenhum objeto publicado/modificado.
