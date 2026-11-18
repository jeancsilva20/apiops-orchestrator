# V-11 · Conformidade com a régua (API 414) — severidades e saída

| Meta | Valor |
|---|---|
| Status | **FECHADO** na severidade e no alvo · V-11 segue aberto no binding (`spec.template`: onde mora e qual valor) |
| Data | 2026-10-14 |
| Fonte | `GET /revisions/9131` (régua), `/9103` (API 409), `/9175` (API 417) — somente leitura |
| Papel da 414 | **só interceptors**. Tags são governadas pelo Adaptive Governance (ver [V-23](V-23-bloqueio-do-adaptive-governance.md)) |

## 1. Decisão

**A validação informa; quem julga é o code review.** Nada aqui bloqueia publish ou deploy.

| Situação | Severidade | Tratamento |
|---|---|---|
| **Append** — itens além dos da régua | `INFO` | permitido em **todos** os cenários; apenas logado |
| **Override** — item da régua ausente, removido (tombstone) ou alterado em algum caminho | `WARNING` | logado com **o que falta e onde falta**; revisto no code review |
| Qualquer um dos dois | — | **não bloqueia** `publish` nem `deploy`; exit code `0` |

Regras rígidas (exceções declaradas, bloqueio por política) ficam para depois, quando houver uso real
suficiente para saber o que vale bloquear.

**Alvo da comparação: conformidade efetiva.** "Onde falta" só existe se a verificação percorrer cada
caminho de execução — raiz da revision, recurso e operação — resolvendo herança, tombstones e override.
A comparação estrutural (só a raiz) não serviria: nas duas APIs reais a raiz está conforme e todas as
divergências estão abaixo dela.

Itens de **estado não governado** (fora de `FIRST`/`SECOND`) não entram na comparação — ver
[V-22](V-22-estado-nao-governado.md).

## 2. Como isso se distingue do bloqueio do AG

| Canal | Origem | Bloqueia? | Exit code |
|---|---|---|---|
| Conformidade com a régua | cálculo local do orquestrador | **não** | `0` |
| Adaptive Governance (HTTP 412) | plataforma, no publish | **sim** | `3` ([V-23](V-23-bloqueio-do-adaptive-governance.md)) |

São dois canais independentes: a régua é higiene de fluxo revisada por humano; o AG é precondição da
plataforma, que simplesmente recusa a subida.

## 3. Achados reais — o que a regra produz hoje

Régua (revision 9131), 8 itens governados:
`Custom#125 · Log · Custom#178 · Rate limit · Payload size · XSS threat protection · Log` (FIRST) + `Log` (SECOND).

| API | Escopo | Achado | Severidade |
|---|---|---|---|
| 409 e 417 | raiz da revision | **conforme** — 8 de 8 | — |
| 409 (op 9113) · 417 (op 9183) | `GET /tarefas` | **tombstone** removendo `XSS threat protection` | `WARNING` |
| 409 (op 9112) · 417 (op 9186) | `GET /health-check` | **override** sem `Custom#178` (*CyberArk and OAuth Autentication*) | `WARNING` |
| 409 (res 9106) · 417 (res 9179) | recurso de atribuição | **append** de `Additional Info` (SECOND) | `INFO` |
| 409 (op 9111) · 417 (op 9181) | `POST /…/atribuicao-responsavel` | `Log` na posição 7 com `encryptContent: true` — a régua tem `false` | `WARNING` (alterado) |

As duas APIs produzem exatamente os mesmos quatro achados. Nenhum deles impede a publicação.

> ⚠️ **Releitura em 2026-10-15 — o estado medido mudou, a regra não.**
>
> A régua (414, revisão 9131) continua idêntica: os mesmos 8 itens. O que mudou foi a **417**: o
> `Custom#125` da raiz foi trocado por `#32`, como o [caderno §5](../prova-fluxo-validate/CADERNO-DE-TESTES.md)
> registra (*"os ids 125/178 foram trocados por 32/33 antes desta bateria"*). A régua segue pedindo
> `#125`, então a divergência é **real** e se propaga a todo escopo que herda da raiz.
>
> Rodando o comparador implementado contra o estado de 2026-10-15: **28 achados** (18 `WARNING`,
> 10 `INFO`). Os quatro originais continuam lá — tombstone do XSS em `GET /tarefas`, append de
> `Additional Info` no recurso de atribuição, `Log` com `encryptContent` divergente no
> `POST /…/atribuicao-responsavel` — e o excedente é a deriva do `Custom`, mais os escopos cujo fluxo
> encurtou.
>
> A linha "raiz da revision — **conforme** 8 de 8" da tabela acima vale para 2026-10-14. Hoje a raiz
> produz 2 achados, um par `WARNING`/`INFO` na posição do `Custom`.
>
> **É o caso que o snapshot da régua (D-4/P-3) existe para resolver:** sem gravar `id`,
> `revisionNumber` e hash do fluxo junto com o achado, uma tabela como esta envelhece sem aviso. O
> conjunto de 2026-10-15 está congelado em `tests/fixtures/manager/` e travado por teste.
>
> ⚠️ **Segunda deriva, no mesmo dia — agora na própria régua.** Horas depois da releitura acima, a
> **414 passou a pedir `Custom#32`/`#33`** no lugar de `#125`/`#178`, com ids de interceptor novos
> (`19768`, `19769`). As referências mortas foram corrigidas no template, como foram na 417. Com
> isso o conjunto de achados contra a revisão 9175 subiu de 28 para **38** (23 `WARNING`,
> 15 `INFO`) — a 9175 ainda executa `#125`/`#178`.
>
> Duas derivas da régua em um único dia é o argumento prático mais forte a favor do snapshot
> (D-4/P-3): **um achado sem `id`, `revisionNumber` e hash não é reproduzível nem por algumas horas.**
>
> **Formato do rótulo (§5) corrigido na implementação:** os achados passaram a trazer
> `Custom #33 — CyberArk and OAuth Autentication` em vez de `Custom#33`. Sem o nome, as duas pontas
> da deriva (`#178` ausente da régua, `#33` exigido) parecem interceptors diferentes; com ele, vê-se
> que é o mesmo sob ids distintos.

