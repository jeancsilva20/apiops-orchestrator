# V-28 · A plataforma compõe a herança; o escopo guarda só o que é dele

| Meta | Valor |
|---|---|
| Status | **FECHADO** — 2026-10-22 |
| Altera | **W-3, W-4, W-5** ([plano-comandos-sen.md](../plano-comandos-sen.md) §8) · [V-25](V-25-tombstone.md) §2 · [V-26](V-26-inherit.md) §3 · [V-27](V-27-fluxo-resolvido-no-repositorio.md) (premissa) · T06, T07, T08 e T11 do [caderno](../prova-fluxo-validate/CADERNO-DE-TESTES.md) |
| Evidência | Execução medida em runtime na API-lab 425 do tenant consulting, 21/10/2026, e um save da UI capturado no mesmo dia |
| Change | `openspec/changes/fix-interceptor-inheritance` |

## 1. A pergunta

A W-4 dizia que o Manager guarda o fluxo **resolvido** de cada escopo: lista própria não vazia seria o
fluxo inteiro do escopo. A V-27 partiu dela para publicar o herdado copiado dentro de cada escopo.

O `f018ca5` achou o contrário numa rota com `inherit: false`: ela seguia executando o fluxo do pai,
com os itens do arquivo no fim. A pergunta voltou a ficar aberta: o Manager guarda o resolvido ou
compõe o fluxo na execução?

## 2. Como foi medido

O estado gravado (GET) não responde a pergunta, porque mostra o que cada escopo guarda e não o que ele
executa. A medição foi feita em runtime:

- API **425**, `[APIOps] Lab Heranca Interceptors`, criada para isso no consulting; deploy no ambiente
  7 (DEV-APIOPS);
- cada interceptor é um `Header` que injeta `X-Lab-<rótulo>` e um `X-Lab-Ordem` compartilhado;
- o destino é `https://httpbin.org/anything`, que devolve os headers recebidos;
- para cada chamada, o trace do gateway (`GET /calls/{id}`) dá o número de linhas
  `Executing ... Interceptor` e os `requestHeaders` na ordem de inserção.

Seis rodadas de escrita: estrutura, marcações com ids reais, item novo na raiz marcado por `idTemp`,
volta à herança, item removido do pai, raiz vazia.

## 3. O modelo medido

1. Cada escopo (raiz, recurso, rota) guarda **só** os itens próprios (`status: REFERENCE`) e as
   **marcações** (`status: REMOVED`, `parent.id` = id do item herdado que o escopo deixa de executar).
2. O escopo executa: **o fluxo que o pai executa, menos os itens marcados, mais os itens próprios**.
3. A ordem é por escopo: o bloco herdado primeiro, depois os próprios. A `position` só ordena dentro
   do mesmo escopo. Um item de rota com `position` 0 roda depois de todos os herdados.
4. Lista vazia herda tudo (W-5 continua certa para recurso e rota). Na raiz, lista vazia é raiz sem
   nada (pendência E-1 da V-27).
5. **Rota sem interceptors existe**: basta marcar todo item herdado, sem itens próprios.
6. A marcação pode apontar qualquer item do fluxo que o pai executa, inclusive um item da raiz numa
   rota cujo recurso só acrescenta. Marcação para item que o pai não executa, ou para item apagado,
   é **descartada em silêncio** no PUT.
7. Omitir uma marcação no PUT a apaga: o herdado volta. `parentType` é ignorado (o Manager grava
   sempre `REVISION`).

## 4. Evidência por cenário

| Rota | O que o escopo guarda | Executou |
|---|---|---|
| `s1` | nada | R1, R2 |
| `s2` | S2 | R1, R2, S2 |
| `s3` | cópias de R1 e R2, mais S3 (o que a V-27 publica) | **5 execuções** para 3 interceptors: o herdado roda duas vezes |
| `s4` | S4 (`inherit: false` sem marcação) | R1, R2, S4 |
| `s5` | S5, marcações de R1 e R2 | S5 |
| `s6` | marcação de R1 | R2 |
| `s7` | marcações de R1 e R2, nada próprio | **nada** (0 execuções) |
| `s8` | S8 com `position` 0 | R1, R2, S8 |
| `s9` | marcações de R1 e R2, cópias na ordem R2, R1 | R2, R1 |
| `b3` | sob recurso com B1: marcações de R1, R2 e B1, mais B3 | B3 |
| `b4` | sob recurso com B1: marcação de B1, mais B4 | R1, R2, B4 |
| `c1` | sob recurso que marca R1 e R2 e tem C1: nada | C1 |
| `c3` | sob esse recurso: marcação de C1, mais C3 | C3 |
| `c4` | sob esse recurso: marcações de R1 e R2, mais C4 | C1, C4 — as marcações foram descartadas no PUT |
| `d1` | sob recurso com D1 e sem marcação: nada | R1, R2, D1 |

