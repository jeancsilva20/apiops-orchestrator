# V-07 … V-10 · Releitura da API 409 — o que é dado real e o que vazou da 417

| Meta | Valor |
|---|---|
| Status | **FECHADOS** (os quatro) |
| Data | 2026-10-14 |
| Origem | `../validacao-api-letras-409.md` §4 |
| Método | `GET /apis/409` + `GET /revisions/9103` (tenant consulting, somente leitura) |

## Wire vigente — revision 9103 (API 409, `/letras/v1`, revision 1, `deployments: []`)

Raiz da revision: **as chaves `destination` e `timeout` não existem** no payload.

| Recurso | `destination` | `timeout` | Operação | `destination` | `timeout` |
|---|---|---|---|---|---|
| 9104 `/tarefas` | `null` | `null` | 9113 `GET /tarefas` | `…dev-backend…/tarefas` | `null` |
| 9105 `/health-check` | `null` | `null` | 9112 `GET /health-check` | `…dev-backend…/health-check` | `null` |
| 9106 `/tarefas/{id}/atribuicao-responsavel` | `null` | `null` | 9111 `POST …` | `…dev-backend…/…` | `null` |
| " | " | " | 9144 `GET …` | `null` | `null` |
| 9107 `/letras/{id}` | `null` | `null` | 9114 `DELETE /letras/{id}` | `…dev-backend…/letras/{id}` | `null` |
| 9108 `/tarefas/{id}/letras` | `null` | `null` | 9115 `POST …/letras` | `…dev-backend…/…/letras` | `null` |
| 9109 `/tarefas/{id}` | `null` | `null` | 9110 `GET /tarefas/{id}` | `…dev-backend…/tarefas/{id}` | `null` |

Nada mudou na 409 desde a simulação original: 6 recursos, 7 operações, nenhum timeout preenchido.

## Veredito item a item

| Item | O que a pasta `api-letras-409/` declara | Wire da 409 | Veredito |
|---|---|---|---|
| **V-07** | `timeout: '30'` nas duas ops de atribuição | `null` em **todos** os 13 objetos | ❌ **valor importado da 417** — a 409 não tem timeout em lugar nenhum |
| **V-08** | `destination` com URL absoluta no `GET …/atribuicao-responsavel` | op 9144 = `null` | ❌ **divergente** — e o cabeçalho do próprio arquivo diz `destination: null`, logo o corpo é que está errado (resolve o V-04) |
| **V-09** | `resource.yaml` de atribuição com `https://teste.com` + `timeout '30'` | recurso 9106 = `null`/`null` | ❌ **importado da 417** (lá é o valor da revision 9175 e do recurso 9179) |
| **V-10** | `all-all.yaml` com `{url: '', timeout: '30'}` | chaves **ausentes** na raiz da 9103 | ❌ **importado da 417**; na 409 o escopo `all` está vazio — o `url: ''` é, por acaso, a representação correta de "sem valor", mas o `timeout: '30'` não |

## Consequência

A pasta `api-letras-409/` **não é uma leitura fiel da API 409**: quatro valores vieram da 417.
Isso não invalida o exercício — ela foi feita para desenhar o layout, não para ser fixture — mas
decide o **V-19**: no papel de fixture dourada ela precisaria ser regerada do wire da 409.

Enquanto for material de desenho, cada arquivo deveria dizer de qual API veio o valor que ilustra.
