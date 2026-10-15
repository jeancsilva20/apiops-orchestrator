# Análise de complexidade — adequar o orquestrador à D-005

| Meta | Valor |
|---|---|
| Data | 2026-10-14 |
| Natureza | **Exploração registrada.** Não é decisão; não autoriza código. Alimenta a change proposal OpenSpec |
| Pergunta de origem | Qual a complexidade de ajustar o orquestrador ao layout da D-005 e ao uso do template via Manager (e não via schema)? |
| Método | Leitura cruzada dos docs da feature + rastreio de call sites em `src/apiops_orchestrator/` + exemplos gerados de 6 APIs reais |
| Escrita na plataforma | nenhuma |

> Este documento tem duas metades. A §1–§7 é o diagnóstico. A **§8 é a fila de pendências**, que é o
> artefato operacional: um item por vez, com status, para não perder nada no caminho.

---

## 1. Achado que reenquadra a pergunta: o ciclo não roda hoje

Rastreio de call sites em produção (fora de testes):

| Peça | Estado real | Evidência |
|---|---|---|
| `PublisherService` | **sem call site em produção** | só `tests/unit/application/services/test_publisher_service.py` |
| `JsonToYamlService` (import Manager→repo) | **sem call site em produção** | só `tests/unit/domain/services/test_json_to_yaml_service.py` |
| `LocalFileExporterAdapter` | **sem call site em produção** | só teste homônimo |
| `run_bare_pipeline` | roda só com `python main.py` desnudo; `repo_path` **hardcoded** (`main.py:44`); termina em `rprint(api_full)` — **não publica** | `main.py:148-194` |
| `revision_file_generator.py` | importa `application.enums.json_to_yaml_enum`, **módulo inexistente** → não executável; só existe nesta branch, não em `main` | `revision_file_generator.py:5` |
| `versioner_service.py` | **peça viva do versionador, incompleta** — ver §1.1 | `versioner_service.py:17-21` |

> **Correção (2026-10-15):** a versão anterior desta tabela classificava `versioner_service.py` como
> código morto a remover. **Errado.** O versionador é a peça que materializa o repositório a partir do
> Manager e **permanece**; o que ele precisa é de adaptação ao novo layout, mais o fechamento de um
> buraco que já existe. Igualmente corrigido: o OpenSpec do CLI **não está vazio** (§8.2, P-6).

### 1.1 O versionador — quatro peças, estado real

Fluxo **Manager → repositório**. O `importer` é o caminho inverso (repo → orquestrador) e é interno,
acionado pelos comandos; não é comando de usuário.

| Peça | Papel | Estado |
|---|---|---|
| `ApiRepoAdapter` + `ApiRepoPort` | primitivas de FS (`create_dir`, `create_file`, `rename_dir`, `delete_file`) | **funciona e é agnóstico de layout — preservar inteiro** |
| `VersionerService` | orquestra: GET → calcula revision → `.lock` + `.tmp_N_timestamp` → **[buraco]** → renomeia → apaga lock | **esqueleto com buraco**: o `# Create files` (`versioner_service.py:20`) nunca foi implementado — cria pastas e renomeia, mas **não escreve YAML nenhum**. As pastas criadas (`env-variables/`, `resources/`, `templates/` sob `src/apis/revisions/N`) são do layout antigo |
| `JsonToYamlService` | `ApiFull` → partes YAML | implementado **para o layout antigo** (gera `resources.yaml`, `default-interceptors.yaml`); sem call site |
| `RevisionFileGenerator` | partes YAML → arquivos e pastas | implementado **para o layout antigo**, com import quebrado; sem call site |

**Elo ausente:** nada converte a resposta do `GET` do Manager em `ApiFull`. O `JsonToYamlService`
recebe um `ApiFull` pronto, e o `VersionerService.version()` usa do GET apenas
`lastRevision.revisionNumber`. O caminho `GET → ApiFull → arquivos` nunca foi ligado ponta a ponta.
| `publish_api_changes` | `POST /revisions` — a D-005 §9 proíbe (*"o orquestrador nunca usa POST /revisions"*) | `manager_api_adapter.py:355` |

Comandos Typer expostos hoje: `login`, `list api`, `completeness`. **Import e publish não têm porta de entrada.**

Consequências:

