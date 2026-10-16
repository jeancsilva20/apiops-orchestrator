# D-003 — Layout canônico do repositório de API

**Status:** Fechada em 2026-09-29 (decisões do grill com o responsável + reunião "[APIOps] Dúvidas Estrutura" de 2026-09-28).
**Natureza:** Spec viva. Toda mudança de layout subsequente deve ser registrada aqui antes de tocar schemas/models.

> ⚠️ **Revisada pela [D-005](d005-layout-revisado.md) em 2026-10-14.** Os pontos §1 (itens 2 e 3), §2, §4, §5 e §6 foram revisados pelo refino das APIs 409/417. Onde a D-005 não dispõe, esta decisão continua valendo. Antes de implementar qualquer seção marcada, leia a D-005 §2.

---

## 1. Precedentes incorporados

Esta decisão assume como entrada as decisões alinhadas na reunião de 2026-09-28:

1. **Templates canônicos no Manager (Golden Path):** os arquivos de template e schema deixam de existir no repositório. A plataforma guarda o template de API; o APIOps apenas referencia e valida por GET.
2. ~~**Override total via booleano**~~ → **revisado pela D-005 §6**: a herança é declarada com `inherit: true|false` (ausente ≡ `true`). `override` não existe mais.
3. ~~**Herança por busca ascendente até o template**~~ → **revisado pela D-005 §3 e §7**: a herança é **por escopo** — operação → recurso → revision (`all`) → gateway (60 s). O template **não participa** da herança em runtime; o papel dele é validar interceptors.
4. **Tags visuais por execution point:** `interceptors_request` / `interceptors_response` substituem o campo `executionPoint` no YAML.

## 2. Árvore canônica do repositório

> **Revisada pela D-005 §4** em 2026-10-14: a árvore deixou de derivar do path e passou a espelhar o
> agrupamento de recursos do Manager — **uma pasta por recurso**.

```text
repositorio-da-api/
├── api-basic-info.yaml                       ← manifesto de identidade (raiz)
├── all-all.yaml                              ← escopo `all` (raiz da revision)
└── resources/
    ├── letras/                               ← slug do `resource.name`
    │   ├── resource.yaml
    │   ├── delete_letras_{id}.yaml
    │   └── post_tarefas_{id}_letras.yaml     ← mesmo recurso, sem prefixo comum
    └── tarefas/
        ├── resource.yaml
        ├── get_tarefas.yaml
        └── get_tarefas_{id}.yaml
```

Pontos estruturais:

| Decisão | Conteúdo |
|---|---|
| Discovery | **Descoberta recursiva** por `resources/<slug>/`. Não existe `resources.yaml` índice. |
| Granularidade | Exatamente **uma operação por arquivo**. |
| Pasta do recurso | `slug(resource.name)` com teto de 60 chars; colisão ou truncamento desambiguam por sufixo legível e, em último caso, por `sha1(operações)[:6]` (D-005 §4). **A pasta não precisa casar com `name`.** |
| Nomenclatura do arquivo | `<método>_<path completo>.yaml` — `/` vira `_`, `{param}` preservado, teto de 90 chars (D-005 §4). Colisão no mesmo recurso é condição de erro do validador. |
| Identidade | O repo **não versiona** id de recurso nem de operação; a chave é `(método, path)` (D-005 §5). |
| Revisions | **Não existem no repositório.** O publish grava na revisão fixa informada pelo **número** via ambiente — 1 Draft, 2 DEV, 3 HML, 4 PRD (D-005 §9). |
| OpenAPI | **Não versionado neste momento.** Methods/paths têm como fonte exclusiva os arquivos de resource/operation. |
| Localização do basic info | **Raiz** do repositório. |

> **Exemplo vivo:** o layout está materializado a partir de 6 APIs reais em
> [`decisoes-refino-409/exemplos-gerados/`](decisoes-refino-409/exemplos-gerados/README.md), gerado pelo
> extrator determinístico `extrair_estrutura.py`. Os moldes desta decisão (revisados pela D-005)
> permanecem a autoridade normativa; o exemplo é ilustrativo e deve ser regerado a cada incremento.

## 3. `api-basic-info.yaml` (raiz)

