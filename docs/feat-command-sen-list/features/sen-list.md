# Feature — `sen list`

| Meta | Valor |
|---|---|
| Ramo | `feat/command-sen-list` (incremento sobre `feat/comand-sen-login`) |
| Data | 2026-09-15 |
| Estado | **Decisões seladas** (grill 15/09 + validação externa do Paulo em 16/09 — 5 votos incorporados, ver §2) |
| Pré-requisito | `sen login` antecede esta feature (sequenciamento decidido) |
| Fontes primárias | Sessão de grill 15/09/2026 · sondas read-only em produção (comprovadas inline) · `auth/api-orq-auth-contrato.md` · `docs/features/sen-login.md` |

> **Régua permanente:** este documento é planejamento/documentação. Nenhuma alteração de código foi realizada nesta feature até o momento; todos os pontos técnicos referem-se ao estado observado do código em `src/apiops_orchestrator/` na branch base.

---

## 1. Contexto e autoridade

1. **Login antecede `sen list`.** A CLI opera com o token/JTV entregue pelo login (`/orq-auth/v1`), não com par OAuth cru.
2. **A CLI confia no filtro server-side de visibilidade.** `sen list api` renderiza o que a plataforma retornar para o chamante — **não** recalcula matemática de times/grupos no cliente. Justificativa empírica: ver §4 (objeto `visibility` é a fonte da verdade do vínculo team↔API).
3. **Teams do usuário passam a viajar no JWT** (`extra_info.teams`, além de `permissions`) — decisão adicional à feature de login, capturada em [`sen-login-incremento-teams-jwt.md`](../sen-login-incremento-teams-jwt.md). Uso futuro: parâmetro de filtragem client-side (evolução posterior; não é escopo desta fatia).
4. **MD-1 — Normalização de username:** a CLI converte `email@dominio` → `username bare` antes de qualquer chamada a grupos/validação. Evidência: `isaac.machado@sensedia.com → 404`; `isaac.machado → 200`.

## 2. Decisões seladas (grill 15/09 + validação Paulo 16/09)

| # | Decisão | Detalhe |
|---|---|---|
| **A1** | `sen list api` — substantivo no **singular** | Escola gh (verbo + recurso singular); consistente com futuras `sen list revision …` |
| **A2** | Lookup por flag: `sen list api --id <api_id>` | Mantém padrão vivo (cli_adapter atual) e docs/TDD existentes. **Princípio arquitetural herdado: comandos mutantes (publish/deploy) EXIGEM `--id` explícito — nunca inferência** |
| **A3-1** | Saída de máquina: conjunto completo por padrão | Flags `--limit`/`--offset` **sempre explícitas**. Micro-regras: **1a** ordenação client-side por `id` asc (determinismo/diff); **1b** `--limit ≤ 0` → erro amigável, `exit 1`; **1c** `--offset` além do total → lista vazia, `exit 0` |
| **A3-2** | Janelamento: `--limit`/`--offset` **sempre explícitos em TODAS as saídas** (humana e máquina) *(revogado o default silencioso — voto Paulo 16/09)* | Caso **desnudo** (`sen list api` sem flags): aplica **default anunciado** — executa com `--limit 10 --offset 0` e exibe rodapé `usando padrões: --limit 10 --offset 0 · detalhes: sen list api --help` |
| **A3-3** | `--query "autenticacao"` — filtro client-side *(flag renomeada de `--term` — voto Paulo 16/09)* | Campos `name` + `description`; **case-insensitive + accent-folded** (`autenticação` casa `Autenticacao`); **mutuamente exclusiva com `--id`** (erro imediato); janela aplica-se **após** o filtro |
| **A3-4** | Fora desta fatia → backlog | Busca server-side, `--domain`, `--tag` (ver `backlog/sen-list-despriorizacoes.md`) |
| **B2** | `-o json` **despriorizado** | Canal de máquina vai a backlog **herdando** o contrato já negociado (full-set default, janelas explícitas, campos mínimos `id, name, internal_name, version, state, owners[]`). A esteira não perde nada: recebe `API_ID` explícito (regra A2) |
| **C2** | Grades canônicas (§3) | Colunas 100% respaldadas por payload real (mapa em §4) |
| **C3** | **YAML dormente** | Wire `-o` existe (`output_display.py`) e permanece; **sem promessa pública** nesta fatia. Toda a linha "máquina" herda o backlog de B2 |
| **D1-a** | Metadados nunca exigem `.env` | `sen`, `sen --help`, `sen list --help` respondem instantâneo com/sem configuração (composition root lazy — ver ADR 0006) |
| **D1-b** | Comando de rede sem chaves ⇒ **degradação educativa** | Erro curto + como resolver + ponteiro para o sub-help, `exit 1` (padrão git/npm). Help completo apenas no `sen` desnudo (`no_args_is_help`) |

### ⏳ Pendências de placa (não bloqueiam; cada uma vira linha ao ser selada)

