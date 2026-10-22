# Caderno de testes — `sen validate` contra a API 417

| Meta | Valor |
|---|---|
| Data | 2026-10-15 |
| Alvo | API **417** (`Serviço de Letras 2.0.0`, `/letras/v2`), revisão **9161** (Draft, nº 1) |
| Repositório | `decisoes-refino-409/exemplos-gerados/saida/api-417-rev2` |
| Instrumento | `provar_sen_validate.py` (v3.2) |
| Método | para cada teste: **altera o repo → publica → GET na plataforma → verifica o efeito → restaura o baseline** |
| Veredito | vem da **verificação por GET**, nunca do HTTP — três perdas silenciosas sob 200 nesta investigação |
| Estado final | **idêntico ao baseline** (nome, description, tags, basePath, recursos, operações, interceptors) |

> O que este caderno responde não é "o script funciona", e sim **como a plataforma
> se comporta** — cada linha é contrato observado, não inferido.

> ⚠️ **Revisto pela [V-28](../decisoes-refino-409/V-28-heranca-composta-pela-plataforma.md) em
> 2026-10-22.** Este caderno conferiu o estado gravado, não o que executa. Medido em runtime, o
> Manager compõe a herança: T06 mediu certo e concluiu errado ("não representável"); T07 e T08 só
> provaram que os itens subiram — sem marcação, o escopo seguia executando o herdado; o ✅ original
> do T11 estava certo, e a revisão de 15/10 o inverteu com base na W-4.

---

## 1. Resultado

| # | Teste | Esperado | Veredito |
|---|---|---|---|
| **T01** | Editar a `description` da API | aparece no GET | ✅ **PASSOU** |
| **T02** | Editar o `basePath` | a guarda recusa antes de escrever | ✅ **PASSOU** |
| **T03** | Remover a tag `My new` | o AG bloqueia e a tag permanece | ✅ **PASSOU** |
| **T04** | Editar o `destination` de `GET /tarefas` | o novo destino aparece no GET | ✅ **PASSOU** |
| **T05** | Adicionar a rota `GET /musicas` | a rota existe e herda o fluxo | ✅ **PASSOU** |
| **T06** | `inherit: false` vazio em recurso e rota | a rota sobe **sem** interceptors | ⚠️ **HIPÓTESE NÃO CONFIRMADA** |
| **T07** | `inherit: false` + interceptors no **recurso** | as rotas do recurso herdam | ✅ **PASSOU** |
| **T08** | `inherit: false` + interceptors numa **rota** | os interceptors sobem | ✅ **PASSOU** |
| **T10** | Remover a rota `DELETE /letras/{id}` | some da plataforma | ✅ **PASSOU** |
| **T11** | Acrescentar interceptor com `inherit: true` | append ao fim do fluxo | ✅ **PASSOU** |

Nove de dez confirmam o comportamento esperado. O **T06 refuta a hipótese** — e é
o achado mais valioso do caderno.

---

## 2. Teste a teste

### T01 · Editar a `description` da API ✅

**Alteração:** `description` no `api-basic-info.yaml`.
**GET depois:** `"Descricao EDITADA pelo teste automatizado do APIOps."`

Campo simples do basic info replica pelo `api` aninhado do payload da revision.

### T02 · Editar o `basePath` ✅

**Alteração:** `/letras/v2` → `/letras/v9`.
**Resultado:** **ABORTADO na guarda 1**, antes de qualquer escrita.
**GET depois:** `basePath` intacto (`/letras/v2`).

A guarda da D-11 funciona: identidade divergente não chega a tocar a plataforma.

### T03 · Remover a tag `My new` ✅

**Alteração:** retirada do par `My new`/`Tag1` do `api-basic-info.yaml`.
**Resultado:** **HTTP 412** — `"API must contain attribute My new"`.
**GET depois:** a tag **continua** na plataforma.

Com o PUT único (só a revision), o bloqueio do AG **não deixa estado parcial**.
Na versão anterior do instrumento, que fazia `PUT /apis` antes, a tag era removida
e só então a revision era barrada — o estado ficava meio aplicado.

### T04 · Editar o `destination` de uma rota ✅

**Alteração:** `destination.url` em `get_tarefas.yaml`.
**GET depois:** `https://dev-backend.ecad.org.br/EDITADO-PELO-TESTE/tarefas`.

### T05 · Adicionar a rota `GET /musicas` ✅

**Alteração:** pasta `resources/musicas/` com `resource.yaml` e `get_musicas.yaml`.
**GET depois:** recurso `Musicas` e operação `GET /musicas` criados; a rota tem
**0 interceptors próprios** e a raiz tem 8 — ou seja, **herda por lista vazia**.

O recurso e a operação nascem **sem `id`**; o Manager os gera.

### T06 · `inherit: false` vazio ⚠️ HIPÓTESE NÃO CONFIRMADA

**Alteração:** `inherit: true` → `false` no `resource.yaml` do `Letras` **e** na
rota `POST /tarefas/{id}/letras`, sem declarar fluxo.
**Esperado:** a rota sobe **sem** interceptors.
**GET depois:** recurso e rota com **lista vazia** (0 e 0).

> **No Manager, lista vazia significa HERDAR — não "fluxo vazio".** A rota continua
> executando o fluxo da revision. **Não existe representação para "esta rota não
> executa nada".**

Para a rota *não* executar um item herdado é preciso **declarar explicitamente o
fluxo que vale**, como o `GET /health-check` faz reproduzindo seus 7 itens.

