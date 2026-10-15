# Feature — Estrutura de Repositório de API

| Meta | Valor |
|---|---|
| Data de início | 2026-09-28 |
| Estado | Layout fechado (D-003) e **revisado pela D-005** (2026-10-14); implementação pendente |
| Objetivo | Definir o layout final de uma API consumida pelo APIOps Orchestrator |
| Fontes principais | `arquitetura-apiops-memory-bank/`, `mapeamento APIM/`, `apiestructure/`, `api-gateway/` e implementação atual do CLI |

> Este documento registra incrementalmente as questões discutidas e as decisões fechadas durante o refinamento. Uma decisão fechada não significa que seus impactos de código e migração já foram implementados.

## Refinamentos em andamento

- **Resumo consolidado:** [exploração, decisões e pendências](resumo-exploracao.md).
- **Fontes e evidências:** [inventário rastreável das referências usadas](fontes-e-evidencias.md).
- **Interceptors e rotas:** [achados, gaps do CLI e questões ainda abertas](interceptors-e-rotas-levantamento.md).
- **D-002 — Contrato de `api-basic-info.yaml`:** [worksheet para classificação dos campos](api-basic-info-campos.md), [exemplo da API 400](api-basic-info-exemplo-api-400.yaml), [validação da hidratação no publish](api-basic-info-validacao-publicacao.md) e [criticidade dos campos omitidos com a API 405](api-basic-info-criticidade-campos-omitidos.md).
- **D-003 — Layout canônico do repositório:** [árvore, moldes de YAML e ciclo de vida](d003-layout-repo.md), fechado em 2026-09-29 a partir da reunião "[APIOps] Dúvidas Estrutura" (2026-09-28) e do grill de definição do layout.
- **Evidência de tags/atributos (2026-09-29):** [varredura read-only de 110 APIs](evidencia-tags-e-atributos.md) — fechou `tags[]`, `identityApi` e o regime de `apiTags[].attributeName`.
- **Padrão de exemplos anotados (2026-09-29):** [norma](padrao-exemplos-anotados.md) — arquivo fechado no refinamento ganha exemplo completo, comentado campo a campo (função, obrigatório, readOnly, regime de omissão, origem). Desde a D-005, o exemplo vivo é o layout materializado a partir de APIs reais em [`decisoes-refino-409/exemplos-gerados/`](decisoes-refino-409/exemplos-gerados/README.md).
- **D-005 — Layout revisado (2026-10-14):** [consolidacao do refino das APIs 409/417](d005-layout-revisado.md) — arvore por recurso, `destination`/`timeout` por escopo, `inherit`, estado nao governado, regua 414 e publish em revisao fixa. Decisoes item a item em [`decisoes-refino-409/`](decisoes-refino-409/README.md); layout materializado em 6 APIs reais em [`decisoes-refino-409/exemplos-gerados/`](decisoes-refino-409/exemplos-gerados/README.md).
- **Fila de templates/schemas (2026-09-29):** [inventário dos desalinhados + ordem](fila-templates-schemas.md) — alimentação da change proposal OpenSpec ( schemas e models alinhados a D-003).

## Cobertura do objetivo original

| Tema | Situação documental | Situação decisória |
|---|---|---|
| Identidade e `bindings.json` | Documentado em D-001 abaixo | Fechado |
| Campos de basic info e hidratação | Documentado na série D-002 | Fechado em 2026-09-29 (resto: separação do Adaptive Governance, pendente de produto) |
| Representação de interceptor | Fechado em D-003 | Fechado |
| Escopos revision/resource/operation | D-003 + **D-005 §3**: os três escopos carregam `destination`/`timeout` e flows; herança por substituição | Fechado |
| Rotas com flows diferentes | D-003 + **D-005 §6**: `inherit: true|false`, declarado sempre | Fechado |
| Layout completo da árvore | Fechado em D-003 | Fechado |

## Registro de decisões

### D-001 — Identidade da API e remoção do `bindings.json`

**Status:** Fechada em 2026-09-28.

#### Contexto

O exemplo `api-gateway/` possui um `bindings.json` na raiz com a intenção de vincular o repositório a uma API física do Sensedia API Manager:

```json
{
  "$schema": "./schemas/binding.schema.json",
  "platform": "sensedia",
  "api_id": 386,
  "metadata": {
    "managed_by": "apiops-orchestrator",
    "customer": "mag",
    "last_synced": "2026-04-24T12:46:09.290Z",
    "do_not_edit": true
  }
}
```

A inspeção do CLI mostrou que esse arquivo não é lido pela implementação atual. O alvo das chamadas ao Manager vem de `Settings.API_ID`, enquanto o `bindings.json` existe apenas como precedente documental. O schema indicado pelo campo `$schema` também não existe no projeto.

