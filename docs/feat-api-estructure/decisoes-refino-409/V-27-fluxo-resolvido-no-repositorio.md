# V-27 · O fluxo efetivo é resolvido no repositório, não na plataforma

| Meta | Valor |
|---|---|
| Status | **FECHADO** — 2026-10-15 |
| Altera | [V-26](V-26-inherit.md) (semântica de `inherit` **na publicação**) · [V-25](V-25-tombstone.md) (a lista completa explícita deixa de ser recurso do tombstone e vira a regra geral) |
| Origem | implementação do `sen validate`; defeito observado no `POST /tarefas/{id}/atribuicao-responsavel` da API 417 |
| Evidência | **T06** e **T11** do [CADERNO-DE-TESTES](../prova-fluxo-validate/CADERNO-DE-TESTES.md) |

## 1. A pergunta

Quem resolve a herança de interceptors: **a plataforma**, a partir de listas vazias, ou **o
repositório**, computando o fluxo efetivo e enviando-o explícito?

Até aqui o publisher delegava. Um escopo com `inherit: true` tinha sua lista remota **preservada**,
e o declarado somava a ela. A plataforma decidia o que o escopo executava.

## 2. A decisão

**O repositório resolve.** O orquestrador computa o fluxo efetivo de cada escopo descendo a
hierarquia declarada — `all.yaml` → `resource.yaml` → arquivo de operação — e publica o resultado.
A plataforma guarda; não decide.

| No repositório | Fluxo efetivo (computado do repo) | O que vai no wire |
|---|---|---|
| `inherit: true`, sem itens | o do pai, tal como o repo o define | `[]` — herança pura |
| `inherit: true`, com itens | o do pai **+** os declarados | a lista completa, explícita |
| `inherit: false`, com itens | exatamente os declarados | a lista completa, explícita |
| `inherit: false`, sem itens | contraditório | `[]` + **WARNING** (ver §5) |

O escopo raiz não herda de ninguém: seu fluxo é exatamente o que o `all.yaml` declara, e `inherit`
ali permanece **INFO** (decidido no refino do `sen validate`).

### Por que `[]` na herança pura, e não a lista completa

Parece inconsistente mandar vazio num caso e explícito nos outros. Não é: nos dois casos **o repo já
sabe a resposta**, e `[]` é apenas a codificação compacta dela. O que muda é que a resposta não
depende mais do que a plataforma guardava.

E a codificação compacta é a **melhor** ali, por dois motivos:

1. **Propagação viva.** Congelar uma cópia do fluxo do pai num escopo que só herda cria exatamente a
   deriva que a [V-25 §4.2](V-25-tombstone.md) existe para avisar. Com `[]`, mudar o `all.yaml`
   propaga sozinho.
2. **Consistência dentro do PUT.** Todos os escopos viajam no mesmo payload. Quando o filho manda
   `[]`, o pai que ele herda já foi reescrito nessa mesma chamada com o fluxo que o repo computou —
   então `[]` resolve para o `P` que o repo calculou, não para um `P` antigo.

## 3. O defeito que motivou a mudança — e a evidência de que ele é real

O **T11** do caderno está registrado como ✅, e não deveria estar.

> **T11 · Append com `inherit: true`** — `Payload size` acrescentado a
> `post_tarefas_{id}_letras.yaml`, mantendo `inherit: true`.
> **GET depois:** a rota foi de **0 para 1** item próprio.

O oráculo do teste perguntou "a rota ganhou o item?" e a resposta foi sim. A pergunta certa era
"a rota continua executando o que herdava?". Pelas duas regras já confirmadas:

- **W-5** (T06) — lista vazia significa **HERDAR**;
- **W-4** — o Manager guarda o fluxo **resolvido**, não o delta.

Antes: 0 próprios → a rota executava os ~9 itens herdados.
Depois: 1 próprio → a lista própria não vazia **É** o fluxo efetivo. A rota passou a executar **só o
`Payload size`**.

O append apagou a herança, sob HTTP 200, e o caderno marcou verde. É a mesma classe das três perdas
silenciosas do W-8 — e desta vez quem a produziu foi o próprio orquestrador.

