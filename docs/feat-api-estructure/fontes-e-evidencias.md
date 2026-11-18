# Fontes e evidências da exploração

> ⚠️ **Alinhado à [D-005](d005-layout-revisado.md) em 2026-10-14.** As citações a `artifacts/Resources/` e
> `resources.yaml` descrevem **repositórios-fonte históricos** (`api-gateway/`), não o layout canônico —
> que desde a D-005 é `resources/<slug-do-recurso>/`. A procedência das decisões do refino 409/417 está em
> [`decisoes-refino-409/CAMINHOS-DE-VALIDACAO.md`](decisoes-refino-409/CAMINHOS-DE-VALIDACAO.md).


**Atualizado em:** 2026-09-28  
**Objetivo:** permitir rastrear cada conclusão deste refinamento até sua origem e distinguir decisão, evidência empírica, comportamento do código atual e simples proposta de layout.

## Como interpretar as fontes

| Classificação | Significado |
|---|---|
| Decisão do responsável | Escolha de produto confirmada nesta exploração; é normativa para o layout alvo. |
| Evidência empírica | Comportamento observado por GET/PUT/POST no Manager. Descreve a plataforma no tenant e versão testados. |
| Código atual | Comportamento implementado hoje no CLI. Não significa que seja o comportamento desejado. |
| Premissa arquitetural | Restrição ou direção já registrada no memory bank. |
| Exemplo/proposta | Ajuda a comparar formatos, mas não é fonte normativa por si só. |

## 1. Premissas arquiteturais

Fontes consultadas em `arquitetura-apiops-memory-bank/`:

| Arquivo | Uso nesta exploração |
|---|---|
| `knowledge/arquitetura-do-orquestrador.md` | Git é a fonte da verdade do estado versionado; Manager é o estado operacional; a V1 é CLI; cada versão funcional da API possui repositório/esteira próprios e o APIOps gerencia revisions. |
| `delivery/backlog-orquestrador.md` | Confirma a necessidade de modelos para `Revision`, `RevisionFlow`, resource por diretório, parser recursivo de operations e validações específicas de interceptors. |
| `decisions/open-decisions.md` | Mostra que regras de estrutura, schemas, nomenclatura, enums e interceptors ainda dependem de revisão arquitetural do Validator. |
| `decisions/records/decisoes-fechadas-2026-08-17.md` | Dá contexto ao fluxo V1: a API é criada no Manager e depois passa a ser versionada pelo orquestrador. |
| `delivery/technical-debt.md` | Foi usado para não tratar o layout do manual/desenvolvimento atual como contrato definitivo. |

Consequência para este refinamento: o repositório deve expressar o estado declarativo que pertence ao usuário, sem tentar espelhar todos os campos operacionais do Manager.

## 2. Mapeamento empírico do Sensedia API Manager

Fontes consultadas em `mapeamento APIM/`:

| Arquivo | Evidência utilizada |
|---|---|
| `mapeamento-criacao-api-sensedia.md` | Shape denso de API/revision/resource/operation e estrutura `component.parent`. |
| `docs-sensedia/03-edicao-revisoes-recursos.md` | Diferença entre Save e Save as new Revision; shadow-copy de recursos/operações; payload denso; campos de resource/operation; endpoints de leitura corretos. |
| `docs-sensedia/06-interceptadores.md` | Shape persistido do interceptor, tipos de `content`, `executionPoint`, `status`, `idTemp`, `persist` e aplicação comprovada de interceptors em revision. |
| `docs-sensedia/15-interceptores-custom.md` | Catálogo e CRUD de custom interceptors; conteúdo do custom; limitação encontrada ao vincular um custom criado ao flow. |
| `docs-sensedia/99-modelo-de-dados.md` | Modelo observado de API, revision, resource, operation e interceptor. |
| `docs-sensedia/98-erros-e-validacoes.md` | Erros de payload e cuidados metodológicos, especialmente `lifeCycle` e writes densos. |
| `docs-sensedia/12-adaptive-governance.md` e `docs-sensedia/13-abas-e-campos-mapeados.md` | Contexto de attributes/tags e campos administrados pela plataforma. |

Esses documentos foram tratados como registros de exploração do tenant, não como documentação pública e estável de contrato. Onde houve conflito com um teste novo, o teste mais recente foi registrado separadamente.

## 3. Estruturas candidatas

### `apiestructure/`

Arquivos principais consultados:

- `main/apisStruct.md` e `main/readme.md`;
- `main/api-info/api-basic-info.yaml`;
- `main/api-info/schema-interceptors.json`;
- `main/revisions/{n}/revision.yaml`;
- `main/revisions/{n}/revision-flow.yaml`;
- `main/revisions/{n}/resources/{resource}/resource.yaml`;
- `main/revisions/{n}/resources/{resource}/operations/{method}_{path}.yaml`.

O exemplo propõe três níveis para flow — revision, resource e operation — mas repete listas completas de interceptors e não define formalmente herança, override, remoção ou reutilização. Portanto, ele foi usado como ponto de partida, não como contrato aprovado.

### `api-gateway/`

Arquivos principais consultados:

- `bindings.json`;
- `docs/api-blueprint.md`;
- `artifacts/Templates/api-basic-info.yaml`;
- `artifacts/Templates/default-interceptors.yaml`;
- `artifacts/Resources/resources.yaml`;
- os 26 arquivos de operation em `artifacts/Resources/{resource}/`.

Achados relevantes:

