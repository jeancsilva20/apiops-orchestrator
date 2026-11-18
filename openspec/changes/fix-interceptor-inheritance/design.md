## Design

### Contexto

O `sen validate` e o `sen publish` montam o payload em `revision_payload.montar` e conferem o publicado em `revision_payload.conferir`, pelo `RevisionWriter`. A resolução da herança está em `interceptor_flow.py`:

- `resolver_fluxo_declarado` devolve o `FluxoDoEscopo` (`efetivo`, `heranca_pura`, `contraditorio`, `substitui`). Para `inherit: true` com itens, o `efetivo` é herdado + declarados, e é ele que vai para o wire;
- `montar_fluxo_do_escopo` escreve o `efetivo` no wire e, quando `substitui`, acrescenta as marcações do herdado (`_marcar_como_removido`), pulando o item sem `id`;
- `fluxo_efetivo` segue a W-4 e é usado pela conformidade (`ValidateService._conformidade`);
- `fluxo_composto` já compõe como o Manager, mas só reconhece marcação por `parent.id`.

O importador (`repo_materializer`) já compõe o fluxo do recurso para as rotas, mas grava `inherit: false` para lista própria sem marcações, pela W-4.

O modelo medido está na [V-28](../../../docs/feat-api-estructure/decisoes-refino-409/V-28-heranca-composta-pela-plataforma.md) §3.

### Decisões

**D1 — O modelo de composição.** O que um escopo executa é o que o pai executa, menos os itens marcados `REMOVED` no escopo, mais os itens próprios. A ordem é por escopo: o bloco herdado inteiro, depois os próprios; dentro do escopo, por `position`. A raiz não tem pai: executa os itens próprios. Vale por execution point governado (`FIRST`, `SECOND`); o que está fora deles segue a V-22 e não entra na composição nem nas marcações.

**D2 — O que cada escopo guarda.**

| Declaração | Itens próprios no wire | Marcações no wire | Executa |
|---|---|---|---|
| raiz (`all.yaml`) | os declarados | — | os declarados |
| `inherit: true`, sem itens | nenhum | nenhuma | o herdado |
| `inherit: true`, com itens | os declarados | nenhuma | herdado + declarados |
| `inherit: false`, com itens | os declarados | uma por item que o pai executa | os declarados |
| `inherit: false`, sem itens | nenhum | uma por item que o pai executa | nada |

"O que o pai executa" é o fluxo composto do pai **neste mesmo payload**: numa rota, o do recurso como o repositório o declara agora. Recurso que quebra e rota que quebra: a rota marca só o que o recurso executa. Recurso que acrescenta e rota que quebra: a rota marca os itens da raiz e os do recurso.

**D3 — Marcação de item que entra no pai na mesma publicação.** Todo item novo — próprio ou marcação — vai como a UI manda: `id` = `idTemp` = número temporário do contador global (W-9). A marcação de um item novo aponta `parent: {id: <temp>, idTemp: <temp>}`, e o Manager grava o id real (V-28 §5). Com `id` nulo, a marcação de rota para item novo do recurso some quando o recurso também marca item novo da raiz no mesmo PUT (medido na bateria da 425). O contador começa em 10¹² (`PISO_IDTEMP`), acima de qualquer id gerado pelo Manager, para o número temporário nunca coincidir com o id de um item existente. Marcação que o escopo já tem no Manager para o mesmo item é reaproveitada, como hoje.

A identidade de um item passa a ser `id` ou, sem ele, `idTemp`; a de uma marcação, `parent.id` ou, sem ele, `parent.idTemp`. A composição (`fluxo_composto`) usa essa identidade, então reconhece as marcações do payload antes de o Manager gravá-las.

**D4 — Decisão separada da escrita.** `resolver_fluxo_declarado` decide o que o escopo guarda e o que executa; `montar_fluxo_do_escopo` escreve isso no formato do PUT de revisão. O `FluxoDoEscopo` passa a ter:

| Campo | Significado |
|---|---|
| `proprios` | itens declarados que o escopo guarda |
| `quebra` | marcar todo item que o pai executa |
| `efetivo` | o que o escopo executa (para conformidade e avisos) |
| `heranca_pura` | sem itens próprios e sem quebra: o wire vai vazio |

Saem `contraditorio` e `substitui`. A publicação via swagger do roadmap usa a mesma decisão e troca só a escrita: chave do documento e `x-interceptor-parent-id` no lugar de `idTemp` e `parent.id` (V-28 §7).

**D5 — Posições.** Os itens próprios seguem a regra atual: reaproveitam as posições que o escopo já ocupa, os novos estendem a faixa, e o conjunto segue a ordem do arquivo. Sai `_posicionar_depois_do_herdado`: a posição não ordena entre escopos. A marcação leva a `position` do item que remove, como a UI.

**D6 — Avisos da montagem.**

| Aviso | Situação |
|---|---|
| `inherit: false` sem itens é contraditório | **sai** |
| herdado novo não pode ser marcado; rode de novo | **sai** |
| o repositório diz que o escopo só herda, e o Manager tem itens próprios nele | **fica**. O texto para de mandar usar `inherit: false` para mantê-los e passa a dizer "liste-os no arquivo" |
| `all.yaml` sem interceptors e raiz remota populada | fica |
| **herdado que o escopo deixa de executar** | **novo** |

