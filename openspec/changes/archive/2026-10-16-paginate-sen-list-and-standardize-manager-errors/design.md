## Context

Motivação em `proposal.md` (Why). Estado atual relevante para o desenho:

- **Leitura do catálogo** (`ApiListingService._fetch_catalog`): faz uma 1ª chamada com `_limit = offset + limit` e, se o header `Count` indicar mais registros (até `_FETCH_GROW_CAP = 2000`), uma 2ª chamada com `_limit = Count`. É essa 2ª chamada que recebe `413`. Medição em produção (16/10/2026): 127 APIs; páginas de 25 entre 8 KB e 2,7 MB foram aceitas, e a resposta única de 127 (~7,9 MB) foi recusada. O limite do gateway fica, portanto, entre 2,7 MB e 7,9 MB. O api-finder aceita `_offset` + `_limit` e devolve `Count` em toda página; `_page` é ignorado. As sondas r5 de setembro registravam o skip como "inerte" (origem do refetch do universo inteiro); a sonda de 16/10 confirmou que `_offset` desloca a página.
- **Visibilidade**: o token das chamadas é de super admin e compartilhado por todos, então só o cliente conhece o perfil do usuário logado. A visibilidade é, e continua sendo, client-side (`finder_rows_visible_to`).
- **Tradução de falhas**: o port já separa `ManagerApiTransportRejectedError` (4xx, com `status_code`/`title`) de `ManagerApiTransportUnavailableError` (conexão ou 5xx esgotado). Cada service traduz por conta própria:
  - `api_listing_service._catalog_access_error`: todo 4xx vira "recusada… faça `sen login`".
  - `completeness_service._translate_rejection`: trata 401, 403 e 404; o resto vira `HTTP {status}: {title}`.
  - `ReguaInalcancavelError`: trata 403 e 404; o resto vira "O Manager não respondeu".
- **Mapper**: o `HttpErrorMapper` só lê `error`/`message` do corpo. O api-finder responde `{"code": "...", "message": "..."}`, então o código vira o título genérico "Invalid Request".
- **Logging**: `setup_logging()` não é chamado (divergência registrada no ADR 0005). Sem handler configurado, o `logging.lastResort` do Python imprime em stderr tudo que for WARNING ou acima, e o resto é descartado.

## Goals / Non-Goals

**Goals:**
- Uma única classificação de falhas do Manager, reutilizada pelos três consumidores, sem que cada um perca o próprio `exit_code` nem as mensagens de negócio que já tem.
- Nenhuma requisição ao catálogo maior que uma página. Parada antecipada assim que a janela fecha.
- Diagnóstico (status, `code`, request-id, stacktrace) disponível em log e nunca na tela.

**Non-Goals:**
- Ligar o `setup_logging()` ou mudar o comportamento de logging (decisão do autor, 16/10/2026).
- Visibilidade no drill-down `--id`/`--revisions` (change próprio).
- Paginação por chave (`apiId > último`) e qualquer filtro de visibilidade no servidor.
- Mudar os `exit_code` existentes: `sen list` 1, `sen completeness` 2, `sen validate`/`sen diag` 1.

## Decisions

### D1 — Classificador compartilhado na camada de aplicação, mensagens por família

Novo módulo `application/services/manager_failure_translator.py`, com o enum `ManagerFailureKind` em `application/enums/manager_failure_kind_enum.py` (convenção `*_enum.py`, `(str, Enum)`). Os textos ficam em `application/exceptions/manager_failure_messages.py`, ao lado das hierarquias, para que as exceções (`completeness_exceptions`, `validate_exceptions`) os reutilizem sem importar a camada de serviço:

| Kind | Origem (sinal do port) | Mensagem padrão (PT-BR) |
|---|---|---|
| `UNAUTHORIZED` | Rejected 401 | "Sessão inválida ou expirada. Faça `sen login` novamente." |
| `FORBIDDEN` | Rejected 403 | "Acesso negado pelo Manager. Rode `sen login` e tente de novo; se continuar negado, acione o time de acesso." |
| `NOT_FOUND` | Rejected 404 | sem texto padrão: cada comando tem o seu (API, revisão ou template) |
| `INTERNAL` | demais Rejected (incl. `ResponseTooLarge`) e erros inesperados | "Ocorreu um erro interno na consulta. Tente novamente em instantes; se persistir, acione o suporte." |
| `UNAVAILABLE` | Unavailable (conexão ou 5xx esgotado) | "Manager indisponível no momento. Verifique sua rede e tente novamente em instantes." |

