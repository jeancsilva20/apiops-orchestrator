# D-002 — Exemplo e validação da hidratação no publish

> Alinhado à [D-005](d005-layout-revisado.md) em 2026-10-14: a hidratação validada aqui continua valendo e passou a conviver com a **preservação do estado não governado** (D-005 §8).


**Status:** Evidência coletada em 2026-09-28; correções de implementação pendentes.

## Objetivo

Validar o formato candidato de `api-basic-info.yaml` com a API 400 e confirmar se o orquestrador atual busca no Manager os campos não versionados e os reaplica sem alterá-los ao publicar.

Foram usados:

- `GET /api-manager/api/v3/apis/400`, apenas para leitura;
- inspeção de `RepoImporterService`, `ConversorService`, `ApiPartialInfo`, `ApiRevision` e `PublisherService`;
- testes unitários de `PublisherService` (`4 passed`).

Nenhum `POST`, `PUT`, `PATCH`, deploy ou outra operação de escrita foi executado.

## Exemplo resultante

O arquivo candidato está em [api-basic-info-exemplo-api-400.yaml](api-basic-info-exemplo-api-400.yaml). Ele contém somente os campos marcados para permanência na worksheet:

```yaml
apiVersion: api-management.sensedia.com/v1
kind: ApiBasicInfo
spec:
  id: 400
  name: Orchestrator Auth API
  version: 1.0.1
  basePath: /orq-auth/v1
  description: Auth API.
  apiResponsible:
    username: paulo.silva
    groupName: ""
  apiTags:
    - attributeName: My new
      tags:
        - Tag1
  tags: []
```

`identityApi` não foi incluído porque sua decisão permanece aberta.

Este é o contrato-alvo, não o comportamento já suportado integralmente: o schema atual ainda não declara `apiTags` e `tags` nesse shape, e o conversor atual não respeita o `id` nem as tags lidas do arquivo.

## YAML declarativo versus payload efetivo

O exemplo YAML **não deve** conter todos os campos exigidos pelo endpoint de revisão. Ele registra apenas o que pertence ao contrato do repositório.

No publish, o payload é composto por duas fontes:

```text
api-basic-info.yaml + GET remoto da API → payload efetivo de revisão
```

| Campo | Fica no YAML? | Fonte no payload efetivo |
|---|---|---|
| `id`, `name`, `version`, `basePath`, `description` | Sim | Manifesto; `id` é validado como somente leitura |
| `apiResponsible.username/groupName` | Sim | Manifesto |
| `apiTags` e, enquanto aprovado, `tags` | Sim | Manifesto |
| `visibility` completo | Não | GET remoto; obrigatório no PUT |
| `apiType` | Não | GET remoto; obrigatório no PUT |
| `creationDate` | Não | GET remoto; obrigatório no PUT |
| Planos, ambientes, histórico, flags e dados calculados | Não | Omitidos do payload quando o Manager os preserva |

Portanto, a ausência de `visibility`, `apiType` e `creationDate` no YAML é intencional. O erro está no publicador se esses campos não forem hidratados no payload, não no layout declarativo.

## Resultado da validação

A premissa de que “todo campo ausente é copiado de forma oculta e mantido com o valor atual” **não corresponde à implementação atual**. A hidratação é explícita, parcial e, em alguns pontos, destrutiva.

A investigação posterior com a API 405 confirmou também que **o contrato sparse não pode ser assumido como válido**. Consulte [api-basic-info-criticidade-campos-omitidos.md](api-basic-info-criticidade-campos-omitidos.md) para o baseline com tags/time, a matriz de criticidade e os ensaios de escrita.

| Campo ou grupo | Comportamento atual antes do publish | Resultado para a API 400 |
|---|---|---|
| `id` | Removido pelo importador e substituído por `Settings.API_ID` no conversor | O `400` do arquivo não é a fonte efetiva |
| `name`, `version`, `basePath`, `description` | Vêm do repositório | São editáveis pelo arquivo |
| `apiResponsible.username/groupName` | Vêm do repositório | Mantidos conforme o arquivo |
| `apiResponsible.id` | Não existe no model de saída | O valor remoto `1126` não é copiado para o payload |
| `apiTags` | Ignorado no arquivo e substituído por variáveis `API_TAGS_*` | `My new: Tag1` só permanece se estiver duplicado no ambiente |
| `tags` | Não existe no model de saída | Não é enviado |
| `creationDate` | Copiado integralmente do GET | Preservado no payload |
| `visibility` | Copiado por um model reduzido | Preserva `visibilityType` e `groupVisibility.name`; perde `id`, `owner` e `users` |
| `apiSwaggerConfiguration` | Não é copiado; o model injeta defaults | `showAppRegister: true` vira `false`; o `id` e a lista de ambientes desaparecem |
| `apiType` | Não é copiado; o model injeta `REST` | Coincide com a API 400, mas não foi preservado do GET |
| `environments` | Não é copiado; o model usa `[]` | Os 3 ambientes retornados não são reenviados nesse bloco |
| `revisions` e `lastRevision` | São convertidos para `ApiRevision` | Recursos, interceptors e deployments são forçados para `[]`; `apiBroken` é forçado para `false` |
| `workflowId` e `workflowStageId` | Copiados da última posição de `revisions` | Hidratados no objeto raiz da revisão a publicar |
| `swaggerType`, `releaseNotes`, `identityApi`, `privateAPI`, `lastVersion`, `appsCount`, `plans`, `lastUpdate` | Não existem no model de saída e não são hidratados | Não são enviados no payload montado pelo CLI |

### Evidência posterior de escrita

Na API 405, o round-trip via Bearer foi confirmado com sucesso: PUT denso retornou 200 e POST criou a revisão 3, ID 9089, sem deploy. Os testes leave-one-out identificaram campos obrigatórios, preservados e destrutivos.

O risco do código atual também foi comprovado: visibilidade reduzida removeu `users[]`; defaults de `apiSwaggerConfiguration` alteraram `showAppRegister` e `privateAPI`; a omissão de `apiTags` apagou as tags. Todos os valores funcionais foram restaurados ao final. A matriz definitiva está em [api-basic-info-criticidade-campos-omitidos.md](api-basic-info-criticidade-campos-omitidos.md).

## Decisão de desenho necessária

Para cumprir a regra desejada, a implementação deve distinguir três categorias:

1. **Versionado e editável:** valor do repositório vence.
2. **Versionado e somente leitura:** valor do repositório identifica o alvo, mas deve ser conferido contra o Manager e não pode ser alterado pelo usuário.
3. **Não versionado:** valor atual deve ser copiado integralmente do GET para o payload, sem defaults locais e sem redução por models parciais, quando o contrato do endpoint exigir o campo.

Essa mudança deve ser feita antes de considerar D-002 implementada. Apenas retirar campos do YAML, mantendo o publicador atual, não garante preservação.

## Evidência concreta da API 400

O GET retornou, entre outros dados não versionados:

- `identityApi: false`;
- `apiType: REST`;
- `privateAPI: false`;
- `lastVersion: false`;
- `appsCount: 4`;
- 1 plano, 3 ambientes e 4 revisões;
- `apiSwaggerConfiguration.showAppRegister: true`;
- visibilidade do tipo `GROUP`, com grupo, owner, users e identificadores internos.

Esses valores servem como fixture para os futuros testes de preservação sem que seja necessário gravá-los no `api-basic-info.yaml`.