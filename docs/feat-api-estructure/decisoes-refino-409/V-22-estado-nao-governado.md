# V-22 · Estado não governado — o que o repo não versiona e o publish preserva

| Meta | Valor |
|---|---|
| Status | **FECHADO** — regra decidida em 2026-10-14 |
| Data | 2026-10-14 |
| Origem | achado da validação do V-11: interceptor `Custom` em `executionPoint: THIRD` na revision 9175 |
| Fonte | `GET /revisions/9103`, `/9131`, `/9175` (tenant consulting, somente leitura) |

## 1. O conceito

Existe estado que vive no Manager, **não é versionado no repo** e ainda assim **não pode ser perdido**
no publish. Em vez de tratar caso a caso, vale um nome só:

> **Estado não governado** — tudo que o orquestrador lê por `GET` antes de publicar e reenvia
> **exatamente como estava**. Ausente no remoto ⇒ sobe vazio. Nunca aparece no YAML, nunca entra em
> diff do git.

É o mesmo mecanismo da hidratação da D-002 (`visibility`, `apiType`, `creationDate`) e cumpre o
princípio estruturante do projeto: *manifesto versionado + estado remoto (GET) → payload efetivo*.

Hoje o conjunto tem duas famílias:

| Família | Itens | Decidido em |
|---|---|---|
| **Campos** | `async`, `urls`, `instruction`, `certificateId` (operação); `connector`, `certificateId` (recurso) | V-01 §5 |
| **Interceptors** | tudo com `executionPoint` fora de `FIRST` e `SECOND` | este documento |

## 2. A evidência do caso dos interceptors

| Revision | `revision` | `resource` | `operation` | Custom sem `customInterceptorId` |
|---|---|---|---|---|
| 9103 (API 409) | FIRST 7 · SECOND 1 | FIRST 7 · SECOND 2 | FIRST 8 · SECOND 1 | nenhum |
| 9131 (API 414, régua) | FIRST 7 · SECOND 1 | — | — | nenhum |
| 9175 (API 417) | FIRST 7 · SECOND 1 · **THIRD 1** | FIRST 7 · SECOND 2 | FIRST 8 · SECOND 1 | **1** — o próprio THIRD (id 19446) |

O item THIRD é um `Custom` com o script **inline no `content`** (tratador de erro:
`$call.flowError.httpErrorCode == 401`), sem referência ao catálogo de Custom do tenant.

Dois fatos que tornam a regra segura:

1. **`executionPoint` é um enum do wire**, não uma convenção do repo — discriminante estável.
2. **THIRD não participa da numeração contínua.** Na 9175 as posições são FIRST `1…7`, SECOND `8`,
   THIRD `8` — a colisão mostra que o THIRD tem espaço de numeração próprio. Ignorá-lo **não desloca**
   nada; incluí-lo no recálculo global é que corromperia as posições.

## 3. A regra

```python
GOVERNED_EXECUTION_POINTS = frozenset({"FIRST", "SECOND"})

def partition(remote_interceptors):
    """Separa o que o YAML governa do que o publish apenas preserva."""
    governed, preserved = [], []
    for item in remote_interceptors or []:
        bucket = governed if item.get("executionPoint") in GOVERNED_EXECUTION_POINTS else preserved
        bucket.append(item)
    return governed, preserved
```

| Momento | Comportamento |
|---|---|
| **import** | só `governed` vira YAML; `preserved` não chega ao repo |
| **publish** | payload = itens reconstruídos do YAML (com `position` recalculada **apenas sobre os governados**) **+** `preserved` copiado literal do GET, com `id`, `idTemp`, `position`, `status`, `parentType` e `content` intactos |
| **sem o item no remoto** | `preserved` vem vazio ⇒ sobe sem ele |
| **quando a regra de validação existir** | mover `"THIRD"` para o conjunto governado e definir a gramática YAML. Nada mais muda |

Vale nos **três escopos** (revision, resource, operation) sem exceção.

## 4. Limites declarados

1. **A regra é por `executionPoint`, não por "representável".** Um item que o YAML não saiba expressar
   mas esteja em `FIRST`/`SECOND` **não** é capturado. Hoje não existe nenhum — o único `Custom` inline
   do conjunto está em THIRD. Salvaguarda obrigatória: se o import encontrar um item governado que não
   consiga representar, deve **falhar explicitamente**, nunca silenciar. Perda silenciosa é o único
   desfecho inaceitável.
2. **Preservar exige ler antes.** O publish sempre faz o GET do estado atual; sem ele não há o que
   preservar. Em API nova não há remoto — sobe vazio, que é o comportamento desejado.
3. **Posições.** Copiar literal funciona porque o espaço de numeração do THIRD é separado. Se um dia
   houver preservado dentro de FIRST/SECOND, o recálculo global terá de considerá-lo — mais um motivo
   para a salvaguarda do item 1.
4. **Remoção no Manager não deixa rastro no repo.** Se alguém apagar o item preservado, o próximo
   publish simplesmente não o envia. Consistente com a regra, mas invisível no git.

## 5. Impacto no CLI

| Peça | O que muda |
|---|---|
| `domain/schemas/schema-interceptors.json` | hoje fixa `executionPoint` como `const: "FIRST"` — nem SECOND aceita. Precisa do enum governado |
| `ApiFull.set_interceptor_positions()` | recalcular **só** sobre os governados; preservados entram depois, intactos |
| adapter de publish | obter `preserved` do GET da revision atual e reanexar ao payload |
| import | particionar antes de gerar YAML + falhar alto no caso do limite 1 |
