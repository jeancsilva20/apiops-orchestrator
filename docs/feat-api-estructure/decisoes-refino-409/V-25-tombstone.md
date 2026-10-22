# V-25 · Tombstone — a lista completa explícita é a única forma expressável

> ⚠️ **Revisada pela [V-28](V-28-heranca-composta-pela-plataforma.md) em 2026-10-22.** A lista
> completa explícita continua sendo a gramática do YAML. "Única forma expressável" cai: o wire expressa
> remoção por marcação `REMOVED`, e marcar todo o herdado sem itens próprios dá uma rota sem
> interceptors — o que o T06 não testou.

| Meta | Valor |
|---|---|
| Status | **FECHADO** — 2026-10-15 |
| Fecha | **D-2** (`plano-comandos-sen.md` §9) e **P-4** (`analise-complexidade-orquestrador.md` §8.2) |
| Descongela | **D-004 §2.2** — a remoção seletiva era o que restava congelado |
| Evidência | **T06** do [caderno de testes](../prova-fluxo-validate/CADERNO-DE-TESTES.md), escrita real contra a API 417 |

## 1. Decisão

> A remoção de um item herdado é expressa **reproduzindo no YAML o fluxo completo que vale**, com
> `inherit: false`. Não existe gramática de remoção; não existe marcação de item removido.

Não é a forma mais econômica. É a **única expressável** — e isso foi medido, não escolhido.

## 2. Por que não havia alternativa

A V-25 oferecia duas opções: **(a)** lista completa explícita e **(b)** uma gramática de remoção, com
uma chave identificando o item a suprimir. O T06 eliminou a (b).

**O teste:** `inherit: true` → `false` no `resource.yaml` do `Letras` **e** na rota
`POST /tarefas/{id}/letras`, sem declarar fluxo.
**Esperado:** a rota sobe sem interceptors.
**Resultado:** recurso e rota subiram com **lista vazia (0 e 0)** — e continuaram executando o fluxo
da revision.

> **No Manager, lista vazia significa HERDAR — não "fluxo vazio".** Não existe representação para
> "esta rota não executa nada".

Uma gramática de remoção teria de ser **expandida para a lista completa no momento da publicação** de
qualquer forma, porque é só assim que o wire expressa supressão. A opção (b) seria açúcar sintático
sobre a (a), com uma chave de identificação a mais para manter e nenhum ganho de expressividade.

O repositório já tinha a forma certa em outro arquivo: `health-check/get.yaml` reproduz 6 itens para
derrubar 1 (`Custom #178`).

## 2.1 Como o wire aponta o item removido (V-e, respondido em 2026-10-15)

A análise de complexidade deixou em aberto *"qual chave o tombstone usa para apontar o item
removido"* (item V-e). Leitura somente GET da revisão 9175, operação `GET /tarefas`:

```json
{
  "id": 19430, "idTemp": 19430, "position": 6,
  "type": "XSS threat protection",
  "executionPoint": "FIRST",
  "status": "REMOVED",
  "parent": { "id": 19422, "idTemp": 19422 },
  "parentType": "REVISION",
  "customInterceptorId": null,
  "content": { "regexList": [ ... ] }
}
```

| Campo | Papel |
|---|---|
| `parent.id` | **a chave**: o `id` do interceptor herdado que está sendo suprimido |
| `parentType` | o escopo de onde vinha a herança (`REVISION` = raiz) |
| `type` e `content` | cópia do item removido — o tombstone carrega o que suprime |
| `status: REMOVED` | o marcador |

**Consequência para o importador:** a lista completa se calcula sem heurística. Toma-se o fluxo
herdado do escopo indicado por `parentType`, retiram-se os itens cujo `id` aparece em algum
`parent.id` de tombstone, e publica-se o que sobra com `inherit: false`. Nada disso depende de casar
por nome ou por `content`.

## 3. O que isso substitui

O importador gravava a remoção em **comentário**:

```yaml
inherit: true
# TOMBSTONE: o fluxo herdado vale, MENOS -> XSS threat protection
# a remocao ainda nao tem representacao no YAML (item V-25 do refino)
```

Isso é **lossy**: publicar esse arquivo manda `inherit: true` sem itens, o que resulta em append de
nada — e o XSS volta. Import → publish não reproduz o original.

Passa a ser:

```yaml
inherit: false
# o fluxo herdado vale, MENOS -> XSS threat protection
interceptors_request:
  - type: ...   # os oito itens que permanecem, na ordem
```

O comentário pode continuar, como anotação para humanos. **A lista é a verdade.**

## 4. O custo, nomeado

### 4.1 Verbosidade

Remover 1 item de um fluxo herdado de 9 custa escrever 8. O recurso `Atribuicao Responsavel` é o caso
extremo do conjunto atual: 9 itens no wire.

### 4.2 Deriva silenciosa — e seu remédio

A cópia explícita **congela** o fluxo do pai no momento do import. Se alguém acrescenta um interceptor
na raiz depois, a rota que fez override não recebe — e o override, que existia para remover um item,
vira uma rota que ficou para trás em tudo.

Não há como evitar a cópia. Há como avisar: o comparador de conformidade compara o escopo também com
o **fluxo do pai** e emite `WARNING` quando a diferença for maior do que a supressão declarada.

```
WARNING  GET /tarefas (op 9183): o override omite 3 itens do fluxo herdado;
         a supressão declarada é de 1. O fluxo do pai pode ter evoluído.
```

## 5. Impactos

| Onde | O quê |
|---|---|
| importador | materializar a lista completa; parar de gravar a remoção só em comentário |
| comparador de conformidade | `WARNING` de deriva de override |
| `d003-layout-repo.md` §4, linha de `status` | a gramática do tombstone deixa de estar "em aberto" |
| `exemplos-gerados/saida/api-417-rev2/resources/tarefas/get_tarefas.yaml` | regerar com `inherit: false` e os oito itens |
| `V-26` | permanece válida: a herança continua declarada sempre; o que muda é como a supressão se escreve |
