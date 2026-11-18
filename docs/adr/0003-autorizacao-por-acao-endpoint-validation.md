# ADR 0003 — Autorização por ação via endpoint `/oauth2/token/validation`

| | |
|---|---|
| **Status** | Aceito |
| **Data** | 2026-09-15 |
| **Supersede** | Nenhum registro anterior em ADR |
| **Correlatos** | [ADR 0002](0002-ciclo-de-vida-de-tokens-dev-x-superadmin.md), [contrato da API de auth](../auth/api-orq-auth-contrato.md) |

## Contexto

No fluxo do developer, cada ação executada na CLI (`sen list`, futuro `sen publish` na esteira, etc.) precisa de
autorização server-side antes de tocar nas APIs administrativas.

Inspeção da API **400 — Orchestrator Auth API** (produção, 15/09/2026) identificou, na última revisão:

- `POST /oauth2/token` → proxy para serviço OAuth (funcional);
- `POST /oauth2/token/validation` → **sem destino, `apiBroken=true`, com interceptor Mock** — hoje é um stub;
- `GET /users/{username}/groups` → proxy para o User Management (identidade/grupos).

A hipótese de desenho — *`/validation` é o endpoint de autorização-por-ação, devolvendo um super admin token
efêmero* — foi **confirmada por Jean Carlos da Silva** durante a exploração ("sim a hipótese está correta, é essa
rota").

## Decisão

Adotar o contrato de autorização por ação abaixo:

```
POST /orq-auth/v1/oauth2/token/validation
Authorization: Bearer {token_dev}

corpo: identificação da ação (definir payload fino com o time da API)
   ↓
valida se o usuário tem permissão para a ação
   ↓
autoricado → responde com SUPER ADMIN TOKEN efêmero
negado     → erro categorizado
```

O orquestrador:

1. usa o grant **uma única vez** contra a API administrativa da ação e o descarta;
2. trata a API de auth como **autoridade máxima** — os scopes locais servem apenas como gate de UX;
3. registra a rota como **parametrizável** (`AUTH_VALIDATE_ACTION_PATH` em `Settings`), para acompanhar
   Consult ↔ ECAD e futuras mudanças.

## Alternativas consideradas e rejeitadas

| Alternativa | Motivo da rejeição |
|---|---|
| Autorizar 100% localmente (scopes coletados no login via `GET /users/{username}/groups`) | Permissões podem mudar após o login; servidor perderia a prerrogativa de autorizar cada ação |
| Chamar APIs administrativas com o token do dev diretamente | A plataforma negaria; e exporia à CLI tentativas contra superfície administrativa (ruído + dependência de mensagens de erro da plataforma) |
| Endpoint novo dedicado no Gateway | A rota `/validation` já está prevista no desenho da API 400 (stub presente na revisão 2) |

## Consequências

**Positivas**
- Servidor continua sendo autoridade de autorização a cada ação;
- desenho já reflete na API existente (menos retrabalho no Gateway);
- gate local elimina chamadas que nunca passariam (economia + clareza para o dev).

**Negativas / pré-requisitos**
- `/oauth2/token/validation` está **Mock/broken** — implementação é pré-requisito externo do time da API de auth;
- payload fino da requisição (representação da ação) **pendente de swagger**;
- recusa server-side deve **invalidar caches locais de scopes** (sessão suspeita → re-login).

## Fontes

- Inspeção read-only da API 400 em produção (15/09/2026): `GET /api-manager/api/v3/apis/400` — revisão 8876
  (DRAFT), resources/interceptors documentados em [contrato da API de auth](../auth/api-orq-auth-contrato.md).
- Confirmação verbal de Jean Carlos da Silva na exploração (15/09/2026).
- Documento Confluence `Módulo: Auth` — responsabilidades: Orchestrator Auth API intermedeia; User Management
  valida identidade/grupo; OAuth gera tokens.
