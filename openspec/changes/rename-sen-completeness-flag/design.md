## Design

### Contexto

`sen completeness` exige o ID da API via `--api-id`; `sen list api` usa `--id` para o mesmo conceito. A grafia duplicada contraria a própria orientação de erro do comando (`sen list api --id X --revisions`).

### Decisão

**D1 — Renomeação limpa sem alias legado.** A opção passa a declarar-se como `typer.Option(None, "--id", ...)`. Um alias `--api-id` manteria duas grafias vivas indefinidamente — exatamente o problema que se quer eliminar. A quebra é pontual (um comando novo, arquivado ontem) e fica anunciada no proposal como BREAKING.

**D2 — Nome interno preservado.** O parâmetro Python mantém-se `api_id` (nome já descritivo dentro do corpo do comando/factory); só a superfície CLI muda. Escopo confinado à camada inbound — service, port, adapter HTTP e contrato JSON `apiops.sen-completeness/v1` intocados.

**D3 — Superfície de testes.** Os testes de CLI exercitam o parser literalmente, então viram parte da mudança: invocações `["sen", "completeness", "--api-id", ...]` → `--id`, incluindo a assertion que valida o texto do erro pré-rede (que passa a citar `--id e --revision`).

### Alternativas descartadas

- **Alias duplo (`--id` + `--api-id`)**: Typer suporta múltiplos nomes na mesma Option, mas perpetua a ambiguidade; rejeitado pelo autor (29/09/2026).
- **Argumento posicional**: romperia a gramática de opções da casa (flags explícitas, princípio dos comandos mutantes herdados do ADR 0006 do sen-list).