- **A favor:** não há usuário, compatibilidade retroativa, migração de repositórios existentes, dual-read
  ou feature flag. Quebrar o layout antigo custa **zero** — ele nunca foi contrato com ninguém.
- **Contra:** não dá para fatiar como refactor incremental de algo que funciona. Boa parte do trabalho
  é **primeira construção** com reaproveitamento de peças, não ajuste.

```
                   HOJE                              D-005
  ┌────────────────────────────────┐   ┌────────────────────────────────┐
  │ sen login ──────────────► OK   │   │ sen login              ► OK    │
  │ sen list api ───────────► OK   │   │ sen list api           ► OK    │
  │ sen completeness ───────► OK   │   │ sen completeness       ► OK    │
  │                                │   │ sen import  ◄── GET    ► NOVO  │
  │ python main.py (bare)          │   │ sen validate (régua)   ► NOVO  │
  │   └─ repo hardcoded            │   │ sen publish ──► PUT    ► NOVO  │
  │   └─ converte, imprime, para   │   │                                │
  │ [publisher/exporter órfãos]    │   │                                │
  └────────────────────────────────┘   └────────────────────────────────┘
```

---

## 2. O delta por camada

```
┌─ IDENTIDADE / CONFIG ────────────────────── tradução ──── BAIXO ──┐
│  spec.id em vez de Settings.API_ID · remove API_TAGS_*            │
│  entra EXECUTION_MODE, TARGET_REVISION_NUMBER, TEMPLATE_API_ID    │
├─ ESTRUTURA DE ARQUIVOS ──────────────────── tradução ──── BAIXO ──┤
│  revisions/N/resources/X/operations/  →  resources/<slug>/        │
│  nomes determinísticos  ← PROTÓTIPO PRONTO + 155 YAML de fixture  │
├─ MODELO DE FLUXO ──────────────────── semi-tradução ──── MÉDIO ───┤
│  destination: str → {url, timeout} · inherit · listas req/resp    │
│  interceptor perde id/idTemp/position/executionPoint/status       │
├─ PARTIÇÃO GOVERNADO × PRESERVADO ───── invariante novo ─── ALTO ──┤
│  atravessa import E publish; não é campo, é regra de corte        │
├─ HERANÇA EFETIVA (3 escopos) ───────────── lógica nova ─── ALTO ──┤
│  resolver inherit + destination/timeout por substituição          │
├─ PUBLISH ──────────────────────────── reescrita total ─── ALTO ───┤
│  POST /revisions → PUT /revisions/{id} em revisão fixa + hidratar │
└─ RÉGUA (template) ──────── mudança de natureza ────────── ALTO ───┘
```

O volume de linhas está em cima (barato). O risco está embaixo (caro).

---

## 3. Eixo A — layout: muito volume, pouca incerteza

**Tradução pura** (mecânica, determinística, testável offline):

- 3 schemas reescritos, 2 apagados (`api-revision*`), **7 apagados** (`*-default-interceptors`,
  4.230 linhas), `catalog.json` repontuado
- `settings.py`: pastas + 3 env vars novas; `API_TAGS_*` sai
- `repo_validator.py`: inteiro — as 98 linhas validam uma árvore que deixa de existir
- models: `destination` objeto, `inherit`, interceptor enxuto
- nomes de pasta e de arquivo

O último item é o maior ativo disponível. `extrair_estrutura.py` já é protótipo determinístico
exercitado contra **6 APIs reais / 155 YAML**, e já tropeçou nos casos que só aparecem no real:
`WinError 206` no caminho longo da FDX, truncamento criando colisão, marca derivada do `name` falhando
nos dois `Letras` homônimos. É **especificação executável + fixture dourada**, não documentação.

**Lógica nova dentro do eixo "layout":** a partição governado × preservado (D-005 §8 / V-22) não é um
campo a mais — é um invariante que corta toda entidade em duas metades (a que o YAML descreve e a que
só existe no GET) e precisa valer no import, no publish e na validação. É o item com maior risco de
implementação silenciosamente errada, porque **o modo de falha é perda de configuração sem erro**.

---

## 4. Eixo B — régua via Manager: pouco volume, mudança de natureza