```yaml
apiVersion: api-management.sensedia.com/v1
kind: ApiBasicInfo
spec:
  id: 386                    # readOnly; gravado pelo orquestrador; imutável
  name: "API CEP"            # obrigatório; editável
  version: v1                # obrigatório; editável
  basePath: /api.cep/v1      # readOnly; imutável
  description: "API para consulta de CEP"   # obrigatório; editável
  template: 414              # ★ binding à API-régua de interceptors (D-005 §7)
                             # chave SEMPRE declarada; '' = sem régua, validação não roda
                             # na esteira o valor vem de variável de ambiente, não do YAML
  apiResponsible:
    username: jean.silva     # readOnly; presente no YAML; hidratado no import
    groupName: MATRIZ-DEV    # readOnly; idem; sem atualização via CLI no MVP
                             # regime de escalares: ausente = preserva; "" = limpa; null proibido
  apiTags:                   # ausente = preserva remoto; [] = remoção EXPLÍCITA
                             # lista declarativa completa; par (attributeName, tags[])
    - attributeName: "Nome do Atributo"   # deve existir no catálogo do Adaptive Governance
      tags: ["valor"]                      # editável; não versionar nada disso fora daqui
```

Regras confirmadas:

- Shape direto `spec.<campo>` (não `spec.api.<campo>`);
- `spec.id` e `spec.basePath` são imutáveis; alteração é bloqueada pelo validador (indício de redirecionamento do repo);
- `apiResponsible` segue o mesmo regime de `spec.id`: recuperado no import, presente no YAML, não editável via CLI no MVP;
- Campos de fundo (`visibility` completo, `apiType`, `creationDate`, `revisions`, `lastRevision`, flags/contadores) **nunca entram no YAML** — hidratação via GET remoto no publish;
- `apiTags` ausente preserva as tags remotas (aprendizado da API 405); `apiTags: []` remove explicitamente; é lista declarativa completa — o PUT da revision replanta os pares `(attributeName, tags[])` (evidência 405 + varredura 110 APIs em `evidencia-tags-e-atributos.md`);
- `attributeName` referencia o catálogo de Attributes do Adaptive Governance; atributos/tags novos nascem no produto AG, nunca no repo; o validador futuro pode conferir existência via GET do catálogo (evolução);
- Escalares opcionais (ex.: `groupName`): **ausente = preserva remoto; `""` = limpa explicitamente; `null` proibido no schema** — espelhando a régua de listas;
- `spec.tags[]` simples: **suprimido do contrato** (0 de 110 APIs do tenant com lista não-vazia; omissão preserva) — sai do YAML e do payload;
- `identityApi`: **não versionar e não enviar** (campo opaco do Manager; omissão aceita e preservada na API 405; decisão do responsável em 2026-09-29).

## 4. Molde do arquivo de operação

> **Revisado pela D-005 §3 e §6** em 2026-10-14: `destination` virou objeto, `timeout` mudou de lugar
> e `override` deu lugar a `inherit`.

```yaml
path: /tarefas/{id}/letras    # fonte da verdade da rota; o método vem do nome do arquivo
destination:
  url: <backend>              # SEMPRE declarado. '' = herda do escopo acima
  timeout: <segundos>         # opcional. Ausente = herda. Teto do gateway: 60
description: ""               # sempre declarada, mesmo vazia
inherit: true                 # true/ausente = herda; false = herança quebrada
interceptors_request: []      # ordem da lista = ordem de execução (FIRST)
interceptors_response: []     # sempre executam ao final, por construção (SECOND)
```

Itens de interceptor:

```yaml
# Interceptor de plataforma
- type: OAuth
  content:                    # objeto TIPADO no YAML
    grantTypes:
      - CLIENT_CREDENTIALS
# Só o adapter serializa content para string JSON no wire.

# Custom interceptor
- type: Custom
  id: 241                     # ID numérico do catálogo; portabilidade cross-tenant
                              # fica planejada para depois (nome/alias único)
```

Regras confirmadas:

| Tema | Regra |
|---|---|
| `position` | **Não existe no YAML.** A ordem da lista é a fonte; a position é calculada apenas no payload, por escopo e execution point |
| `executionPoint` | Não existe no YAML — derivado da lista (`request` → FIRST, `response` → SECOND) |
| `status` | **Fora do YAML.** A gramática do tombstone (`REMOVED`/`parent`) segue **em aberto** (V-25): hoje `inherit: false` sinaliza a quebra, mas não expressa o item removido |
| `content` | Objeto YAML tipado; serialização para string JSON apenas no adapter |
| Append vs quebra | `inherit: true` (ou ausente): as listas **somam** ao fluxo herdado. `inherit: false`: o arquivo declara o fluxo que vale — por substituição ou por remoção (D-005 §6) |
| `inherit` a nível resource | **Implementado.** `resource.yaml` declara `inherit` e pode ter listas próprias (D-005 §3) |
| Escopos não governados | Interceptors com `executionPoint` fora de `FIRST`/`SECOND` **não entram no YAML**: são lidos por GET e reenviados intactos (D-005 §8) |
| Validação estrutural | Itens que executam na resposta pertencem exclusivamente a `interceptors_response` (não há "SECOND" no meio da lista de request) |

