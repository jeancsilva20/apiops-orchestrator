# ADR 0001 — Autenticação da CLI via pass-through de Base64

| | |
|---|---|
| **Status** | Aceito |
| **Data** | 2026-09-15 |
| **Supersede** | Nenhum registro anterior em ADR |
| **Correlatos** | [ADR 0004](0004-variavel-de-ambiente-sen-credentials.md), [spec `sen login`](../features/sen-login.md) |

## Contexto

A CLI (`sen`) precisa autenticar usuários e pipelines no Sensedia API Manager. A reunião `[ECAD] - API OPS`
(15/09/2026) fechou as diretrizes de arquitetura de autenticação:

- Adoção de **client apps** (fluxo já validado por Paulo de Oliveira) como base da autenticação;
- entrada do developer por **um único blob Base64** no `.env` da máquina local;
- autenticação por usuário/senha na V1 é dispensada; a preocupação explícita era **evitar complexidade de SSO
  no primeiro release**;
- no ambiente ECAD **já existe um interceptor que recebe Base64 e decodifica** no lado do Gateway/API — não há
  necessidade (nem desejo) de o CLI quebrar o dado localmente.

Trecho da transcrição (00:39–00:41) que fundamenta a decisão:

> **Jean:** "Se pegar o cliente […] de mandar ali naquele base64, igual a gente faz ali com dois pontos no meio…
> o orquestrador receber assim, quebrar e mandar?"
> **Paulo:** "Não. […] a gente no ECAD tem um interceptor que faz isso já, ele já recebe nesse padrão de base64."
> **Jean:** "Eu posso colocar então aqui que a entrada vai ser um base64, não vai ser um client_id."

## Decisão

A CLI **não interpreta, não quebra e não reconstrói** as credenciais. O `sen login`:

1. lê o valor de `SEN_CREDENTIALS` — `Base64(client_id:secret)` — do ambiente local (`.env`) ou da esteira (GitHub
   Secrets);
2. **repassa o valor intacto** para a API de autenticação do orquestrador (`POST /orq-auth/v1/oauth2/token`);
3. a **decodificação é responsabilidade server-side** (interceptor/API de auth), que extrai `client_id`/`secret` e
   executa as validações de identidade, App e grupo.

O transporte de credenciais passa a ser tratado como um único dado opaco pelo orquestrador.

## Alternativas consideradas e rejeitadas

| Alternativa | Motivo da rejeição |
|---|---|
| CLI decodifica o Base64 e monta `HTTP Basic` nativo (formato `client_id:secret` separado) | Diverge do formato acordado (blob único); duplica lógica de credencial no cliente; ingresso pelo interceptor ECAD espera Base64 |
| Fluxo OAuth interativo via navegador (OIDC/SSO) | Complexidade alta para a V1; reunião optou por login sem navegador inicialmente |
| Manter `OAUTH_CLIENT_ID` + `OAUTH_CLIENT_SECRET` como padrão da esteira | Esteira em PoC usa o par separado, porém decidido que **migrará para Base64** (aparidade com o dev). O par permanece apenas como legado/transição |

## Consequências

**Positivas**
- Contrato de entrada único e simples ("uma informação só");
- o cliente não vira peça de confiança na manipulação de credenciais;
- estreita a experiência dev ↔ esteira (mesmo formato de entrada).

**Negativas / pontos de atenção**
- O formato `Base64(client_id:secret)` não cifra — deve trafegar **somente em TLS** e nunca ser logado
  (garantias em [ADR 0005](0005-padrao-de-logs-de-autenticacao.md));
- exige que todos os ambientes (Consult, ECAD) tenham o interceptor/decodificador ativado — pré-requisito externo
  registrado em [divergencias-abertas.md](../auth/divergencias-abertas.md);
- migação da esteira (GitHub Secrets) para Base64 é trabalho à parte (backlog).

## Fontes

- Agenda `[ECAD] - API OPS` — 15/09/2026 (decisões: *Codificação Base64 para credenciais de cliente*;
  *Autenticação por usuário e senha na CLI*; transcrição 00:18:43, 00:39:31, 00:42:18).
- Documento Confluence `Módulo: Auth` (Nexus) — camadas e responsabilidades do Authenticator Module.
- Pipelines de teste da esteira (PoC) — variáveis `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET` via `secrets` (formato atual
  a migrar).
- `.env.example` e `src/apiops_orchestrator/config/settings.py` (branch `develop`) — variáveis existentes.