| Selo | Valor recomendado aguardando |
|---|---|
| **D2** | Esteira PoC passa a falhar rápido (`sen create revision` inexistente) — ganho: não gasta auth/conversão |
| **D3** | Fluxo legacy (validação de estrutura + normalização + `ApiFull`) → `scripts/generate_api_json.py`, fora do pacote |
| **E1** | Tabela mínima de erros RFC7807→humano: `401` credenciais · `403` sem permissão · `404` API não encontrada · `--query` vazio → dica útil · rede caída; todos `exit 1`, sem stacktrace |
| **E2** | Aceite inclui smoke real (somente GETs, HOST default do projeto) |
| **E3** | Unit tests com mocks na **port** + smoke manual documentado; sem integração real em CI |

## 3. Grades aprovadas (dados reais)

**1) Listagem** — `sen list api --limit 10 --offset 0` *(sem flags ⇒ default anunciado, selo Paulo-5)*

```
  ID   │ NAME                    │ VERSION │ BASE PATH    │ LAST REV │ LIFE CYCLE
  400  │ Orchestrator Auth API   │ 1.0.0   │ /orq-auth/v1 │    3     │ DRAFT
  ...
  usando padrões: --limit 10 --offset 0  ·  detalhes: sen list api --help
```

**2) Busca** — `sen list api --query autenticacao`

**3) Drill-down** — `sen list api --id 400 --revisions` (atalho `-r`)

```
  REV ID │ REV # │ STAGE      │ CREATED     │ LAST DEPLOY │ ENVS        │ COMPLETE
   8882  │   3   │ Stage One  │ 2026-09-15  │ 2026-09-15  │ HMG-APIOPS  │ 85%
```

**4) Combinações**

```
sen list api --id 400                    # cabeçalho 1-linha da API
sen list api --query auth --id 400       # ERRO: mutuamente exclusivas
sen list api --offset 90 --limit 5       # janela explícita
sen list api                             # desnudo ⇒ default anunciado (rodapé)
```

## 4. Mapa de fontes vivas (sondas read-only, 15/09/2026)

| Dado exibido | Endpoint | Observação |
|---|---|---|
| Lista/API | `GET /api-manager/api/v3/apis[`/`{id}`]` | 107 itens; `?filter=BASIC_INFO` remove interceptors/resources (peso ↓) |
| Revisões | `GET /api-manager/api/v3/apis/{id}/revisions` | traz `id, revisionNumber, creationDate, lifeCycle, workflowId, workflowStageId` |
| Completeness | `GET /api-manager/api/v3/revisions/{rid}/completeness` | `completenessScore: 85.0` + `suggestions[]` (suggestions → backlog/audit) |
| Stage NAME | `GET /api-governance/api/v3/workflows/{workflowId}/stages` | catálogo **cacheável por sessão** (420→Stage One; 753→Teste) |
| Workflows por team | `GET /api-governance/api/v3/workflows` | categoria `TEAM` vinculada a `groupId` (Lab-tech, PulseTeam…) — corrobora teams-no-JWT |
| Times do usuário | `GET /user-management/v1/users/{username}/groups` | username **bare**; fallback do JWT |
| Catálogo de times | `GET /user-management/v1/groups` → 200 (7 itens) | primitiva viva |
| **Vínculo team↔API** | objeto `visibility` dentro da API | **fonte da verdade**: `{visibilityType: GROUP, groupVisibility.name, owner, users[]}` |
| Paginação | inexistente no servidor | `?offset/limit/_limit` ignorados (107/107/107) — client-side é obrigação |

**Economia de chamadas:** listagem = 1 chamada (sem sub-queries); drill-down = 1 detail + 1 stages (cache) + K×completeness (K = revisões exibidas).

**Cenário de referência validado empiricamente (isaac):** API 400 tem `visibility {GROUP: APIOps, owner: paulo.silva, users:[isaac.machado]}` e `isaac.machado ∈ APIOps` — acesso confirmado por **dois caminhos independentes** (grupo ∨ allowlist; owner é terceira via à margem).

## 5. Critérios de aceite

1. Grades/renderizam com payload real (executoras à época da implementação — código congelado por regra de processo);
2. Smoke read-only: `sen list api` e drill-down 400, somente GETs (E2, pendente de placa);
3. Exclusividade `--query`×`--id` respeitada; `--limit`/`--offset` explícitos em toda saída, com default anunciado no caso desnudo (selos Paulo 1 e 5);
4. `sen --help` funcional sem `.env` (D1-a) e degradação educativa sem chaves (D1-b);
5. Validação de padrões pelo Paulo **SELADA** (5 votos em 16/09: limit-offset explícitos · `--query` · `REV #` · gramática atual · default anunciado);
6. No dia da integração do login: (i) token real do isaac ⊇ API 400 na lista; (ii) API fora dos times dele **não** aparece (exclusão server-side comprovada); (iii) claims `teams` batem com o desenho.

## 6. Ligação com o restante da documentação

- Contrato da API de autenticação: [`../auth/api-orq-auth-contrato.md`](../../auth/api-orq-auth-contrato.md)
- Spec original do login (não editada neste incremento): [`../../features/sen-login.md`](../../features/sen-login.md)
- Incremento do login (teams no JWT): [`../sen-login-incremento-teams-jwt.md`](../sen-login-incremento-teams-jwt.md)
- Despriorizações desta fatia: [`../backlog/sen-list-despriorizacoes.md`](../backlog/sen-list-despriorizacoes.md)
- Composition root lazy (por que `sen --help` voa sem `.env`): [`../adr/0006-composition-root-lazy-cli.md`](../adr/0006-composition-root-lazy-cli.md)