Uma consulta read-only ao Manager mostrou ainda que o `api_id` registrado no exemplo não corresponde à API descrita pelos demais artefatos no contexto autenticado atual. A divergência reforçou o risco de manter duas fontes para a identidade da API.

#### Pontos questionados

1. O `bindings.json` é necessário para o funcionamento do orquestrador?
2. Onde deve residir o identificador físico da API no Manager?
3. É necessário registrar o tenant se o token já é individual e restrito ao tenant?
4. É necessário registrar o provider se o orquestrador suporta somente a plataforma Sensedia?
5. `apiName` e `basePath` deveriam ser duplicados no binding?
6. Metadados como `lastSynced`, `doNotEdit` e `managedBy` produzem algum comportamento efetivo?
7. O `$schema` do binding precisa ser mantido ou ajustado em alguma API externa?

#### Decisão fechada

1. O arquivo `bindings.json` será removido do layout final.
2. O identificador da API permanecerá em `api-basic-info.yaml`, no campo `spec.id`.
3. `spec.id` será um valor gerenciado pelo orquestrador e somente leitura para o usuário comum.
4. O tenant não será persistido no repositório. O token utilizado na execução já determina e restringe o tenant.
5. O provider não será persistido. O orquestrador é específico da plataforma Sensedia.
6. `name` e `basePath` permanecem exclusivamente em `api-basic-info.yaml`.
7. `lastSynced`, `doNotEdit` e `managedBy` serão removidos junto com o binding.
8. O `$schema` do binding será removido. Ele era apenas uma referência local de JSON Schema e não possui relação com uma API externa do Manager.
9. Não haverá arquivo substituto para o `bindings.json`.

O formato de identidade aprovado fica assim:

```yaml
apiVersion: api-management.sensedia.com/v1
kind: ApiBasicInfo
spec:
  id: 231
  name: API CEP
  version: v1
  basePath: /api.cep/v1
  description: API para consulta de CEP
```

#### Consequências

- `api-basic-info.yaml` passa a ser a única fonte versionada da identidade e das informações básicas da API.
- Não haverá precedência ou reconciliação entre `bindings.json`, `API_ID` e `api-basic-info.yaml`, pois o binding deixa de existir.
- A restrição do tenant continuará sendo responsabilidade da credencial usada pelo orquestrador.
- A ausência de múltiplos providers elimina a necessidade de um discriminador de plataforma no repositório.
- O ID não é segredo, mas sua alteração representa uma tentativa de redirecionar o repositório para outra API e deve ser bloqueada pelo processo de validação.

#### Impactos de implementação pendentes

- Remover `bindings.json` dos templates, exemplos, arquétipos e documentação ativa.
- Manter `spec.id` obrigatório no schema de `ApiBasicInfo` e adicionar `readOnly: true` como anotação documental.
- Implementar a imutabilidade de `spec.id` no validador/pipeline; `readOnly` em JSON Schema, sozinho, não bloqueia alterações.
- Deixar de remover o ID durante a normalização do `api-basic-info.yaml`.
- Deixar de injetar `Settings.API_ID` no conversor.
- Fazer comandos vinculados ao repositório obterem o alvo a partir de `spec.id`.
- Reavaliar a obrigatoriedade da variável de ambiente `API_ID` para esses comandos.
- Prever, fora do fluxo comum, um mecanismo administrativo explícito caso seja necessário reassociar um repositório a outra API.

#### Evidências consultadas

- `api-gateway/bindings.json`
- `api-gateway/artifacts/Templates/api-basic-info.yaml`
- `apiestructure/main/api-info/api-basic-info.yaml`
- `CLI/apiops-orchestrator/src/apiops_orchestrator/config/settings.py`
- `CLI/apiops-orchestrator/src/apiops_orchestrator/application/services/repo_importer_service.py`
- `CLI/apiops-orchestrator/src/apiops_orchestrator/application/services/conversor_service.py`
- `CLI/apiops-orchestrator/src/apiops_orchestrator/main.py`

### D-003 — Layout canônico do repositório de API

**Status:** Fechada em 2026-09-29.

**Entradas:** reunião "[APIOps] Dúvidas Estrutura" (2026-09-28, com Paulo de Oliveira, Augusto Vial Bilibio e Isaac Machado) e grill de definição do layout (2026-09-29). Especificação completa, moldes de YAML, regras de import/publish e impactos de implementação em [d003-layout-repo.md](d003-layout-repo.md).

#### Decisões alinhadas na reunião

1. **Templates canônicos no Manager (Golden Path):** template e schema deixam de existir no repositório; a plataforma guarda o template de API e o APIOps apenas referencia e valida por GET. Aprovação unânime.
2. ~~**Override total via booleano**~~ → **revisado pela D-005 §6**: `inherit: true|false`, declarado sempre; ausente ≡ `true`. A remoção seletiva (tombstone) continua sem gramática — item V-25.
3. **Herança por busca ascendente:** pasta da operação → pasta do recurso → template canônico (único obrigatório). Nearest-parent vence; não há merge de deltas.
4. **Tags visuais por execution point:** `interceptors_request` / `interceptors_response` substituem `executionPoint` no YAML.

