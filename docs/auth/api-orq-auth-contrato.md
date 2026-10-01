# Contrato — API de autenticação do orquestrador (`/orq-auth/v1`)

> Estado: **em construção pelo time de auth**. Este documento registra o que é **conhecido/verificado** vs
> **pendente**. Última verificação: 15/09/2026 (inspeção read-only em produção).
> Fonte estrutural: inspeção da API **400 — Orchestrator Auth API** + Confluence `Módulo: Auth` +
> confirmações do stakeholder.

## Metadados da API (produção, 15/09/2026)

| Campo | Valor |
|---|---|
| id | `400` |
| nome | Orchestrator Auth API |
| versão / basePath | `1.0.0` / `/orq-auth/v1` |
| tipo | REST |
| dono | `paulo.silva` |
| plano | `Orchestrator Auth API` (id 66) |
| ambientes | `Default` (rev 1 deployada), `DEV-APIOPS`, `HMG-APIOPS` |
| revisões | rev 1 (id 8862, deployada em Default) · rev 2 (id 8876, **DRAFT**) |

## Interceptores da revisão

Ordem no execution point **FIRST**: `Log → Client ID validation → Log → OAuth(grant_types=[CLIENT_CREDENTIALS])`.
Execution point **SECOND**: `Log`.

Nos resources `Token` e `Groups` há registro de **OAuth herdado da revisão com `status=REMOVED`** — coerente com o
desenho: os endpoints de autenticação **não podem exigir** um Bearer pré-existente (quebra o bootstrap).

## Endpoints

### `POST /oauth2/token` — login (emissão)

| Propriedade | Valor |
|---|---|
| Estado na rev 2 | Proxy para `https://api-consulting.sensedia.com/oauth/v1/access-token` (operacional na rev 1 deployada) |
| Autenticação | Header com `Base64(client_id:secret)` repassado **intacto** pela CLI (decodificado server-side) |
| Retorno | access token + `extra info` com perfil/grupos/permissões (read/write/admin) |
| Usado por | `sen login` (dev e esteira) |

### `POST /oauth2/token/validation` — autorização por ação

| Propriedade | Valor |
|---|---|
| Estado na rev 2 | **Mock / destino vazio / `apiBroken=true`** — stub; implementação é pré-requisito externo |
| Entrada (esperada) | `Authorization: Bearer {token_dev}` + identificação da ação (payload fino pendente) |
| Retorno (esperado) | **Super admin token efêmero** (uso único) ou erro categorizado de negação |
| Usado por | cada ação autorizada do dev — ver [ADR 0003](../adr/0003-autorizacao-por-acao-endpoint-validation.md) |

### `GET /users/{username}/groups` — identidade e grupos

| Propriedade | Valor |
|---|---|
| Estado na rev 2 | Proxy para `…/user-management/v1/users/{username}/groups` (operacional) |
| Usado por | validação de identidade/grupo durante o fluxo de auth |

## Operação na plataforma (referência) — esquemas OAuth2 existentes

Verificados empiricamente na exploração de 15/09/2026 (detalhes: [exploracao-empirica-2026-09.md](exploracao-empirica-2026-09.md)):

| Esquema | Endpoint | Payload | Observações |
|---|---|---|---|
| User Credentials (LEGACY) | `POST /user-management/v1/oauth2/token` | JSON `{grantType, scope}` | usado hoje pelo `SensediaAuthenticationAdapter` |
| Client App (M2M) | `POST /access-control/api/v1/oauth2/token` | form `grant_type=client_credentials` | token ≈ 24h (`expires_in=86400`); pode servir à esteira enquanto `/orq-auth` não estiver completa |

O desenho **oficial** da esteira/API de auth orquestrador passa pela API 400 (`/orq-auth/v1`); os demais são
referências de operação vigente no ambiente.

## Pendências / parâmetros

| Pendência | Dono |
|---|---|
| Swagger/contrato formal dos endpoints (payloads de entrada/saída, códigos de erro RFC 7807) | Time de auth |
| Implementação efetiva de `POST /oauth2/token/validation` | Time de auth |
| Rotas parametrizáveis no orquestrador (`AUTH_LOGIN_PATH`, `AUTH_VALIDATE_ACTION_PATH`) em `Settings` | Orquestrador (implementação da feature) |
| Deltas de ambiente Consult ↔ ECAD (interceptor Base64 ativo nos dois) | Time de auth / plataformas |
