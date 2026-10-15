# V-01 · `destination` e `timeout`: escopos, presença e herança

| Meta | Valor |
|---|---|
| Status | **FECHADO** — semântica e shape (Forma B) decididos em 2026-10-14 |
| Data | 2026-10-14 |
| Origem | `../validacao-api-letras-409.md` §2 — V-01 (arrasta V-02 e V-03) |
| Método | Leitura ao vivo somente GET (tenant consulting) + documentação oficial Sensedia |
| Escrita na plataforma | Nenhuma. Só `GET` + o POST de token/validation |

## 1. Pergunta

`destination` aparecia em 4 formas na pasta `api-letras-409/`. Antes de qualquer schema:
o campo existe em quais escopos, pode faltar, e o que significa quando vem vazio?

## 2. Decisão

**O modelo é de escopos com herança por substituição, idêntico ao da plataforma.**

1. `destination` e `timeout` existem em **três escopos**: fluxo `all` (= revision), `resource` e `operation`.
2. Em qualquer um deles o campo **pode ou não** ter valor.
3. **`destination` é sempre declarado** no YAML. Vazio ⇒ **herda do escopo acima**.
4. **`timeout` não é obrigatório.** Vazio ou ausente ⇒ **herda do escopo acima**; se nenhum escopo
   definir, vale o timeout do gateway (**60 s**), que é também o **teto** de qualquer valor cadastrado.
5. A herança é de **substituição, não de composição**: o valor do escopo mais específico troca o de
   cima por inteiro. Não existe "base + sufixo".
6. **Shape: Forma B** — objeto `destination: {url, timeout}`, sempre declarado. `url: ''` significa
   herdar; `timeout` ausente significa herdar. O caso "timeout próprio sem destino próprio" se escreve
   `url: ''` com `timeout` preenchido. Molde completo e tradução YAML↔wire em
   [V-01-molde-yaml-validado-417.md](V-01-molde-yaml-validado-417.md).
7. **Campos sem casa no YAML** (`async`, `urls`, `instruction`, `certificateId`; por simetria
   `connector`) são **preservados por GET** no publish, não versionados.

## 3. Evidência ao vivo — `GET /revisions/9175` (API 417), 2026-10-14

| Escopo | `destination` | `timeout` |
|---|---|---|
| **revision 9175** (`all`) | `https://teste.com` | `30` |
| resource 9176 `/health-check` | `null` | `null` |
| resource 9177 `Tarefas` | `https://google.com` | `30` |
| resource 9178 `Letras` | `null` | `null` |
| resource 9179 `Atribuicao Responsavel` | `https://teste.com` | `23` ⭐ novo |
| op 9186 `GET /health-check` | `…dev-backend…/health-check` | `null` |
| op 9183 `GET /tarefas` | `…dev-backend…/tarefas` | `null` |
| op 9185 `GET /tarefas/{id}` | `…dev-backend…/tarefas/{id}` | `null` |
| op 9180 `POST /tarefas/{id}/letras` | `…dev-backend…/tarefas/{id}/letras` | `55` |
| op 9182 `DELETE /letras/{id}` | `…dev-backend…/letras/{id}` | `null` |
| op 9181 `POST …/atribuicao-responsavel` | `…dev-backend…/…` | `null` |
| op 9184 `GET …/atribuicao-responsavel` | `null` | `null` |

⭐ O recurso 9179 foi preenchido **depois** da leitura de 13/10 16:45 (era `null`/`null`), de propósito,
para exercitar a cadeia: agora a op 9184 tem **dois** níveis acima com valor (recurso `teste.com`/`23`
e revision `teste.com`/`30`), o que isola a regra "o mais específico vence".

O que o wire prova e o que **não** prova:

- ✅ a chave existe nos três escopos e aceita valor **ou** nulo em qualquer um;
- ✅ a cadeia é de substituição (recurso `google.com` × operações `dev-backend…`);
- ❌ a herança **em runtime** não é observável por GET, e a revision 9175 está com `deployments: []`
  (nunca implantada) — não há tráfego para testar. A herança vem da documentação (§4), não do wire.

**Regime de omissão difere por escopo** (confirmado nas duas APIs):