## 5. `resource.yaml`

> **Revisado pela D-005 §3, §4 e §6** em 2026-10-14: deixou de ser mapa leve — ganhou `destination`,
> `timeout` e `inherit` —, e `name` deixou de precisar casar com a pasta.

```yaml
# resources/tarefas/resource.yaml
name: "Tarefas"                                  # rótulo livre do Manager; NÃO é chave
description: "Gerenciamento de tarefas"          # alimenta a completude do Manager
destination:
  url: https://google.com                        # '' = herda do escopo `all`
  timeout: '30'                                  # opcional; ausente = herda
inherit: true                                    # listas abaixo somam ao fluxo da revision
```

- `name` é **dado versionado**, não identificador: pode repetir entre recursos da mesma API (ocorreu na API 417) e muda sem reescrever a árvore.
- O recurso é identificado pelo **conjunto de operações** que agrupa (D-005 §5).
- `connector` e `certificateId` existem no contrato mas **não entram no YAML**: são estado não governado, preservado por GET (D-005 §8).

## 6. Ciclo de vida — importação e publicação

### Importação (Manager → repo)

> **Revisado pela D-005 §8 e §9** em 2026-10-14: a heurística passou a comparar com o fluxo da
> **própria revision** (não com o template), e o publish grava em revisão fixa com `PUT` denso.

Regra de reconstrução (heurística diff-vs-revision):

1. `GET` da revisão alvo: fluxo da revision, dos recursos e das operações, num único payload.
2. **Particionar** os interceptors: `FIRST`/`SECOND` são governados; o restante é estado não governado, que não chega ao repo (D-005 §8).
3. Comparar o fluxo da operação com o herdado, **incluindo `content`** e por **sequência**: só itens novos ⇒ `inherit: true` com as caudas; itens herdados reproduzidos ou ausentes ⇒ `inherit: false`.
4. Item governado que o YAML não saiba representar ⇒ **falhar explicitamente** (nunca silenciar).
5. `spec.id`, `apiResponsible` e demais campos read-only são trazidos para o YAML no import.

### Publicação (repo → Manager)

1. Resolver o modo (`EXECUTION_MODE`) e o **número** da revisão alvo (`TARGET_REVISION_NUMBER`); local só publica na Revision 1 (Draft).
2. `GET /apis/{spec.id}` — traduz número → id, hidrata campos de fundo (`visibility`, `apiType`, `creationDate`) e carrega o **estado não governado** a preservar.
3. Descoberta por `resources/<slug>/`; resolver o fluxo efetivo por escopo (operação → recurso → revision), aplicando `inherit`.
4. Traduzir YAML → wire: `destination = url or null`, `timeout = destination.timeout or null`; na raiz da revision, vazio ⇒ chave omitida.
5. Calcular positions **apenas sobre os governados**; reanexar os preservados intactos; serializar `content` para string JSON.
6. `PUT /api-manager/api/v3/revisions/{id}` — payload denso, estado completo. Criar revisão é ato humano; o orquestrador nunca usa `POST /revisions`.

### Validação

- Conformidade com a **API-régua** (`spec.template`): comparação **efetiva** por caminho de execução, com `content` e por sequência. **Append = `INFO`**, **quebra = `WARNING`**, **sem bloqueio** — o julgamento é do code review (D-005 §7).
- Bloqueio do **Adaptive Governance** (HTTP 412) é canal separado, com exit code `3` e faltantes calculados por GET (D-005 §10).
- Governança de **valores** (ex.: limites de rate limit) permanece como pendência de produto — a régua governa o shape, não os valores.

## 7. Registro das decisões fechadas neste grill (2026-09-29)

