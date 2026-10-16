## Context

O orquestrador é hexagonal: `domain/` não conhece rede, `application/` conversa com ports,
`adapters/` traduzem transporte. O `sen completeness` é o comando mais recente e estabeleceu a forma
da borda — factory no composition root, `display_output` com `text_callback`, view `frozen=True` com
`to_document()`, exceções tipadas que carregam `message` e `exit_code`.

O `sen validate` é o primeiro comando que **escreve** na plataforma. Isso muda o peso de cada erro:
no `completeness` um engano devolve número errado; aqui devolve estado errado no Manager. A
investigação registrada em [feat-api-estructure](../../../docs/feat-api-estructure/) produziu nove
regras de wire (W-1 a W-9) observadas contra a API 417, e três delas descrevem **perda silenciosa sob
HTTP 200**. O desenho abaixo é organizado em torno disso.

Restrições já fechadas, que não se renegociam aqui:

- publicação local **só** na Revision 1 (Draft), pelo número, nunca pelo id (V-24);
- criar revision é ato humano — o orquestrador usa `PUT`, nunca `POST /revisions` (D-005 §9);
- `--dry-run` real é impossível: o Adaptive Governance só avalia o que foi publicado (D-16).

## Goals / Non-Goals

**Goals:**

- Fechar o ciclo `repositório → veredito` antes do PR, com saída consumível por humano e por esteira.
- Tornar determinístico o que hoje é texto livre: o faltante de governança é **calculado**, nunca
  extraído de `messages[]`.
- Falhar alto no que é falha técnica; informar sem bloquear no que é escolha do dev.
- Deixar o `domain/` inteiramente testável sem rede — toda a aritmética de identidade do wire mora lá.

**Non-Goals:**

- Promover revisão, fazer deploy ou publicar em DEV/HML/PRD — isso é do `sen publish`.
- Reconciliar o ADR de versionamento incremental × revisions fixas (P9, herdado).
- Resolver portabilidade de `Custom` entre tenants (estacionado).
- Validar herança em **runtime**: exige deploy e tráfego, e a Draft tem `deployments: []`.

## Decisions

### D1 · O stage do Adaptive Governance é lido em runtime, nunca configurado

`workflowId` e `workflowStageId` são lidos do `GET /revisions/{id}` da revisão alvo e reenviados
intactos. O stage é propriedade da API e do ambiente — muda por API e por tenant, e o CLI não precisa
conhecê-lo de antemão.

*Alternativa descartada:* avançar para o "próximo" stage para forçar o gate. Além de escrever uma
intenção que o dev não teve, é indefinida na prática — no tenant medido a Draft já está no **último**
stage do workflow.

*Evidência (leitura em 2026-10-15):* as revisions 9161 (Draft) e 9175 carregam ambas `workflowId 500`
e `workflowStageId 1402`, e o stage 1402 pertence ao workflow 500. A divergência registrada na
[V-23 §3](../../../docs/feat-api-estructure/decisoes-refino-409/V-23-bloqueio-do-adaptive-governance.md)
— revision em `139/420` validada pelo workflow `500` — era estado transitório e não existe mais. Um
PUT aceito **não** move o ponteiro de stage: nove execuções do caderno releram `1402` depois de
publicações bem sucedidas.

### D2 · Um único PUT, na revision

O payload da revision carrega o `api` aninhado com `apiTags`, `name` e `description`, e é ali que o
AG atua. `PUT /apis/{id}` grava **sem validar** (200); `PUT /revisions/{id}` devolve **412**. Escrever
nos dois deixa estado meio-aplicado: no ensaio, a API perdeu a tag e a revision não publicou.

### D3 · HTTP 200 não encerra a E3

A conferência pós-publicação é obrigatória, não opcional. Compara operações (método, path),
interceptors por escopo e recursos vazios entre enviado e publicado. Divergência é **falha**, mesmo
com 200. Três perdas silenciosas distintas foram observadas: `idTemp` colidido, operação migrada de
recurso, e item descartado por dedupe.

### D4 · A identidade do wire mora em `domain/services/interceptor_flow.py`

```
position  ->  do ESCOPO    (por escopo e execution point; contínua entre escopos no wire)
idTemp    ->  do PAYLOAD   (único em toda a chamada; contador global)
id        ->  null em item novo; preservado em item existente
```

`interceptors_model.set_ids_from_position` **não** implementa isso: deriva `idTemp` de `position`, que
é do escopo, e fabrica exatamente a colisão do W-9. O modelo é separado em declarativo (o que o YAML
expressa) e wire (o que o payload exige).