| | hoje (schema) | D-004 §2.1 + V-11 |
|---|---|---|
| Onde mora | 7 JSON Schema no pacote, **um por cliente** | API 414 no Manager do tenant |
| Quando resolve | build-time, estático, distribuído com o CLI | **runtime**, via GET |
| O que compara | forma do YAML + valores fixos (`prefixItems`/`const`) | **fluxo efetivo** × fluxo real da régua |
| Alcance | só a raiz (`default-interceptors.yaml`) | **todos** os caminhos de execução |
| Chave de comparação | posição + type | **sequência + `content`** |
| Severidade | erro de schema → **falha** | INFO/WARNING → **nunca bloqueia** |
| Multi-tenant | schema novo por cliente, no git do CLI | id por tenant, via env na esteira |

Três consequências:

**(a) A validação deixa de ser offline.** Conformidade passa a exigir token + GET. Isso cria um desfecho
que a V-11 §4 ainda não cobre: **régua inalcançável** (sem rede, token expirado, 404, id de outro
tenant). A tabela de bordas cobre `TEMPLATE_API_ID` ausente em pipeline, não a régua inacessível.

**(b) A régua vira dado vivo e não versionado.** Hoje está no git do CLI — diffável, com histórico e PR.
Depois é o `lastRevision` de uma API editável pela UI a qualquer momento. **O mesmo commit valida verde
hoje e amarelo amanhã sem nada ter mudado no repositório.** Para WARNING não-bloqueante é tolerável,
mas sem gravar o snapshot usado (id + `revisionNumber` + hash do fluxo) o achado não é reproduzível.

**(c) O ganho é desacoplamento de produto, não só limpeza.** Apagar `ecad-*` e `mag-*` tira **nome de
cliente de dentro do pacote**. Hoje onboarding de cliente novo = PR no CLI. Depois = uma API no Manager
do tenant dele. Provavelmente o maior ganho estrutural da mudança, e cai junto com as 4.230 linhas.

Separação resultante: **schema = gramática** (forma, offline, bloqueia) · **régua = política** (fluxo
efetivo, online, informa). Hoje os dois estão misturados dentro de `jsonschema`.

---

## 5. O nó: V-25 (tombstone)

O que os exemplos gerados produzem hoje:

```yaml
# resources/tarefas/get_tarefas.yaml
inherit: false
# o fluxo herdado e quebrado: remove -> XSS threat protection
# representacao do item removido ainda nao decidida (item V-25 do refino)
```

A remoção é **um comentário**. Nos exemplos reais: 3 append · 3 override · **3 tombstone** — um terço
dos fluxos cai nessa lacuna. Enquanto ela existir, **o round-trip import→publish não fecha**:
reimportar e republicar ressuscita o item removido.

```
(a) inherit:false + lista COMPLETA explícita
    + zero gramática nova, já expressável hoje
    - verboso (health-check reproduz 6 itens para derrubar 1)
    - drift: a régua muda, o override não acompanha, ninguém percebe

(b) gramática de remoção (append-com-exceção)
    + enxuto, intenção explícita, sobrevive à régua mudar
    - precisa de CHAVE de identificação do item — e a V-11 §4 já provou
      que `type` sozinho não serve (dois `Log` diferindo só no `content`)
```

**V-25 não bloqueia as ondas 0–2** (§7). O import pode gravar o comentário como hoje; a conformidade
detecta o tombstone pelo wire (`status: REMOVED`). Só o publish fiel precisa da decisão.

---

## 6. Tensões e riscos levantados

| # | Item | Natureza |
|---|---|---|
| 1 | **`position`**: três pontos vigentes da D-003 dizem "por escopo/execution point" (§4 linha 129, §9 item 4) enquanto a D-004 §4 item 2 **afirma ter reescrito** a D-003 §9 item 4 para "global e contínuo" — reescrita que não está no arquivo | **documental**, com risco de implementação errada |
| 2 | `PUT /revisions/{id}` **nunca foi exercitado** — toda a evidência do refino é GET; a D-005 §12 admite que herança em runtime, `''`↔`null` e as inferências do AG seguem sem prova | risco técnico não provado |
| 3 | `conversor_service.py:197` — o `else` manda para `get_custom_interceptor_by_id()` qualquer interceptor que não seja (não-custom **e** dict), inclusive não-custom com content string | bug latente; some na reescrita |
| 4 | `README.md` dos exemplos descreve nome de arquivo "relativo ao prefixo comum"; código (`extrair_estrutura.py:167`) e saída usam **path completo** (regra D-005 §4). Código e saída concordam; só o README ficou para trás | documental menor |
| 5 | `openspec/` vazio — sem `project.md`, sem specs, zero changes. A regra 3 da feature exige proposal aprovada antes de código | processo |