| Escopo | Quando não há valor |
|---|---|
| raiz da revision | a **chave não existe** no payload (409/9103 não tem `destination` nem `timeout`; 417/9175 tem) |
| resource e operation | a chave vem **sempre presente**, com `null` |

**Correção de contrato:** `destination`/`timeout` **não existem** em `GET /apis/{id}` — confirmado em
`/apis/417` e `/apis/409`. O nível que a UI chama de "API" é a **revision** no contrato v3. Logo o
escopo `all` do YAML mapeia para a raiz da revision, não para o `api-basic-info.yaml`.

## 4. Evidência documental (Sensedia)

| Ponto | Texto oficial |
|---|---|
| Hierarquia | *"the more specific timeout overwrites the more generic timeout, but the gateway timeout will always be respected"* |
| Vazio herda | *"If no value is entered, the gateway will consider the next value in the hierarchy"* |
| Exemplo oficial | API 30 s; `/resource1` 10 s; POST 40 s; GET 20 s; **PUT sem valor ⇒ usa os 10 s do recurso**; **`/resource2` sem valor ⇒ usa os 30 s da API** |
| Gateway | *"has a default value of 60 seconds and can't be changed by users"*; o valor cadastrado precisa ser *"less than or equal to the gateway timeout"* |
| Unidade | **segundos** |
| Escopo do destino | o destination *"pode ser definido como o mesmo para todas as chamadas da API ou específico para um determinado recurso ou operação"* (campos Resource/Operation em `All`) |
| Variável de ambiente | *"No Target ou no Timeout da API Destination"*; *"Todas as variáveis de ambiente devem ser precedidas pelo símbolo `$`"* |

Fontes: FAQ de timeout (`docs-legacy.sensedia.com/en/faqs/Latest/consumption/timeout.html`),
guia de Flows (`docs-legacy.sensedia.com/{pt,en}/api-management-guide/Latest/apis/flows.html`),
variáveis de ambiente (`docs-legacy.sensedia.com/pt/api-management-guide/Latest/environments/environment-variables.html`).

## 5. O que esta decisão muda nas decisões existentes

| Decisão | Efeito |
|---|---|
| **D-f** (409 §3) — "versionar só o sufixo; o publish reconstrói" | **REVOGADA na reconstrução.** Não há base derivável: a cadeia é de substituição. O YAML passa a declarar o **valor do escopo**, não um sufixo. Sobrevive da D-f: a portabilidade entre ambientes, que agora se resolve com **variável de ambiente** (`$var`), mecanismo nativo documentado |
| **D-m** pendência 1 (unidade do timeout) | **FECHADA — segundos**, com teto de 60 s do gateway |
| **D-m** pendência 2 (precedência entre escopos) | **FECHADA — o mais específico vence** (documentação + exemplo oficial) |
| **D-m** pendência 3 (regime de omissão) | **FECHADA na leitura**: revision omite a chave, resource/operation trazem `null`. Falta só a confirmação de escrita (publish), que é write |
| **D-m** "não escrever `timeout` por padrão" | **MANTIDA** — `timeout` continua opcional no YAML |
| **D-e** (campos do Resource fora da D-003 §5) | **CONFIRMADA como real**: `resource.yaml` precisa de `destination` e `timeout`; o mapa leve perderia dado |
| **D-003 §3** (ausente preserva · `""` limpa · `null` proibido) | **NÃO se aplica** a estes dois campos: aqui `destination` é sempre declarado e vazio **significa herdar** (≡ `null` no wire). Precisa de régua própria — ver §6 |
| **V-18** (`all-all.yaml` sem casa) | O escopo `all` ganha conteúdo legítimo e mapeia para a raiz da **revision** |

## 6. O que fica aberto

1. **Representação do vazio no publish** (V-03). A regra adotada: YAML vazio vira `null` em
   resource/operation e **chave omitida** na raiz da revision. A equivalência entre `""` e `null`
   na escrita só se confirma com um write.
2. **Herança de `destination` em runtime.** Documentada explicitamente só para `timeout`; para o
   destino a documentação afirma o escopo, não a herança. Só um deploy + chamada real fecha.
3. **Código de erro no estouro:** FAQ atual diz **504**, guia de Flows diz **502** — divergência da
   própria documentação, irrelevante para o layout, anotada para não se perder.