### D5 · O fluxo efetivo é resolvido no repositório, não na plataforma

> **Revista em 2026-10-15.** A formulação anterior — *"`inherit: true` preserva a lista remota"* —
> delegava a resolução à plataforma e produzia um defeito real; ver D14.

O Manager guarda o fluxo **resolvido**, não o delta (W-4), e lista vazia significa **herdar** (W-5).
Dessas duas regras segue que a lista própria não vazia de um escopo **é** o fluxo inteiro que ele
executa — a plataforma não tem estado "append".

Logo o orquestrador resolve a herança descendo a hierarquia **declarada no repositório**
(`all.yaml` → `resource.yaml` → arquivo de operação) e publica o resultado:

| no repositório | efetivo | no wire |
|---|---|---|
| `inherit: true`, sem itens | o do pai | `[]` |
| `inherit: true`, com itens | o do pai **+** os declarados | lista completa |
| `inherit: false`, com itens | exatamente os declarados | lista completa |
| `inherit: false`, sem itens | o do pai (contraditório) | `[]` + `WARNING` |

A `position` não é renumerada nos itens reusados (W-3). Decisão completa, com evidência e custos:
[V-27](../../../docs/feat-api-estructure/decisoes-refino-409/V-27-fluxo-resolvido-no-repositorio.md).

### D14 · O append da D5 original apagava a herança — e o T11 provava isso

Preservar a lista remota e somar o declarado funciona quando o escopo **já tem** lista própria. Quando
ele herda (lista vazia), o "append" publica uma lista de um item — e pela W-4 essa lista passa a ser o
fluxo inteiro do escopo. Os herdados somem, sob HTTP 200.

O T11 da bateria registrou exatamente isso como ✅: *"a rota foi de 0 para 1 item próprio"*. O oráculo
perguntava se a rota ganhara o item; a pergunta certa era se ela continuava executando o que herdava.

Duas consequências assumidas de propósito, com a intenção de produto declarada pelo usuário em
2026-10-15 (*"o dev tem liberdade de ajustar a API pelo repo"*):

1. **o repositório sobrescreve a plataforma** — um escopo editado direto no Manager é substituído;
2. **a hierarquia do repo precisa estar completa** — um `resource.yaml` incompleto propaga o erro para
   baixo, onde antes a plataforma cobria o buraco.

Por isso toda remoção que a mudança provoca é **avisada**: lista própria que sai em favor da herança,
`inherit: false` sem itens, e `all.yaml` sem interceptors com raiz remota populada.

### D6 · A régua vem de uma API template, não de schema versionado

Os 7 `*-default-interceptors.schema.json` congelam o fluxo por cliente (`minItems`/`maxItems`/`const`,
posição a posição) dentro do `domain/`. São substituídos por `GET /apis/{template}` — um GET basta,
`lastRevision` já traz o fluxo completo com `content`. A template valida **tipo e preenchimento** do
interceptor e emite `INFO`/`WARNING`: o dev decide subir algo fora do padrão.

*Consequência aceita:* a template diz o que **ela usa**, não o que **é válido**. O comparador afirma
com segurança "difere da régua", não "é tipo inválido" — então `quota: "abacaxi"` e
`encryptContent: true` contra `false` chegam ao dev com a mesma severidade, embora só o primeiro vá
ser recusado na E3.

### D7 · Conformidade compara `content` nos tipos nativos; `Custom` casa por id

`Custom` é referenciado por `customInterceptorId`: mesmo id, mesmo objeto no tenant, mesmo script —
comparar `content` seria redundante e produziria diff textual de script. Nos tipos nativos o `content`
**é** a configuração, e é onde mora o caso real (um `Log` com `encryptContent` divergente da régua).

A comparação é por **sequência**, não por conjunto: um append de um tipo que já existe na régua
desaparece numa comparação por conjunto. Exige normalização prévia de escalar numérico — o wire
devolve `"quota": "1000"` como string, e o lado do repositório vem do YAML.

### D8 · Falha técnica bloqueia; divergência de padrão informa

| Situação | Desfecho |
|---|---|
| régua inalcançável (404/403/rede) ou `spec.template` vazio | **aborta**, nos dois modos de execução |
| `Custom` referenciado que não existe no tenant | **aborta**, nomeando o id |
| arquivo base ausente (`all.yaml`, `resource.yaml`) | **aborta** na E1, antes de rede |
| bloqueio do Adaptive Governance | **aborta** com exit 3 |
| divergência da régua, preenchimento fora do padrão, deriva de override | `INFO`/`WARNING`, exit 0 |
| completeness abaixo de 70% | informativo, exit 0 |

