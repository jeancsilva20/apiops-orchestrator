## Why

`sen list api` quebra em produção com `HTTP 413` (16/10/2026). A listagem lê 1 linha do catálogo (api-finder) só para obter o total (`Count: 127`) e, em seguida, pede o universo inteiro de uma vez (`_limit=127`) para filtrar a visibilidade no cliente. O peso por API varia muito (revisões, ambientes, completeness e workflow vêm inline; média de ~100 KB), e o gateway recusa a resposta de ~7,9 MB com `{"code":"BACKEND_RESPONSE_TOO_LARGE"}`. Para piorar, a CLI apresenta a falha como "Consulta recusada… faça `sen login` novamente", uma orientação falsa que manda o usuário para o caminho errado. O mesmo padrão de tradução (status cru `HTTP {status}: {title}` ou conselho de login para qualquer 4xx) se repete em `sen completeness` e na régua do `sen validate`.

## What Changes

Ordem de entrega: primeiro a correção das mensagens (o usuário passa a receber o diagnóstico honesto), depois a correção do 413.

- **Padronização das falhas do Manager**: uma única classificação reutilizável (`401` sessão · `403` acesso negado · `404` não encontrado · demais 4xx, incluindo `413`, como **erro interno** · conexão/5xx esgotado como indisponível), consumida por `sen list`, `sen completeness` e régua/`sen validate`. Cada comando mantém o próprio `exit_code` e as mensagens de negócio que já tem (ex.: 404 de revisão no completeness, 403 ambíguo da régua).
- **Diagnóstico só no log**: `code` do corpo da resposta (ex.: `BACKEND_RESPONSE_TOO_LARGE`) e request-id da plataforma (`x-amzn-RequestId`) passam a ser capturados e registrados em log. Nunca aparecem na tela.
- **Fallback de erro inesperado**: os `except Exception` da CLI (`sen list`, `sen completeness`, `sen validate` e `sen diag`) deixam de imprimir o texto cru da exceção. Passam a exibir a mensagem padrão de erro interno, com o detalhe técnico só no log.
- **Busca paginada do catálogo**: a listagem passa a ler o catálogo em páginas de 25 (`_offset`/`_limit`), aplicando a visibilidade client-side página a página e **parando assim que a janela pedida está preenchida**. Se a plataforma responder `413`, a página é reduzida pela metade (25 → 12 → 6 → 3 → 1), e o tamanho reduzido vale até o fim da varredura. Uma página de 1 ainda recusada resulta em erro interno.
- **Super admin**: a visibilidade é "tudo", então o `--offset` do usuário vai direto para o servidor, sem varrer desde o início.
- **Deduplicação por `apiId`** durante a varredura. Uma página sem nenhum id novo interrompe a varredura com erro interno, protegendo contra loop infinito caso a plataforma ignore o `_offset`.
- **Nova flag `--all`** em `sen list api`: lista todas as APIs visíveis. É mutuamente exclusiva com `--limit`, `--offset` e `--id`.
- **Remoção do teto `_FETCH_GROW_CAP` (2000)**: a paginação torna o teto desnecessário. Hoje, acima dele, a listagem trunca sem aviso.
- **Correção do spec de `--query`**: a busca é delegada ao Manager (`customSearch` em nome e descrição), e não client-side como o spec vigente afirma. O comportamento do código não muda.

## Capabilities

### New Capabilities

(nenhuma)

### Modified Capabilities

- `sen-list`: requisito "Comando `sen list api`" (fim da chamada única: leitura paginada com parada antecipada, redução adaptativa no 413 e `--all`); "Busca `--query` client-side" (passa a ser delegada ao Manager); "Erros HTTP mapeados para humanos (E1)" (família de erro interno, erro inesperado, diagnóstico só em log); "Filtragem de visibilidade client-side" (ordem do pipeline com a busca delegada e varredura paginada).
- `sen-completeness`: requisito "Exit code matrix" (recusas fora de 401/403/404 e erros inesperados passam a exibir a mensagem padrão de erro interno, sem status ou título crus; `exit 2` mantido).

## Impact

- **Código**:
  - `domain/ports/manager_api_port.py`: `offset` em `list_catalog_apis`; sinal de resposta grande demais; `code`/`request_id` no sinal de recusa.
  - `adapters/outbound/http/manager_api/manager_api_adapter.py`.
  - `adapters/outbound/http/common/http_error_mapper.py` e `infrastructure/utils/http_client.py` + `infrastructure/exceptions/http_client_exceptions.py`: ler `code`/`message` e o request-id.
  - `application/services/api_listing_service.py` (varredura), `completeness_service.py`, `regua_service.py`.
  - Hierarquias em `application/exceptions/`.
  - `adapters/inbound/cli/cli_adapter.py` (`--all`, fallbacks).
- **Testes**: `tests/unit/application/services/test_api_listing_service.py`, `test_api_listing_pipeline.py`, `test_completeness_service.py`, `test_regua_service.py`, `tests/unit/adapters/outbound/http/manager_api/test_manager_api_adapter.py`, testes do `HttpClient`/mapper e da CLI.
- **Plataforma**: a listagem padrão (`--limit 10`) passa de 2 requisições (a 2ª estourando) para 1 ou 2 páginas de 25 (medido: 2 requisições, de 2,7 MB e 0,8 MB, para um developer que enxerga 27 de 127 APIs). `--all` ou um usuário com pouca visibilidade varre o catálogo inteiro em páginas (6 requisições para 127 APIs).
- **Fora do escopo**:
  - Visibilidade no drill-down `--id`/`--revisions`, que hoje não aplica o filtro. Fica para um change próprio.
  - Ligar o `setup_logging()`. Os registros de diagnóstico nascem em nível INFO e só passam a ser gravados quando o logging for ligado.
