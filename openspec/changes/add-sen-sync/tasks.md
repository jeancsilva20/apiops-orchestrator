## 1. Remoção do versionador legado (commit `refactor:` separado)

- [x] 1.1 Remover `versioner_service.py`, `api_repo_port.py`, `template_repo/api_repo_adapter.py` e `test_versioner_service.py`
- [x] 1.2 Remover `Settings.API_REPO_FOLDER`, o `api_id` do construtor do `ManagerApiAdapter` (`get_api_by_id(api_id)` obrigatório), `publish_api_changes` e `get_apis` do port e do adapter; ajustar os fakes de teste
- [x] 1.3 Remover `adapters/outbound/diff_engine/.keep`; atualizar `docs/padroes-desenvolvimento.md` (§2 e §4.4) e `analise-complexidade-orquestrador.md`

## 2. Domínio

- [x] 2.1 `repo_materializer.materialize(api, revision, *, template='')` grava `spec.template`; testes
- [x] 2.0 Comentários fixos do materializer (decisão de 13/11): cabeçalho único do `all.yaml`, bloco de herança único, comentários do `api-basic-info.yaml`; sem comentário de interceptors não governados nem de remoção; oracle apontado para `../apiops-docs` e árvores de referência regeneradas
- [x] 2.2 Avisos do script que faltam no `materialize` (status não reconhecido, `REMOVED` fora do herdado, próprio idêntico ao herdado); testes
- [x] 2.3 `domain/services/revision_diff.py`: comparação campo a campo de duas árvores materializadas (YAML relido), `Difference(file, field, repo_value, manager_value)`; testes com comentários, ordem de chaves e `timeout` citado × inteiro
- [x] 2.4 `domain/models/sync_view.py` com `to_document()` emitindo `apiops.sen-sync/v1`
- [x] 2.5 Teste de referência contra o script: `gerar` offline (swagger vazio) sobre as fixtures 417 e 400, YAML relido igual ao `materialize`, exceto strings numéricas; `skip` sem o script

## 2b. Contrato OpenAPI (decisão de 16/11)

- [x] 2.6 `openapi_contract.py`: `without_extensions`, `swagger_root_contract`, `swagger_components`, `swagger_operations_contract`, `is_openapi_3`, `document_format`; `NAME_MAPS`/`FREE_VALUES` como fonte única para o validador; testes
- [x] 2.7 `materialize(..., swagger=None)`: `components.yaml` sempre, contrato da raiz no basic-info, bloco da rota, avisos de rota fora do swagger e sem `responses`; testes
- [x] 2.8 `SyncService`: `get_revision_swagger` depois da revisão, `UnsupportedSwaggerError` (exit 4) fora do OpenAPI 3, `--check` com `apply_contract`; testes (Swagger 2.0, contrato alterado no Manager e no repositório)
- [x] 2.9 Teste de referência contra o script com swagger sintético: árvore e contrato relidos iguais, inclusive `components.yaml`

- [x] 2.11 `domain/models/api_model.py` (`Api`, `Revision`, `Resource`, `Operation`, `Interceptor`, `extra="allow"`, `to_wire`) com teste de round-trip nas fixtures reais; port e adapter devolvendo os modelos; `materialize`, `SyncService` e `from_api` lendo atributos; ponte `as_wire` nos comandos não migrados e `tests/integration/_wire.py` nas baterias
- [x] 2.10 `domain/services/revisions.py` (`revision_by_number`, `revision_numbers`) usado por `RevisionWriter`, `DeployService` e `SyncService`; comentários fixos do materializer num mapa `COMMENTS`; testes

## 3. Porta e adapter

- [x] 3.1 `domain/ports/repo_writer_port.py` (`RepoWriterPort`, `RepoWriteError`) e `adapters/outbound/filesystem/repo_writer_adapter.py`: temporário na raiz, limite de caminho antes de gravar, substituição da área gerenciada, limpeza em falha; testes com `tmp_path`

## 4. Aplicação

- [x] 4.1 `application/exceptions/sync_exceptions.py`: `SyncError` (1) e subclasses com os códigos da spec
- [x] 4.2 `application/services/sync_service.py`: `SyncService.sync()` na ordem do design D9 e `SyncService.check()` conforme D6; `spec.template` preservado; avisos deduplicados
- [x] 4.3 Testes do serviço com fakes (Manager, escrita em memória): API invisível, revisão inexistente, revisão sem recursos, id ≠ `spec.id`, id ausente sem `spec.id`, template preservado, nada escrito em cada falha, `--check` igual/diferente/só formatação, nenhuma chamada além de GET

## 5. Borda

