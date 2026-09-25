# Módulo Authenticator — documentação canônica

> **Fontes primárias:** Confluence Nexus [`Módulo: Auth`](https://sensedia.atlassian.net/wiki/spaces/Nexus/pages/5656150037/M+dulo+Auth)
> (versão 5, 27/08/2026) · reunião `[ECAD] - API OPS` 15/09/2026 (agenda + transcrição) · TDDs fornecidos pelo
> stakeholder. Última revisão deste documento: 2026-09-15.
> Documentação canônica complementar: `Docs revisados/knowledge/autenticacao-e-seguranca-da-cli.md`.

## Objetivo

O **Authenticator Module** autentica/autoriza usuários e sistemas que executam o APIOps Orchestrator, gerando um
**access token** para as chamadas subsequentes à plataforma. O token carrega, no **`extra info`**, os níveis de
permissão do portador:

- `read` — acesso de leitura
- `write` — criação/alteração de recursos
- `admin` — controle administrativo completo

## Camadas

```
APIOps Orchestrator
  └─ Module: Authenticator
        │
        ▼
Sensedia API Gateway
  └─ API: Orchestrator Auth            (API 400 — /orq-auth/v1)
        │
        ▼
Sensedia API Gateway
  ├─ API: User Management              (valida identidade, usuário, grupo)
  └─ API: OAuth                        (gera tokens)
```

| Camada | Responsabilidade |
|---|---|
| Authenticator Module | Iniciar autenticação e devolver token à CLI/esteira |
| Orchestrator Auth API (400) | Intermediar autenticação e integração com os serviços do Gateway |
| User Management API | Validar identidade, usuário, App e grupo para autorização |
| OAuth API | Gerar os tokens de acesso |

## Fluxos

### Fluxo 1 — Pipeline (CI/CD)

1. A esteira executa o orquestrador (comando `sen …`);
2. o Authenticator Module chama a Orchestrator Auth API;
3. as credenciais da pipeline são recuperadas do **Vault** ou de **variáveis de ambiente do API Gateway**
   (Vault é opcional — reunião 15/09/2026 definiu ambientar credenciais nas env vars do Gateway, não no Vault);
4. a API identifica o **App associado ao super admin** e gera um **token super admin**;
5. token volta ao Authenticator Module e à esteira.

Identificação de super admin: pelo **App usado na requisição** → consulta ao User Management → usuário vinculado
ao App → se super admin, token com permissões administrativas.

**Estrutura conceitual do token (pipeline):**
```json
{ "source": "pipeline", "profile": "super-admin", "permissions": ["admin"] }
```

### Fluxo 2 — Developer (CLI)

1. O dev executa um comando (ex.: `sen login`);
2. o Authenticator Module chama a Orchestrator Auth API;
3. validações server-side (User Management):
   - identidade e `username`;
   - App identificado pelo `client_id`;
   - **`app.name == username`** e **`app.enabled == true`** (senão rejeita);
   - grupo do usuário;
4. a API chama a OAuth e gera o token;
5. as permissões derivadas do **grupo** são inseridas no `extra info` do token.

**Estrutura conceitual do token (developer):**
```json
{ "user": "developer@email.com", "group": "apiops-developers", "permissions": ["read", "write"] }
```

### Exemplo de mapeamento grupo → permissões

| Grupo | Permissões |
|---|---|
| `apiops-readers` | `read` |
| `apiops-developers` | `read`, `write` |
| `apiops-admins` | `admin` |

Os times de negócio mantêm suas permissões próprias nas APIs de negócio, **somadas** ao grupo dedicado de API Ops
(decisão da reunião 15/09/2026).

## Entrada de credenciais (V1)

- **Desenvolvedor:** blob `Base64(client_id:secret)` no `.env` local, repassado **intacto** pela CLI
  → ver [ADR 0001](../adr/0001-autenticacao-cli-base64-passthrough.md) e [ADR 0004](../adr/0004-variavel-de-ambiente-sen-credentials.md).
- **Esteira:** GitHub Secrets injetando env vars; **migração para o mesmo padrão Base64** pendente (backlog).
- Autenticação por usuário/senha foi a alternativa adotada "temporariamente" para a V1, evitando SSO — na prática o
  envolvente operacional são as credenciais do App via Base64.

## Ciclo de vida do token

Resumo executivo (detalhes e consequências: [ADR 0002](../adr/0002-ciclo-de-vida-de-tokens-dev-x-superadmin.md)):
- **Dev:** token+scopes em arquivo temporário oculto; autorização por ação via `/validation` com super admin token
  efêmero, descartado após uso; re-login orientado na expiração.
- **Superadmin/esteira:** token apenas em memória do processo; nada persistido nem logado.

## DevEx — provisionamento do App

Ambas as opções exigem: **`app.name == username`** e **`enabled: true`**.

| Opção | Descrição | Situação |
|---|---|---|
| 1 — Administrador cria | Plataforma centraliza criação dos Apps dos devs | Alinhada à reunião 15/09 ("a equipe centralizará a criação dos aplicativos") |
| 2 — Developer cria, admin revisa | Máxima autonomia com aprovação | Marcada como "DEFINIDA" no Confluence |

⚠️ **Divergência aberta entre fontes** — ver [divergencias-abertas.md](divergencias-abertas.md) (D4).

## Vínculos registrados

- Apps de developer vinculados às APIs **1** e **400** (exemplo prático: App **43**).
- Dono técnico do fluxo: Paul O. de Oliveira (App/API 400 sob responsabilidade `paulo.silva`).
