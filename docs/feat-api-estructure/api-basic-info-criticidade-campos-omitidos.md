# D-002 — Criticidade dos campos não versionados

> Alinhado à [D-005](d005-layout-revisado.md) em 2026-10-14: nada aqui foi revisado — o estudo trata de campos do basic info, que a D-005 não alterou (exceto o regime de `spec.template`, em `api-basic-info-campos.md`).


**Status:** Validação empírica concluída em 2026-09-28 com a API 405.

## Pergunta avaliada

Se um campo não aparecer no `api-basic-info.yaml`, o orquestrador pode deixá-lo de fora do payload ou precisa recuperar e reapresentar o valor remoto?

## Resposta curta

Depende do campo. O Manager apresentou três comportamentos diferentes:

1. **Obrigatório no payload:** omitir causa HTTP 400.
2. **Opcional e preservado:** pode ser omitido; o Manager conserva o valor atual.
3. **Opcional e destrutivo:** o write é aceito, mas o valor é apagado ou alterado.

Portanto, “não versionar no Git” e “não enviar ao Manager” são decisões independentes.

## Ambiente do ensaio

- API: `405 — docs-demo-api`.
- Autenticação: endpoint LEGACY documentado, Basic para gerar Bearer, com scope `apis/all`.
- Revisão criada para o teste: revisão 3, ID `9089`.
- Revisão 3: três resources, seis interceptors e nenhum deployment.
- Revisão implantada no Default permaneceu sendo a revisão 2, ID `8986`.
- Cada caso foi executado isoladamente e seguido de PUT com o objeto completo para restauração.
- Nenhum deploy foi executado.

### Correção metodológica

As primeiras tentativas com `Invoke-WebRequest`/`Invoke-RestMethod` reportaram 400 sem corpo. O mesmo token e o mesmo payload, enviados por `System.Net.Http.HttpClient`, produziram:

- `PUT /revisions/8986` → 200 `{"result":"success"}`;
- `POST /revisions` → 201 `{"id":9089}`.

Logo, a credencial estava correta e não era necessário cookie/XSRF para este fluxo. Os resultados provisórios que atribuíam a falha ao perfil de autenticação foram descartados.

## Baseline antes do teste

| Grupo | Valor observado |
|---|---|
| Responsável | ID 1133, username `jean.silva`, `groupName` vazio |
| Adaptive Governance | `My new: Tag1` |
| Tags simples | Lista vazia |
| Visibilidade | `GROUP`, grupo `APIOps`, owner `jean.silva` |
| Usuários adicionais | ID 7, username `paulo.silva` |
| Portal | `showAppRegister: true`, `showApiBrowser: false`, ID 829 |
| Plano | `68 — docs-demo-plan` |
| Ambientes | Default, DEV-APIOPS e HMG-APIOPS |
| Flags | `apiType: REST`, `identityApi: false`, `privateAPI: false`, `lastVersion: false` |

## Resultado campo a campo

### Obrigatórios no payload

| Campo | Ensaio | Resultado |
|---|---|---|
| `visibility` | Propriedade inteira omitida | HTTP 400 `Invalid fields in request` |
| `apiType` | Propriedade omitida | HTTP 400 `Invalid fields in request` |
| `creationDate` | Propriedade omitida | HTTP 400 `Invalid fields in request` |

Esses campos podem continuar fora do YAML, mas precisam ser hidratados a partir do GET remoto antes do write.

### Omitidos e preservados pelo Manager

| Campo/grupo omitido | Resultado do PUT | Estado após GET |
|---|---|---|
| `apiSwaggerConfiguration` | 200 | `showAppRegister: true` e `showApiBrowser: false` preservados |
| `plans` | 200 | Plano 68 preservado |
| `environments` | 200 | Os três ambientes preservados |
| `revisions` + `lastRevision` | 200 | Revisões e última revisão preservadas |
| `identityApi` | 200 | `false` preservado |
| `privateAPI` | 200 | `false` preservado |
| `lastVersion` | 200 | `false` preservado |
| `appsCount` | 200 | `0` preservado |
| `tags` | 200 | Lista vazia preservada na API 405 |

Também foi testado `environments: []`, como o CLI envia hoje. O Manager preservou os três ambientes.

### Omitido e apagado

| Campo | Resultado do PUT | Estado após GET |
|---|---|---|
| `apiTags` | 200 | Lista passou de `My new: Tag1` para vazia |