O módulo expõe `classify_manager_failure(exc) -> ManagerFailureKind`, `manager_failure_message(kind) -> str` e a constante `INTERNAL_ERROR_MESSAGE`. Cada consumidor continua lançando a **própria** hierarquia (`ApiCollectionError`, `CompletenessError`, `ValidateError`), com o próprio `exit_code`, e sobrescreve só onde já tem semântica de negócio:
- listagem: 404 no drill-down vira `ApiNotFound`;
- completeness: 404/403 viram o template de revisão não encontrada;
- régua: 403/404 mantêm as causas atuais de `ReguaInalcancavelError`.

Por que assim: o `exit_code` pertence ao contrato de cada comando (a esteira ramifica por ele), então uma exceção compartilhada única quebraria o `exit 2` do completeness. Já o texto e a classificação são o que estava divergindo, e por isso são o que se compartilha.

Alternativas descartadas:
- **Base `ManagerFailureError` herdada pelas três hierarquias**: obrigaria herança múltipla com bases que têm `exit_code` diferentes, sem ganho sobre a função.
- **Tradução no adapter**: o adapter não conhece UX nem PT-BR, o que viola a fronteira do §5 de padrões.

### D2 — Diagnóstico carregado pelo sinal do port e registrado no adapter, em INFO

- O `HttpErrorMapper` passa a ler `code` (com fallback para `error`) e `message` do corpo, e captura o request-id do header `x-amzn-RequestId` como extensão do problema RFC 7807.
- O `HttpClient4xxError` ganha os campos opcionais `code` e `request_id`.
- O `ManagerApiTransportRejectedError` ganha os mesmos campos opcionais, com defaults para não quebrar os chamadores.
- O log fica num ponto só, onde a recusa nasce: `manager_api.transport.rejected status_code=%s code=%s request_id=%s`, no adapter.

**Nível INFO, nunca WARNING ou acima**: com o logging não ligado, o `lastResort` imprimiria WARNING+ em stderr, e o diagnóstico vazaria para a tela, contrariando a decisão "só no log". Em INFO, o registro é descartado hoje e passa a ser gravado quando o logging for ligado. Nenhum header de autorização é registrado (ADR 0005).

### D3 — Sinal específico para resposta grande demais

Novo `ManagerApiResponseTooLargeError(ManagerApiTransportRejectedError)`, no arquivo do port, lançado pelo adapter quando o status é `413`.

Por que uma subclasse: a varredura captura **só** esse sinal para reduzir a página, e qualquer outro chamador que já trata `Rejected` continua funcionando, caindo em `INTERNAL` pelo classificador. Inspecionar `status_code == 413` dentro do service vazaria detalhe HTTP para a aplicação.

### D4 — Varredura paginada no service, adapter "burro"

O port passa a ter `list_catalog_apis(limit, offset=0, query=None)`, e o adapter envia `_offset`. A política fica no `ApiListingService`, porque visibilidade é regra de domínio:

```
page_size = 25
srv_off   = offset if super_admin else 0
needed    = limit if super_admin else offset + limit      # None quando --all
seen, visible = set(), []
loop:
    page = port.list_catalog_apis(limit=page_size, offset=srv_off, query)
        ResponseTooLarge → page_size == 1 ? erro INTERNAL : page_size //= 2 ; repete a mesma posição
    new = rows de page cujo id ∉ seen ; seen += ids
    page não vazia e new vazio → log catalog.scan.no_progress ; erro INTERNAL
    visible += visíveis(new)
    srv_off += len(page.rows)
    para se: needed e len(visible) >= needed
             | len(page.rows) < page_size
             | (page.total >= 0 e srv_off >= page.total)
janela: super_admin → visible[:limit] ; demais → visible[offset : offset + limit]
```

