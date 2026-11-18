# V-12 (a) · Identidade no repo — nenhum id além do da API

| Meta | Valor |
|---|---|
| Status | **FECHADO** — 2026-10-14 |
| Escopo | identidade, correlação e **alvo do publish**. A forma da árvore (V-12) e a regra de slug (V-16) seguem abertas |
| Fonte | `GET /revisions/9161` e `/9175` (API 417) · `mapeamento APIM/docs-sensedia/03-edicao-revisoes-recursos.md` |

## 1. Decisão

1. O repo **não versiona** `id` de recurso nem de operação. O **único** id versionado é o da API
   (`spec.id`, readOnly, D-003).
2. A chave estável de correlação é **`(método, path)`** da operação.
3. `name` do recurso é **dado versionado**, não chave.
4. O recurso é identificado pelo **conjunto de operações que agrupa**.
5. O publish envia o estado completo; o Manager regenera os ids.

Motivo declarado pelo usuário: id visível é editável — e um id editado à mão sobrepõe outro recurso
ou duplica rota, silenciosamente.

## 2. Evidência

### 2.1 Os ids morrem a cada revisão (shadow-copy)

Mesma API 417, duas revisions:

| | revision 1 (9161) | revision 2 (9175) |
|---|---|---|
| recursos | 9162 – 9167 | 9176 – 9179 |
| operações | 9168 – 9174 | 9180 – 9186 |

Nenhum id se repete. `DELETE /letras/{id}` é **9174** na rev1 e **9182** na rev2 — mesma rota, id novo.

O mapeamento já registrava: *"**Shadow-copy por revisão**: cada nova revisão re-gera
`resources[]`/`operations[]` com IDs novos (8959-8971 → 8987-8999) — dados isolados por revisão"*.

Consequência prática: versionar esses ids faria **todo publish gerar diff em todos os arquivos**, por
um número sem significado fora daquela revisão.

### 2.2 A escrita é sobreposição total

| Ação na UI | Endpoint | Efeito |
|---|---|---|
| Save | `PUT /api-manager/api/v3/revisions/{id}` | grava na revisão corrente |
| Save as new Revision | `POST /api-manager/api/v3/revisions` | cria `revisionNumber + 1` |

Payload *"**DENSO** — nada de sparse"*: `resources[]` completos, cada operação com `destination`,
`timeout`, `certificateId`, `async`, `urls`, `instruction`.

Isso dissolve a objeção de que renomear um recurso "perderia" seus interceptors e destination: ela
pressupõe publish incremental. Com sobreposição total não há merge a preservar — o repo descreve o
estado final.

### 2.3 `name` não é único — colisão real, não hipotética

Revision 1 da 417:

```
resource 9162 name='Letras'    -> DELETE /letras/{id}
resource 9163 name='Letras'    -> POST   /tarefas/{id}/letras
resource 9165 name='Tarefas'   -> GET    /tarefas/{id}
resource 9167 name='Tarefas'   -> GET    /tarefas
```

Dois `Letras` e dois `Tarefas` convivendo — foi o que a revision 2 consolidou (6 recursos → 4).
O que sobreviveu intacto à reorganização foram os **7 pares `(método, path)`**, idênticos nas duas.

## 3. Comparativo que sustentou a escolha

| Critério | Identidade por `id` | Identidade por `(método, path)` |
|---|---|---|
| Estabilidade | ❌ muda a cada revisão | ✅ sobreviveu à reorganização de recursos |
| Risco de edição humana | ❌ número editado sobrepõe ou duplica rota em silêncio | ✅ editar o path muda a rota — visível e intencional |
| Necessário no publish? | ❌ não: o PUT é denso e regenera tudo | ✅ o estado completo basta |
| Ruído no git | ❌ todos os arquivos mudam a cada publish | ✅ diff reflete só mudança real |
| Unicidade | ✅ garantida | ⚠️ `name` duplica; a chave tem de ser `(método, path)` |

## 4. Consequências para o desenho

1. **Import** decide em que pasta escrever pelo conjunto de operações já presentes nela — não por id.
2. **Slug de pasta precisa de regra de colisão real** (dois recursos `Letras`): é o V-16, e deixou de
   ser hipótese.
3. **Publish** monta o estado completo a partir do repo + estado não governado lido por GET
   ([V-22](V-22-estado-nao-governado.md)); nenhum id de recurso/operação sai do repo.
4. Mover uma operação entre recursos é expressá-la em outra pasta — o diff é um rename de arquivo.

## 5. Alvo do publish — revisão fixa

**Decisão (2026-10-14):** ids diferentes entre revisões são **comportamento esperado da plataforma**,
não um problema a resolver. O orquestrador **não compara revisões**: ele é orientado explicitamente a
subir o update em uma **revisão fixa**, informada a cada execução.

| Consequência | Efeito |
|---|---|
| operação de escrita | `PUT /api-manager/api/v3/revisions/{alvo}` — grava na revisão corrente, **não** cria nova |
| regeneração de ids dentro da revisão | **irrelevante** — nada no repo depende deles |
| `POST /revisions` (save-as-new) | fora do fluxo do publish; criar revisão é ato humano, não do orquestrador |
| comparação entre revisões | **não existe** no ciclo |

Nos exemplos deste refino o alvo é a **revisão 2 da API 417 (id 9175)**.

### 5.1 Número da revisão × id — sondagem das rotas (somente leitura)

| Chamada | Resultado |
|---|---|
| `GET /revisions/2` | **404** — `"Revision with identifier 2 not found!"` → o path param é o **id**, nunca o número |
| `GET /apis/417/revisions/2` | **403** (rota inexistente, rejeitada no gateway) |
| `GET /revisions?apiId=417&revisionNumber=2` | **500** |
| `GET /revisions?revisionNumber=2` | **500** |
| `GET /apis/417/revisions` | **200** — devolve **um objeto**: a revisão **corrente** inteira (id 9175, `revisionNumber` 2, 4 recursos) |
| `GET /apis/417` | **200** — `revisions: [{id 9161, n 1}, {id 9175, n 2}]` e `lastRevision: {id 9175, n 2}` |

**Conclusão:** a plataforma **não aceita o número** como identificador de rota — o `PUT` exige o id.
Mas a tradução número → id **não custa chamada extra**: o `GET /apis/{id}` já devolve o par
`{id, revisionNumber}` de todas as revisões, e esse GET o publish já faz de qualquer forma
(hidratação da D-002 + estado não governado do [V-22](V-22-estado-nao-governado.md)).

**Proposta:** a interface do orquestrador aceita o **número** da revisão (é o que o humano enxerga na
UI e o que não muda de significado), resolve para o id com o GET que já faz, e aceita o id como
alternativa. Se o número não existir na API, falha antes de qualquer escrita, nomeando as revisões
disponíveis.

**Resolvido em [V-24](V-24-revisao-alvo-do-publish.md):** a revisão alvo é declarada por variável de ambiente,
pelo **número** (1=Draft, 2=DEV, 3=HML, 4=PRD); local publica apenas na Revision 1. Como a D-003 §2 mantém revisões **fora**
do repo, ele não cabe no manifesto — proposta: mesmo arranjo do template ([V-11](V-11-binding-do-template.md)),
variável de configuração local e variável de ambiente na esteira, com possibilidade de override por
parâmetro de comando.

## 6. Aberto

| Ponto | Situação |
|---|---|
| Forma da árvore (pasta-por-recurso × por path) | **V-12**, ainda aberto |
| Regra de slug e de colisão | **V-16**, ainda aberto |
| Onde declarar a revisão alvo | **fechado** → [V-24](V-24-revisao-alvo-do-publish.md) |