`apiTags` precisa ser enviado explicitamente. Como o usuário decidiu versioná-lo, o valor do manifesto deve vencer. Se o campo opcional estiver ausente no manifesto, precisamos decidir entre preservar o remoto e interpretar ausência como remoção; omitir silenciosamente hoje equivale a apagar.

## Casos próximos ao comportamento atual do CLI

### `visibility` reduzida

Payload enviado:

```yaml
visibility:
  visibilityType: GROUP
  groupVisibility:
    name: APIOps
```

O PUT foi aceito, mas `visibility.users[]` ficou vazio. O `owner` foi preservado pelo Manager. Após a restauração, `paulo.silva` voltou a aparecer.

**Conclusão:** `visibility` é obrigatória e não pode passar pelo model reduzido atual. Deve ser copiada integralmente do GET, pois o model atual remove acessos de usuários.

### Defaults de `apiSwaggerConfiguration`

Payload enviado pelo comportamento atual:

```yaml
apiSwaggerConfiguration:
  showAppRegister: false
  showApiBrowser: false
```

O PUT foi aceito e provocou duas alterações:

- `showAppRegister` mudou de `true` para `false`;
- `privateAPI` mudou de `false` para `true`.

O restore recuperou ambos os valores.

**Conclusão:** como o Manager preserva a configuração quando a propriedade inteira é omitida, o CLI deve omiti-la, e não enviar defaults.

### `apiResponsible` sem ID

Enviar somente `username` e `groupName` foi aceito. O Manager resolveu o usuário, mas gerou novo ID interno.

Os IDs de responsável, usuário e configuração de portal também mudaram durante round-trips completos. Eles são IDs de registros internos recriados/normalizados no write, não identidades estáveis para versionamento.

**Conclusão:** manter no YAML apenas `username` e `groupName`; não versionar os IDs internos.

### Revisões reduzidas

Enviar `revisions` e `lastRevision` no formato reduzido do CLI foi aceito e não causou perda visível no GET. Ainda assim, como a omissão completa também é aceita e preservada, o comportamento mais simples e seguro é não reenviar esses campos.

## Classificação final

| Categoria | Campos | Tratamento no orquestrador |
|---|---|---|
| Obrigatórios, não versionados | `visibility`, `apiType`, `creationDate` | Copiar integralmente do GET; nunca aplicar defaults |
| Versionado e necessário | `apiTags` | Enviar valor do manifesto; definir semântica explícita para ausência versus `[]` |
| Seguros para omissão | `plans`, `environments`, `revisions`, `lastRevision`, `apiSwaggerConfiguration`, `identityApi`, `privateAPI`, `lastVersion`, `appsCount` | Não incluir no payload; Manager preserva |
| Condicionalmente seguro | `tags` | Omitir preservou `[]`; repetir com valor não vazio antes de generalizar |
| IDs internos | IDs de responsável, usuário, visibility e portal | Não versionar nem validar imutabilidade; o Manager pode regenerá-los |
| Ausentes na fixture | `swaggerType`, `releaseNotes`, `lastUpdate`/`updateDate` | Não versionar; sem conclusão empírica de wire |

## Regra de implementação fechada

O publicador não deve mais montar `api` serializando `ApiPartialInfo` com defaults. Deve construir explicitamente o payload mínimo aceito:

```text
api.id                  = manifesto (somente leitura, validado contra o GET)
api.name                = manifesto
api.version             = manifesto
api.basePath            = manifesto
api.description         = manifesto
api.apiResponsible      = manifesto (username + groupName)
api.apiTags             = manifesto
api.tags                = manifesto, enquanto mantido no contrato
api.visibility          = GET remoto completo
api.apiType             = GET remoto
api.creationDate        = GET remoto
```

Não enviar:

- `apiSwaggerConfiguration` com defaults;
- `environments: []` apenas por exigência do model;
- `revisions`/`lastRevision` reduzidos;
- flags e campos calculados que o Manager já preserva quando omitidos.

## Estado deixado para reset posterior

O usuário solicitou que o reset seja feito somente quando indicado. Estado final após os ensaios:

- revisão 3, ID `9089`, é a `lastRevision`;
- revisão 3 não está implantada;
- revisão 2, ID `8986`, continua implantada no Default;
- `My new: Tag1` restaurada;
- visibilidade `GROUP/APIOps`, owner `jean.silva` e usuário `paulo.silva` restaurados;
- `showAppRegister: true`, `privateAPI: false`, plano 68 e três ambientes preservados;
- IDs internos foram regenerados durante os writes e não retornaram aos números originais.