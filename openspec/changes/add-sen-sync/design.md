## Context

O `extrair_estrutura.py` já faz a leitura (`GET /apis/{id}` → `revisions[]` por `revisionNumber` →
`GET /revisions/{id}`) e a geração da árvore. O orquestrador já tem quase todas as peças que o
script implementa, só que ligadas ao `sen validate`/`sen publish`:

| Peça do script | Já existe no orquestrador | Observação |
|---|---|---|
| `http_get` | `ManagerApiAdapter` + `HttpClient` | timeout, retry em 5xx, 401/403 tipados |
| `main` (API → revisão pelo número) | `ManagerApiPort.get_api_by_id` + `get_revision` | mesma sequência de GETs do script |
| `slug`, `nome_pasta`, `slug_path`, `nome_arquivo`, `marca` | `domain/services/repo_layout.py` | transplantado do protótipo, com o reparo dos nomes reservados |
| `escalar` | `domain/services/yaml_serialization.py` | com os reparos 23 e 24 da fila |
| `resolver_fluxo`, `bloco_heranca`, `gerar_basic_info`, `gerar` | `domain/services/repo_materializer.py` (`materialize(api, revision)`) | usado só por testes (oracle e baterias 417/425); protegido por oracle byte a byte contra `exemplos-gerados/saida` |
| `contrato_operacoes`, `contrato_raiz`, `gerar_components`, `sem_extensoes`, `expandir_parametro` | `domain/services/openapi_contract.py` (sentido swagger → repositório, novo neste change) | ao lado do sentido inverso, `extract_contract`/`apply_contract`, que o validate e o publish já usam |
| `escrever` | — | a porta nova |
| validação de sessão, time, visibilidade | `AdminTokenProvider`, `require_access`, `ApiAccessGuard` + `api_visible` | |

Diff medido em 2026-11-12 entre a saída do script e a do `materialize` para as fixtures 417 e 400
(sem contrato): mesmos caminhos e mesmos arquivos; diferenças só de aspas em strings, do texto dos
comentários de herança e dos comentários explicativos do `api-basic-info.yaml`, de `apiTags` em
bloco em vez de `[a, b]`, de `description: ""` omitida, e de **uma** diferença de conteúdo
intencional: o script emite `quota: 1000` e `maxSize: 2048` sem aspas, que relidos viram inteiro
(reparo 24 da fila); o orquestrador emite `"1000"`.

A herança é tratada igual nos dois: pelos marcadores do Manager. Marca `REMOVED` com `parent.id`
suprime um herdado (`inherit: false`, fluxo efetivo inteiro no arquivo); item sem `parent` é
próprio e soma ao herdado (`inherit: true`); sem item próprio, só `inherit: true`. O script emite
três avisos que o materializer ainda não emite (ver D1).

## Goals / Non-Goals

**Goals**

- Expor o comportamento do script como comando da CLI, dentro da arquitetura hexagonal e do padrão
  dos outros comandos (factory preguiçosa, ports, exceções com `exit_code`, mensagens PT-BR).
- Ler só o que a sessão enxerga; nunca escrever no Manager nem no Git.
- Nenhuma falha deixa árvore parcial.

**Non-Goals (fase 2 ou outros changes)**

- Qualquer consulta ao Git: branch atual, aviso de revisão inesperada para a branch, recusa de carga
  já publicada no remoto, identificação da branch na esteira.
- Aplicar no Git as diferenças do `--check`; rodar o `--check` na esteira.
- Padronizar os exit codes de toda a CLI.

## Decisions

### D1 — O Conversor Manager → arquivos é o `repo_materializer`

O formato canônico é o do orquestrador, não o do script: o `materialize` já é o que os testes de
integração (417, 425) e o oracle protegem, e o round-trip com o `RepoCanonicalReader` já fecha.
O critério de aceite "idêntico byte a byte ao script" passa a ser **"mesma árvore e mesmo conteúdo
YAML relido"**, com uma exceção documentada: strings numéricas (`"1000"`) ficam citadas, porque sem
aspas o round-trip quebra.

O `materialize` ganha:

- parâmetro `template`, gravado em `spec.template` (hoje sempre `''`), para preservar o valor que a
  geração do repositório deixou no arquivo;
- os três avisos do script que ele ainda não emite: item com `parent` e status não reconhecido
  (tratado como próprio), `REMOVED` apontando para fora do fluxo herdado (hoje só vira comentário
  no arquivo) e item próprio idêntico a um herdado.

O oracle byte a byte continua protegendo o formato; entra um teste de referência que roda o
`gerar` do script offline (swagger vazio) sobre as fixtures 417 e 400 e compara o YAML relido.