**Consequência para o V-25:** a opção (a) — lista completa explícita — não é apenas
a mais simples, é a **única expressável**. Uma gramática de remoção teria de ser
expandida para a lista completa na publicação de qualquer forma.

### T07 · `inherit: false` + interceptors no recurso ✅

**Alteração:** `resource.yaml` do `Tarefas` com `inherit: false` e dois itens
próprios (`Custom #32`, `Payload size`).
**GET depois:** o recurso tem os 2 itens; `GET /tarefas` e `GET /tarefas/{id}`
seguem com **0 próprios**.

As rotas **herdam por lista vazia**, não por cópia. O Manager não materializa o
fluxo do recurso dentro de cada operação no momento da escrita.

### T08 · `inherit: false` + interceptors numa rota ✅

**Alteração:** `get_tarefas_{id}.yaml` com `inherit: false` e dois itens
(`Custom #33`, `Log`).
**GET depois:** a rota subiu com exatamente esses 2 — `[('Custom', 33), ('Log', None)]`.

### T10 · Remover uma rota ✅

**Alteração:** arquivo `delete_letras_{id}.yaml` apagado.
**GET depois:** `DELETE /letras/{id}` não existe mais; `Letras` ficou com 1 operação.

O que não está no repositório não é enviado, e o que não é enviado é removido.

### T11 · Append com `inherit: true` ⚠️ ORÁCULO ERRADO (revisto em 2026-10-15)

**Alteração:** `Payload size` acrescentado a `post_tarefas_{id}_letras.yaml`,
mantendo `inherit: true`.
**GET depois:** a rota foi de **0 para 1** item próprio.

> **O ✅ original estava errado, e a medição não.** O oráculo perguntou "a rota
> ganhou o item?". A pergunta certa era "a rota continua executando o que
> herdava?". Pela **W-5** (T06) 0 próprios significa herdar os ~9 da raiz; pela
> **W-4** uma lista própria de 1 item **é** o fluxo inteiro da rota. O append
> publicou 1 e apagou os 9, sob HTTP 200 — a mesma classe das perdas do W-8,
> desta vez produzida pelo próprio instrumento.
>
> A consequência em runtime é **derivada** das duas regras, não medida: a §5
> registra que herança em runtime não foi exercitada. O estado pós-T11 está
> medido; o que ele significa na execução vem do contrato do wire.
>
> Fechado pela [V-27](../decisoes-refino-409/V-27-fluxo-resolvido-no-repositorio.md):
> o fluxo efetivo passou a ser resolvido no repositório e publicado completo. O
> cenário equivalente na bateria automatizada
> (`tests/integration/test_bateria_417.py`) teve o oráculo corrigido e ganhou um
> **T12** para o caso de restaurar a herança e acrescentar na mesma declaração.

---

## 3. Contrato do wire confirmado por estes testes

| # | Regra | Como apareceu |
|---|---|---|
| **W-1** | **`idTemp` é obrigatório** em interceptor novo | sem ele o Manager devolve **500** com `errors: []` |
| **W-9** | **`idTemp` é único no payload inteiro**, não por escopo | dois itens novos em escopos diferentes com o mesmo `idTemp` → o Manager **descarta um**, com HTTP 200 |
| **W-5** | **Lista vazia = herda** | T06 |
| **W-6** | A operação **pertence ao recurso** | operação que muda de recurso precisa ir sem `id` |
| **W-7** | O gate do AG está no **`PUT /revisions`** | T03 |
| **W-8** | **Perda silenciosa sob HTTP 200** | três ocorrências distintas nesta investigação |

### A regra do `idTemp`, em detalhe

```
position  →  do ESCOPO    (por escopo e execution point)
idTemp    →  do PAYLOAD   (único em toda a chamada)
id        →  pode ser null em item novo
```

Violar a segunda linha custou o `Custom #33`: a raiz lhe deu `idTemp 9` e o
recurso `Atribuicao Responsavel` deu `idTemp 9` ao `Custom #32`. O Manager
deduplicou e devolveu 200.

É a mesma convenção que o orquestrador já carrega em
`domain/models/interceptors_model.py:17` (`set_ids_from_position`) — o modelo
estava certo; quem monta payload à mão precisa respeitá-la.

---

## 4. Como reproduzir

```powershell
cd docs\feat-api-estructure\prova-fluxo-validate
# cole o admin access token na constante TOKEN do script
..\..\..\.venv\Scripts\python.exe provar_sen_validate.py
```

A bateria automatizada vive no diretório de trabalho da sessão (`caderno.py`):
cada teste copia o repositório, altera, publica, confere por GET e restaura.

**Salvaguardas:** backup completo (API + todas as revisions) antes de qualquer
escrita; `--restore <pasta>` desfaz; a fase 5.1 relê e compara o publicado com o
enviado, falhando alto na divergência.

---

## 5. O que estes testes **não** cobrem

| Lacuna | Por quê |
|---|---|
| Herança em **runtime** | exige deploy e tráfego; a revisão 9161 tem `deployments: []` |
| Equivalência `''` ↔ `null` na escrita | não exercitada |
| Conformidade com a régua **comparando `content`** | o instrumento classifica por tipo e `customInterceptorId` |
| `sen publish` nas revisions 2/3/4 | todos os testes gravam na revisão 1 (Draft) |
| Custom **inexistente** no tenant | os ids 125/178 foram trocados por 32/33 antes desta bateria; o caso "repositório referencia Custom apagado" continua sem validação prévia |