- O tamanho reduzido **não volta** para 25 (decisão do autor). Uma API pesada tende a ter vizinhas pesadas, e oscilar custaria um `413` a cada subida.
- A sequência 25 → 12 → 6 → 3 → 1 é `max(1, size // 2)`.
- `_FETCH_GROW_CAP` sai. A parada natural (página curta ou `Count`) mais a dedup substituem o teto.
- A `--query` segue como `customSearch` em toda página, sem mudança de semântica.

Alternativas descartadas:
- **Paginação por chave (`apiId > último`)**: eliminaria até a omissão por deleção concorrente, mas disputa o `customSearch` com a `--query` e depende de busca por faixa no api-finder.
- **Visibilidade via `customSearch`**: o casamento de caixa/acento do servidor pode divergir do `accent_fold`. Uma sub-seleção do servidor esconderia API sem aviso, e o filtro client-side não recupera o que nem chegou.
- **Teto de linhas varridas**: só limitaria tempo em catálogos muito grandes, cenário inexistente hoje (127 APIs). Fica registrado como risco.

### D5 — `--all` na CLI como ausência de janela

`--all` chama o service com `offset=0, limit=None`, contrato que o service já aceita (`limit=None` = sem corte). A validação de exclusividade com `--limit`/`--offset`/`--id` fica na CLI, pré-rede, no mesmo estilo da validação `--query` × `--id`. O rodapé informa "janela: todas as APIs visíveis (--all)". O help de `--query` passa a dizer que a busca é feita no Manager.

### D6 — Fallback de erro inesperado padronizado na CLI

Um helper único no `cli_adapter` substitui os `except Exception` de `list api`, `completeness`, `validate`, `diag template` e `diag draft`. Ele:
- imprime `[bold red]Erro:[/bold red]` + `INTERNAL_ERROR_MESSAGE`;
- registra `cli.unexpected_error command=%s type=%s` em INFO com `exc_info=True` (mesma razão de nível do D2);
- sai com o `exit_code` do comando (1, ou 2 no completeness).

`typer.Exit` e as hierarquias de negócio continuam tratados antes dele.

Achado na implementação: as factories de serviço rodam **dentro** do `try` de cada comando, então dois erros já categorizados chegavam ao `except Exception` e eram exibidos por ele: configuração incompleta (`CliError`) e a recusa da rota validate ao resolver o admin token (`LoginError`, que orienta `sen login`). O helper preserva a mensagem educativa dos dois (exit do `CliError`; `exit 1` no `LoginError`, como antes). Só o restante vira erro interno. O catch-all do `main()` segue a mesma regra (mensagem padrão + log INFO), cobrindo comandos sem fallback próprio.

## Risks / Trade-offs

- **[Omissão por deleção concorrente]** Se uma API já lida for apagada durante a varredura, as seguintes deslocam 1 posição e uma é pulada. → Aceito: a varredura dura segundos e a próxima execução corrige. A dedup cobre o caso inverso (duplicação).
- **[Diagnóstico descartado até o logging ser ligado]** Os registros INFO não são gravados hoje. → Registrado como pendência do ADR 0005. Quando o logging for ligado, o diagnóstico passa a existir sem mudar código.
- **[Varredura longa em catálogo muito grande]** `--all` ou um usuário com pouca visibilidade leem o catálogo inteiro (hoje ~6 requisições). → Sem teto, por decisão. Reavaliar se o catálogo passar de alguns milhares.
- **[Página reduzida "gruda"]** Uma API pesada no início deixa o resto da varredura com páginas menores e mais requisições. → Aceito em troca de não tomar um `413` por subida.
- **[`Count` ausente]** Sem o header, `total = -1`, e a parada depende só da página curta. → Já é o comportamento degradado atual; a dedup cobre o loop.
- **[Mensagem de erro interno genérica demais para o suporte]** → O request-id em log (D2) é o elo de rastreio, e foi ele que permitiu diagnosticar este 413.

## Migration Plan

Sem migração de dados ou configuração. Entrega em duas etapas, na mesma branch e no mesmo change (ver `tasks.md`): primeiro a padronização de erros, depois a paginação. Rollback: reverter os commits; nenhum estado persistido muda.