#### Decisões adicionais fechadas no grill

1. O binding ao template vive em `api-basic-info.yaml`, no campo `spec.template`.
2. Descoberta recursiva por `resources/<slug-do-recurso>/` (**D-005 §4**); `resources.yaml` não existe no layout final.
3. Uma operação por arquivo em `{resource}/{metodo}_{parametros}.yaml`; colisões de nome são erro de validação.
4. Revisions não existem no repositório: a esteira indica a revision-alvo (uma por ambiente), conforme premissa do memory bank.
5. Ordem da lista substitui `position` no YAML; posição é calculada apenas no payload.
6. `content` é objeto YAML tipado; string JSON apenas no adapter.
7. `status` sai do YAML; a gramática do tombstone segue aberta (V-25) — `inherit: false` sinaliza a quebra, sem expressar o item removido.
8. Custom interceptors são referenciados por ID numérico por ora; portabilidade cross-tenant fica planejada para depois.
9. ~~Sem `override: true`… substituem integralmente.~~ → **D-005 §6**: `inherit: true` soma ao herdado; `inherit: false` declara o fluxo que vale.
10. OpenAPI não é versionado neste momento; methods/paths vêm exclusivamente dos arquivos de resource/operation.
11. ~~`resource.yaml` é mapa leve~~ → **D-005 §3**: ganha `destination`, `timeout`, `inherit` e listas próprias.
12. `api-basic-info.yaml` fica na raiz do repositório.
13. `apiTags` ausente preserva as tags remotas; `apiTags: []` remove explicitamente.
14. `apiResponsible` (username/groupName) é presente no YAML, hidratado no import e read-only no MVP.
15. Shape direto `spec.<campo>` confirmado.
16. ~~Importação usa heurística diff-vs-template…~~ → **D-005 §8**: o diff é contra o fluxo da própria revision, compara `content`, usa sequência e falha alto no item governado não representável.

#### Consequências e estacionados

Ver as seções 7 e 8 de [d003-layout-repo.md](d003-layout-repo.md): itens estacionados e a fila de impactos de implementação. Esta decisão supersede parcialmente o baseline do levantamento de interceptors (níveis de revision e o papel do `resources.yaml`).

#### Refinamento de campos do basic info (2026-09-29)

Incremento de D-003 §3/§7/§8 a partir do refinamento com o responsável e de [varredura read-only de 110 APIs](evidencia-tags-e-atributos.md) (método: sessão do CLI → validate → admin token; apenas GET; zero erros; zero writes):

1. **Escalares opcionais:** ausente = preserva remoto; `""` = limpa explicitamente; `null` proibido no schema (simetria com a régua de listas).
2. **`spec.tags[]` simples:** suprimido do YAML e do payload — zero usos em 110 APIs; omissão preserva o valor remoto.
3. **`identityApi`:** não versionar e não enviar — campo opaco; omissão aceita e preservada na API 405; decisão do responsável.
4. **`apiTags`:** lista declarativa completa (ausente preserva; `[]` remove). `attributeName` referencia o catálogo de Attributes do Adaptive Governance: editar `tags[]` redefine valores; trocar `attributeName` replanta o par via PUT (comprovado que o PUT da revision muta os bindings, contrariando a nota antiga de rota assinada). Atributos novos nascem no produto AG, nunca no repo.

Com isso, a worksheet D-002 fecha exceto pela separação do Adaptive Governance (pendente de produto) e pelos fluxos administrativos estacionados.

#### Padrão de exemplos anotados (2026-09-29)

Decisão de conformação com o responsável: **todo arquivo fechado no refinamento recebe, no mesmo movimento, um exemplo completo** — árvore de pastas real, dado de exemplo coerente (reutilizando valores reais do tenant quando possível) e comentário **acima de cada campo** com função, obrigatoriedade, readOnly, regime de omissão e origem; cabeçalho lista o que não aparece e por quê; o exemplo cita a decisão que o fechou. Norma completa: [`padrao-exemplos-anotados.md`](padrao-exemplos-anotados.md). Regra também registrada no AGENTS.md do workspace.

> **Atualização (2026-10-14, D-005):** a simulação "API CEP" e as simulações 409/417 foram retiradas da pasta na consolidação. O exemplo vivo passou a ser **gerado de APIs reais** em [`decisoes-refino-409/exemplos-gerados/`](decisoes-refino-409/exemplos-gerados/README.md) — 6 APIs, 143 YAML, cobrindo herança pura, append, quebra de herança, tombstone, colisão de nome de recurso e paths longos.