O arquivo base é obrigatório **pelo nome exato**: assim um typo (`alll.yaml`) produz ausência, que
aborta, sem precisar proibir `.yaml` não relacionados no repositório. A gravidade justifica o aborto —
a raiz não herda de ninguém, então publicar sem ela não preserva nada: **apaga o fluxo da revision**.

*Alternativa descartada para o `Custom` inexistente:* repor o `content` a partir de outra revision da
própria API, como faz o protótipo. Ressuscita uma referência que um administrador apagou de propósito
e, quando não acha, descarta o item em silêncio.

### D9 · Tombstone é a lista completa explícita

Lista vazia significa **herdar**; "rota sem fluxo" não existe na plataforma. Para não executar um item
herdado é preciso declarar o fluxo inteiro que vale. Não é a melhor forma — é a única expressável.

*Consequência:* a cópia explícita congela o fluxo do pai. Se o pai ganha um interceptor depois, a rota
que fez override não recebe. O comparador emite `WARNING` quando a diferença contra o fluxo do pai for
maior que a remoção declarada.

### D10 · Dois regimes de saída, um contrato

`text` renderiza para leitura no PowerShell. `json` e `yaml` serializam a mesma árvore sob
`apiops.sen-validate/v1`, com o **snapshot da régua** (`id`, `revisionNumber`, hash do fluxo) para que
um achado continue reproduzível depois que a template mudar. `--verbose` afeta verbosidade de log,
nunca formato. Nenhuma saída pode conter token, cookie ou material de credencial, nem dump cru de wire.

Exit codes: `0` sucesso (inclui INFO/WARNING), `1` falha técnica ou de gramática, `3` bloqueio de
governança — canal distinto, para a esteira ramificar sem ler texto.

### D11 · O pré-check de governança calcula, não parseia

`"API must contain attribute My new"` é mensagem livre. O faltante sai de
`exigidos(mustHave do stage) - presentes(apiTags do repositório)`, com o catálogo `id <-> name` lido
por GET. Os requisitos são **configuração mutável do tenant**: entre 2026-10-14 e 2026-10-15 o stage
1402 trocou `{149 My new, 96 CLI}` por `{149 My new, 231 teste giroto}`. Nenhum valor pode ser fixado
em código.

### D12 · O `validate` local escreve, sob consentimento explícito

O canônico de 17/08 concede a exceção da Draft à esteira — *"uso exclusivo da esteira, sobrescrita a
cada execução"* (Decisão 10 + P1). A D-005 §9 estende a escrita a `EXECUTION_MODE=local`. A
reconciliação é a **guarda 2**: em modo local a publicação exige confirmação `s/n`; em `pipeline` não
pergunta. A intenção do canônico era impedir publicação **acidental**, e a guarda é exatamente esse
mecanismo — a escrita local passa a ser ato deliberado do dev.

*Alternativa descartada:* `validate` local sem escrita, parando após o pré-check. O pré-check já
calcula o atributo faltante sem publicar, mas se perderia a conferência pós-publicação (D3), que é a
única defesa contra as perdas silenciosas sob 200.

### D13 · `Custom` continua referenciado por id numérico

O id é estável dentro de um ambiente. Quando muda — por exemplo ao mover o repositório entre
ambientes — a validação é responsabilidade do dev, e o aborto da D8 a torna visível: o comando nomeia
o id inexistente, em vez de falhar tarde ou publicar sem o item.

*Alternativa descartada:* referenciar por nome, ou pelo par id + nome. Trocaria a chave de identidade
por um campo que a plataforma não garante único, para cobrir um caso que não é falha de rotina.

## Risks / Trade-offs

- **A plataforma aceita e perde, com 200** → conferência pós-publicação obrigatória (D3); divergência
  é falha, e o teste de integração cobre os 10 cenários do caderno com backup e restore.
- **O `WARNING` não distingue escolha de quebra** (D6) → documentar o limite na saída; a E3 continua
  sendo quem recusa valor inválido.
- **403 é ambíguo** entre sessão expirada e id de outro tenant, e a plataforma não devolve 401 para
  token inválido → a mensagem nomeia as duas possibilidades em vez de escolher uma.
- **Override congelado deriva em silêncio** (D9) → `WARNING` de deriva; não há como evitar a cópia, só
  como avisar.