| # | Decisão |
|---|---|
| 1 | `spec.template` é o binding ao Golden Path — **D-005 §7**: régua = API 414, chave sempre declarada, valor por ambiente na esteira |
| 2 | Descoberta recursiva; sem `resources.yaml` |
| 3 | ~~`{resource}/{metodo_parametros}.yaml`~~ → **D-005 §4**: `resources/<slug>/<método>_<path completo>.yaml` |
| 4 | Revision pertence à esteira (uma por ambiente); repo ignora revisions — **D-005 §9** fixou o alvo pelo **número** |
| 5 | Duas listas req/resp com ordem implícita; position só no payload |
| 6 | `content` tipado no YAML |
| 7 | `status` fora do YAML |
| 8 | Custom por ID numérico por ora |
| 9 | ~~Sem override = append; com override = troca total~~ → **D-005 §6**: `inherit: true|false`, declarado sempre |
| 10 | OpenAPI não versionado neste momento |
| 11 | ~~`resource.yaml` = mapa leve~~ → **D-005 §3**: ganha `destination`, `timeout` e `inherit` |
| 12 | Basic info na raiz |
| 13 | apiTags: ausente preserva; `[]` remove |
| 14 | `groupName`: presente, hidratado no import, read-only no MVP |
| 15 | Shape direto `spec.<campo>` |
| 16 | ~~Import: heurística diff-vs-template~~ → **D-005 §8**: diff contra o fluxo da **própria revision** |
| 17 | Escalares opcionais: ausente preserva; `""` limpa; `null` proibido (refinamento 2026-09-29) |
| 18 | `spec.tags[]` simples suprimido do YAML e do payload (varredura 0/110) |
| 19 | `identityApi` fora do YAML e do payload (decisão do responsável; omissão preservada) |
| 20 | `apiTags` é lista declarativa completa; `attributeName` referencia catálogo do AG |
| 21 | **(D-005)** Árvore por recurso; pasta não precisa casar com `name` |
| 22 | **(D-005)** Repo não versiona id de recurso/operação; chave é `(método, path)` |
| 23 | **(D-005)** `destination` objeto `{url, timeout}` nos 3 escopos; herança por substituição |
| 24 | **(D-005)** Estado não governado preservado por GET (campos + `executionPoint` fora de FIRST/SECOND) |
| 25 | **(D-005)** Conformidade com a régua informa, não bloqueia; AG bloqueia com exit code próprio |

## 8. Estacionados (não bloqueiam o layout)

Fechados no refinamento de 2026-09-29 (ver §7 itens 17–20): `spec.tags[]`, `identityApi`, regime de escalares e regime de `apiTags[].attributeName`. Permanecem estacionados:

- Governança de valores do template (rate limit e similares);
- Fluxo administrativo para mudança legítima de `id`/`basePath`/responsável;
- Sintaxe de flow a nível resource (cenário MAG);
- Portabilidade de Custom entre tenants. **Revisitado em 2026-10-15:** permanece o `id` numérico.
  O id é estável dentro de um ambiente; quando muda — por exemplo ao mover o repositório entre
  ambientes — a validação é responsabilidade do dev, e o aborto por `Custom` inexistente (W-2) torna
  a troca visível em vez de silenciosa. Referenciar por nome, ou pelo par id + nome, foi descartado:
  trocaria a chave de identidade por um campo que a plataforma não garante único, para cobrir um caso
  que não é falha de rotina.

## 9. Impactos de implementação (fila de proposta)

> **Desdobramento arquivo-a-arquivo:** ver [`fila-templates-schemas.md`](fila-templates-schemas.md) — inventário exato dos schemas/templates desalinhados e a ordem de execução proposta (alimenta a change proposal).

> **Atualizado pela [D-005 §11](d005-layout-revisado.md) e por `fila-templates-schemas.md` §4** (itens 13–21).

1. Models/schemas: `SpecTemplate` no basic info; remover `position`/`executionPoint`/`status` dos models declarativos; `inherit` no lugar de `override`; `destination` como objeto.
2. Descoberta recursiva no importer substituindo leitura de índice.
3. Preservar `destination`/`timeout`/flows do resource nos models (gap atual do CLI).
4. Substituir `set_interceptor_positions()` global por cálculo por escopo/execution point.
5. Adapter de `content` tipado → string JSON.
6. Importer com heurística diff-vs-**revision** e particionamento governado × preservado (seção 6; D-005 §8).
7. Publisher com hidratação ampliada (D-002), preservação do estado não governado e alvo de revisão pelo **número** (D-005 §9).
8. Remover schemas locais e `default-interceptors.yaml` dos templates; incluir `spec.template` nos exemplos.
9. Testes de regressão: matriz revision/resource/operation (com a esteira simulando ambiente), append/override, tombstones recebidos do Manager, round-trip de Custom.

> Esta decisão supersede parcialmente a seção "Baseline de desenho" do levantamento de interceptors (item 1 — nível de revision — e o papel do `resources.yaml`), conforme as escolhas da reunião de 2026-09-28 e deste grill.
