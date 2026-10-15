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

## 4. Requisitos do comparador (lições do cálculo real)

1. **Comparar sequência, não conjunto.** Um append de um tipo que já existe na régua (outro `Log`)
   desaparece numa comparação por conjunto. O comparador precisa de multiconjunto/ordem.
2. **Comparar `content`.** O caso da `POST /…/atribuicao-responsavel` é um `Log` que a régua também
   tem — a diferença está só no `content` (`encryptContent: true` × `false`), e ela muda o
   comportamento. Comparar apenas `(executionPoint, type, customInterceptorId)` deixaria passar.
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
