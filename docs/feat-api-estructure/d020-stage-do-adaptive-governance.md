# D-020 — O stage do Adaptive Governance é lido em runtime

**Status:** Fechada em 2026-10-15.
**Natureza:** Decisão de comportamento do `sen validate` e do `sen publish`. Não altera o layout.
**Origem:** refino do `sen validate`. Substitui a formulação da D-20 registrada em [`guia-implementacao-sen-validate.md`](guia-implementacao-sen-validate.md) §10 e corrige a afirmação de [`plano-comandos-sen.md`](plano-comandos-sen.md) §8.4 sobre o stage 1401.
**Evidência:** leitura **somente GET** do tenant consulting em 2026-10-15 (`/apis/417`, `/revisions/9161`, `/revisions/9175`, `/workflows/500`, `/workflows/139`, `/attributes`) e os nove logs da bateria em [`prova-fluxo-validate/logs-caderno/`](prova-fluxo-validate/logs-caderno/). Nenhuma escrita.

---

## 1. Decisão

> O orquestrador **lê** `workflowId` e `workflowStageId` do `GET /revisions/{id}` da revisão alvo e os
> **reenvia intactos** no payload do `PUT`. Nunca configura, nunca infere, nunca avança o stage.

O stage é propriedade da API e do ambiente: muda por API e por tenant, e é pré-configurado na
plataforma. O CLI não precisa conhecê-lo de antemão, e não deve ter opção para escolhê-lo.

Na prática isso já acontece por construção quando o payload é montado como cópia profunda do estado
remoto — os dois campos viajam na cópia, sem serem reescritos.

## 2. A pergunta original estava mal formulada

A D-20 perguntava: *"o `validate` reenvia o stage atual ou avança para o próximo?"*, apoiada nesta
afirmação do plano §8.4:

> o gate só dispara se o `workflowStageId` enviado apontar para um stage com `attributesRequisites` —
> reenviar o stage atual (**1401**, sem requisitos) **pula a validação**

A premissa não se sustenta. O stage **1401 nunca esteve em jogo**: não aparece em nenhum log da
bateria. Ele foi lido do catálogo do workflow 500 (V-23 §2), onde de fato tem
`attributesRequisites: []`, e dali se concluiu — por dedução, não por observação — que a Draft
estaria nele.

A Draft está no **1402**. Os dez cenários rodaram com o stage atual reenviado, sem forçar nada, e o
**AG disparou** (T03 → HTTP 412). Reenviar o stage atual não pula a validação: faz exatamente o que
se espera dela.

Não havia escolha a fazer. Há um comportamento a descrever.

## 3. Evidência

### 3.1 O par `workflowId` / `workflowStageId` é autoconsistente

| Leitura | Resultado |
|---|---|
| `GET /revisions/9161` (Draft, nº 1) | `workflowId: 500` · `workflowStageId: 1402` |
| `GET /revisions/9175` (nº 2) | `workflowId: 500` · `workflowStageId: 1402` |
| `GET /workflows/500` | `TEAM`, `groupId: APIOps`, stages **1401** (`position 1`) e **1402** (`position 2`), ambos com `workflowId: 500` |

O stage gravado na revisão pertence ao workflow gravado na mesma revisão. **O pré-check lê o par da
própria revisão** — não precisa resolver o workflow pelo grupo da API.

### 3.2 A divergência da V-23 §3 não existe mais

A [V-23 §3](decisoes-refino-409/V-23-bloqueio-do-adaptive-governance.md) registrou a revisão 9175 em
`workflowId 139` / `workflowStageId 420`, validada pelo workflow `500` — e concluiu que *"ler
`revision.workflowId` **não** antecipa o bloqueio"*.

Hoje a 9175 carrega `500/1402`. Era **estado transitório**: o workflow 500 foi criado minutos antes
daquela leitura (`creationDate: 1791976185382`), e a revisão ainda não havia migrado.

*Ressalva de engenharia:* a plataforma já exibiu o estado inconsistente uma vez. O pré-check deve
degradar com elegância quando o `workflowStageId` não for encontrado no workflow lido — reportar, não
assumir.

### 3.3 Um PUT aceito não move o ponteiro de stage

Os nove logs da bateria releem a Draft a cada execução, e **todos** registram `workflowStageId=1402`.
Sete deles foram publicações aceitas (T01, T04, T05, T07, T08, T10, T11). Se um PUT bem-sucedido
avançasse o stage, a execução seguinte leria outro valor. Nunca leu.

**Publicar não promove.** Coerente com a V-24: a Draft é contexto de diagnóstico, sem deploy.

### 3.4 Os requisitos do stage são configuração mutável

| | `attributesRequisites` do stage 1402 |
|---|---|
| V-23, 2026-10-14 | `{149 My new, 96 CLI}` |
| leitura de 2026-10-15 | `{149 My new, 231 teste giroto}` |

No catálogo, `96 CLI` passou a `inUse: false`. A configuração mudou em menos de 24 h, sem que
ninguém alterasse o orquestrador.

Isso confirma a regra da V-23 §4 e a endurece: **nenhum id de atributo, nome ou requisito pode ser
fixado em código**. Tudo é lido da plataforma a cada execução, e o faltante é calculado por
`exigidos(mustHave) − presentes(apiTags do repositório)`.

E fecha o T03 item a item: requisitos `{149, 231}`, `apiTags` da API `{My new, teste giroto}`,
remove-se `My new` → falta exatamente **149**, e a mensagem diz `"API must contain attribute My new"`.

## 4. O que esta decisão fecha e corrige

| Item | Efeito |
|---|---|
| **D-20** (guia §10) | **Fechada.** Não era escolha de desenho; era comportamento a observar |
| **plano §8.4**, parágrafo do stage 1401 | **Corrigido.** O 1401 nunca esteve na Draft; reenviar o stage atual dispara o AG quando o stage tem requisitos |
| **V-23 §3**, hipótese da resolução pelo grupo | **Superada por observação.** O par da revisão basta |
| **V-23 §2**, exemplo do atributo faltante | **Obsoleto.** Era `CLI`; hoje o stage exige `teste giroto` |

## 5. Consequências para a implementação

1. O payload do `PUT` **preserva** `workflowId` e `workflowStageId`; não existe opção de CLI para
   escolher stage. O `WORKFLOW_STAGE_OVERRIDE` do protótipo é **instrumento de teste** e não deve ser
   transplantado.
2. O pré-check resolve workflow e stage pela revisão alvo, e degrada com mensagem quando o stage não
   estiver no workflow lido.
3. Se a Draft de um tenant estiver num stage sem `attributesRequisites`, o AG não exige nada ali — e
   o resultado verde é **correto**, não um falso positivo.
4. Um `PUT` aceito não altera o stage: o `validate` é diagnóstico, não promoção.
