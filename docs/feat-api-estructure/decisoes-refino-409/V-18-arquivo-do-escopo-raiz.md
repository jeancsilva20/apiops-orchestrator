# V-18 · `all.yaml` — o arquivo do escopo raiz

| Meta | Valor |
|---|---|
| Status | **FECHADO** — 2026-10-15 |
| Fecha | **D-6** (`plano-comandos-sen.md` §9) e a pendência de **I-7** (`.yaml` solto) |
| Altera | **D-005 §4** — a árvore passa de `all-all.yaml` para `all.yaml` |
| Apoia-se em | [V-01](V-01-destination-timeout-escopos.md) §5 (o escopo `all` mapeia para a raiz da revision) · [V-26](V-26-inherit.md) (herança declarada) · T06 do [caderno](../prova-fluxo-validate/CADERNO-DE-TESTES.md) |

## 1. As três perguntas, respondidas

A V-18 deixou três itens em aberto. Eles se resolvem assim:

**(a) O fluxo base fica na régua e sai daqui?** Não. São coisas distintas que o nome antigo
confundia: `all.yaml` declara o fluxo **desta** API na raiz da revision; a régua é uma **API template
externa**, lida por GET e usada só para comparar. O arquivo permanece, e seu conteúdo é estado
próprio — não cópia do padrão.

**(b) Onde moram `destination` e `timeout` do escopo revision?** Em `all.yaml`, conforme a V-01 §5 já
havia atribuído ao escopo `all`. Não vão para o basic info nem para um arquivo de defaults.

**(c) Qual é o nome e a gramática canônicos?** Abaixo.

## 2. Decisão

### 2.1 O nome

O arquivo do escopo raiz chama-se **`all.yaml`**, na raiz do repositório.

O nome anterior, `all-all.yaml`, era literal fixado no gerador (`exemplos-gerados/extrair_estrutura.py:354`),
sem derivação. O `-all` duplicado sugeria uma convenção `{recurso}-{metodo}` que nunca existiu. `all`
é o nome do escopo em toda a documentação; a duplicação não carregava significado.

*Alternativa descartada:* `revision.yaml`, que teria simetria perfeita com `resource.yaml`. Reintroduz
"revision" no repositório — vocabulário **operacional** que a D-003 e a D-005 retiraram de propósito,
já que o Git guarda o estado declarativo e a revision é estado do Manager.

### 2.2 A gramática

A raiz aceita três chaves de topo:

| Chave | Regime |
|---|---|
| `destination` | objeto `{url, timeout}` — o `timeout` mora **dentro** dele, não no nível de cima (D-005 §3; fila item 14: *"`timeout` sai do nível da operação"*). `url` é obrigatória quando o objeto existe; `timeout` é opcional, em segundos, com teto de 60 s do gateway |
| `interceptors_request` | lista; a ordem é a fonte declarativa, mapeia para `FIRST` |
| `interceptors_response` | lista; a ordem é a fonte declarativa, mapeia para `SECOND` |

`position`, `executionPoint` e `status` **não aparecem no YAML**, em nenhum escopo (D-003 §4).

**`inherit` não cabe na raiz.** A raiz da revision não herda de nenhum escopo acima — é o topo da
cadeia. Declará-la é inerte, e o comando emite `INFO` e prossegue, em vez de rejeitar: uma chave a
mais não destrói estado.

**O vazio se escreve diferente na raiz.** Conforme a V-01 §6: na raiz a chave é **omitida**; em
recurso e operação o vazio é `null`.

### 2.3 O arquivo é obrigatório pelo nome exato

`all.yaml`, na raiz, e `resource.yaml`, em cada pasta de recurso, são **obrigatórios pelo nome
exato**. A ausência de qualquer um aborta a operação na E1, antes de qualquer chamada de rede.

**Por que aborto, e não aviso.** A raiz não herda de ninguém. Publicar sem o escopo raiz não
preserva o que está lá — **apaga o fluxo da revision inteira**. É a mesma classe de perda silenciosa
do W-8, com a diferença de que a causa seria um erro de digitação no nome de um arquivo.

### 2.4 I-7 — o `.yaml` solto

Resolvido como consequência, sem regra própria: como o arquivo base é obrigatório pelo nome exato, um
typo (`alll.yaml`) produz **ausência**, e ausência aborta. Não é preciso proibir `.yaml` não
reconhecidos no repositório — um arquivo de notas ou de configuração de outra ferramenta convive sem
derrubar a descoberta.

Isso corrige o `plano-comandos-sen.md` §4, item I-7, que oferecia a escolha entre "ignorado com
`INFO`" e "erro": a proteção não vem de classificar o arquivo solto, vem de exigir o esperado.

## 3. Impactos

| Onde | O quê |
|---|---|
| `exemplos-gerados/extrair_estrutura.py:354` | emitir `all.yaml` |
| `d005-layout-revisado.md` §4 | árvore canônica passa a `all.yaml` |
| `exemplos-gerados/saida/` | os dois repositórios de exemplo precisam ser regerados |
| `exemplo-layout-final/` | ganha o exemplo anotado de `all.yaml`, conforme o [padrão](../padrao-exemplos-anotados.md) |
| `plano-comandos-sen.md` §4 (I-7) e §9 (D-6) | atualizar para a regra do nome exato |
