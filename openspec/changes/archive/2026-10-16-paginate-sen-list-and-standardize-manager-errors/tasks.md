## 0. Linha de base

- [x] 0.1 Rodar `poetry run pytest` antes de qualquer mudança e registrar as falhas pré-existentes (para não confundi-las com regressões deste change)
  - Linha de base (16/10/2026, `tests/unit`): 514 passam, 7 falham, 2 erros de coleta (`SessionStorageError` em `test_login_service`/`test_session_store`), todos alheios a este change. A bateria `tests/integration/test_bateria_417.py` ESCREVE na plataforma e não foi executada (só roda com `APIOPS_BATERIA_417=1`).

## 1. Diagnóstico na camada HTTP (etapa 1 — erros)

- [x] 1.1 `adapters/outbound/http/common/http_error_mapper.py`: ler `code` (fallback `error`) e `message` do corpo; capturar o request-id do header `x-amzn-RequestId` como extensão do problema RFC 7807
- [x] 1.2 `infrastructure/exceptions/http_client_exceptions.py` + `infrastructure/utils/http_client.py`: `HttpClient4xxError` ganha `code` e `request_id` opcionais, preenchidos a partir do problema mapeado
- [x] 1.3 Testes em `tests/unit/infrastructure/utils/test_http_client_reporting.py`: corpo `{"code","message"}` gera `code`/`detail` corretos; request-id capturado; corpo não JSON segue degradando como hoje

## 2. Sinais do port e adapter

- [x] 2.1 `domain/ports/manager_api_port.py`: `ManagerApiTransportRejectedError` ganha `code` e `request_id` opcionais (defaults preservam os chamadores atuais); novo `ManagerApiResponseTooLargeError(ManagerApiTransportRejectedError)`
- [x] 2.2 `manager_api_adapter._request`: repassar `code`/`request_id` ao sinal; lançar `ManagerApiResponseTooLargeError` para status `413`; log `manager_api.transport.rejected status_code=%s code=%s request_id=%s` em **INFO** (nunca WARNING+, ver design D2)
- [x] 2.3 Testes em `test_manager_api_adapter.py`: 413 vira `ResponseTooLarge` (e continua sendo `Rejected`); `code`/`request_id` propagados; nenhum token no log

## 3. Classificador compartilhado

