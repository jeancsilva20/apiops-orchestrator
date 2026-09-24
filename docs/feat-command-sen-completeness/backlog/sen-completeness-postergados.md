# Backlog — postergados do `sen completeness`

> Itens deliberadamente FORA da fatia atual, com seus contratos congelados por escrito para que a retomada seja cópia, não reconstrução.

## 1. Gate dinâmico da barra (pendência P-a)

**Estado hoje:** barra usa `hardcoded.p10.v1` — 70%, herança normativa do memory bank (P3/P10: threshold fixo configurado no AG). As sondas de 24/09 provaram que **nenhum payload** (search, maturity-reports) expõe o requisito — legitimando o hardcode na V1.

**Contrato congelado à espera:**
- Fonte do valor real: `GET /api-governance/api/v3/workflows/{workflowId}/stages` → `stages[].completenessRequisite` do stage da revisão consultada;
- Encadeamento: frame do api-finder (satélite) → `workflowId/workflowStageId` → stages (cache por workflow — a infra `get_workflow_stages` já existe em `ManagerApiPort`);
- Saída: `gate.percent` e o marcador físico da barra passam a exibir o requisito real do stage; degradação se stages indisponível → exibir `(gate: indisponível)`, **nunca** exibir 70 inventado;
- `E3/ADR 0008` registra a evolução; nada muda na UI além da fonte do número.

## 2. JWT platform-native no `sen login` (pendência P-b)

**Estado hoje:** as sondas de 24/09 provaram que o token opaco do fluxo `orq-auth` recebe `401` no gateway para Manager, api-finder **e** AG — um Bearer JWT RS256 do mundo-plataforma abre todas as superfícies.

**Contrato congelado à espera:**
- `sen login` precisa emitir/propagar o JWT do mundo-plataforma (origem, TTL e mecanismo de renovação a definir com a Plataforma);
- Shape preferencial: `LoginSession` continua válido (`accessToken/tokenType/expiresIn/…`) — o contrato de modelos não muda, muda a **moeda** do token;
- Afeta todos os comandos (não apenas esta fatia); tratado em coordenação com `docs/auth/divergencias-abertas.md`.

## 3. Harmonização de severidade agregada (pendência P-c)

**Estado hoje:** a `issues[]` da search rotulou API de teste como `MEDIUM` enquanto o fullReport exibia violações `HIGH` para o mesmo catálogo.

**Contrato congelado:** fonte-display única = **fullReport**; search fica como teaser/contagem. Se a divergência persistir, reportar à Plataforma com os dois payloads (fixtures da fatia).

## 4. Enriquecimentos futuros da tela

- **Legendas de ambiente por origem** (nome + gateway/org) quando a Plataforma expuser mapeamento de `originId`→nome sem custo de satélite;
- **Ordenações alternativas** (`--sort impact|rule`) — hoje: Sev ↓, Impact ↓ (decisão F7);
- **Export de arquivo** (`--out json`) acompanhando o canal de máquina — herda o debate homônimo do `sen list`;
- Exibição de `riskRating` quando o AG começar a populá-lo (hoje `null` ao vivo).

## 5. Hook do `sen validate` (fase 2 — pendência P-e)

**Contrato congelado:** `sen validate` reutiliza `CompletenessService` como bloco de aquisição; acrescenta o lado **local/estático** (swagger dos artefatos, contexto Draft, perfil developer) e a dimensão de bloqueio, que **continua sendo da esteira**. É o território onde a pendência P9 do memory bank volta ao jogo (completeness de revision não-deployada). Nenhuma decisão de validate está nesta fatia.