**Alternativa descartada:** reescrever o `materialize` para casar byte a byte com o script.
Reintroduziria o reparo 24 e invalidaria o oracle sem ganho funcional.

### D2 — Leitura do Manager igual ao script, pelas operações que o port já tem

`GET /apis/{id}` (com a regra de visibilidade aplicada ao `visibility` da resposta, via
`api_visible`, sem chamada extra), `revisions[]` procurado pelo `revisionNumber`, `GET
/revisions/{id}`. O Publicador não ganha operação nova: `get_api_by_id` e `get_revision` já
existem. API inexistente e invisível respondem com a mesma mensagem (`API_NOT_FOUND_TEMPLATE`),
exit `3`. Revisão inexistente lista os números disponíveis; revisão sem recursos aborta; os dois
com exit `4`.

### D3 — Um serviço, dois casos de uso

O módulo é `application/services/sync_service.py` com `SyncService.sync(...)` e
`SyncService.check(...)`, que compartilham os passos de argumentos, sessão, API e revisão. Sem IO
direto: recebe `ManagerApiPort`, `LocalFileImporterPort`, `RepoWriterPort` e a sessão.

### D4 — Uma porta nova para a escrita

`RepoWriterPort` (`domain/ports/repo_writer_port.py`), com `write_managed_area(root, files)`: grava
num diretório temporário dentro da raiz e substitui `api-basic-info.yaml`, `all.yaml` e `resources/`
de uma vez; sinal `RepoWriteError` (caminho longo, permissão). Adapter em
`adapters/outbound/filesystem/repo_writer_adapter.py`.

A leitura da árvore local (template existente, `spec.id`, `--check`) não precisa de porta nova: é o
`LocalFileImporterPort` com o `RepoCanonicalReader`, como no `validate`.

### D5 — Fase 1 sem Git

A revisão que vai para o diretório atual é a do `--revision`, escolhida por quem roda o comando,
como no script. O comando não sabe em que branch está e não consulta o remoto. A `GitPort`, o
aviso de revisão inesperada e a recusa de carga publicada entram na fase 2, junto com a decisão de
como a esteira informa a branch.

### D6 — O `--check` compara duas materializações

O sentido arquivos → modelo do Manager já existe: `RepoCanonicalReader` + `revision_payload.assemble`
(o mesmo que o `validate` usa para montar o `PUT`). A comparação:

```
remoto  = materialize(api, revisão lida)
local   = materialize(api, assemble(draft=revisão lida, basic_info, root, resources).body)
diff    = revision_diff.compare(local, remoto)   # YAML relido, campo a campo
```

Passar os dois lados pela mesma canonicalização absorve comentários, ordem de chaves, aspas e
`timeout: 30` × `'30'`; o que o repositório não governa (interceptors fora de FIRST/SECOND,
`apiTags` ausente) vem do próprio remoto e não gera diferença falsa. O resultado nasce por arquivo
e campo, com os dois valores, como a spec pede. O `api-basic-info.yaml` entra na mesma comparação.
`revision_diff.py` é o `diff_engine` da sub-task 02.01.04, no domínio (lógica pura); a pasta vazia
`adapters/outbound/diff_engine/` sai.

**Alternativa descartada:** reusar `revision_payload.verify`. Ele relata por escopo
("foram enviados N interceptors e o Manager gravou M"), não por arquivo e campo, e sua semântica é
"enviado × publicado".

### D7 — Exit codes da tabela, com o `2` do Click anotado

`sync_exceptions.py` segue o padrão: `SyncError` (exit 1) e subclasses com os códigos da spec.
`AuthenticationRejectedError` e `AccessDeniedError` (fora do time APIOps) são traduzidos pela CLI
para o `2` do sync. O Click devolve `2` em erro de uso (ex.: `--revision` ausente), como em todos os
comandos `sen`; a tabela vale para os erros que o próprio comando detecta. Os códigos `5` (branch,
carga publicada) e `7` (remoto) ficam reservados para a fase 2; nesta fase o `5` cobre só o
`spec.id` diferente do `<api-id>`.

### D8 — Saída `text` e `--output json|yaml`

Como os outros comandos, com o documento `apiops.sen-sync/v1` (api, revisão, pasta da carga, arquivos,
contagens, avisos; no `--check`, a lista de diferenças). O texto mostra só a pasta e as contagens.

### D9 — Ordem da carga: tudo que não precisa de rede vem antes

```
argumentos      api-id × spec.id existente (exit 1 / 5)                      sem rede
sessão          token da sessão, time APIOps (2)                             auth
API             GET /apis/{id} + visibilidade (3)                            GET
revisão         revisionNumber em revisions[], GET /revisions/{id} (4)       GET
montagem        materialize(api, revisão, template=spec.template existente)  sem rede
escrita         temporário + substituição da área gerenciada (6)             disco
```

