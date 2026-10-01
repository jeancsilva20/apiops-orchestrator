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
- **Arquitetura alinhada à casa PADRONIZADA (pós-`type-api-catalog-frame`, 25/09):** extensão de `ManagerApiPort`/`ManagerApiAdapter` (1 assinatura + tradutor wire→leitura tipada no estilo `_translate_row`); **service** (`completeness_service.py`, reutilizável pelo futuro `sen validate`) responde com **view tipado** (`CompletenessView`, dataclass frozen — o CLI consome atributos; dict só em `to_document()` para o canal stdout); erros via módulo dedicado `application/exceptions/completeness_exceptions.py` (peer de `listing_exceptions.py`), traduzidos no CLI para exit/msg PT-BR. Supersedência explícita do ADR 0008 (port dedicada afastada junto com a rota AG).
- **Completude co-localizada em `CatalogRevision` (pivot de model, 28/09):** a leitura de completude vira o objeto aninhado `CatalogRevision.completeness` (`CatalogRevisionCompleteness{score, suggestions[]}` em `catalog_revision_model.py`); o flat `completenessScore` é aposentado (frame do catálogo e endpoint do Manager populam o MESMO objeto — teaser do drill-down e espelho integral compartilham a forma); o envelope `SenCompleteness` foi EXCLUÍDO — a árvore v1 de saída é projeção montada no service (sem model redundante). Spec `api-catalog` recebe MODIFIED mínimo; `sen-list` permanece intacta (coluna COMPLETE intacta).

## Capabilities

### New Capabilities
- `sen-completeness`: comando top-level `sen completeness` — espelho read-only da completude calculada pela plataforma por API + revisão, via `GET /revisions/{rid}/completeness` do Manager, com gramática (--api-id/--revision obrigatórios, --score-only, -o/-v), contrato JSON versionado `apiops.sen-completeness/v1` (rebalanceado) e matriz de erros.

### Modified Capabilities

- `api-catalog`: MODIFIED mínimo no requisito "Selado rules of the catalog revision" — o cenário "Duplicate completeness score ignored" passa a citar o objeto aninhado `CatalogRevision.completeness.score` (flat `completenessScore` aposentado — ver pivot D9 no design). Demais cenários e demais requisitos preservados.

*Além disso, sem modificações:* `sen-list` e `cli-auth` não têm requisitos alterados (drill-down `sen list` continua com fontes próprias — completa desacoplamento das sondas: o comando consumirá a mesma família do api-finder somente como satélite de contexto, opcional e degradável; a coluna COMPLETE do drill-down segue derivada de `rev.completeness.score`).

## Impact

- **Código:** `domain/ports/manager_api_port.py` (nova assinatura `get_revision_completeness`); `adapters/outbound/http/manager_api/manager_api_adapter.py` (implementação + tradutor wire→`CompletionReading` no estilo `_translate_row`); `application/exceptions/completeness_exceptions.py` (novo, padrão da casa); `application/services/completeness_service.py` (novo); `domain/models/completeness_model.py` (✔ já implementado/revisado); `adapters/inbound/cli/cli_adapter.py` (comando + render). Consumo do catálogo TIPADO da fundação (`ApiCatalogEntry` — já arquivada e consolidada) para identidade/posse.
- **Plataformas/rotas:** consome apenas `GET /api-manager/api/v3/revisions/{rid}/completeness` + satélite opcional `GET /api-finder/api/v3/apis/customSearch=(apiId:X)` (ambos GET, read-only). Rotas do AG (`search`, `maturity-reports`) saem do consumo do comando (voltam a ser candidatas quando a Plataforma entregar histórico por revisão).
- **Docs:** ADR 0008 registra supersedência parcial (fonte primária); `problems.md` P-f reduzido a "histórico por revisão no AG ainda não existe — hoje atendemos via Manager". Spec selada original permanece intacta (registro histórico).
- **Riscos herdados:** autenticação (JWT platform-native, pendência P-b) segue pré-requisito de runtime; suggestions[] sem estrutura gera ordem/caso de severidade impossível — mitigado na visualização (lista simples, sem Severidade).
