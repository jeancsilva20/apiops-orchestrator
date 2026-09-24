# ADR 0008 — `sen completeness`: port dedicada + AG direto como fonte primária

## Metadados

| Campo | Valor |
|---|---|
| Status | Aceito (documentado; **implementação congelada** pela regra de processo do projeto) |
| Data | 2026-09-24 |
| Autor do documento | Jean Silva |
| Supersedes | — |
| Correlatos | [ADR 0007](../adr/0007-sen-como-casa-do-bloco-de-credenciais-e-residencia-dos-arquivos-sen.md) (bloco de credenciais), [ADR 0005](../adr/0005-padrao-de-logs-de-autenticacao.md) (`-v` nunca muda formato), fatia [`feat-command-sen-list`](../../feat-command-sen-list/features/sen-list.md), memory bank APIOps (P3/P10, P9) |

## Contexto

O grill de 24/09/2026 definiu o comando `sen completeness` (espelho read-only da maturidade calculada pela plataforma, por API + revisão). Foi seguido de bateria de 4 sondas read-only em produção, que revelaram:

1. **Autenticação em duas moedas:** o token opaco do fluxo `orq-auth` (moeda atual da CLI) recebe `401` do gateway para **todas** as rotas sob `platform-production` — Manager, api-finder e AG. Um **Bearer JWT RS256 do mundo-plataforma** abre as três superfícies simultaneamente (Manager `revisions/{rid}/completeness` incluído), sem cookie e sem XSRF em leituras.
2. **Dois produtos, uma engine:** o Manager (`revisions/{rid}/completeness`) devolve `{completenessScore, suggestions[]}` em texto corrido; o AG (`maturity-reports`) devolve a mesma mensageria **estruturada** por regra (SSD-001..017, com `code` estável, `path`, `severity`, `range{line,character}`), além de `deployedEnvironments`, `contracts` e trilha de auditoria (`createdBy/updatedAt`).
3. **Tradução de identificadores declarativa:** os payloads do AG carregam `catalog.catalogOriginId` (id da API no Manager) e `revision.originId` (id da revisão no Manager) — a ponte Manager↔AG existe em payload, sem dedução.
4. **Lacunas do AG:** nomes de ambientes e contexto/posse (team/organização) não existem no AG — vivem no frame do api-finder, já consumido pela CLI.
5. **O gate de completude não está exposto** em nenhum payload sondado; o valor 70% vem da decisão normativa P10 do memory bank (threshold fixo configurado no AG).

Fonte do grill: sessão 24/09/2026 (bateria de sondas consolidada no doc da feature, §4).

## Decisão

1. **Port dedicada `CompletenessPort`** (`domain/ports/completeness_port.py`) — a fonte de maturidade ganha plano próprio; a `ManagerApiPort` permanece intocada (retrocompatibilidade do `sen list`).
2. **Adapter novo** `adapters/outbound/http/adaptive_governance/` implementando a port, falando **diretamente com o AG** (`/adaptive-governance/api/v1/search` + `/maturity-reports`), com `fullReport=true` por padrão e Bearer JWT da sessão.
3. **Satélite api-finder único** para enriquecimento (nomes de ambientes + contexto/posse) reutilizando `ManagerApiPort.list_api_detail` — com **degradação suave** (`exit 0`, IDs crus + `Contexto: -`).
4. **`CompletenessService` desenhado como gêmeo do `sen validate`** (fase 2): o bloco de aquisição/normalização é compartilhado; o espelho (este comando) e o diagnóstico (validate futuro) dividem o mesmo código de fontes.
5. **Contrato de máquina versionado** `apiops.sen-completeness/v1` (JSON/YAML da mesma árvore) — nunca dump cru; impacto por violação = `lostScore ÷ violationCount`.
6. **Gate hardcoded 70%** (`source: "hardcoded.p10.v1"` — herança P10 do memory bank), com pendência registrada de tornar dinâmico via `workflows/{id}/stages`.

## Alternativas consideradas e rejeitadas

| Alternativa | Motivo da rejeição |
|---|---|
| Consumir apenas o Manager (`revisions/{rid}/completeness`) | Dado reduzido a strings (sem `code`, `severity`, `range`, deploy, auditoria) — perde tudo que o painel "Top violations" da plataforma expõe |
| Engordar a `ManagerApiPort` com os endpoints do AG | Mistura planos de dados de produtos distintos; agranda contrato já maduro do `sen list` |
| Sub-comando (`sen list completeness`) ou flag (`--completeness`) | O dado pertence à família de "valores de plataforma" (top-level), não ao catálogo; grill 24/09 selou comando próprio |
| `--revision` opcional com default "última" | Dado visto ≠ dado real em APIs com dezenas de revisions; integridade semântica venceu (revogado no grill) |
| Restringir a APIs com deploy | A obrigatoriedade de `--revision` elimina a necessidade do filtro; recusas (ex.: Draft) viram degradação declarada (422-wrap → exit 2) |
| Gate dinâmico já na V1 (ler `workflows/{id}/stages`) | +1 chamada e dependência de `workflowId` em cascata; valor não existe nos payloads sondados — hardcode 70 (P10) cobre a V1, dinâmico fica pendência P-a |
| Exibir `ruleId` (SSD-xxx) e `contracts` na tela | Irrelevância para o usuário final; informação segue viva no JSON (canal de auditoria) |

## Consequências

| Positivas | Negativas/neutras |
|---|---|
| Fonte única e mais rica que o Manager para maturidade (17 regras + violações posicionadas + deploy + auditoria) | **Runtime depende de JWT platform-native** (P-b) — o fluxo de login atual não entrega essa moeda; pré-requisito externo à fatia |
| Código de aquisição compartilhado com `sen validate` (fase 2) — sem duplicação | Adapter novo + port nova (superfície de manutenção a mais) — mitigado por reuso integral do `HttpClient` |
| Satélite degrade-software: comando nunca "morre" por causa do enriquecimento | Gate hardcoded pode divergir de requisitos por stage de equipes específicas (exceções internas do AG) — P-a registra a correção |
| Contrato v1 estável para a esteira sem acoplar ao wire do AG | `revisionIds` exige resolver o `revUuid` AG por casamento de `originId` (1 varredura de reports a mais quando a revisão não é a `last`) |
| Ponte originId eliminou o risco de guess entre mundos de IDs |  |

## Fontes citadas

- Sondas read-only de 24/09/2026 (bateria de 4 testes: search, maturity-reports, fullReport, manager-completeness) — registradas no §4 de [`features/sen-completeness.md`](../features/sen-completeness.md);
- Memory bank APIOps — `arquitetura-apiops-memory-bank/knowledge/adaptive-governance-completeness.md` (P3/P10: threshold fixo 70% configurado no AG), `knowledge/comandos-cli-sen.md`;
- Mapeamento APIM — `docs-sensedia/05-maturity-score.md` (SSD-001..017, prova funcional 50→87,5→99,5%), `docs-sensedia/12-adaptive-governance.md` (endpoints do AG, faixas de classificação);
- Código da branch base — `src/apiops_orchestrator/adapters/outbound/http/manager_api/manager_api_adapter.py` (`get_revision_completeness`, `get_workflow_stages`), `domain/ports/manager_api_port.py`;
- Grill de 24/09/2026 — decisões A1–A7, B1–B2, C1–C6, D1–D5, E1–E4, F1–F7, G1–G2 (doc da feature, §2).