A spec coloca a checagem do `spec.id` no passo 7; aqui ela sobe para antes da rede, como a guarda de
identidade dos outros comandos, sem mudar o resultado ("nada foi escrito" nos dois casos).

### D10 — Escrita atômica e limite de caminho

O adapter calcula o maior caminho absoluto antes de gravar; acima do limite do sistema (260 no
Windows) falha com exit `6` sem tocar o disco. Grava tudo em `.sen-sync.tmp/` na raiz do
repositório, apaga a área gerenciada antiga e move a nova; qualquer `OSError` remove o temporário e
falha com `6`. Arquivos fora da área gerenciada (wrapper, `.github/`) não são tocados.

### D11 — Remoção do versionador legado

Commit separado (`refactor:`), antes do sync: `versioner_service.py`, `api_repo_port.py`,
`template_repo/api_repo_adapter.py`, `test_versioner_service.py`, `Settings.API_REPO_FOLDER`, o
`api_id` do construtor do `ManagerApiAdapter` (`get_api_by_id(api_id)` passa a exigir o id),
`publish_api_changes` (`POST /revisions`, que a spec do sync proíbe) e `get_apis` (manager cru,
sem uso). Os fakes de teste que declaram `publish_api_changes` são ajustados.

### D12 — Contrato OpenAPI no mesmo change (decisão de 16/11)

O `sen validate` exige `responses` em toda rota desde o APIOPS-115, então uma árvore sem contrato
não passa nele. O contrato entra aqui, com as regras do script:

- O sentido swagger → repositório fica em `openapi_contract.py`, o mesmo módulo do sentido inverso,
  e o `materialize` o chama como o `gerar` do script chama `contrato_operacoes`. Os conjuntos
  `NAME_MAPS` e `FREE_VALUES` saem do validador para esse módulo: a leitura de `x-*` é uma só.
- `materialize(api, revision, *, template, swagger=None)`: com swagger, `components.yaml` sempre
  (`{}` quando vazio), `contact`/`tags`/`security` no `api-basic-info.yaml` depois de `apiTags`, e o
  bloco `# contrato OpenAPI da rota` no fim de cada operação, serializado por PyYAML (ordem de
  chaves preservada, texto multilinha em `|`). Sem swagger a árvore sai só com o fluxo, e os
  oracles antigos continuam válidos.
- Parâmetros do path mesclados em cada operação (na mesma `name`+`in` vale o da operação), `$ref`
  de parâmetro expandido, item que não é objeto descartado, `x-*` removidas.
- Só OpenAPI 3: Swagger 2.0 ou documento sem `openapi` aborta com exit `4`, nada gravado.
- Rota fora do swagger ou sem `responses` fica sem contrato, com aviso; o `validate` barra até o
  dev declarar, como a spec decide.
- No `--check`, o lado local do swagger é `apply_contract(swagger remoto, extract_contract(repo))`;
  os dois lados materializados com swagger, então o contrato entra no diff pelos mesmos arquivos.

### D13 — Modelos do Manager tipados e tolerantes (16/11)

Os três comandos anteriores leem o JSON do Manager como dicionário, porque o publish precisa devolver
a revisão inteira no `PUT`, inclusive o que o repositório não governa. A saída que concilia os dois
lados é um modelo **tipado no que o domínio lê e tolerante no resto**: `domain/models/api_model.py`
(`Api`, `Revision`, `Resource`, `Operation`, `Interceptor`, Pydantic com `extra="allow"` e alias do
wire). Campo conhecido vira atributo; campo desconhecido viaja em `model_extra` e volta intacto em
`to_wire()`. O contrato é o round-trip, provado contra as fixtures reais 417 e 400 em
`tests/unit/domain/models/test_api_model.py`.

- O port passa a devolver `Api` em `get_api_by_id` e `Revision` em `get_revision`; o adapter valida
  na borda e uma forma que o modelo recusa vira `ManagerApiUnexpectedResponseError`.
- O sync, o `materialize` e a visibilidade (`from_api`) leem atributos. A resolução da revisão pelo
  número é `Api.revision_by_number`.
