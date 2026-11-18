# V-12 (b) · Forma da árvore — pasta por recurso, espelhando o Manager

| Meta | Valor |
|---|---|
| Status | **FECHADO** — 2026-10-14. Com a parte (a), o V-12 fecha por inteiro |
| Fecha também | **V-13** (`resource.name` × nome da pasta) |
| Complementa | [V-12 (a) identidade](V-12-identidade-sem-ids.md) |
| Fonte | `GET /revisions/9161` e `/9175` (API 417) — somente leitura |

## 1. Decisão

**A organização do repo segue a do Manager: uma pasta por recurso.**

```
resources/<slug-do-recurso>/
├── resource.yaml
└── <metodo>_<rótulo>.yaml      (uma por operação)
```

Substitui a árvore derivada do path (D-003 §2 e D-a), onde as pastas espelhavam os segmentos da URL.

**Consequência que fecha o V-13:** o nome da pasta **não precisa casar** com `resource.name`.
A regra da D-003 §5 que exigia a correspondência cai. `name` é rótulo livre do usuário, versionado
dentro do `resource.yaml`; a pasta é identificador de organização, derivado no import.

## 2. Por que — três motivos medidos

### 2.1 Existe recurso que a árvore por path não consegue representar

O recurso 9178 (`Letras`) tem `POST /tarefas/{id}/letras` e `DELETE /letras/{id}` — **nenhum prefixo
comum**. Gerando a árvore por path a partir do wire, o `resource.yaml` dele literalmente cai em
`artifacts/Resources/(SEM CASA)/`. Não é hipótese: é o que o algoritmo produz com o dado de hoje.

### 2.2 A reorganização de recursos some do diff

Experimento: gerar os dois layouts para as duas revisions da 417 (rev1 com 6 recursos → rev2 com 4) e
comparar.

| Layout | rev1 → rev2 | O que o diff mostra |
|---|---|---|
| por path | 13 → 11 arquivos, **10 inalterados** | só some `resource.yaml`; **todas as 7 operações ficam no mesmo lugar** — a fusão de recursos é invisível, e aparece um `(SEM CASA)` |
| por recurso | 13 → 11 arquivos, 9 inalterados | `post_tarefas-id-letras.yaml` migra de `letras-2/` para `letras/`; o `resource.yaml` duplicado some — **a fusão fica legível em code review** |

### 2.3 O agrupamento virou informação funcional

Com o [V-01](V-01-destination-timeout-escopos.md), o recurso carrega `destination`, `timeout` e
interceptors que as operações herdam — a op 9184 herda `https://teste.com` e `23 s` do recurso 9179.
Um layout que não expressa o agrupamento não consegue calcular a herança nem montar o payload.

## 3. A árvore resultante (API 417, revision 2 — 11 arquivos)

```
api-basic-info.yaml
all-all.yaml                                    destination teste.com/30 + 8 interceptors governados
resources/
├── health-check/
│   ├── resource.yaml                           name "/health-check" · url '' (herda)
│   └── get_health-check.yaml                   OVERRIDE (sem Custom #178)
├── tarefas/
│   ├── resource.yaml                           name "Tarefas" · google.com / 30
│   ├── get_tarefas.yaml                        TOMBSTONE (remove XSS threat protection)
│   └── get_tarefas-id.yaml                     herança pura
├── letras/
│   ├── resource.yaml                           name "Letras" · url '' (herda)
│   ├── post_tarefas-id-letras.yaml             timeout 55 · herança pura
│   └── delete_letras-id.yaml                   herança pura
└── atribuicao-responsavel/
    ├── resource.yaml                           name "Atribuicao Responsavel" · teste.com / 23 · +Additional Info
    ├── post_tarefas-id-atribuicao-responsavel.yaml   APPEND (Log cifrado)
    └── get_tarefas-id-atribuicao-responsavel.yaml    url '' (herda) · herança pura
```

## 4. Custo aceito

Perde-se a navegação por URL: não se encontra mais o arquivo descendo a árvore como se fosse a rota.
Mitigação: o nome do arquivo carrega o path e o campo `path:` dentro dele é a fonte da verdade
(D-a, opção A) — busca por texto resolve.

## 5. O que isso deixa em aberto

| Item | Pergunta |
|---|---|
| **V-16** | regra de slug e de **colisão** — a rev1 tinha dois `Letras` e dois `Tarefas`; a desambiguação por ordem do payload (`letras-2`) é instável e precisa ser derivada do conteúdo |
| **V-17** | nome do arquivo de operação — com a pasta já identificando o recurso, `post_tarefas-id-atribuicao-responsavel.yaml` é mais longo do que precisa |
| **V-25** (novo) | como escrever um **tombstone** no YAML: `get_tarefas.yaml` precisa remover só o XSS herdado, e a D-003 §4 só oferece override total |