---

## 7. Fatiamento proposto

Critério de corte: **o que é testável sem escrita na plataforma.**

```
ONDA 0 · demolição + contrato              │ rede: nenhuma │ risco: baixo
  schemas (3 reescritos, 9 apagados), catalog, settings, enums, repo_validator
  (o versionador NAO sai: e adaptado na onda 1)
  ↳ ~4.500 linhas a menos; nada quebra porque nada chama

ONDA 1 · import                            │ rede: só GET  │ risco: médio
  extrair_estrutura.py ──► importer de produção
  partição governado × preservado + falha alta no não representável
  ↳ oracle pronto: as 6 APIs reais / 155 YAML têm de sair idênticos

ONDA 2 · conformidade com a régua          │ rede: só GET  │ risco: médio
  comparador efetivo (sequência + content), INFO/WARNING, sem bloqueio
  ↳ oracle pronto: V-11 §3 prevê exatamente 4 achados nas APIs 409 e 417

ONDA 3 · publish                           │ rede: ESCRITA │ risco: alto
  PUT em revisão fixa, hidratação, preservação, AG 412 / exit 3
  ↳ sem oracle; depende de ambiente de escrita + decisão V-25
```

Leitura: **onda 0 é volume sem risco; ondas 1–2 são trabalho com rede de proteção; a onda 3 concentra
quase todo o risco** — e é a única que depende de coisas que ainda não existem (ambiente de escrita,
V-25, item 1 da §6). Tratar "ajustar ao novo layout" como bloco único esconde exatamente isso.

---

## 8. Fila de pendências — um item por vez

> Esta é a seção operacional. Atualizar o status conforme cada item for resolvido.

### 8.1 Validações ainda possíveis por GET — antes da proposal

Cruzamento desta análise com a [D-005 §12](d005-layout-revisado.md) e o
[`CAMINHOS-DE-VALIDACAO.md`](decisoes-refino-409/CAMINHOS-DE-VALIDACAO.md) §5. Receita de token e
bases: §1 e §2 do mesmo documento. **Somente leitura** — nenhuma escrita.

| # | Pergunta aberta | Chamada | Fecha / informa |
|---|---|---|---|
| V-a | **Posições por escopo** — a V-22 anotou `position` só do escopo revision (FIRST `1…7`, SECOND `8`) | `GET /revisions/9103` e `/9175`, campo `position` dos interceptors de **resource** e **operation** | P-1 perguntas 2 e 3 |
| V-b | **V-19 — fixture dourada** — ver achado abaixo; o determinismo segue sem reconferir | reexecutar `extrair_estrutura.py` e diferenciar contra `saida/` | **premissa central da onda 1** |
| V-c | **V-20 — `Additional Info`** — `content.attributes[].id` é versionável? | comparar o interceptor do recurso 9179 (417) com o do 9106 (409): o `id` é estável entre revisions? | schema de interceptors (onda 0) |
| V-d | ~~**V-21 — `null` dentro de `content`**~~ | — | **RESPONDIDO** — ver §8.3 |
| V-e | **V-25 (parte validável)** — qual chave o tombstone usa para apontar o item removido | no item `status: REMOVED`, inspecionar o que `parent` referencia | opção (b) do P-4 |
| V-f | **P-2 — régua inalcançável** — quais status a plataforma devolve | `GET /apis/<id inexistente>` · id de outro tenant · token expirado | P-2 |
| V-g | **P-3 — snapshot da régua** — `lastRevision` traz `revisionNumber`? | `GET /apis/414` | P-3 |

#### Achado de 2026-10-14 — a fixture dourada não está no estado que o README declara

Verificado localmente, sem rede:

| Declarado no `exemplos-gerados/README.md` | Estado real em `saida/` |
|---|---|
| 6 APIs (417 rev2/rev1, 409, 17, 2, 5) | **2 pastas**: `api-417-rev2/` e `api-400-rev4/` — esta última **não aparece no README** |
| 155 YAML, "**todos parseiam**" | **21 YAML; 2 falham o parse** |