O aviso novo sai quando o escopo existe no Manager, quebra a herança (`inherit: false`), e há item herdado que ele executa hoje e que continua no pai depois desta publicação. "Executa hoje" vem da composição do estado remoto (o escopo e seus pais como estão no Manager); "continua no pai" é ter o mesmo `id` no fluxo do pai no payload. Item que sai do próprio pai não entra: é mudança do pai, não do escopo. Texto:

> GET /x: o arquivo declara `inherit: false`, e ao publicar este ponto deixa de executar 2 interceptor(es) herdado(s) que executa hoje (Log, Custom#178).
> Se a intenção era mantê-los, use `inherit: true` para seguir herdando, ou liste-os no arquivo.

Ele existe principalmente para repositórios importados antes desta change: o importador gravava `inherit: false` em escopo que, no Manager, acrescenta ao herdado, e publicar um desses passa a cortar o herdado.

Não há aviso para herdado que **volta** a executar quando marcações saem (decisão do usuário em 22/10/2026).

**D7 — Conferência pós-publicação.**

- **Itens próprios.** O `esperado` de cada escopo passa a ser `proprios` (o que o arquivo declara), e não o `efetivo`. A raiz entra. A comparação segue por tipo, ordem e `content` normalizado.
- **Marcações.** Cada marcação é identificada pelo item herdado que remove: resolve-se `parent.id` (ou `parent.idTemp`) no fluxo composto do pai **do mesmo lado** — enviado ou gravado — e usa-se tipo, `customInterceptorId`, execution point e `content` normalizado desse item. Marcação cujo alvo não está no fluxo do pai usa os próprios campos, que copiam o item removido. Os dois lados são comparados como multiconjuntos, com as duas mensagens de hoje: enviada e não gravada ("esses itens herdados continuam executando aqui") e gravada e não enviada.
- Ficam como estão: contagem de itens vivos por escopo, operações, recursos, destinos e basic info.

**D8 — Conformidade.** `ValidateService._conformidade` compõe o fluxo de cada escopo com `fluxo_composto`, descendo raiz → recurso → rota sobre o payload. `fluxo_efetivo` (W-4) é removida. `_so_herda` não muda: escopo só com marcações não "só herda" e é comparado com a régua com o fluxo que executa, inclusive vazio.

**D9 — Importador.**

| Estado remoto do escopo | YAML |
|---|---|
| nada | `inherit: true`, sem itens |
| itens próprios, sem marcações | `inherit: true` com os itens próprios |
| marcações (com ou sem itens próprios) | `inherit: false` com a lista completa: o herdado não marcado, depois os próprios |
| todo o herdado marcado, sem itens próprios | `inherit: false`, sem itens, com comentário "não executa nenhum interceptor" |

O herdado de uma rota continua sendo o fluxo composto do recurso. O comentário sobre marcação que aponta para item fora do herdado fica.

**D10 — Schemas YAML.** A descrição de `inherit` em `api-resource.schema.json` e `api-operations.schema.json` passa a dizer: `true` = os itens declarados executam depois do fluxo herdado; `false` = executa exatamente o declarado, e sem itens o escopo não executa nada. Sem citar W-4 e W-5.

**D11 — Remoção da deriva de override.** `comparar_deriva_de_override` nunca foi chamada por nenhum comando. A situação que ela avisaria — escopo com `inherit: false` que deixa de receber o que o pai ganhou — é o efeito pedido pela declaração, e o corte de herdado que executava hoje é coberto pelo aviso da D6. Saem a função, os testes e o requisito "Override drift is reported".

**D12 — Bateria de herança na API-lab.** `tests/integration/test_bateria_heranca_425.py`, opt-in por `APIOPS_BATERIA_425=1`, escreve na Draft da API 425 pelo `ValidateService` e mede em runtime, com o mesmo método da V-28 §2: interceptors `Header` com `X-Lab-<rótulo>`, destino `https://httpbin.org/anything`, deploy no ambiente 7 e leitura do trace por `GET /calls` e `GET /calls/{id}`. O arnês faz backup da revisão antes da primeira escrita e a restaura ao fim pelo swagger exportado (`PUT /revisions/{id}/swagger`): as fases apagam recursos, e o backup da revisão apontaria ids que deixaram de existir. Cenários: os cinco da D2 nos três níveis, rota que quebra sob recurso que quebra, item novo na raiz e no recurso com escopos que quebram, volta à herança, item tirado do pai e o aviso de herdado cortado.

A `test_bateria_417.py` continua conferindo o estado gravado: os oráculos de T06, T07, T08, T11 e T12 passam a seguir a D2. Nesta change ela não é executada: a validação com escrita fica só na API-lab (decisão do usuário em 22/10/2026).

**D13 — Fora do escopo.**

- Publicação via swagger: roadmap (V-28 §7).
- Mover rota de recurso: segue a W-6.
- Item próprio do Manager que o arquivo não declara, num escopo com itens: sai sem aviso, como hoje.

### Riscos

- **Repositórios importados antes desta change.** Escopos que acrescentam ao herdado no Manager estão gravados com `inherit: false`. Publicá-los corta o herdado — o `f018ca5` já faz isso hoje. O aviso da D6 nomeia o que sai; a correção é trocar para `inherit: true` ou reimportar.
- **APIs publicadas pela V-27.** Escopos com `inherit: true` e itens têm cópias do herdado. A primeira publicação com a correção as remove; o efeito é parar a execução duplicada.
- **Bateria dependente de serviço externo.** A bateria da 425 depende do httpbin, do ambiente 7 e da API-lab existir. Fica fora da suíte padrão.

### Open Questions

Nenhuma.
