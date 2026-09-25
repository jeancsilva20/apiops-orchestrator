# Proposal — add-sen-completeness

*(pt-BR. Estrutura e palavras-chave SHALL/MUST mantidas em inglês conforme padrão OpenSpec do projeto.)*

## Why

A spec selada do `sen completeness` (grill 24/09, `docs/feat-command-sen-completeness/features/sen-completeness.md`) escolheu o Adaptive Governance (AG) como fonte primária. As sondas posteriores em produção — registradas em `docs/feat-command-sen-completeness/problemas.md` — provaram um bloqueio estrutural: **o AG só mantém report de maturidade da última revisão** do catálogo, e nem o produto (tela Overview do Manager) oferece histórico de completude por revisão. Com `--revision` obrigatório (A3), o comando ficaria inútil para toda revisão que não fosse a vigente (recusa `exit 2` garantida).

O endpoint do Manager `GET /api-manager/api/v3/revisions/{rid}/completeness` **já aceita o id da revisão** diretamente no path (confirmado no swagger do Manager, `CompletenessBean`) e funcionava ao vivo nas sondas (HTTP 200 com o mesmo JWT) — para qualquer revisão. A mudança de rota elimina a limitação sem trocar a gramática do comando.

## What Changes

- **Fonte primária trocada: AG → Manager.** O comando passa a consumir `GET /api-manager/api/v3/revisions/{rid}/completeness` (`{completenessScore, suggestions[]}`) em vez de `search` + `maturity-reports` + `fullReport` do AG. **BREAKING** em relação às decisões C1/C2/C5 e C6 da spec selada (documento da feature não será alterado — a divergência fica registrada aqui e o ADR ganha supersedência explícita).
- **Revisão consultável = qualquer revisão** do histórico (`sen list api --id X --revisions` deixa de ser só formalidade), removendo a regra selada em `problemas.md` ("revisão antiga → exit 2"); recusas só ocorrem quando a plataforma recusa (erro HTTP real).
- **Simplificação de chamadas:** fim da ponte via Connect Catalog / integração NATIVE (observacoes_filtros.md deixam de ser caminho do comando); 1 chamada de manager-completeness (+ satélite api-finder quando possível).
- **Contrato de saída v1 rebalanceado (o que exibimos muda):**
  - `maturity.score` continua (vem agora de `completenessScore`). **Classificação (Basic/Intermediate/Advanced) sai do report**: o wire real (probe 25/09) não traz bucket algum e a derivação client-side foi rejeitada como invenção de dado — headline exibe apenas o percentual.
  - Perde-se (dado não presente no Manager): `ruleId` (SSD-xxx), `severity`, `impactPoints` rateado, `path`/`range` do swagger, `rulesLost`, `classification`, `deployedEnvironments` do AG. O contrato v1 REMOVE esses campos (não os aprovisiona como `null` fantasma).
  - Ganha-se: `suggestions[]` (texto integral, 1:1 com a tela do Manager) — vira corpo central do relatório TEXT.
- **Visualização TEXT adaptada:** cabeçalho (API/revision/contexto) mantém o desenho aprovado, com score como percentual neutro (sem classificação/paleta — o wire não classifica); a tabela `Sev │ Impact │ Description │ Where` é aposentada e substituída por lista numerada de `Suggestions` (word-wrap integral, F4 preservado); barra de progresso + gate mantêm-se (score existe).
- **Arquitetura simplificada:** **sem port/adapter/exceções novos em arquivos dedicados** — a fronteira já é detida por `ManagerApiPort`/`ManagerApiAdapter` (extensão: 1 método `get_revision_completeness`); **model** (`completion_model`) e **service** (`CompletenessService`, compartilhável com o futuro `sen validate`) permanecem como peças novas; erros via exceção única `CompletenessError(message, exit_code)` seguindo o padrão vigente (`CliError` + RFC 7807 do `HttpErrorMapper`). Supersedência explícita do ADR 0008 (port dedicada afastada junto com a rota AG).

## Capabilities

### New Capabilities
- `sen-completeness`: comando top-level `sen completeness` — espelho read-only da completude calculada pela plataforma por API + revisão, via `GET /revisions/{rid}/completeness` do Manager, com gramática (--api-id/--revision obrigatórios, --score-only, -o/-v), contrato JSON versionado `apiops.sen-completeness/v1` (rebalanceado) e matriz de erros.

### Modified Capabilities

*Nenhuma.* `sen-list` e `cli-auth` não têm requisitos alterados (drill-down `sen list` continua com fontes próprias — completa desacoplamento das sondas: o comando consumirá a mesma familia do api-finder somente como satélite de contexto, opcional e degradável).

## Impact

- **Código:** `domain/ports/manager_api_port.py` (nova assinatura: `get_revision_completeness`); `adapters/outbound/http/manager_api/manager_api_adapter.py` (implementação — esboço já existente na fatia sen-list); `application/services/completeness_service.py` (novo, inclui `CompletenessError(message, exit_code)`); `domain/models/completeness_model.py` (reescreve a árvore v1 rebalanceada); CLI presentation (`sen completeness`); `display_output`; sem port/adapter/arquivo de exceptions novos.
- **Plataformas/rotas:** consome apenas `GET /api-manager/api/v3/revisions/{rid}/completeness` + satélite opcional `GET /api-finder/api/v3/apis/customSearch=(apiId:X)` (ambos GET, read-only). Rotas do AG (`search`, `maturity-reports`) saem do consumo do comando (voltam a ser candidatas quando a Plataforma entregar histórico por revisão).
- **Docs:** ADR 0008 registra supersedência parcial (fonte primária); `problems.md` P-f reduzido a "histórico por revisão no AG ainda não existe — hoje atendemos via Manager". Spec selada original permanece intacta (registro histórico).
- **Riscos herdados:** autenticação (JWT platform-native, pendência P-b) segue pré-requisito de runtime; suggestions[] sem estrutura gera ordem/caso de severidade impossível — mitigado na visualização (lista simples, sem Severidade).
