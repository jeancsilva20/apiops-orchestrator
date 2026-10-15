# V-26 · `inherit` substitui `override` — a herança passa a ser declarada

| Meta | Valor |
|---|---|
| Status | **FECHADO** — 2026-10-14 |
| Altera | **D-003 §4** (`override: true` = substituição total) |
| Validado com | `exemplos-gerados/` — 131 arquivos com `inherit`, nenhum com `override` |

## 1. Decisão

A régua se inverte: em vez de marcar a **exceção**, o repo declara **sempre o estado da herança**.

```yaml
inherit: true     # herda o fluxo do escopo acima
inherit: false    # herança quebrada: este arquivo declara o fluxo que vale
```

- **Ausente ≡ `true`.** O default é herdar.
- **Declarado sempre** que houver herança — nos três casos: herança pura, append e quebra.
- Vale nos dois escopos que herdam: `resource.yaml` e arquivo de operação.

`override: true` deixa de existir.

## 2. Por que

`override` só aparecia na exceção, então o arquivo silencioso era ambíguo: não dava para distinguir
"herda tudo" de "ninguém pensou nisso". Com `inherit` declarado, a herança vira afirmação explícita,
visível em code review — que é onde a D-003/V-11 colocaram o julgamento.

E a leitura fica direta: `inherit: false` significa que o fluxo herdado **não** vale ali, seja porque
o arquivo o substitui por inteiro, seja porque remove um item dele.

## 3. Como aparece nos exemplos

```yaml
# resources/letras/delete_letras_{id}.yaml — herança pura
inherit: true
# heranca pura: nenhum item proprio nesta operacao
```

```yaml
# resources/atribuicao-responsavel/post_tarefas_{id}_atribuicao-responsavel.yaml — append
inherit: true
# heranca preservada; o que vem abaixo SOMA ao fluxo herdado

interceptors_request:
  - type: Log
    content:
      encryptContent: true
      ...
```

```yaml
# resources/health-check/get_health-check.yaml — substituição
inherit: false
# heranca quebrada: o fluxo abaixo substitui o herdado (ausentes: Custom#178)

interceptors_request:
  - type: Custom
    id: 125
  ...
```

```yaml
# resources/tarefas/get_tarefas.yaml — tombstone
inherit: false
# o fluxo herdado e quebrado: remove -> XSS threat protection
# representacao do item removido ainda nao decidida (item V-25 do refino)
```

## 4. O que fica aberto

O **tombstone** ([V-25](../validacao-api-letras-409.md)) continua sem forma no YAML. Hoje ele produz
`inherit: false` mais um comentário, porque a alternativa — reproduzir os outros 7 itens para remover
1 — é o custo que a D-g já mediu. `inherit` resolve a **sinalização**; falta a **gramática** da remoção
seletiva.
