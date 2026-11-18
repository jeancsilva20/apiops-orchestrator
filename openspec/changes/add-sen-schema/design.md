## Context

A motivação está no `proposal.md` (Why). O estado de hoje:

- `domain/schemas/` tem um schema por arquivo do layout. O `catalog.json` (v2) liga cada padrão de caminho ao seu schema, e vale a primeira correspondência; o `select_schema` faz essa escolha nos testes. Nenhum schema do catálogo tem `$ref` para outro arquivo, então cada um se basta.
- A pasta também tem `api-environment.schema.json` e `env-variables.schema.json`, do layout antigo (PR #64). Eles não estão no catálogo e nenhum arquivo do layout atual os usa.
- O `validate` e o `publish` não aplicam os schemas (D4 do `tighten-api-tags-precheck`). Eles só rodam nos testes, e o teste com repositório real aponta para `docs/feat-api-estructure/.../api-417-rev2`, que saiu do repositório em 22/10/2026.
- O build do executável proíbe coletar dados do pacote (`scripts/build-exe.ps1:57`), porque na máquina de quem gera o build o `.sen` e o `.sen_session` moram na pasta do pacote. Por isso o binário de hoje não tem schemas.
- O `_app_root()` (`config/settings.py`) põe o `.sen` ao lado do binário quando congelado. O `ORCHEST_SCHEMA_FOLDER` é um caminho relativo que nenhum código lê.
- Precedente de comando oculto: os subcomandos do `sen diag` são `hidden=True` (change `add-sen-validate`).

## Goals / Non-Goals

**Goals**

- O agente obtém o schema de um arquivo antes de escrevê-lo, sem sessão e sem rede.
- O schema impresso é sempre o da versão da CLI que está rodando.

**Non-Goals**

- Validar um arquivo com o comando (algo como `sen schema --check`). Quem decide se o repositório está certo continua sendo o `sen validate`.
- Resolver regras entre arquivos (rota duplicada, catálogo de `apiTags`, régua, herança efetiva). Elas não cabem num schema e continuam no `validate`.

## Decisions

**D1 — Comando oculto de primeiro nível.** `sen schema`, com `hidden=True`.
- Alternativa: `sen diag schema`. Rejeitada porque o `diag` diagnostica as etapas do `validate` e exige um repositório; o schema não depende de nenhum dos dois.
- Alternativa: mostrar no help. Adiada por decisão do responsável; por enquanto só as skills citam o comando.

**D2 — O schema é escolhido pelo tipo de arquivo** (revista em 06/11). `sen schema <tipo>`, com os tipos `basic-info`, `all`, `components`, `resource` e `operation`.
- Os tipos são o `name` de cada entrada do `layout` no `catalog.json`. No código, eles são o `Enum` `RepoFileType`, e um teste garante que os dois batem.
- O tipo é um parâmetro posicional com valores fixos, como o `-o`, e não um subcomando. Subcomando serve quando cada alvo tem opções próprias, como o `sen list api`; aqui os cinco tipos fazem a mesma coisa. Com o `Enum`, o Typer valida o valor e o help lista os tipos.
- Alternativa: escolher pelo caminho do arquivo (`sen schema resources/tarefas/resource.yaml`), que foi a primeira versão. Rejeitada porque parecia que o comando lia o repositório da API e exigia um `--repo` só para converter caminho absoluto. O agente tira o tipo do caminho com a regra que a listagem mostra: `resource.yaml` é `resource`, e outro `.yaml` em `resources/<pasta>/` é `operation`.
- Alternativa: aceitar só o nome da pasta (`sen schema resources`). Rejeitada porque em `resources/<pasta>/` há dois tipos de arquivo, com schemas diferentes.

**D3 — Schema sem envelope; listagem com documento versionado.**
- O `sen schema <tipo>` imprime o próprio JSON Schema, que já traz `$schema` e `$id`. Assim a saída pode ser redirecionada para um arquivo e usada num editor (extensão YAML do VS Code) ou num validador.
- A listagem em `-o json`/`-o yaml` segue o padrão dos outros comandos, com o campo `schema` de versão: o documento `apiops.sen-schema/v1`, com a lista plana `layout` e, em cada item, `type`, `file` e `occurs` (revisto em 06/11).
  - `file` é o caminho com marcadores (`resources/<recurso>/<método>_<path>.yaml`). A hierarquia está no próprio caminho, então a lista não precisa de nós aninhados.
  - `occurs` diz quantos desse arquivo o repositório tem (por exemplo, "um por rota, ao menos um na pasta"). Os textos cabem numa linha de 80 colunas na árvore.
  - `file` e `occurs` são campos de cada entrada do `catalog.json`, ao lado do `pattern`. Um teste garante que o `file`, com os marcadores trocados, cai no mesmo schema pelo `pattern`.
  - Saíram `pattern`, `schemaFile` e `required`. Os dois primeiros são detalhe interno. O `required` do catálogo quer dizer "obrigatório pelo nome exato", e por isso marcava a operação como opcional, embora a CLI recuse recurso sem operação.
- Em texto, a listagem é uma árvore de pastas (`rich.tree`), com o tipo e o `occurs` ao lado de cada arquivo, alinhados. Em console sem UTF-8 o Rich desenha com ASCII; em terminal estreito a linha quebra alinhada, sem cortar texto.
- A impressão usa a mesma saída estruturada dos outros comandos (`display_output`): texto bruto no stdout fora do terminal, e nenhum markup do Rich sobre o conteúdo do schema.

**D4 — A pasta dos schemas é resolvida a partir do pacote.**
- A regra é uma linha: `Path(__file__).resolve().parents[1] / "domain" / "schemas"`, que substitui o `ORCHEST_SCHEMA_FOLDER`.
- No código-fonte, ela aponta para `src/apiops_orchestrator/domain/schemas/`. No executável, o PyInstaller extrai o pacote numa pasta temporária a cada execução e o `__file__` dos módulos aponta para dentro dela; a regra cai em `<pasta temporária>/apiops_orchestrator/domain/schemas/`, onde o `--add-data` (D5) põe os schemas.
- Não há `if frozen`: diferente do `.sen`, os schemas fazem parte da versão e vão dentro dela.

**D5 — `--add-data` só da pasta de schemas.**
- `src\apiops_orchestrator\domain\schemas;apiops_orchestrator\domain\schemas` no Windows (`;`) e o equivalente com `:` no Linux.
- A origem é só `domain/schemas/`, que não contém o `.sen` nem o `.sen_session`, e a conferência de segredos do build continua.
- A mesma etapa passa a conferir que todo schema citado no `catalog.json` entrou no binário. O build falha se faltar algum. O smoke test também roda o `sen schema -o json`.
- O caminho de origem é absoluto, porque o PyInstaller resolve um caminho relativo a partir da pasta do `.spec` (`build\exe`).
- **UTF-8 (06/11, aprovado pelo responsável):** o executável roda com `--python-option "X utf8"`.
  - Sem isso, no Windows, a saída em pipe ou em arquivo sai em cp1252, e o agente lê "par�metros". O executável ignora o `PYTHONIOENCODING`, então não dá para corrigir de fora.
  - Todas as leituras de arquivo do código já passam `encoding`, então a opção só muda a entrada e a saída padrão.
  - Vale para todos os comandos do executável, não só para o `sen schema`.
- Alternativa: embutir os schemas num módulo Python gerado. Rejeitada porque cria duas cópias da mesma coisa.

**D6 — Removida em 06/11.** Tratava do caminho absoluto e do `--repo`, que deixaram de existir com a D2 revista.

**D7 — Teste de fidelidade com exemplo dentro de `tests/`.**
- O exemplo fica em `tests/fixtures/api-repo-400/`, no layout atual. A árvore do fluxo sai do próprio materializador da CLI (`repo_materializer.materialize`), aplicado ao payload higienizado da API 400 (Orchestrator Auth API) que já está em `tests/fixtures/manager/api-400-rev4.json`. O contrato foi completado à mão: `contact`, `tags`, `security`, as seis seções do `components.yaml`, `parameters` de recurso e de rota, `requestBody`, `responses` e `timeout`.
- **Revisto em 06/11:** o plano era gerar o exemplo da API-lab 425 pelo extrator. Duas coisas mudaram isso. O `.sen` local aponta para o ECAD, e a 425 está no consulting. E o payload da 417 traz backends do ECAD, que é dado de cliente. A 400 é da Sensedia, já estava higienizada no repositório e gera o exemplo sem rede.
- O teste confere três coisas: que o `sen validate` lê o exemplo sem erro (o `load` do `RevisionWriter`), que o validador de contrato não acusa erro nem aviso, e que cada arquivo passa no schema que o catálogo indica.
- A referência é o que a CLI aceita, e a divergência vale nos dois sentidos. Um schema que recusa o que a CLI aceita é corrigido. Um schema que aceita o que a CLI sempre recusa também é corrigido, porque o agente escreveria um arquivo válido no schema que o `validate` barra. Foi o caso do item de `apiTags` sem tag, recusado pelo pré-check desde o `tighten-api-tags-precheck` e aceito pelo schema até esta change.
- A correção vai no schema, num commit `fix:` próprio, e nunca no exemplo.

**D8 — Descrições escritas para quem preenche o arquivo** (06/11). O `sen schema <tipo>` entrega o schema ao agente, que é consumidor e não precisa do histórico do projeto.
- `title` e `description` dos cinco schemas do catálogo dizem o que o campo é, como preencher e o que o `sen validate` recusa. Não citam decisões (D-xx, V-xx, W-xx), refino, contrato do wire nem variáveis da esteira.
- `title` e `description` ficam em português, com acentuação: o schema virou saída de comando, lida pelo agente e pelo dev (por exemplo, no hover da extensão YAML), e a seção 3 dos padrões põe mensagens ao usuário final em PT-BR. Chaves, valores de `enum` e demais palavras-chave do JSON Schema ficam como são.
- Os `comment` do `catalog.json` continuam como estão, porque o comando não os mostra.

## Risks / Trade-offs

- [Um campo novo entra no código e o schema fica para trás] → O teste só pega o que o exemplo cobre. Toda change que acrescentar campo a um YAML acrescenta o campo também ao exemplo.
- [O agente confia no schema e ignora as regras entre arquivos] → A skill sempre fecha o ciclo com o `sen validate` (fica na change das skills).
- [O separador do `--add-data` muda por sistema] → Cada script tem a sua linha, e a conferência do build pega a ausência dos schemas.
- [Alguém descobre e usa o comando oculto] → Aceito: o comando só lê arquivos da própria instalação e não tem efeito colateral.
- [O erro de tipo inválido vem do Click, em inglês e com `exit 2`] → É o mesmo comportamento de um valor inválido de `-o` em todos os comandos, e a mensagem lista os tipos aceitos.
- [Um tipo novo entra no catálogo e não no `Enum`, ou o contrário] → O teste que compara os dois falha.

## Migration Plan

Não há migração: o comando é novo e não muda nenhum outro. Para reverter, basta remover o comando e o `--add-data`.
