# Importador: puxar também o contrato OpenAPI para o repositório da API

> Para quem vai editar o script que puxa a API do Manager para o repositório declarativo.
> Desenho completo: change `add-openapi-contract` (APIOPS-115).

## Por que o importador precisa mudar

O `sen validate` e o `sen publish` passaram a gravar o contrato OpenAPI no swagger da revisão
a partir do repositório. Nos campos de contrato, **o repositório é a verdade**: o que ele não
declara sai da documentação do Manager na próxima subida. Além disso, `responses` passou a ser
**obrigatório** em todo arquivo de operação — sem ele o comando aborta com exit 1 antes de gravar.

Logo, o importador precisa puxar o contrato junto com o fluxo. Sem isso, o repositório puxado
não passa no `sen validate`.

O que **não muda**: o layout, os nomes de pasta e de arquivo, e tudo que já é puxado hoje
(interceptors, destinos, `inherit`, `description`, basic info). O contrato é **acréscimo**.

## Fonte

`GET /api-manager/api/v3/revisions/{revisionId}/swagger`, da mesma revisão de onde o fluxo é
puxado. A resposta é JSON.

| O GET devolve | O que fazer |
|---|---|
| `"openapi": "3.x"` | puxar o contrato (seções abaixo) |
| `"swagger": "2.0"` | **não converter**: o extrator estoura erro (ver "Swagger 2.0" abaixo) |

Medido em 2026-10-26: 11 de 40 APIs do consulting estão em Swagger 2.0.

### Swagger 2.0

Decidido em 2026-10-26: 2.0 não é tratado. O extrator estoura erro; a API só entra no fluxo
depois de migrar para OpenAPI 3.

## Onde cada campo do swagger vai no repositório

| No swagger | No repositório |
|---|---|
| `info.contact` | `api-basic-info.yaml` → `spec.contact` |
| `tags` (raiz) | `api-basic-info.yaml` → `spec.tags` (não confundir com `spec.apiTags`, que é governança e continua igual) |
| `security` (raiz) | `api-basic-info.yaml` → `spec.security` |
| `components.schemas`, `securitySchemes`, `responses`, `requestBodies`, `headers`, `examples` | **`components.yaml`** (arquivo novo, na raiz do repositório), mesmas seções e mesmo conteúdo |
| `paths.<path>.<método>.operationId`, `summary`, `tags`, `security`, `requestBody`, `responses` | arquivo da operação (`resources/<slug>/<metodo>_<path>.yaml`), mesmos nomes de campo, no mesmo nível de `path` |
| `paths.<path>.<método>.parameters` | `parameters` no arquivo da operação |
| `paths.<path>.parameters` (nível do path, compartilhado pelos métodos) | **mesclar** em `parameters` de cada operação daquele path; no mesmo `name`+`in`, vale o da operação |

`components.yaml` só é escrito se houver alguma das seis seções; ausente é válido.

### `resource.yaml` (opcional)

O orquestrador aceita `parameters` no `resource.yaml` e os copia para cada rota do recurso.
**Recomendação: não usar no importador** — escrever tudo no arquivo da operação é equivalente e
evita a regra abaixo. Se usar, só entra ali o que vale para **todas** as rotas do recurso, e
parâmetro de path só se o `{nome}` existir no template de todas elas.

## O que NÃO puxar

| Item | Motivo |
|---|---|
| `openapi`, `servers`, `info.title`, `info.version`, `info.description` | o Manager é dono; declarar `servers` ou `info` no `api-basic-info.yaml` é erro de validação |
| qualquer chave `x-*` | extensões são do Manager; `x-*` em arquivo do repositório é erro de validação. O fluxo continua vindo da revisão, como hoje |
| `components.parameters`, `components.links`, `components.callbacks` e outras seções | fora do modelo; declarar no `components.yaml` é erro |
| `description` da operação | já é puxada hoje; não muda |

## Regras para o repositório puxado passar no `sen validate`

1. **`responses` é copiado como o Manager devolve, sem placeholder** (decisão de 2026-10-26).
   Rota nunca documentada já vem do Manager com `responses: {'200': {description: OK}}` — copiar
   isso basta para passar. Se a rota vier sem `responses` no swagger, o importador não inventa:
   o `sen validate` barra aquela rota (exit 1, antes de qualquer escrita) até o dev declarar, e o
   importador deve avisar quais rotas ficaram sem `responses`.
2. **Parâmetro sempre por extenso.** Se aparecer `$ref: '#/components/parameters/X'` numa lista de
   `parameters`, substituir pelo conteúdo de `components.parameters.X` (o Manager normalmente já
   devolve expandido).
