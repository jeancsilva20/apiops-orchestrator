## ADDED Requirements

### Requirement: Grammar of the sen sync command

A CLI SHALL expor o comando `sen sync --id <api-id> --revision <n> [--repo <pasta>] [--check] [--output text|json|yaml]`,
rodado na raiz do repositório da API. `--revision` MUST ser o `revisionNumber` da interface do
Manager, nunca o id interno. `<api-id>` MAY ser omitido quando `spec.id` do `api-basic-info.yaml`
está preenchido; quando os dois existem, MUST ser iguais. O comando MUST NOT consultar o Git: a
revisão que vai para o diretório atual é a informada. O serviço MUST ser obtido por factory no
contexto do Typer, montada no composition root de forma preguiçosa.

#### Scenario: Carga com o id
- **WHEN** o usuário roda `sen sync --id 425 --revision 4` com `spec.id` ausente
- **THEN** o comando carrega a revisão 4 da API 425 e grava `spec.id: 425`

#### Scenario: Id ausente
- **WHEN** o usuário roda `sen sync --revision 4` com `spec.id` ausente
- **THEN** o comando encerra com `exit 1`, mostrando a sintaxe, sem rede

#### Scenario: Id diferente do spec.id
- **WHEN** `spec.id` é `425` e o usuário passa `417`
- **THEN** o comando encerra com `exit 5` antes de qualquer chamada HTTP

### Requirement: API and revision are read as the session sees them

O comando SHALL usar o token da sessão do `sen login`, exigindo o time APIOps como os outros
comandos; sem sessão válida, `401` ou `403`, MUST encerrar com `exit 2`. A API SHALL ser lida por
`GET /apis/{id}` e a regra de `api-visibility` SHALL ser aplicada ao `visibility` da resposta: API
inexistente e invisível MUST responder com a mesma mensagem e `exit 3`. A revisão SHALL ser procurada
pelo `revisionNumber` em `revisions[]` e lida por `GET /revisions/{id}`; número inexistente (listando
os disponíveis) e revisão sem recursos MUST encerrar com `exit 4`. Erro de rede ou 5xx MUST encerrar
com `exit 7`. O swagger da revisão SHALL ser lido por `GET /revisions/{id}/swagger` e MUST ser
OpenAPI 3; Swagger 2.0 ou documento sem `openapi` MUST encerrar com `exit 4`, orientando a migração
no Manager. O comando MUST NOT emitir nenhuma chamada além de `GET`.

#### Scenario: Dev fora da visibilidade
- **WHEN** a sessão de dev roda `sen sync --id 400 --revision 4` e a API 400 é `GROUP` de outro grupo
- **THEN** o comando encerra com `exit 3` e "API 400 não encontrada ou sem permissão de acesso.", sem `GET /revisions`

#### Scenario: Revisão inexistente
- **WHEN** a API só tem as revisões 1, 2 e 3 e o usuário pede `--revision 4`
- **THEN** o comando encerra com `exit 4`, listando `1, 2, 3` e o pré-requisito das quatro revisões

#### Scenario: Swagger 2.0
- **WHEN** o swagger da revisão responde `swagger: "2.0"`
- **THEN** o comando encerra com `exit 4`, pedindo a migração para OpenAPI 3, sem gravar

### Requirement: Generated tree is the canonical layout, written atomically

A carga SHALL gerar `api-basic-info.yaml`, `all.yaml` e `resources/<slug>/{resource.yaml,
<método>_<path>.yaml}` com as regras de nome, destination, interceptors FIRST/SECOND e herança do
`repo_materializer`, equivalentes às do `extrair_estrutura.py` no YAML relido (strings numéricas
ficam citadas). `spec.template` SHALL ser preservado do arquivo existente e `spec.id` gravado com o
id da API. A área gerenciada SHALL ser substituída por inteiro; arquivos fora dela MUST NOT ser
tocados. A escrita SHALL ocorrer num diretório temporário e ser movida ao final; caminho acima do
limite do sistema ou erro de escrita MUST encerrar com `exit 6` sem deixar árvore parcial. Nenhuma
falha anterior à escrita MUST deixar arquivo no destino. Rodar a carga duas vezes com os mesmos
argumentos MUST produzir a mesma árvore.

#### Scenario: Template preservado
- **WHEN** o `api-basic-info.yaml` existente tem `spec.template: 414`
- **THEN** o arquivo gerado mantém `template: 414` e passa a ter `id: 425`