> **Nota de procedência:** a consequência em runtime é **derivada** de W-4 + W-5 aplicadas ao estado
> medido, não medida diretamente. A §5 do caderno declara que herança em runtime não foi exercitada
> (exige deploy e tráfego; a revisão 9161 tem `deployments: []`). O estado pós-T11 está medido; o que
> ele significa na execução vem das regras do wire.

Sob a V-27 o mesmo T11 envia **os ~9 herdados + `Payload size`**, e a rota passa a executar 10.

## 4. O caso do usuário, que a V-26 não expressava

O dev quer, numa só declaração: **restaurar a herança** que havia quebrado **e** acrescentar um
interceptor. Sob a semântica anterior isso não era expressável:

```yaml
inherit: true          # "volte a herdar"
interceptors_request:
  - type: Payload size # "e acrescente isto"
```

A plataforma recebia a lista própria antiga mais o novo item — nem a herança voltava, nem o fluxo
ficava correto. Sob a V-27 a declaração significa exatamente o que lê: **o fluxo do pai, segundo o
repositório, mais o `Payload size`**.

## 5. `inherit: false` sem itens

Permanece sem representação na plataforma — o **T06** provou que não existe "escopo que não executa
nada". A declaração é contraditória: não herda e não tem fluxo.

O comando **avisa** (`WARNING`) e envia `[]`, que é a única coisa que a plataforma aceita; o efeito
real é voltar a herdar. O aviso existe porque o silêncio aqui faria o dev concluir que a publicação
falhou.

## 6. O que isso custa

Duas consequências que pesam, e que a decisão assume de propósito:

1. **O repositório sobrescreve a plataforma.** Um escopo cuja lista alguém editou direto no Manager
   é substituído pelo que o repo computa. É o comportamento correto sob *"Git é a fonte da verdade do
   estado declarativo"*, mas é inversão de postura: o publisher preservava.
2. **A hierarquia do repo precisa estar completa.** O efetivo de uma operação passa a depender de
   `all.yaml` → `resource.yaml` → arquivo da operação. Um `resource.yaml` incompleto propaga o erro
   para baixo, enquanto antes a plataforma cobria o buraco.

A intenção do produto aceita as duas: **o dev tem liberdade de ajustar a API pelo repositório**
(decisão do usuário, 2026-10-15).

## 7. Efeito sobre decisões existentes

| Decisão | Efeito |
|---|---|
| [V-26](V-26-inherit.md) | **Alterada na publicação.** A gramática do YAML não muda — `inherit` booleano, ausente ≡ `true`. O que muda é o que `inherit: true` **produz no wire**: antes "preserve o remoto e some"; agora "o fluxo do pai segundo o repo, mais o declarado" |
| [V-25](V-25-tombstone.md) | **Generalizada.** A lista completa explícita deixa de ser o recurso excepcional do tombstone e passa a ser como todo escopo com fluxo próprio é publicado. A supressão continua se escrevendo por omissão da lista |
| [V-22](V-22-estado-nao-governado.md) | **Intacta.** O que está fora de `FIRST`/`SECOND` continua voltando sem ser tocado |
| W-4 / W-5 | **Intactas** — são as regras da plataforma, e é justamente por elas que a resolução precisa sair de lá |
| V-11 (conformidade) | **Fortalecida.** A conformidade já avalia o **payload**; com o fluxo resolvido no repo, o que ela compara é o que o repositório afirma, não o que a plataforma guardava |

## 8. Pendências empíricas abertas

| # | Pergunta | Por que não foi fechada |
|---|---|---|
| E-1 | `[]` no **escopo raiz** limpa o fluxo da revision, ou é preservado? | O T06 cobriu recurso e operação, **não a raiz**. A raiz não tem pai, então "vazio = herda" não se aplica — e o comportamento não foi medido. Até medir, o comando emite `WARNING` quando o `all.yaml` não declara interceptors e a raiz remota tem itens |
| E-2 | Um **tombstone remanescente** sobrevive a um PUT que manda a lista completa sem ele? | Sob a V-27 nunca enviamos tombstone. Se a plataforma o mantiver, ele continua suprimindo um item. A conferência pós-publicação passa a **reportar** tombstone presente no publicado como divergência |

Ambas exigem escrita na plataforma e ficam para a próxima bateria autorizada.
