# D-002 — Worksheet de campos do `api-basic-info.yaml`

**Status:** Fechamento parcial pela [D-003](d003-layout-repo.md) (2026-09-29), **alinhado à [D-005](d005-layout-revisado.md)** (2026-10-14: regime de `spec.template`) — shape `spec.<campo>` confirmado; `spec.template` incluído; regime de `apiResponsible` redefinido (presente no YAML, hidratado no import, read-only no MVP); `tags[]` simples e `identityApi` fechados em 2026-09-29 com varredura read-only de 110 APIs ([evidência](evidencia-tags-e-atributos.md)); regime de escalares fechado (ausente=preserva, `""`=limpa, `null` proibido). Hidratação validada na API 405.

Esta worksheet será usada para decidir o contrato mínimo e declarativo de `api-basic-info.yaml`. Ela reúne campos dos layouts candidatos, do modelo atual do CLI, dos payloads documentados de criação e de GETs read-only realizados no Manager.

## Como preencher

- Marque exatamente uma opção em cada coluna booleana, trocando `[ ]` por `[x]`.
- Em **Origem**, use preferencialmente: `Usuário`, `Orquestrador`, `Manager`, `Derivado` ou uma combinação explícita.
- **Manter?** significa versionar o campo em `api-basic-info.yaml`, não apenas utilizá-lo internamente no payload enviado ao Manager.
- **Obrigatório?** refere-se ao arquivo no Git. Um campo necessário apenas no payload remoto pode ser hidratado pelo orquestrador e continuar ausente do arquivo.
- **Editável?** refere-se ao usuário comum. Campos alteráveis somente por bootstrap, migração ou outra operação administrativa devem ser marcados como não editáveis e explicados após a tabela.

## Identidade e catálogo

| Campo | Manter? | Obrigatório? | Editável? | Origem |
|---|---|---|---|---|
| `spec.id` | [x] Sim · [ ] Não | [x] Sim · [ ] Não | [ ] Sim · [x] Não | Manager, gravado pelo Orquestrador |
| `spec.name` | [x] Sim · [ ] Não | [x] Sim · [ ] Não | [x] Sim · [ ] Não | |
| `spec.version` | [x] Sim · [ ] Não | [x] Sim · [ ] Não | [x] Sim · [ ] Não | |
| `spec.basePath` | [x] Sim · [ ] Não | [x] Sim · [ ] Não | [ ] Sim · [x] Não | |
| `spec.description` | [x] Sim · [ ] Não | [x] Sim · [ ] Não | [x] Sim · [ ] Não | |
| `spec.apiType` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.swaggerType` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.releaseNotes` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.identityApi` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [x] Não | Manager, opaco; omitido no PUT foi preservado (405); 0/110 com `true` — decisão 2026-09-29 |
| `spec.privateAPI` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.lastVersion` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |

## Responsabilidade

| Campo | Manter? | Obrigatório? | Editável? | Origem |
|---|---|---|---|---|
| `spec.apiResponsible.username` | [x] Sim · [ ] Não | [x] Sim · [ ] Não | [ ] Sim · [x] Não | |
| `spec.apiResponsible.groupName` | [x] Sim · [ ] Não | [x] Sim · [ ] Não | [ ] Sim · [x] Não | |
| `spec.apiResponsible.id` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.apiResponsible.userOrGroup.id` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.apiResponsible.userOrGroup.email` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |

## Visibilidade e acesso ao catálogo

| Campo | Manter? | Obrigatório? | Editável? | Origem |
|---|---|---|---|---|
| `spec.visibility.visibilityType` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.visibility.groupVisibility.name` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.visibility.groupVisibility.id` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.visibility.owner` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.visibility.users[].username` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.visibility.users[].id` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.visibility.id` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |

## Portal e documentação

| Campo | Manter? | Obrigatório? | Editável? | Origem |
|---|---|---|---|---|
| `spec.apiSwaggerConfiguration.showAppRegister` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.apiSwaggerConfiguration.showApiBrowser` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.apiSwaggerConfiguration.id` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.apiSwaggerConfiguration.apiSwaggerConfigurationEnvironments[]` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |

## Atributos e classificações

| Campo | Manter? | Obrigatório? | Editável? | Origem |
|---|---|---|---|---|
| `spec.apiTags[].attributeName` | [x] Sim · [ ] Não | [ ] Sim · [x] Não | [x] Sim (replanta o par; nome deve existir no catálogo AG) · [ ] Não | Orquestrador/do usuário via YAML; catálogo nasce no AG ([evidência](evidencia-tags-e-atributos.md)) |
| `spec.apiTags[].tags[]` | [x] Sim · [ ] Não | [ ] Sim · [x] Não | [x] Sim · [ ] Não | |
| `spec.tags[]` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [x] Não | Suprimido 2026-09-29: 0/110 APIs com uso; omissão preserva | |

## Estado operacional retornado pelo Manager

Estes campos aparecem em respostas do Manager, mas não são automaticamente candidatos ao versionamento. Devem ser avaliados para que sua exclusão também fique explícita.

| Campo | Manter? | Obrigatório? | Editável? | Origem |
|---|---|---|---|---|
| `spec.creationDate` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.lastUpdate` / `spec.updateDate` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.appsCount` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.plans[]` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.environments[]` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.revisions[]` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |
| `spec.lastRevision` | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |

## Campos adicionais

Use esta seção para campos necessários que não aparecem no inventário acima.

| Campo | Manter? | Obrigatório? | Editável? | Origem |
|---|---|---|---|---|
| `spec.template` | [x] Sim · [ ] Não | [x] Sim · [ ] Não | [ ] Sim · [x] Não | Binding à API-régua de interceptors; **não existe no wire** — 8 confirmações de ausência (D-005 §7) |
| ~~`spec.tags[]`~~ | [ ] Sim · [x] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | Suprimido (D-003 §3, refinamento 2026-09-29) |
|  | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | [ ] Sim · [ ] Não | |

## Observações para o fechamento

- ~~Definir se o shape final será `spec.<campo>` ou `spec.api.<campo>`.~~ **FECHADO (D-003): `spec.<campo>` direto.**
- ~~Definir como a imutabilidade de `spec.id` será verificada.~~ **FECHADO (D-001/D-003): validador bloqueia alteração; `readOnly` permanece como anotação documental.**
- ~~Definir se campos opcionais ausentes serão omitidos ou materializados com `null`, string vazia ou lista vazia.~~ **FECHADO (D-003): para listas — ausente preserva, `[]` remove (apiTags, interceptors). Para escalares — ausente preserva, `""` limpa, `null` proibido no schema (refinamento 2026-09-29).**
- Definir se atributos do Adaptive Governance pertencem a este arquivo ou a um manifesto separado. **Pendente de produto.**
- Após o preenchimento, confrontar os campos mantidos com o payload mínimo aceito pelo Manager e com os models/schemas do CLI.

## Régua de regimes por campo (D-003)

| Campo | Regime |
|---|---|
| `spec.id`, `spec.basePath` | Presente no YAML; readOnly; imutável (bloqueio no validador) |
| `spec.name`, `spec.version`, `spec.description` | Obrigatório; editável normalmente |
| `spec.template` | **Chave sempre declarada; valor pode ser vazio** (`''` = sem régua, validação não roda). Valor = id numérico da API-régua (hoje 414). Em esteira, o valor vem de variável de ambiente e o YAML é ignorado (**D-005 §7**) |
| `spec.apiResponsible.username/.groupName` | Presente no YAML; hidratado no import; read-only no MVP (sem update via CLI) |
| Escalares opcionais (ex.: `groupName`) | Ausente = preserva; `""` = limpa explicitamente; `null` proibido no schema |
| `spec.apiTags` | Editável; lista declarativa completa; ausente = preserva remoto; `[]` = remove explicitamente |
| `spec.apiTags[].attributeName` | Referencia catálogo de Attributes do AG; replantável via YAML, mas o nome deve existir no catálogo |
| `spec.tags[]` simples | Suprimido do YAML e do payload; omissão preserva o remoto |
| `identityApi` | Nunca no YAML, nunca no payload; Manager preserva quando omitido |
| Campos de fundo (visibility, apiType, creationDate, revisões, flags, contadores) | Nunca no YAML; hidratação via GET no publish |

## Evidências após o preenchimento

- Exemplo candidato baseado no GET read-only da API 400: [api-basic-info-exemplo-api-400.yaml](api-basic-info-exemplo-api-400.yaml).
- Validação do comportamento de publicação atual: [api-basic-info-validacao-publicacao.md](api-basic-info-validacao-publicacao.md).
- Criticidade dos campos omitidos, com baseline da API 405: [api-basic-info-criticidade-campos-omitidos.md](api-basic-info-criticidade-campos-omitidos.md).
- Resultado central: o publicador atual não copia genericamente todos os campos necessários. `visibility`, `apiType` e `creationDate` são obrigatórios; `apiTags` é apagado quando omitido; vários outros campos podem ser omitidos e são preservados pelo Manager.
- Regra validada: hidratar integralmente `visibility`, copiar `apiType` e `creationDate`, enviar `apiTags` do manifesto e omitir campos preservados pelo Manager em vez de serializar defaults locais.

## Esclarecimento — `identityApi` (FECHADO em 2026-09-29)

O campo é um booleano retornado pelo Manager, mas não aparece no formulário candidato nem no payload de criação documentado localmente. A investigação empírica encontrou:

- API 400 (`Orchestrator Auth API`): `identityApi: false`;
- listagem de 110 APIs do tenant: nenhum exemplo com `identityApi: true`;
- nenhuma definição funcional do campo nas fontes locais ou na documentação pública consultada.

**Decisão fechada (responsável, 2026-09-29):** `Manter? Não` — campo opaco do Manager; não vai ao YAML e não vai ao payload montado. Base da prova de preservação: na API 405, `identityApi` foi omitido em um PUT aceito e permaneceu `false` — o endpoint não exige sua reapresentação. O comportamento de `identityApi: true` segue sem exemplo real (residual, sem impacto no contrato declarativo).