## 4. Requisitos do comparador (lições do cálculo real)

1. **Comparar sequência, não conjunto.** Um append de um tipo que já existe na régua (outro `Log`)
   desaparece numa comparação por conjunto. O comparador precisa de multiconjunto/ordem.
2. **Comparar `content`.** O caso da `POST /…/atribuicao-responsavel` é um `Log` que a régua também
   tem — a diferença está só no `content` (`encryptContent: true` × `false`), e ela muda o
   comportamento. Comparar apenas `(executionPoint, type, customInterceptorId)` deixaria passar.

   **Granularidade fechada em 2026-10-15:** o `content` é comparado **nos tipos nativos**, onde ele
   *é* a configuração. Para interceptors **`Custom` o casamento é por `customInterceptorId`, e o
   `content` NÃO é comparado**: o mesmo id designa o mesmo objeto no tenant, então a comparação seria
   redundante e produziria diff textual de script. Requisito derivado: **normalizar escalar numérico
   antes de comparar** — o wire devolve `"quota": "1000"` como string e o lado do repositório vem do
   YAML, de modo que a igualdade estrutural crua acusaria achado falso num campo idêntico.

   A mesma comparação cobre o **preenchimento** do interceptor, já que os `*-default-interceptors`
   são aposentados (D-5). Limite aceito: a template diz o que *ela usa*, não o que *é válido* — o
   comparador afirma "difere da régua", não "é tipo inválido".
3. **Classificar o modo.** O wire não traz flag de override: o que distingue é a forma da lista —
   poucos itens (append), reprodução do fluxo herdado com omissões (override), item `status: REMOVED`
   (tombstone). Essa classificação é inferência sobre o payload e deve ser testada contra casos novos.
4. **Ignorar o não governado** (`executionPoint` fora de `FIRST`/`SECOND`).

## 5. Formato da saída

Mesmo padrão aprovado no V-23: linha humana + JSON estruturado.

```
WARNING  GET /health-check (op 9186): o fluxo sobrescreve a régua e não executa
         "Custom #178 — CyberArk and OAuth Autentication", exigido pelo template 414.
WARNING  GET /tarefas (op 9183): o fluxo remove "XSS threat protection" herdado da revision.
WARNING  POST /tarefas/{id}/atribuicao-responsavel (op 9181): "Log" na posição 7 difere da régua
         (encryptContent: true × false).
INFO     resource "Atribuicao Responsavel" (9179): 1 item além da régua — "Additional Info".
```

```json
{
  "outcome": "template_conformance",
  "template": 414,
  "blocking": false,
  "findings": [
    { "severity": "WARNING", "kind": "MISSING", "scope": "operation", "id": 9186,
      "method": "GET", "path": "/health-check",
      "item": { "type": "Custom", "customInterceptorId": 178, "executionPoint": "FIRST" },
      "mode": "OVERRIDE" }
  ]
}
```

## 6. Aberto

1. **Binding do `spec.template`** (V-11, perguntas 1 e 4): onde a declaração mora e se o valor é o id
   numérico. Recomendação registrada: `api-basic-info.yaml`, chave sempre declarada, vazio permitido,
   valor = id.
2. **Exceções declaradas** (o health-check é legítimo): fora de escopo agora, por decisão — enquanto a
   validação não bloquear, o `WARNING` recorrente é aceitável.
3. **Separar as duas heurísticas da D-003 §6.** O import distingue append × override comparando com o
   fluxo da **própria revision**; a conformidade compara com a **régua**. A D-004 §2.2 congelou as duas
   como se fossem uma só.