#### Scenario: Template informado
- **WHEN** o usuário roda `sen sync --id 425 --revision 4 --template 414`
- **THEN** o sync confere `GET /apis/414` com a regra de visibilidade e grava `template: 414`, no lugar do valor do arquivo

#### Scenario: Template inexistente
- **WHEN** `--template 999` e a API 999 não existe ou não é visível
- **THEN** o comando encerra com `exit 3` e a mesma mensagem de API não encontrada, sem gravar nada

#### Scenario: Cliente sem Adaptive Governance
- **WHEN** a detecção do Adaptive Governance confirma a ausência do módulo (`GET /attributes` 403)
- **THEN** a carga grava o `api-basic-info.yaml` sem a chave `apiTags` e o `--check` ignora `spec.apiTags`
  nos dois lados; com o módulo, ou sem conseguir saber, `apiTags` entra como sempre

#### Scenario: Template com check
- **WHEN** `--template` é passado junto com `--check`
- **THEN** é erro de uso (`exit 2`): a verificação usa o template do arquivo

#### Scenario: Caminho longo no Windows
- **WHEN** um arquivo de operação ultrapassaria 260 caracteres de caminho absoluto
- **THEN** o comando encerra com `exit 6`, orienta a encurtar o caminho do clone e nada é escrito

### Requirement: OpenAPI contract is part of the tree

Com o swagger lido, a carga SHALL escrever `components.yaml` sempre (as seis seções governadas, `{}`
quando não há nenhuma), `contact`, `tags` e `security` da raiz em `spec` do `api-basic-info.yaml`, e em
cada arquivo de operação `summary`, `operationId`, `tags`, `security`, `parameters`, `requestBody` e
`responses` da rota, com os parâmetros do path mesclados, `$ref` de parâmetro expandido e chaves
`x-*` removidas. Rota fora do swagger ou sem `responses` SHALL ficar sem esses campos, com aviso.
Os avisos de contrato (`$ref` inexistente, parâmetro que não é objeto, rota fora do swagger, rota
sem `responses`) MUST NOT alterar o exit code.

#### Scenario: Rota documentada
- **WHEN** o swagger documenta `GET /tarefas` com `summary` e `responses`
- **THEN** `resources/<slug>/get_tarefas.yaml` termina com o bloco de contrato com esses campos, sem chaves `x-*`

#### Scenario: Rota sem responses
- **WHEN** o swagger tem a rota mas sem `responses`
- **THEN** o arquivo sai sem `responses`, o resumo traz o aviso e o exit code continua `0`

### Requirement: Check compares content, never writes

Com `--check`, o comando SHALL ler a árvore local para o modelo do Manager e compará-la com a
revisão informada por conteúdo (recursos, operações, destinations, interceptors FIRST/SECOND,
herança, `api-basic-info` e o contrato OpenAPI, inclusive `components.yaml`): comentários, ordem de chaves e formatação do YAML MUST NOT contar como
diferença. Cada diferença SHALL indicar arquivo, campo, valor no repositório e valor no Manager.
Com diferença, exit `8`; sem diferença, exit `0`. O `--check` MUST NOT gravar nada, no disco nem no
Manager.

#### Scenario: Só formatação mudou
- **WHEN** o dev reordena chaves e acrescenta comentários num `resource.yaml`
- **THEN** `sen sync --check --revision 2` termina com `exit 0` e "sem diferenças"

#### Scenario: Alteração direta no Manager
- **WHEN** alguém muda o `timeout` de uma operação pela interface do Manager
- **THEN** o `--check` lista o arquivo da operação, o campo `destination.timeout`, os dois valores e termina com `exit 8`

### Requirement: Output and secrecy

A saída texto SHALL trazer API (id, nome, basePath), revisão (id e número), a pasta da carga com
as contagens de arquivos, recursos e operações, e os avisos deduplicados (sem lista de arquivos nem
próximo passo, 16/11). No `--check` a saída SHALL trazer só as diferenças: avisos de materialização
descrevem o estado da API, não a comparação, e MUST NOT aparecer (17/11). `spec.apiTags` SHALL ser
comparado como conjunto (atributo e tags), nunca por posição (17/11). Em `json`/`yaml`
a saída SHALL ser o documento `apiops.sen-sync/v1`. Nenhum token MUST aparecer em argumento, log,
saída ou arquivo gerado. Aviso MUST NOT alterar o exit code.

#### Scenario: Resumo em JSON
- **WHEN** o usuário roda `sen sync --revision 3 -o json`
- **THEN** o stdout contém só o documento `apiops.sen-sync/v1`, sem barra de progresso