- **A onda 3 não tem oracle** → depende de ambiente de escrita provisionado (P-8); até lá, os 10
  cenários do caderno contra a API 417 são a única rede.
- **Dois escritores na mesma Draft** — a esteira e a máquina do dev (D12), sem lock, com janela E3→E4
  → risco aceito (D-15). Era o que o *"uso exclusivo da esteira"* queria evitar; a guarda 2 torna a
  escrita local deliberada, mas não serializa os dois atores.
- **Remover os 7 schemas é BREAKING** → verificado na fase 0: eram **órfãos**, sem referência em
  `src/` ou `tests/` e ausentes do `catalog.json`. A remoção não quebrou nada.
- **A reescrita dos schemas partiu o layout em dois, e a investigação achou a causa** →
  `JsonToYamlService` produzia o layout antigo e validava contra os schemas reescritos. Ao rastrear o
  consumidor, descobriu-se que ele **não tinha nenhum**: `JsonToYamlService`, `RevisionFileGenerator`,
  `LocalFileExporterAdapter`, `PathExporterPort` e os enums `JsonKind` formavam uma ilha fechada,
  referenciada só por si mesma e pelos próprios testes — e o `RevisionFileGenerator` já importava um
  módulo inexistente, portanto estava quebrado. A ilha foi **removida** (5.474 linhas), e o conflito
  desapareceu com ela. O materializador canônico será escrito sobre os dicts crus do Manager, sem
  depender de `ApiFull`, cujos modelos só são corrigidos na fase 3.
- **O despacho de schema por `kind` não cobre o layout canônico** → só `api-basic-info.yaml` carrega
  `kind`; `all.yaml`, `resource.yaml` e os arquivos de operação são planos, e o
  `if kind and kind in kind_to_schema` os ignoraria **em silêncio**. O `catalog.json` passa a
  declarar também um mapa por **caminho**, com primeira correspondência vencendo, consumido pela
  descoberta da E1.

## Migration Plan

Quatro fases, com o corte em **o que é testável sem escrita na plataforma**:

| Fase | Conteúdo | Rede | Oracle |
|---|---|---|---|
| **0 · demolição + contrato** | remoção dos 7 schemas, catalog, settings, enums, `repo_validator`; borda da CLI, `ValidateView`, erros tipados, exit codes | nenhuma | suíte no baseline, com a fronteira de layout marcada por `xfail` estrito |
| **1 · import** | `extrair_estrutura.py` vira importer de produção; `repo_layout`; partição governado × preservado | só GET | 6 APIs reais / 155 YAML saem idênticos |
| **2 · conformidade** | `template_conformance`; sequência + `content`; INFO/WARNING; snapshot da régua | só GET | 4 achados previstos nas APIs 409 e 417 |
| **3 · publish** | `interceptor_flow`, PUT na revisão fixa, hidratação, pré-check do AG, conferência pós-publicação, exit 3 | **ESCRITA** | 10 cenários do caderno, com backup e restore |

Rollback: as fases 0–2 não tocam a plataforma e revertem por git. A fase 3 escreve apenas na Draft,
que não tem deploy; o instrumento de teste já faz backup completo da API e de todas as revisions antes
de qualquer escrita, com restauração por comando.

**Alvo de escrita da fase 3:** a **API 417**, que é específica deste projeto e já atende ao que a
bateria exige — Draft (revisão 9161) sem deploy, stage 1402 com `attributesRequisites` (sem o que a
D1 não seria exercitada), fluxo declarado na raiz, em recurso e em operação, `Custom` referenciados e
um caso de supressão em `GET /tarefas`. O arnês faz backup completo da API e de todas as revisões
antes da primeira escrita, com restauração por comando.

## Open Questions

Nenhuma questão em aberto no escopo desta change. Os itens abaixo ficam registrados porque encostam
nela sem bloqueá-la:

- **Versionador** (D-1) — qual comando expõe o `sen version sync`. Fica para a change seguinte.
- **Pendentes de produto** — `apiTags[].attributeName` editável, separação do Adaptive Governance.
- **P-7** — o README dos exemplos gerados está desalinhado da D-005 §4 e agora também do `all.yaml`.
- **Mapeamento de `403` no `sen completeness`** — `completeness_service.py:84-87` traduz `403` para
  *"revisão não encontrada"*. A plataforma devolveu `403` para token inválido, o que sugere que
  sessão expirada receba a orientação errada. Medido com token adulterado, não expirado: é suspeita,
  não diagnóstico, e pertence ao `sen completeness`, não a esta change.