3. **`$ref` para as seis seções fica como está** (`#/components/schemas/...`, `responses`,
   `requestBodies`, `headers`, `examples`), e o componente apontado precisa estar no `components.yaml`.
4. **Status como texto:** `'200':`, não `200:`.
5. **Tipos preservados no YAML.** Texto que o YAML reinterpretaria (`2024-01-01`, `on`, `off`,
   `yes`, `no`, `012`) precisa sair entre aspas. Serializar o dict vindo do JSON com um dumper que
   preserve tipos (ex.: `yaml.safe_dump(..., allow_unicode=True, sort_keys=False)`) resolve.
6. **Nenhuma chave `x-*`**, em nenhum nível dos campos de contrato.
7. **Parâmetro de path** precisa existir no template da rota e ter `required: true` — o que vem
   do Manager já cumpre; não alterar.

O orquestrador também **avisa** (não bloqueia) descrições curtas que baixam o completeness —
por exemplo, `'200': {description: OK}` gera aviso. É esperado para rota não documentada.

## Critério de aceite: ida e volta

Puxar a API e rodar `sen validate` **sem editar nada** deve:

- não abortar por contrato (nenhum `InvalidContractError`), salvo rota que o Manager devolva sem
  `responses` ou API em Swagger 2.0;
- não listar nada em "estes itens saem da documentação da API no Manager";
- não gravar o swagger: o orquestrador compara o documento normalizado e pula o PUT quando
  nada mudou.

Diferenças que o orquestrador já tolera e o importador **não** precisa reproduzir: `style`,
`explode` e `required: false` com o valor padrão em parâmetros e headers, e a ordem da lista
`required` dos schemas.

Uma exceção conhecida: rota com `description` e sem `summary` no swagger. O orquestrador usa a
`description` como `summary`, então a primeira subida grava esse `summary`. Não é erro.

## Exemplo

Swagger (trecho):

```json
{
  "openapi": "3.0.3",
  "info": {"title": "Tarefas", "version": "1.0.0", "contact": {"name": "Time Tarefas"}},
  "servers": [{"url": "/tarefas/v1"}],
  "tags": [{"name": "Tarefas"}],
  "security": [{"TokenPortador": []}],
  "components": {
    "securitySchemes": {"TokenPortador": {"type": "http", "scheme": "bearer"}},
    "schemas": {"Tarefa": {"type": "object", "properties": {"id": {"type": "string"}}}},
    "responses": {"NaoEncontrado": {"description": "Tarefa não encontrada"}},
    "parameters": {"Expand": {"name": "expand", "in": "query"}}
  },
  "paths": {
    "/tarefas/{id}": {
      "parameters": [{"name": "id", "in": "path", "required": true, "schema": {"type": "string"}}],
      "get": {
        "summary": "Consulta uma tarefa",
        "operationId": "consultarTarefa",
        "tags": ["Tarefas"],
        "parameters": [{"$ref": "#/components/parameters/Expand"}],
        "responses": {
          "200": {"description": "Tarefa encontrada",
                  "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Tarefa"}}}},
          "404": {"$ref": "#/components/responses/NaoEncontrado"}
        },
        "x-resource-name": "Tarefas",
        "x-interceptors": {}
      }
    }
  }
}
```

Repositório puxado (só o que é novo; o resto continua como hoje):

```yaml
# api-basic-info.yaml (acréscimo em spec)
spec:
  contact:
    name: Time Tarefas
  tags:
    - name: Tarefas
  security:
    - TokenPortador: []
```

```yaml
# components.yaml (novo) — sem `parameters`
securitySchemes:
  TokenPortador:
    type: http
    scheme: bearer
schemas:
  Tarefa:
    type: object
    properties:
      id:
        type: string
responses:
  NaoEncontrado:
    description: Tarefa não encontrada
```

```yaml
# resources/tarefas/get_tarefas_{id}.yaml (acréscimo aos campos de hoje)
summary: Consulta uma tarefa
operationId: consultarTarefa
tags:
  - Tarefas
parameters:
  - name: id                # veio do nível do path
    in: path
    required: true
    schema:
      type: string
  - name: expand            # era $ref para components.parameters: escrito por extenso
    in: query
responses:
  '200':
    description: Tarefa encontrada
    content:
      application/json:
        schema:
          $ref: '#/components/schemas/Tarefa'
  '404':
    $ref: '#/components/responses/NaoEncontrado'
```

Não aparecem no repositório: `servers`, `info.title`/`version`, `x-resource-name`,
`x-interceptors` e `components.parameters`.
