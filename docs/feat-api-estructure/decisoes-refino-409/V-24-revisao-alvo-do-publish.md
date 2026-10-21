# V-24 · Revisão alvo do publish — número, não id; local só na Draft

| Meta | Valor |
|---|---|
| Status | **FECHADO** — 2026-10-14 · **revisado** em 2026-10-21 (§6: publish local removido) |
| Depende de | [V-12 identidade](V-12-identidade-sem-ids.md) · [V-11 binding](V-11-binding-do-template.md) (mesmo arranjo de configuração) |
| Fonte | `arquitetura-apiops-memory-bank/artifacts/prd-apiops-cicd.md` §3.3 · `context/domain-glossary.md` · sondagem de rotas (somente leitura) |

## 1. Decisão

1. A revisão alvo do publish é informada por **variável de ambiente**, pelo **número** da revisão —
   nunca pelo id.
2. Em **máquina local**, só é permitida publicação na **Revision 1 (Draft)**, por padrão.
3. O número segue o modelo de **revisions fixas por ambiente** já definido na arquitetura.

## 2. O modelo de revisions fixas (arquitetura, PRD §3.3)

| Branch | Ambiente de deploy | Revision | Stage (AG) |
|---|---|---|---|
| `feat/...` | **nenhum** | **Revision 1 — Draft** | Draft |
| `develop` | DEV | Revision 2 | DEV |
| `release` | HML | Revision 3 | HML |
| `main` | PRD | Revision 4 | PRD |

> `context/domain-glossary.md`: *"**Draft** | Revision 1, contexto de diagnóstico do developer, sem
> deploy e sem bloqueio."*

A trava local é coerente com a decisão de 17/08/2026 registrada em `knowledge/comandos-cli-sen.md`
(*"o dev não publica nem deploya diretamente via CLI para nenhum ambiente"*): a Draft **não é
ambiente** — não tem deploy. Publicar nela é diagnóstico, não promoção.

*Pendência herdada:* o PRD condiciona a publicação na Draft à **P9** (reconciliação do ADR de
versionamento incremental × revisions fixas). A decisão aqui não resolve a P9; apenas assume o modelo
de revisions fixas, que é o vigente.

## 3. Por que número e não id

| Chamada sondada | Resultado |
|---|---|
| `GET /revisions/2` | **404** — `"Revision with identifier 2 not found!"` → a rota usa o **id** |
| `GET /apis/417/revisions/2` | **403** (rota inexistente) |
| `GET /revisions?apiId=417&revisionNumber=2` | **500** |
| `GET /apis/417` | **200** — `revisions: [{id 9161, n 1}, {id 9175, n 2}]` |

A plataforma não aceita o número na rota, mas a tradução **não custa chamada extra**: o
`GET /apis/{id}` que o publish já faz (hidratação da D-002 + estado não governado do
[V-22](V-22-estado-nao-governado.md)) devolve o par `{id, revisionNumber}` de todas as revisões.

O número é o identificador certo para a configuração porque é **o que o humano vê na UI**, é estável
no tempo e é o que o modelo de revisions fixas usa (1=Draft, 2=DEV, 3=HML, 4=PRD). O id é detalhe de
transporte, resolvido pelo CLI no último instante.

## 4. Configuração

```bash
# .env — modo (ver V-11)
EXECUTION_MODE=local            # local | pipeline

# número da revisão alvo — nunca o id
TARGET_REVISION_NUMBER=1        # local: 1 é o único valor aceito
```

```yaml
# esteira — o número vem do ambiente, conforme a branch
env:
  EXECUTION_MODE: pipeline
  TARGET_REVISION_NUMBER: 2     # develop=2 · release=3 · main=4
```

| Situação | Comportamento |
|---|---|
| `EXECUTION_MODE=local` com número ≠ 1 | **recusa antes de qualquer escrita**, explicando que local publica só na Draft |
| número ausente | local assume `1`; em esteira é **falha de configuração** (mesmo critério do template, V-11) |
| número não existe na API | falha antes de escrever, **nomeando as revisões disponíveis** |
| revisão inexistente no Manager | **não cria** — criar revisão é ato humano ([V-12](V-12-identidade-sem-ids.md) §5) |

## 5. Fluxo resultante

```
1. modo   = EXECUTION_MODE                  (default: local)
2. numero = TARGET_REVISION_NUMBER          (local: só 1)
3. GET /apis/{spec.id}                      -> revisions[] + estado para hidratar
4. id = revisions[].id onde revisionNumber == numero
       (ausente -> falha nomeando as disponíveis)
5. PUT /api-manager/api/v3/revisions/{id}   -> payload denso, estado completo do repo
```

O passo 3 é a mesma chamada que já alimenta a hidratação e o estado não governado — nenhuma
requisição é adicionada ao ciclo.

## 6. Revisão de 21/10/2026 — publish só na esteira

Change `hide-pipeline-settings-from-dev`. Substitui o item 2 da §1 e as linhas de modo local da §4.

1. O `sen publish` **não roda na máquina do dev**: fora da esteira ele recusa antes de autenticar e
   de qualquer chamada HTTP, como o `sen deploy`. A confirmação local do publish deixa de existir.
   Fica mais perto da decisão de 17/08/2026 citada na §2 (*"o dev não publica nem deploya
   diretamente via CLI"*).
2. A gravação na Draft pela máquina do dev continua no **`sen validate`**, que nela usa **sempre a
   revisão 1** e **não lê** `TARGET_REVISION_NUMBER`. A recusa "local com número ≠ 1" deixa de
   existir: ela só servia para citar a variável.
3. Na esteira, nada muda: `TARGET_REVISION_NUMBER` continua obrigatória no publish e resolvida pelo
   número, como nas §3–§5.

Motivo: as mensagens da máquina local citavam `EXECUTION_MODE` e `TARGET_REVISION_NUMBER`, dando ao
dev o caminho para se passar pela esteira. Na máquina do dev, a configuração deixa de ter efeito
sobre a revisão alvo, e nenhuma saída cita o modo ou as variáveis da esteira.