## 5. Item que entra no pai na mesma publicação

O item novo ainda não tem `id`. A marcação aponta para ele pelo `idTemp`:

```json
{ "status": "REMOVED", "parent": { "id": null, "idTemp": 987654 } }
```

O R4 entrou na raiz com `idTemp` 987654 e foi gravado com `id` 20034; as marcações foram gravadas com
`parent.id` 20034, e no runtime as rotas que quebram a herança não executam o R4. Funcionou também sem
a chave `id`, e de recurso para rota. A primeira tentativa usou um `idTemp` igual ao próximo `id` da
sequência; a repetição com um valor distante descartou a coincidência.

A UI faz o mesmo. No save capturado, o item novo vai com `id` = `idTemp` = número temporário, e a
marcação da rota aponta esse número no mesmo save; o Manager grava o id real. A UI numera `position` a
partir de 0 em cada escopo.

**`id` nulo não basta (bateria da 425, 22/10/2026).** Com o item novo em `id: null`, a marcação de
uma rota para um item novo do **recurso** é descartada em silêncio quando, no mesmo PUT, o recurso
também marca um item novo da **raiz** por `idTemp`. Isolado em PUTs diretos:

| Caso | Raiz ganha item novo | Recurso | Marcação da rota para o item novo do recurso |
|---|---|---|---|
| C | não | só o item novo | gravada |
| D | sim, sem marcação no recurso | só o item novo | gravada |
| A, B | sim | item novo + marcação do novo da raiz (as duas ordens) | **descartada** |
| E | sim (formato da UI: `id` = `idTemp`) | item novo + marcação do novo da raiz | gravada |

O orquestrador passa a mandar todo item novo como a UI, com `id` = `idTemp`. O número temporário
começa em 10¹², acima de qualquer id que o Manager gere: com `id` preenchido, um número igual ao id de
um item existente faria o Manager tratá-lo como esse item. Começar logo acima do maior id do payload,
como o contador fazia, coincidia com a sequência de ids do próprio Manager.

## 6. O que cai

| Regra | Situação |
|---|---|
| **W-3** (`position` contínua entre escopos) | não é requisito: a ordem é por escopo |
| **W-4** (o Manager guarda o resolvido) | **errada**. Os 9 itens do `Atribuicao Responsavel` da 417 eram cópias próprias, não herança materializada |
| **W-5** (lista vazia herda) | certa para recurso e rota; a consequência "não existe rota sem fluxo" cai |
| **T06** | a medição estava certa (lista vazia herda); a conclusão "não representável" cai |
| **T07, T08** | o oráculo só conferiu o gravado; com `inherit: false` sem marcação, o escopo seguia executando o herdado |
| **T11** | o ✅ original estava certo: só o item novo, com `inherit: true`, é o append correto. A revisão de 15/10 inverteu o resultado com base na W-4 |
| **V-25 §2** | "lista completa explícita" continua sendo a gramática do YAML; "única forma expressável" cai, porque o wire expressa remoção por marcação |
| **V-27** | "o repositório decide" continua; o que vai no wire muda: o delta e as marcações, não o herdado copiado |

## 7. Publicação via swagger — estudo para o roadmap

O roadmap prevê publicar o contrato (request body, responses, schemas) via swagger. A mesma API-lab
mediu o `PUT /revisions/{id}/swagger`:

- O documento é um OpenAPI 3.0 com extensões: `x-interceptors` na raiz, em `x-resources.<nome>` e em
  cada operação; `x-resource-name`; `x-destination` e `x-timeout` nos três escopos;
  `x-interceptor-custom-interceptor-id` no `Custom`.
- Cada interceptor tem uma chave numérica do documento. A marcação aponta o pai por
  `x-interceptor-parent-id` = essa chave. O documento não carrega ids do Manager.
- Cada PUT de swagger recria **todos** os interceptors com ids novos; a semântica é preservada.
  Recursos e operações mantêm o id quando casados.
- Item novo e marcação no mesmo PUT funcionam pela chave do documento.
- Swagger sem `x-interceptors` **apaga todos os interceptors** e responde `success`. OpenAPI sem
  nenhuma extensão ignora `tags`, cria um recurso por path, apaga recursos e operações antigos e perde
  destino e descrições.
- Mudar o `x-resource-name` de uma operação existente é ignorado na estrutura, mas fica no documento.
- O contrato sobrevive a um PUT de revisão posterior.

O modelo de herança é o mesmo nos dois caminhos; muda só a forma de escrever. Por isso a change separa
a decisão de "o que cada escopo guarda" da escrita no PUT de revisão.

## 8. Pendências

| # | Pergunta |
|---|---|
| E-3 | O gate do Adaptive Governance roda no `PUT /revisions/{id}/swagger`? O stage da 425 não tem requisitos. |
| E-4 | Itens em THIRD/ANY passam inteiros pelo swagger? A 425 não tem esses itens. |
