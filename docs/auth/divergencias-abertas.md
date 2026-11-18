# Divergências abertas e pré-requisitos externos

> Registro vivo das tensões entre fontes (Confluence `Módulo: Auth`, agenda `[ECAD] - API OPS` 15/09/2026,
> documentação canônica `Docs revisados`, TDDs e explicações verbais) e do que precisa ser resolvido **fora do
> repositório** para o E2E pleno. Atualizado: 2026-09-15.

## Matriz de divergências

| ID | Tema | Fontes em conflito | Estado |
|---|---|---|---|
| **D1** | Custódia das credenciais da esteira | Confluence: Vault (opcional) / env vars do Gateway · canônico: GitHub Secrets env var · reunião 15/09: migrar credenciais p/ env vars do Gateway | **RESOLVIDO para a CLI** — local: `.env` (Base64); esteira: GitHub Secrets injetando env vars; mesmo comportamento; esteira migrará para Base64 (backlog) |
| **D2** | Escopo Draft do token dev | Canônico: token dev limita validação local ao Draft · Confluence/agenda: só `read/write/admin` por grupo, nada de Draft | ABERTO — onde a regra Draft mora (claim do token? política local?) |
| **D3** | Rota oficial de autenticação | Desenho: `/orq-auth/v1` (API 400) · operação atual: LEGACY `/user-management/v1` (funcional) e M2M `/access-control/api/v1` (funcional, validado na exploração) | PARCIALMENTE FECHADO — desenho oficial = API 400; LEGACY/M2M permanecem como referência; transição decidida na implementação |
| **D4** | Provisionamento do App pessoal | Confluence: "DEFINIDO: OPÇÃO 2" (dev cria, admin aprova) · reunião 15/09: "a equipe centralizará a criação dos aplicativos" | ABERTO — decidir hierarquia/fonte antes de normatizar (fora do escopo da feature) |

## Pré-requisitos externos (bloqueiam E2E, não o código)

| # | Item | Dono | Impacto no orquestrador |
|---|---|---|---|
| 1 | Implementação real de `POST /orq-auth/v1/oauth2/token/validation` (hoje Mock/`apiBroken`) | Time de auth (Isaac/Paulo) | fase de E2E do guard → grant efêmero |
| 2 | Apps provisionados: super admin + dev de exemplo (vinculados às APIs 1 e 400, cf. app 43) | Plataformas/auth | testes com perfil dev |
| 3 | Swagger/contrato formal da API de auth (payloads, erros RFC 7807) | Time de auth | contratos de adapter + testes de contrato |
| 4 | Interceptor/decodificador Base64 ativo em **Consult** (testes iniciam lá) | Plataformas | reproducidade do fluxo em ambiente de teste |
| 5 | Migração da esteira (GitHub Secrets) para `SEN_CREDENTIALS` (Base64) | DevOps | aparidade dev×esteira |

## Itens relacionados (mantidos no backlog — fora do escopo da feature `sen login`)

- **07.01.02** — Correlation ID ponta a ponta (`APIOPS_CORRELATION_ID`/run id do PoC de esteira);
- 02.01.02 — remover side-effects do import de `main.py` (bloqueia uso standalone da CLI);
- 02.02.01+ extensões de auth (suporte M2M além do LEGACY);
- P1/P2/P6/P9 do `open-decisions.md` — itens estruturais não afetam o desenho do login direto.

## Encaminhamento

Cada divergência deve ser fechada (fonte oficial + data + evidência) e movida para histórico — em conformidade com
a regra do projeto: decisão por agente → validação por segundo agente → consolidação normativa.
