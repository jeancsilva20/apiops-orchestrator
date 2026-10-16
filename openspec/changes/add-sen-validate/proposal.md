## Why

O orquestrador trata APIs como código, mas o ciclo não fecha: hoje não existe comando que leia o
repositório, confronte-o com o padrão da organização e devolva o veredito da plataforma antes do PR.
O dev descobre que violou a governança quando a esteira quebra — tarde, fora do contexto, e sem
saber o que faltou.

O `sen validate` fecha esse ciclo na Draft (Revision 1, [V-24](../../../docs/feat-api-estructure/decisoes-refino-409/V-24-revisao-alvo-do-publish.md)),
que não é ambiente e não tem deploy: publicar nela é diagnóstico, não promoção. A base empírica está
pronta — 10 cenários validados contra a API 417 ([caderno](../../../docs/feat-api-estructure/prova-fluxo-validate/CADERNO-DE-TESTES.md)),
com as nove regras de wire (W-1 a W-9) observadas, não inferidas.

## What Changes

**Comando e borda (CLI)**

- Novo comando `sen validate`, seguindo a forma do `sen completeness`: factory no contexto montada
  no composition root, `--output text|json|yaml`, `--verbose` só para verbosidade, exceções tipadas
  que a CLI apenas traduz em `exit_code`.
- Saída em dois regimes: **texto** estruturado para leitura no PowerShell e **JSON** versionado
  (`apiops.sen-validate/v1`) para a esteira consumir sem parsear texto humano.
- O JSON da esteira carrega o **snapshot da régua** — `id`, `revisionNumber` e hash do fluxo do
  template — para que todo achado seja reproduzível depois (D-4/P-3).
- Exit codes: `0` sucesso (inclui INFO/WARNING de régua e completeness abaixo dos 70%), `1` falha
  técnica ou de gramática, `3` bloqueio do Adaptive Governance — canal distinto para a esteira
  ramificar sem ler texto.

**Fluxo E1→E4**

- E1 carrega o repositório sem rede; guarda de identidade (`version`/`basePath`, D-11) aborta antes
  de qualquer chamada.
- E2 lê a régua (`GET /apis/{template}`, um GET basta — `lastRevision` já traz o fluxo completo),
  compara conformidade e roda o pré-check de governança **antes** de escrever.
- E3 faz **um único PUT** na revision (W-7): escrever também em `PUT /apis` fura o gate do AG e deixa
  estado meio-aplicado. O `workflowId`/`workflowStageId` são lidos da revisão alvo em runtime e
  reenviados intactos — nunca configurados, nunca avançados.
- E3.1 confere o publicado contra o enviado por GET. **HTTP 200 não é prova de sucesso**: três perdas
  silenciosas distintas foram observadas sob 200.
- E4 reporta completeness (percentual + issues) de forma informativa.

**Layout e régua**

- Escopo raiz passa a ser `all.yaml` (hoje `all-all.yaml`, literal sem significado), aceitando
  `destination`, `timeout`, `interceptors_request` e `interceptors_response`.
- Tombstone ganha forma: **lista completa explícita** — provado pelo T06 como a única representação
  expressável, já que lista vazia significa herdar e "rota sem fluxo" não existe na plataforma.
- **BREAKING** — os 7 schemas `*-default-interceptors.schema.json` (~128 KB, um por cliente) são
  removidos. A régua passa a vir de uma **API template no Manager**, que varia por ambiente como o
  catálogo de Custom varia. Some junto o acoplamento de `domain/` a nome de cliente.
- Divergência da régua e preenchimento fora do padrão emitem `INFO`/`WARNING` e **não bloqueiam**: o
  dev decide subir algo despadronizado. O que bloqueia é falha técnica — régua inalcançável ou
  ausente, e `Custom` referenciado que não existe no tenant.

## Capabilities

### New Capabilities

- `sen-validate`: gramática do comando, cascata E1→E4, guardas, pré-check de governança, conferência
  pós-publicação, contrato JSON `apiops.sen-validate/v1`, exit codes e regime de logs.
- `api-repo-layout`: contrato do repositório em disco — `all.yaml`, `resources/<slug>/resource.yaml`,
  arquivo de operação `<método>_<path>.yaml`, regime de `inherit`, gramática do tombstone e regra de
  arquivo base obrigatório.
- `api-repo-import`: descoberta e materialização do repositório a partir do estado do Manager,
  incluindo partição governado × preservado e falha alta no não representável.
- `template-conformance`: comparação do fluxo efetivo com a régua por sequência e `content`,
  severidades `INFO`/`WARNING`, e validação de tipo e preenchimento do interceptor contra a template.

### Modified Capabilities

Nenhuma. O `sen validate` reusa `sen-completeness` sem alterar seus requisitos.

## Impact

**Código novo** — `application/services/validate_service.py`, `governance_precheck_service.py`,
`application/exceptions/validate_exceptions.py`, `domain/services/repo_layout.py`,
`interceptor_flow.py`, `template_conformance.py`, `domain/models/validate_view.py`.

**Código alterado** — `domain/ports/manager_api_port.py` (`get_revision`, `update_revision`,
`get_workflow`, `list_attributes`); `manager_api_adapter.py` (implementação + `get_custom_interceptor_by_id`
devolvendo `None` no 404, que hoje vira `ManagerApiTransportRejectedError`);
`domain/models/interceptors_model.py` (separar declarativo × wire — o `set_ids_from_position` atual
deriva `idTemp` de `position`, que é do escopo, e fabrica a colisão do W-9);
`api_operations_model.py` e `resources_model.py` (`destination` objeto, `inherit`);
`application/services/repo_importer_service.py` (reescrita para o layout).

**Código removido** — `domain/schemas/*-default-interceptors.schema.json` (7 arquivos),
`api-revision*.schema.json` (2, obsoletos pela D-003 §2) e a ilha de materialização do layout antigo:
`json_to_yaml_service.py`, `json_to_yaml_enum.py`, `revision_file_generator.py`,
`local_file_exporter_adapter.py`, `file_exporter_strategy.py`, `files_exporter_exceptions.py` e
`domain/ports/file_exporter_port.py`. Verificado antes de remover: nenhum deles é importado por
`main.py` ou por qualquer serviço — a ilha só se referenciava a si mesma e aos próprios testes.

**Rede** — somente `GET` nas ondas 0–2; a onda 3 introduz a escrita (`PUT /revisions/{id}`) e depende
de ambiente de escrita provisionado (P-8).

**Documentação** — `extrair_estrutura.py:354` e a árvore da D-005 §4 passam a `all.yaml`; os repos de
exemplo precisam ser regerados com os dois reparos de serialização (escalar iniciado por indicador
YAML e string numérica preservada).
