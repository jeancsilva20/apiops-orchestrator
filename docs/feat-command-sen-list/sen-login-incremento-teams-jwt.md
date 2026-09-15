# Incremento do `sen login` — Teams no JWT (`extra_info.teams`)

| Meta | Valor |
|---|---|
| Status | **Decisão tomada** (grill de 15/09/2026, durante o desenho do `sen list`) |
| Natureza | Requisito ADICIONAL ao time responsável pela `/orq-auth` — **não** depende da CLI |
| Spec original | [`../../features/sen-login.md`](../../features/sen-login.md) — **não editada** (este arquivo é o delta isolado no ramo do incremento) |

## A decisão

O JWT emitido pelo login passará a carregar **`teams` do usuário** no `extra_info`, além de `permissions`:

```json
{ "extra_info": { "permissions": ["read", "write", "admin"], "teams": ["APIOps", "Lab-tech"] } }
```

Uso previsto: **parâmetro de filtragem de permissões** em evoluções posteriores (ex.: guard de comandos mutantes; potencial filtro client-side no `sen list`).

## Por que não basta o endpoint (motivação da escolha)

| Aspecto | Token com `teams` (decidido) | Somente endpoint `GET /users/{u}/groups` |
|---|---|---|
| Guard de mutantes | Direto (claim no token) | +1 chamada antes de avaliar |
| Estado | Snapshot no login (mid-session stale possível) | Sempre fresco |
| Autor | Time de auth (**desenvolvimento novo deles**) | Endpoint já vivo e validado ✓ |
| Arredondamentos | 0 | +1 por sessão (cache mitigável) |

**Fallback que a CLI continuará possuindo:** leitura de `/users/{u}/groups` — fonte viva e validada em produção (ver §Evidências). Claim em primeiro lugar, endpoint como plano B.

## Evidências que motivaram (todas read-only, 15/09/2026)

1. `GET /users/isaac.machado/groups` → **`APIOps | Lab-tech`** (mechanism funcional);
2. `GET /user-management/v1/oauth2/token/status` → `{"active": true}` — **nenhuma** claim exposta hoje em nenhum token LEGACY/M2M: **nenhuma fonte viva injeta teams no token** — por isso é desenvolvimento do time de auth;
3. `GET /api-governance/api/v3/workflows` → workflows de categoria `TEAM` vinculados a `groupId` (Lab-tech, PulseTeam, team-visualizador) — times dirigem governança, reforçando o transporte em token;
4. Cenário do `visibility` da API 400 (GROUP=APIOps + users=[isaac] + owner=paulo.silva) — ver §4 da [`sen-list.md`](./features/sen-list.md).

## Responsabilidades

- **Time auth (Isaac/Paulo):** incluir `teams` no `extra_info` do JWT do `/orq-auth/v1/oauth2/token` e refletir no contrato/swagger (documento `auth/api-orq-auth-contrato.md` ganha linha correspondente quando o swagger existir);
- **CLI:** leitor de claims + fallback endpoint; normalização MD-1 (bare username) já selada na feature do login.

> Nenhuma credencial, token ou identificador pessoal sensível é registrado neste documento.