- [x] 3.1 `application/enums/manager_failure_kind_enum.py`: `ManagerFailureKind(str, Enum)` com `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `INTERNAL`, `UNAVAILABLE`
- [x] 3.2 `application/services/manager_failure_translator.py`: `classify_manager_failure`, `manager_failure_message` e `INTERNAL_ERROR_MESSAGE`, com os textos da tabela do design D1
- [x] 3.3 Testes unitários do classificador: 401/403/404/413/400/429 → kinds esperados; `Unavailable` → `UNAVAILABLE`; a mensagem `INTERNAL` não contém `sen login`, status nem título

## 4. Aplicar a classificação nos consumidores

- [x] 4.1 `api_listing_service`: substituir `_catalog_access_error` pelo classificador (mantendo `ApiCollectionError`, `exit 1`, e `ApiNotFound` no drill-down)
- [x] 4.2 `completeness_service._translate_rejection` + `completeness_exceptions`: 404/403 mantêm o template de revisão; 401 reutiliza a mensagem `UNAUTHORIZED`; demais 4xx e `Unavailable` usam as mensagens padrão; `CompletenessPlatformError` deixa de receber `HTTP {status}: {title}`; `exit 2` preservado
- [x] 4.3 `regua_service` / `ReguaInalcancavelError`: 403/404 mantêm as causas atuais; `None` (indisponível) → mensagem `UNAVAILABLE`; demais status → mensagem `INTERNAL`
- [x] 4.4 Atualizar `test_api_listing_service.py`, `test_completeness_service.py` e `test_regua_service.py`: um `413` não orienta `sen login` e não expõe status/título/código; 401/403/404 inalterados

## 5. Fallback de erro inesperado na CLI

- [x] 5.1 `cli_adapter`: helper único de erro inesperado (mensagem `INTERNAL_ERROR_MESSAGE`, log `cli.unexpected_error command=%s type=%s` em INFO com `exc_info`, `typer.Exit` com o `exit_code` do comando)
- [x] 5.2 Aplicar em `list api` (exit 1), `completeness` (exit 2), `validate`, `diag template` e `diag draft` (exit 1), preservando o tratamento de `typer.Exit` e das hierarquias de negócio antes dele
- [x] 5.3 Testes em `test_cli_adapter.py` e `test_validate_command.py`: exceção inesperada exibe a mensagem padrão, sem o texto da exceção, com o exit code do comando
- [x] 5.4 Rodar `poetry run pytest` e confirmar verde (exceto as falhas da linha de base 0.1). **Fim da etapa 1.**

## 6. Leitura paginada do catálogo (etapa 2 — 413)

- [x] 6.1 Port e adapter: `list_catalog_apis(limit, offset=0, query=None)`, com o adapter enviando `_offset`
- [x] 6.2 `api_listing_service`: substituir `_fetch_catalog` pela varredura do design D4 (página de 25, redução pela metade que gruda, dedup por id, parada por janela/página curta/`Count`, super admin com offset direto); remover `_FETCH_GROW_CAP`
- [x] 6.3 Erro `INTERNAL` em dois casos, com log INFO `catalog.scan.*`: página de 1 ainda com `413`, e página sem nenhum id novo
- [x] 6.4 Testes em `test_api_listing_service.py` / `test_api_listing_pipeline.py`, com fake de port paginado:
  - janela padrão preenchida na 1ª página → 1 chamada;
  - baixa visibilidade → várias páginas até preencher;
  - catálogo acaba antes de preencher;
  - 413 → 12 → segue com 12;
  - 413 com página 1 → erro interno;
  - página repetida → erro interno sem loop;
  - super admin com `--offset 50` → 1ª chamada com `_offset=50`;
  - `Count` ausente;
  - `--query` repassada em todas as páginas
- [x] 6.5 Teste do adapter: `_offset` e `_limit` enviados corretamente

## 7. Flag `--all`

- [x] 7.1 `cli_adapter.list_apis`: opção `--all`; validação pré-rede de exclusividade com `--limit`/`--offset`/`--id`; chamada do service com `offset=0, limit=None`; rodapé "janela: todas as APIs visíveis (--all)"
- [x] 7.2 Corrigir o help de `--query` ("busca no Manager por nome/descrição")
- [x] 7.3 Testes em `test_cli_adapter.py`: `--all` lista tudo; `--all` combinado com `--limit`, `--offset` ou `--id` falha com exit 1 e zero chamadas ao service

## 8. Verificação

- [x] 8.1 `poetry run pytest` verde (exceto as falhas da linha de base 0.1)
  - Final: 573 passam (+59), com as mesmas 7 falhas e 2 erros da linha de base.
- [x] 8.2 Verificação manual contra o Manager real (somente leitura), com sessão de developer: `sen list api`, `sen list api --limit 50`, `sen list api --all`, `sen list api --query <termo>` e `sen list api --offset 200`. Nenhum `413` e nenhuma orientação de `sen login` indevida
  - Feito (somente leitura, sem `sen validate`): também `sen list api --id 125 --revisions`, `sen completeness --id 125 --revision 9256` e o caso 404 (`--revision 1`, exit 2). O `413` real (`_limit=127`) foi reproduzido direto no adapter: virou `ManagerApiResponseTooLargeError`, com `code`/`request_id` no log e a mensagem padrão de erro interno para o usuário.
- [x] 8.3 `openspec validate paginate-sen-list-and-standardize-manager-errors --strict`

## Workflow follow-up

- Commits só quando o autor pedir, e sem nada de `docs/` ou `openspec/` (a documentação foi removida da árvore de propósito e volta ao Git depois)
- Arquivamento do change (`openspec archive`) quando a documentação voltar ao repositório
- Change separado: visibilidade no drill-down `--id`/`--revisions`
- Pendência do ADR 0005: ligar o `setup_logging()`; até lá, os registros de diagnóstico em INFO não são gravados