- **Ponte transitória**: `validate`, `publish`, `deploy`, `ruler`, `contract_writer` e o `diag` da
  CLI chamam `as_wire(...)` na leitura e seguem no dicionário; `domain/services/revisions.py` atende
  esses dois primeiros. No `--check`, o `assemble` recebe `remote.revision.to_wire()` e o corpo
  volta como `Revision` para o materializer. As baterias de integração embrulham o adapter em
  `tests/integration/_wire.py`. Tudo isso some quando os três comandos migrarem (Story 02.03:
  `revision_payload`, `interceptor_flow`, `template_conformance`, conferência pós-publicação,
  `swagger_flow`), com as baterias de escrita na 425 como prova.
- Tipos frouxos onde o Manager é instável (`timeout` string ou nulo, `content` texto JSON,
  `customInterceptorId` nulo): tipo errado num campo conhecido rejeitaria o payload inteiro.

### D14 — Forma canônica do Mock (16/11)

O Manager devolve o `content` do Mock em duas formas, conforme quem o gravou: `body` como
objeto e `status` como número (criado na interface) ou os dois como texto (gravado pelo
`sen validate`, que é o que o `PUT` aceita). O repositório declara sempre objeto e número,
então o materializer canoniza com `repository_mock_content`, inverso de `_mock_content` em
`revision_payload.py`. Sem isso o `--check` logo depois da carga acusava `content.body {}`
contra `{}` na 426: o lado do Manager materializava o objeto e o lado do repositório, o texto
que o `assemble` produz. Achado na bateria de 16/11; coberto no materializer, no `assemble`
(round-trip) e no `check`. No mesmo caminho, `content` que chega como dicionário deixou de
quebrar a comparação com o herdado (`_key` serializa antes de comparar).

Na mesma bateria, por tipo de interceptor (32 tipos da 425 rev 13, round-trip Manager → sync →
`assemble` → `verify`): os tipos sem configuração (`XML threat protection`, `JSON threat
protection`) chegam com `content: '{}'` e o materializer omitia a chave, então o `PUT` mandaria
`null` e a conferência pós-publicação acusaria. Agora `'{}'` vira `content: {}` declarado, como
as baterias de escrita já declaravam; `null` e vazio continuam sem a chave.

### D15 — `--template` na carga (17/11)

A spec previa o `spec.template` preenchido no onboarding e só preservado pelo sync; numa pasta
vazia o arquivo saía com `template: ''`. A opção `--template <id>` grava o id depois de conferi-lo
no Manager pela mesma regra de visibilidade da API (`GET /apis/<id>`, inexistente ou invisível →
exit 3, nada gravado), para o erro não aparecer só no `validate`. Sem a opção, vale o arquivo. Com
`--check` é erro de uso: a verificação compara com o template que está no arquivo.

### D16 — Verificação só com diferenças e `apiTags` como conjunto (17/11)

Na bateria da 475 o `--check` mostrou dois avisos do materializer ("Log próprio repete um herdado")
e seis diferenças em `apiTags` que eram só reordenação. Os avisos descrevem a API no Manager e
aparecem igual na carga, onde importam; na verificação são ruído, então o `check` devolve
`warnings` vazio. `apiTags` é conjunto no wire (o Manager reordena ao editar na UI e o pré-check
casa por nome): `revision_diff` compara `spec.apiTags` por atributo, com as tags ordenadas, via
`UNORDERED`; a carga continua gravando na ordem que o Manager devolve.

### D17 — Sync em cliente sem Adaptive Governance (18/11)

`apiTags` é dado do Adaptive Governance. Depois da mesclagem com `detect-adaptive-governance`, o
`SyncService` recebe a `GovernanceApiPort` e expõe `governance_available()` com a mesma regra dos
outros serviços (só a ausência confirmada é falsa). Sem AG, `materialize(include_api_tags=False)`
deixa `apiTags` e o comentário fora do manifesto, e o `--check` materializa os dois lados sem o
campo, então um `apiTags` deixado no arquivo não conta. Nada mais do sync depende do AG:
`workflowId`/`workflowStageId` nunca entram nos arquivos, o contrato OpenAPI e o fluxo de
interceptors são do Manager. A detecção é uma chamada por execução, com cache no adapter.

## Risks / Trade-offs

- **Sem a guarda do Git, a carga sobrescreve a área gerenciada de qualquer repositório** em que for
  rodada, inclusive um já no fluxo. Nesta fase a responsabilidade é de quem roda; o `--check` não
  grava. A guarda vem na fase 2.
- **Oracle do script**: o teste de referência importa o `extrair_estrutura.py` de fora do
  repositório; é `skip` quando o arquivo não existe.
- **Diff por materialização**: um recurso renomeado no Manager muda a pasta e aparece como "arquivo
  só no Manager / só no repositório", não como "campo `name` diferente". É fiel ao que o Git veria.

## Open Questions

Registradas na spec como "Decisões em aberto" 1 a 4; nenhuma bloqueia este change.