- [x] 5.1 `sen sync` em `cli_adapter.py`: `--id` (opção obrigatória, como nos outros comandos; era argumento posicional opcional até 16/11), `--revision`, `--repo` (17/11, como no validate; default diretório atual), `--template` (17/11: conferido no Manager, grava `spec.template`, recusado com `--check`), `--check`, `--output`, tradução de `LoginError`/`AccessDeniedError` para exit 2, renderização texto e documento
- [x] 5.2 `build_sync_service_factory()` em `main.py`
- [x] 5.3 Testes da CLI: exit codes, nenhum token na saída, documento JSON sem progresso

## 6. Documentação

- [x] 6.1 `docs/comandos-cli.md`: seção `sen sync` (carga, verificação, passo a passo manual por branch, exit codes, o que fica para a fase 2)
- [ ] 6.2 Memory bank: Story 06.03 (`sen version sync`) dá lugar ao `sen sync` — depende de acesso de escrita

## 7. Verificação

- [x] 7.1 Suíte unitária sem regressão em relação à linha de base
- [x] 7.2 Bateria real contra a API-lab 425 em 2026-11-13 (ela só tem as revisões 4 a 13): carga das revisões 4, 5 e 13 em pastas temporárias, `template` preservado e `spec.id` gravado, `--check` com exit 0 nas três, segunda carga na mesma pasta sem nenhuma diferença de arquivo, `--check --revision 5` na pasta da 4 com exit 8 e 31 diferenças reais; recusas: API inexistente (3, nada escrito), revisão 99 (4), id divergente (5), sem id (1)
- [x] 7.2.1 Bateria com o contrato na 425 em 2026-11-16 (sessão `read`): carga da 13 com `api-basic-info.yaml` (contact, tags), `components.yaml` (securitySchemes) e contrato por rota (summary, tags, parâmetros do path mesclados, responses); carga da 4 com `components.yaml` (schemas); `--check` 0; segunda carga sem diferença de arquivo; `--check --revision 4` na pasta da 13 com exit 8; `summary` e `description` alterados localmente aparecem no `--check`; recusas 1/3/4/5 sem escrita. O `sen validate` é recusado pelo scope `read` da sessão e a 425 não tem a Draft (revisão 1), então as etapas anteriores à gravação rodaram por script com a revisão 13 no lugar da Draft: leitura sem avisos, contrato válido, montagem sem avisos, 106 achados de conformidade com a template 414 (só WARNING e INFO), governança sem bloqueio, nenhum item sairia da documentação e o swagger a gravar é idêntico ao atual
- [x] 7.2.2 `sen validate` real na API 426 (autorizada pelo usuário em 16/11, sessão `write`): árvore gerada pelo `sen sync --id 426 -r 1` com `template: 414`; validate gravou a Draft, conferiu, contrato sem mudança ("o repositório já está igual ao Manager"), governança liberada, quality score 97,8%; `--check` depois do validate com exit 0. O `--check` antes do validate acusou `content.body` do Mock (objeto no Manager × texto do `assemble`): corrigido (D14), com testes no materializer, no `assemble` e no `check`
- [x] 7.2.3 Por tipo de interceptor (16/11): round-trip Manager → sync → `assemble` → `verify` nos 32 tipos da 425 rev 13 e nos 7 da 426 rev 1, sem divergência depois de corrigir o `content: '{}'` (D14); `sen validate` real em modo esteira (`EXECUTION_MODE=pipeline`, `TEMPLATE_API_ID=414`, `TARGET_REVISION_NUMBER=13`) sobre a árvore gerada da 425 rev 13: gravado e conferido, documentação sem mudança, score 87,5%; `--check` depois com exit 0; releitura da revisão igual ao backup (mesmos interceptors, content, destination, timeout e swagger)
- [x] 8.1 (18/11) Mesclagem da `feat/sen-sync` na `feat/detect-adaptive-governance` (merge de46fd7; conflitos só no port e nos imports do adapter) e `SyncService` com a `GovernanceApiPort`: sem AG a carga sai sem `apiTags` e o `--check` ignora o campo; testes no materializer e no serviço (DISABLED, ENABLED, UNKNOWN)
- [x] 8.2 (18/11) Bateria real na 425 rev 13 do consulting com a detecção forçada para ausente dentro do processo (`GovernanceApiAdapter._availability = DISABLED`, só GET): carga sem a chave `apiTags`, `--check` dessa carga em 0, e `--check` de uma pasta carregada com AG (com `apiTags`) também em 0; carga e `--check` pelo comando real com o AG vivo em 0
- [x] 7.3 Alteração local de `timeout` numa operação aparece no `--check` com exit 8, arquivo, campo e os dois valores (2026-11-13); a alteração direta no Manager foi coberta pelo `--check` cruzado entre as revisões 4 e 5
