## Design

### Contexto

O drill-down `sen list api --id X --revisions` foi desenhado (`add-sen-list`, D6) para ler o completeness de `/revisions/{rid}/completeness`, uma chamada por revisão. Na troca para o api-finder como fonte única (`type-api-catalog-frame`), a coluna COMPLETE passou a vir do bloco `completeness[]` do frame, economizando as chamadas. A premissa implícita — de que o finder espelha o Manager — não se sustenta.

### Evidência (sondagem 21/10/2026, somente GETs, tenant de produção)

| Medida | Resultado |
|---|---|
| Amostra | 40 APIs mais recentes do catálogo, 213 revisões |
| Finder = Manager (tolerância 0,05) | 49 |
| Finder ≠ Manager | 164 (72 maiores, 92 menores) |
| Divergentes que são a última revisão | 10 |
| Entradas duplicadas por revisão no finder | 0 |
| Campos do bloco `completeness[]` | só `apiRevision`, `score` |
| Rotas de completeness no swagger do Manager | só `GET /revisions/{id}/completeness` |
| Latência da rota (API 341, 55 revisões) | ~2,2 s por chamada; 55 em paralelo ×8: ~21 s |

API 68 (caso relatado):

| REV # | REV ID | finder | Manager |
|---|---|---|---|
| 1 | 5976 | 74.3 | 74.3 |
| 2 | 10461 | 68.5 | 74.3 |
| 3 | 23625 | 68.5 | 74.3 |
| 4 | 28541 | 66.83333333333333 | 75.8 |
| 5 | 42653 | 88.8 | 88.8 |
| 6 | 43957 | 75.8 | 75.8 |

Leitura: o finder guarda um score indexado em algum momento passado; o Manager recalcula na consulta (o que também explica a latência). Não há marcador no finder que permita distinguir valores defasados dos atuais, nem relação estável entre os dois (diverge nos dois sentidos). A interface do Manager mostra o valor da rota.

### Decisões

**D1 — Fonte única do COMPLETE: rota do Manager.** Cada revisão exibida consulta `get_revision_completeness(revision_id)` (port já existente). É a mesma leitura do `sen completeness`, do gate do `sen deploy` e da interface do Manager — os quatro passam a concordar. Alternativa (manter o finder com aviso) descartada: 77% de divergência torna a coluna enganosa, e o gate do deploy usa a outra fonte.

**D2 — Busca paralela no service, concorrência 8.** O `ApiListingService` dispara as leituras com `ThreadPoolExecutor(max_workers=8)` depois do frame e dos stages. O `HttpClient` usa `requests.request` sem sessão compartilhada, então as chamadas são independentes entre threads. A ordem da grade continua definida pelo `revision_number`, não pela ordem de chegada. O port e o adapter não mudam de forma: o paralelismo é uma decisão de orquestração do caso de uso.

**D3 — Degradação por célula.** Falha de transporte ou recusa do Manager em uma revisão (`ManagerApiTransportRejectedError`, `ManagerApiTransportUnavailableError`) vira `completeness_score=None` naquela linha; a grade sai com exit 0. Mesma postura do `sen validate` (E4 informativa). Erros inesperados (não-transporte) continuam subindo para a rede de segurança do comando. No modo texto, se houver células sem leitura, a grade ganha uma nota de rodapé: `N revisões sem completeness: o Manager não respondeu. Consulte com sen completeness --id X --revision <REV ID>.` Em `json`/`yaml`, o campo vem `null` e nada é impresso além do documento.

**D4 — O frame deixa de ler `completeness[]`.** `_merge_wire_blocks` para de correlacionar o bloco e `CatalogRevision.completeness` sai do modelo (o drill-down era o único consumidor). `CatalogRevisionCompleteness` permanece: é o tipo de retorno da rota do Manager. Manter o campo populado pelo finder deixaria um valor sabidamente errado disponível para o próximo consumidor.

**D5 — Feedback de espera.** Em modo texto e terminal, a busca roda sob o mesmo indicador transitório do login (`_LoadingBar` via `Live`, `transient=True`); fora de terminal, uma linha `[dim]Consultando completeness das revisões...[/dim]`; em `json`/`yaml`, nenhum feedback (stdout só com o documento). Mesma regra de `_authenticate_with_feedback`.

### Fora do escopo

- Paginar ou limitar as revisões exibidas (o drill-down continua mostrando todas).
- Exibir `suggestions` na grade (seguem exclusivas do `sen completeness`).
- Cache de completeness entre execuções.
- Avisar a Plataforma sobre a defasagem do api-finder (registro fica nesta change; abertura de chamado é decisão do time).

### Questões resolvidas (21/10/2026)

- **Q1 — Concorrência 8 é aceitável para o gateway?** Sim (aprovado pelo autor). A sondagem com 8 não recebeu 429 nem 5xx em 213 + 55 chamadas. Se a Plataforma pedir limite menor, só muda a constante.
- **Q2 — Teto de revisões?** Não há teto: ~21 s numa API com 55 revisões é aceitável (aprovado pelo autor). Flag ou teto com aviso ficam fora do escopo.