As duas falhas são o mesmo defeito, em `escalar()` (`extrair_estrutura.py`): a função cita a string
quando ela é vazia, contém `:` `#` ou quebra de linha, tem espaço nas pontas, ou é `true/false/null/yes/no`
— mas **não cita escalares iniciados por indicador YAML**. Resultado:

```yaml
replaceChar: *****        # '*' abre um alias → ScannerError
```

Arquivos: `api-400-rev4/resources/token/post_oauth2_token.yaml` e `post_oauth2_token_validation.yaml`.
A correção é de uma linha; o que importa é que **a asserção "todos parseiam" nunca foi verificada**, e
ela é a base do oracle da onda 1. Mesma classe de risco vale para `&` `!` `|` `>` `%` `@` `` ` `` `[` `]`
`{` `}` `,` `?` em início de escalar.

**Continua sem prova possível por GET** (`CAMINHOS-DE-VALIDACAO.md` §5 + P-1 pergunta 1): herança de
`destination`/`timeout` em runtime · equivalência `''` ↔ `null` na escrita · resolução do workflow
efetivo pelo grupo · stage usado na validação · se a `position` é obrigatória no payload. Tudo isso é
**onda 3** e depende do P-8.

### 8.2 Fila de pendências

| # | Item | Tipo | Bloqueia | Status |
|---|---|---|---|---|
| **P-0** | **Rodada de validação read-only** — executar §8.1 (V-a … V-g) e registrar os achados | evidência | P-1 a P-4 e o conteúdo da proposal | **PRÓXIMO** |
| P-5 | **Granularidade da change proposal** — 4 changes OpenSpec espelhando as ondas, ou uma com fases | processo | tudo | ABERTO (depois do P-0) |
| P-6 | ~~`openspec/` vazio~~ — **corrigido**: o OpenSpec do CLI tem specs (`api-catalog`, `cli-auth`, `sen-completeness`, `sen-list`), archive com changes e 1 change ativa. A proposal nasce em `CLI/apiops-orchestrator/openspec/`, seguindo o padrao do archive | processo | — | **RESOLVIDO** |
| P-2 | **Régua inalcançável** — desfecho quando o GET da API-régua falha (sem rede, 401, 404, id de outro tenant); difere entre `local` e `pipeline`? | decisão de produto | onda 2 | ABERTO |
| P-3 | **Snapshot da régua no relatório** — gravar id + `revisionNumber` + hash do fluxo para tornar o achado reproduzível | decisão de desenho | onda 2 | ABERTO |
| P-4 | **V-25 — tombstone** — escolher entre lista completa explícita (a) e gramática de remoção (b); se (b), definir a chave de identificação do item | decisão de layout | onda 3 | ABERTO |
| P-7 | **README dos exemplos gerados** — alinhar a regra de nome de arquivo ao código e à D-005 §4 | correção documental | nada | ABERTO |
| P-8 | **Ambiente de escrita** — provisionar para validar `PUT /revisions/{id}`, herança em runtime, `''`↔`null` e as inferências do AG | infraestrutura | onda 3 | ABERTO |
| P-1 | **`position` no payload** — ver nota abaixo | serialização | onda 3 | **REBAIXADO** |
| P-9 | **Rotação da credencial** usada nos testes ao vivo | segurança | nada | PENDENTE (herdado) |

### Nota sobre o P-1 (rebaixado em 2026-10-14)

Levantado primeiro como decisão de contrato; **não é**. O que está fechado permanece fechado:
`position` **sai do YAML** e a **ordem da lista é a fonte declarativa** (D-003 §4, V-12).

O resíduo é só de **tradução YAML → wire**: o Manager carrega `position` no payload, então o
orquestrador precisa gravar algum número ao serializar. Isso vive dentro de
`ApiFull.set_interceptor_positions()` (25 linhas) e **só é exercitado no publish — onda 3**. O import
descarta a position; a conformidade compara sequência e `content`, não número.

Três perguntas ficam para quando houver ambiente de escrita, na ordem:

1. A `position` é **obrigatória** no payload, ou o Manager respeita a ordem do array e o número é
   decorativo? Se for decorativa, os itens 2 e 3 evaporam.
2. FIRST e SECOND **compartilham** numeração? Evidência disponível diz que **sim** (V-22 §2 — revision
   9175: FIRST `1…7`, SECOND `8`), contrariando a D-003 §4 ("por escopo **e** execution point").
3. A numeração é **contínua entre escopos** (revision→resource→operation) ou reinicia? Sem evidência:
   a V-22 anotou posições só do escopo revision, e o `1..10, 11..17` citado na D-004 §4 sustenta as
   duas leituras.

Pendência documental que **permanece válida e independente**: a D-004 §4 item 2 declara ter reescrito
a D-003 §9 item 4, e a reescrita não está no arquivo — a D-003, apontada pelo `AGENTS.md` como spec
viva, ainda diz "por escopo/execution point". Corrigir junto com a resposta de (2).

---

## 8.3 Teste de escrita na API 417 — V-21 respondido (2026-10-14)

| Meta | Valor |
|---|---|
| Autorização | **explícita do responsável** nesta sessão (exceção pontual à regra de somente leitura) |
| Alvo | revision **9175** (API 417, nº 2) — `deployments: []` nas duas revisions, **sem tráfego** |
| Plataforma | `platform-production.sensedia.com`, tenant `consulting` |
| Rollback | executado e **confirmado**: estado final idêntico ao original |
| Backups | `backup_api_417.json`, `backup_revision_9161.json`, `backup_revision_9175.json` |

**Experimento:** remover a chave `headerKey` do `content` do interceptor `Rate limit`
(`position 4`, `FIRST`, raiz da revision) e observar o que o Manager faz.

| Passo | Chamada | Resultado |
|---|---|---|
| 0 | `PUT /revisions/9175` com o payload do GET **sem alteração** | **200**; GET idêntico |
| 1 | `PUT` com `headerKey` removido | **200**, sem erro e **sem 412 do AG** |
| 2 | `GET /revisions/9175` | **a chave permaneceu ausente** — o Manager não repôs |
| 3 | `PUT` restaurando o original | **200** |
| 4 | `GET` final | estado original de volta |

### Conclusões

1. **O `content` é substituído por inteiro — não existe merge por chave.** Provado: a chave removida
   sumiu e não voltou.
2. **A régua da D-003 §3 não pode alcançar o interior do `content` — aplicá-la inverteria o
   comportamento real:**

   ```
   régua (basic info):     chave ausente → PRESERVA o valor remoto
   realidade (content):    chave ausente → APAGA o campo
   ```

   Consequência de UX a documentar: apagar uma linha do `content` **remove** o campo; não é um
   "não mexer nisso".
3. **`null` dentro de `content` é valor, não regime.** `headerKey: null` e chave ausente são estados
   distintos e ambos aceitos. O schema **deve permitir `null`** ali — proibir quebraria o import de
   APIs reais (400 e 417).
4. **O PUT denso funciona** — o payload do GET é aceito de volta sem limpeza de campos read-only
   (`creationDate`, `deployments`, `apiBroken` foram juntos). **Derruba o risco nº 2 da §6** e valida
   a premissa central do publish da D-005 §9.

### Perguntas que o teste abriu

| # | Pergunta |
|---|---|
| T-1 | O `PUT` passou **sem** 412 do AG. A V-23 descreve o 412 vindo de `/api-governance/.../validate` — outro endpoint. Confirmar que o gate do AG atua no `validate`/deploy e **não** no PUT da revision: se for assim, o publish grava com governança pendente e o bloqueio só aparece depois |
| T-2 | Fidelidade de tipo: o wire traz `"quota": "1000"` (**string**) e o extrator gera `quota: 1000` (**número**) — mesma classe de defeito do `replaceChar: *****`. O round-trip precisa preservar tipo |
| T-3 | A escrita foi na revision **nº 2**; a D-005 §9 restringe o publish local à **nº 1 (Draft)**. A restrição é do orquestrador, não da plataforma — a plataforma aceitou |

## 9. Referências

- [D-003 — layout canônico](d003-layout-repo.md) · [D-004 — template e validação](d004-template-e-validacao.md) · [D-005 — layout revisado](d005-layout-revisado.md)
- [V-11 binding](decisoes-refino-409/V-11-binding-do-template.md) · [V-11 conformidade](decisoes-refino-409/V-11-conformidade-com-a-regua.md) · [V-22 estado não governado](decisoes-refino-409/V-22-estado-nao-governado.md)
- [Fila de templates e schemas](fila-templates-schemas.md) · [Exemplos gerados](decisoes-refino-409/exemplos-gerados/README.md)
