# ADR 0004 — Variável de ambiente `SEN_CREDENTIALS`

| | |
|---|---|
| **Status** | Aceito |
| **Data** | 2026-09-15 |
| **Supersede** | Uso exclusivo do par `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET` como perfil de entrada da CLI |
| **Correlatos** | [ADR 0001](0001-autenticacao-cli-base64-passthrough.md), [spec `sen login`](../features/sen-login.md) |

## Contexto

A entrada de credenciais da CLI passa a ser um único blob `Base64(client_id:secret)` ([ADR 0001]). Nas configurações
atuais da branch `develop`:

- `Settings` define `OAUTH_CLIENT_ID` e `OAUTH_CLIENT_SECRET` (usados pelo `SensediaAuthenticationAdapter`);
- `.env.example` já traz uma var `AUTHORIZATION="Basic <base64>"` — porém **ignorada** pelo `Settings`
  (`extra="ignore"`), sem semântica formal;
- a esteira (PoC) injeta o **par** de variáveis via GitHub Secrets, aguardando migração para o padrão Base64.

Foi necessária uma variável canônica e inequívoca para o blob Base64.

## Decisão

Criar a variável **`SEN_CREDENTIALS`** contendo `Base64(client_id:secret)`:

```dotenv
# .env local do desenvolvedor
SEN_CREDENTIALS="<base64(client_id:secret)>"
```

Regras:

1. `SEN_CREDENTIALS` é a **fonte primária** para o `sen login`;
2. o par `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET` **permanece** para compatibilidade (PoC da esteira e fluxo legado
   atual), marcado como transicional — deprecação futura fora do escopo desta feature;
3. sem valor válido em `SEN_CREDENTIALS`, o `sen login` falha com erro categorizado antes de qualquer chamada de rede;
4. segredos nunca são ecoados em saídas, logs ou mensagens de erro.

## Alternativas consideradas e rejeitadas

| Alternativa | Motivo da rejeição |
|---|---|
| Reusar `AUTHORIZATION` já presente no `.env.example` | Var historicamente ignorada, sem contrato; semântica sobrecarregada (confunde com header HTTP) |
| Manter o par `OAUTH_CLIENT_ID`+`OAUTH_CLIENT_SECRET` como padrão da CLI | Diverge do formato acordado (blob único), gera divergência dev × esteira |
| Nomear `SEN_TOKEN` | Semântica errada: o valor **não é** um token, são **credenciais** encodadas |

## Consequências

**Positivas**
- Nome exclusivo da CLI, sem colisão com vars existentes ou headers;
- migração gradual: adapter atual continua funcionando; novo fluxo não quebra o PoC da esteira.

**Negativas / pontos de atenção**
- Dois conjuntos de variáveis convivem por tempo indeterminado → documentar claramente no momento da
  implementação (`Settings` + `.env.example`) e sinalizar deprecação do par;
- esteira precisará migrar `OAUTH_CLIENT_ID/SECRET` → `SEN_CREDENTIALS` (backlog separado).

## Fontes

- Decisão confirmada por Jean Carlos da Silva (16/09/2026, exploração — "Nova SEN_CREDENTIALS").
- `src/apiops_orchestrator/config/settings.py` e `.env.example` (branch `develop`).
- Pipeline PoC da esteira (YAML fornecido) — variáveis atuais `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET`.