- o índice `resources.yaml` referencia um arquivo por operação;
- cada operação carrega seu próprio flow, permitindo que rotas distintas tenham sequências distintas;
- foram encontrados 23 flows distintos nos 26 arquivos de operation, considerando a sequência completa e o conteúdo dos interceptors;
- há um prefixo recorrente de `Service callout` seguido de `Custom` ID `241`, mas os interceptors seguintes variam por rota;
- o exemplo não representa revisions nem flows no nível de resource;
- custom interceptors são referenciados por IDs numéricos locais ao tenant;
- o `bindings.json` aponta para a API 386, mas a consulta no contexto autenticado não correspondeu aos demais artefatos. O binding foi tratado como desatualizado e removido do desenho alvo pela D-001.

## 4. Implementação atual do CLI

Arquivos de código consultados:

| Arquivo | Constatação |
|---|---|
| `application/services/repo_importer_service.py` | Remove `id` do basic info; importa `revision-flow.yaml`; sintetiza resource somente com nome, descrição e referências de operations, descartando flow/destination/timeout do resource. |
| `application/services/conversor_service.py` | Injeta `Settings.API_ID` e tags vindas de settings; processa interceptors de revision e operation; não processa interceptors de resource. |
| `application/services/publisher_service.py` | Hidrata somente parte do estado remoto e reduz objetos aninhados antes do publish. |
| `domain/models/api_partial_model.py` | Define defaults que podem divergir do estado remoto. |
| `domain/models/api_full_model.py` | Renumera globalmente interceptors de revision e de todas as operations. |
| `domain/models/resources_model.py` | O modelo final de resource não possui `destination`, `timeout` ou `interceptors`. |
| `domain/models/api_operations_model.py` | A operation possui `destination`, `timeout` e `interceptors`. |
| `domain/models/interceptors_model.py` | Exige `position`, `type`, `content`, `executionPoint` e `status`; deriva `id` e `idTemp` de `position`. |
| `domain/services/json_to_yaml_service.py` | Exporta custom como ID numérico, remove `parent`, `revision`, `id` e `idTemp`; não exporta flow de resource. |
| `domain/schemas/api-basic-info.schema.json` | Schema atual do basic info, ainda não alinhado às decisões D-001/D-002. |
| `domain/schemas/api-revision-flow.schema.json` | Schema atual do flow de revision. |
| `domain/schemas/api-resource.schema.json` | Já descreve flow no resource, embora os models/importer o descartem. |
| `domain/schemas/api-operations.schema.json` | Schema atual de operation e seus interceptors. |

Conclusão: o código atual é uma referência de compatibilidade e de gaps, não a autoridade para o layout final.

## 5. Chamadas realizadas no Manager

### API 400 — Orchestrator Auth API

- Leitura: `GET /api-manager/api/v3/apis/400`.
- Uso: montar o exemplo de `api-basic-info.yaml` e verificar campos operacionais ausentes do manifesto.
- Evidência complementar já registrada em `docs/auth/api-orq-auth-contrato.md`: interceptors existem em revision e resources; nos resources `Token` e `Groups`, um OAuth herdado aparece com `status: REMOVED`.
- Não houve escrita na API 400 nesta exploração.

### API 405 — docs-demo-api

- Leitura: `GET /api-manager/api/v3/apis/405` e leitura das revisions relacionadas.
- Escrita: `PUT /api-manager/api/v3/revisions/{id}` para testes isolados e `POST /api-manager/api/v3/revisions` para criar a revision de teste.
- Uso: determinar quais campos de basic info são obrigatórios, preservados ou destrutivos quando omitidos.
- Resultado detalhado: `api-basic-info-criticidade-campos-omitidos.md`.
- Estado deixado: revision 3, ID 9089, sem deploy; revision 2 permaneceu implantada no Default.

As credenciais, o segredo e o Bearer não foram copiados para a documentação. Os payloads brutos também não foram versionados porque incluem estado operacional e IDs internos; os resultados sanitizados e reproduzíveis estão nos documentos da feature.

### Varredura de 110 APIs — tags e atributos (2026-09-29)

- Leitura: `GET /api-manager/api/v3/apis` + GET individual de cada API do tenant (110/110, zero erros), via fluxo sancionado do CLI (sessão dev → validate → admin token).
- Uso: medir uso real de `tags[]` (0/110 não-vazio) e inventariar os pares `(attributeName, tags[])` do `apiTags` (7 bindings, 3 atributos, todos presentes no catálogo do AG).
- Resultado detalhado: `evidencia-tags-e-atributos.md`.
- Estado deixado: somente leitura; nenhuma mutação executada.

## 6. Matriz de rastreabilidade dos objetivos

| Objetivo original | Evidência/documento atual | Estado |
|---|---|---|
| Layout final da API | D-001 no `README.md`, `resumo-exploracao.md`, este inventário e `interceptors-e-rotas-levantamento.md` | Parcial: identidade/basic info avançaram; árvore completa ainda não foi aprovada. |
| Representação de interceptor | `interceptors-e-rotas-levantamento.md`, mapeamento APIM, schemas e models atuais | Levantada, mas contrato final ainda aberto. |
| Informações básicas | Documentos `api-basic-info-*` | Decisões principais fechadas; perguntas residuais registradas. |
| Rotas com flows diferentes | Comparação de `api-gateway`, `apiestructure` e CLI em `interceptors-e-rotas-levantamento.md` | Evidência levantada; estratégia final de herança/reuso ainda aberta. |

## 7. Limites da evidência

- Os testes ao vivo valem para o tenant e a versão do Manager observados em 2026-09-28.
- `apiestructure` e `api-gateway` não passaram por uma validação end-to-end com o CLI atual.
- O shape retornado pelo Manager contém IDs e campos internos que podem ser regenerados.
- `status: REMOVED` foi observado como supressão de interceptor herdado, mas o algoritmo completo de merge entre revision, resource e operation ainda não foi isolado em uma matriz de testes.
- A conclusão de 23 flows distintos em `api-gateway` descreve os arquivos existentes; não significa que devam permanecer duplicados no layout final.