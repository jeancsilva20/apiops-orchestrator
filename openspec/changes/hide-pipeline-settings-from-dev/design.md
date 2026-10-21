## Design

### Contexto

A CLI roda em dois lugares: na máquina do dev (`EXECUTION_MODE` ausente ou `local`) e na esteira (`EXECUTION_MODE=pipeline`, V-11). O modo decide de onde vem a API-template, qual revisão pode ser gravada, se há confirmação e se `publish` e `deploy` rodam. As mensagens foram escritas para quem configura a esteira e acabaram aparecendo também para o dev, citando o nome das variáveis.

`EXECUTION_MODE` é a única variável que muda o que o dev consegue fazer na própria máquina. As outras (`TARGET_REVISION_NUMBER`, `TARGET_ENVIRONMENT_ID`, `TEMPLATE_API_ID`) só têm efeito na esteira depois desta change: o validate local ignora a revisão alvo, a template local vem do `api-basic-info.yaml`, e publish e deploy não rodam fora da esteira.

### Decisões

**D1 — Quem pode ser nomeado em cada saída.**

| Nome | Fora da esteira | Na esteira |
|---|---|---|
| `SEN_CREDENTIALS`, `AUTH_HOST`, `AUTH_LOGIN_PATH` | sim (o dev recebe no `.sen`, ADR 0007) | sim |
| `TARGET_REVISION_NUMBER`, `TARGET_ENVIRONMENT_ID`, `TEMPLATE_API_ID` | não | sim |
| `EXECUTION_MODE`, "modo local", "modo pipeline", o valor do modo | não | não |

Fora da esteira, o texto fala em "sua máquina" e "esteira". "Saída" aqui é o terminal (stdout e stderr), o `--help` e os documentos `json`/`yaml`. Comentários de código, `.env.example` e documentação interna não entram na regra.

**D2 — `sen publish` só na esteira.** A trava é a primeira coisa do comando, antes de autenticar e de qualquer chamada HTTP, igual ao `sen deploy`. Fora da esteira: `exit 1`. A confirmação interativa do publish sai, junto com o caminho P-2 da V-24 (local publica na Draft). Quem quer o veredito da governança na Draft usa o `sen validate`, que continua gravando nela com confirmação. Os avisos de remoção do publish passam a sair sempre no resultado (era o comportamento da esteira).

**D3 — `sen validate` local sempre na Draft.** Fora da esteira, a revisão alvo é a 1 e `TARGET_REVISION_NUMBER` não é lido. Some a recusa "local fora da Draft", que só existia para citar a variável. O comando de diagnóstico interno `sen diag draft` segue a mesma regra. Na esteira nada muda.

**D4 — `executionMode` só na esteira.** Nos documentos `apiops.sen-validate/v1`, `apiops.sen-publish/v1` e `apiops.sen-deploy/v1`, o campo existe apenas quando o modo é `pipeline`; fora dela, ele é omitido (não vem `null`). Como publish e deploy só rodam na esteira depois desta change, nos dois o campo vem sempre `"pipeline"`. O versionamento `v1` se mantém: a esteira, única consumidora do campo, continua recebendo o mesmo valor. A linha "Modo" sai dos painéis de texto nos dois modos, porque na esteira ela seria sempre a mesma.

**D5 — Falha de carga da configuração.** O `main.py` traduz o `ValidationError` das settings. A mensagem:

- lista as chaves de D1 que o modo permite nomear;
- se houver chave com problema que o modo não permite nomear, acrescenta *"Há outra configuração inválida. Fale com o time da plataforma."*;
- sem nenhuma chave nomeável, fica só *"A configuração do sen é inválida. Fale com o time da plataforma."*

Como as settings não carregaram, o modo é lido do ambiente bruto (`os.environ`, que já recebeu o `.sen` e o `.env` na importação do módulo de settings): só é esteira quando o valor normalizado é `pipeline`. Valor inválido conta como fora da esteira.

**D6 — Mensagens da esteira mantêm as variáveis.** Os logs da CLI estão desligados (`NullHandler` no `main.py`), então a mensagem é o único lugar onde o time da plataforma descobre a variável que falta. Única mudança: o aviso de divergência de template deixa de dizer "definida em variável de ambiente".

**D7 — `--help` em português.** Passam para português a ajuda dos apps (`sen`, `list`), de todos os comandos e de todas as opções. Os rótulos que o Typer/Click gera sozinhos ("Usage", "Options", "Commands", "Show this message and exit.") ficam fora: traduzi-los exige mexer nas constantes internas do Typer (ver Q1).

**D8 — Guarda nos testes.** Um teste percorre as mensagens visíveis fora da esteira (erros de configuração dos services, `--help` de cada comando, painéis e documentos com `EXECUTION_MODE=local`) e falha se qualquer uma contiver `EXECUTION_MODE`, `TARGET_REVISION_NUMBER`, `TARGET_ENVIRONMENT_ID`, `TEMPLATE_API_ID`, `pipeline` ou `executionMode`. Na esteira, ele confere só a ausência de `EXECUTION_MODE`.

### Catálogo de mensagens

Fora da esteira:

| Onde | Hoje | Depois |
|---|---|---|
| `sen deploy` local | "O deploy é feito só pela esteira: o comando não roda na máquina local (EXECUTION_MODE=local). A promoção para DEV, HML e PRD acontece no merge da branch correspondente." | "O deploy é feito só pela esteira: o comando não roda na sua máquina. A promoção para DEV, HML e PRD acontece no merge da branch correspondente.\n\nNenhum deploy foi feito." |
| `sen publish` local | grava na Draft após confirmação | "A publicação é feita só pela esteira: o comando não roda na sua máquina. Para conferir o repositório contra a governança, use `sen validate`, que grava na revisão Draft.\n\nNada foi publicado." |
| `sen validate` local, revisão ≠ 1 | "Em modo local a única revisão publicável é a 1 (Draft), e TARGET_REVISION_NUMBER está em N…" | (deixa de existir, D3) |
| `sen publish` local, revisão ≠ 1 | "Na máquina local só é possível publicar na revisão 1 (Draft), e TARGET_REVISION_NUMBER está em N…" | (deixa de existir, D2) |
| painéis validate/publish/deploy | linha "Modo: local" | (sem a linha) |
| `-o json/yaml` | `"executionMode": "local"` | (sem o campo) |
| configuração inválida | "Configuração incompleta (ausente/inválida): EXECUTION_MODE. Defina as variáveis no .env…" | D5 |
| `sen deploy --help` | "Deploy the revision set in TARGET_REVISION_NUMBER to TARGET_ENVIRONMENT_ID (pipeline only)." | "Faz o deploy da revisão da API no ambiente. Roda só na esteira." |
| `sen publish --help` | "Publish the API repository to the revision set in TARGET_REVISION_NUMBER." | "Publica o repositório da API na revisão do ambiente. Roda só na esteira." |

Na esteira (mantidas, D6): `TARGET_REVISION_NUMBER` ausente, igual a 1 ou inválida; `TARGET_ENVIRONMENT_ID` ausente; ambiente não ligado à API; `TEMPLATE_API_ID` ausente. Muda só o aviso de divergência de template:

> O `api-basic-info.yaml` aponta a API-template 414, mas a esteira está usando a 415, definida pela plataforma. A da esteira tem prioridade, para que a template não possa ser trocada por um commit. Seguindo com a 415.

### Textos de ajuda (D7)

| Item | Depois |
|---|---|
| app `sen` | "CLI do APIOps: framework GitOps para automatizar, padronizar e gerenciar suas APIs." |
| app `list` | "Lista recursos." |
| `--verbose` (global) | "Aumenta o detalhamento dos logs." |
| `--version` | "Mostra a versão da CLI." |
| `sen login` | "Autentica na Orchestrator Auth API e guarda a sessão local. Requer a variável SEN_CREDENTIALS (Base64 de client_id:secret)." |
| `sen list api` | "Lista as APIs do Sensedia Manager." |
| `--id` (list) | "Filtra pelo ID da API." |
| `--query` | "Busca por nome ou descrição, feita pelo Manager." |
| `--limit` | "Quantidade de itens por página." |
| `--offset` | "A partir de qual item exibir." |
| `--all` | "Lista todas as APIs visíveis (não combina com --limit, --offset ou --id)." |
| `--revisions` / `-r` | "Mostra as revisões da API informada em --id." |
| `sen completeness` | "Mostra o completeness de uma revisão de API (Sensedia Manager)." |
| `--id` (completeness) | "ID da API no Manager." |
| `--revision` | "ID da revisão (REV ID do detalhe de revisões)." |
| `--score-only` | "Mostra só a nota e a barra com o mínimo exigido." |
| `sen validate` | "Valida o repositório da API e grava na Draft para obter o veredito da governança." |
| `sen publish` | "Publica o repositório da API na revisão do ambiente. Roda só na esteira." |
| `sen deploy` | "Faz o deploy da revisão da API no ambiente. Roda só na esteira." |
| `--output` / `-o` | "Formato da saída (text, json, yaml)." |
| `--verbose` (comandos) | "Aumenta o detalhamento da saída." |
| `--repo` | (já em português) |

### Fora do escopo

- Ids do Manager exibidos nas telas (revisão, ambiente, deploy): o dev já os vê na própria plataforma, e eles não mudam a configuração.
- Tradução dos rótulos gerados pelo Typer/Click (Q1).
- Autorização no Manager. Esconder o nome de `EXECUTION_MODE` reduz o risco, mas não é barreira: quem ler o código encontra o nome. A barreira de verdade é a credencial do dev não ter permissão para gravar revisões de ambiente nem fazer deploy (autorização por ação, ADR 0003). Fica como item separado (Q2).

### Questões abertas

- **Q1 — Rótulos do Typer/Click.** Traduzir "Usage", "Options", "Commands" e "Show this message and exit." exige sobrescrever constantes do `typer.rich_utils` e o texto da opção de ajuda. Fica para depois ou entra aqui?
- **Q2 — Permissão do perfil developer.** Confirmar se a credencial do dev já é recusada pelo Manager num `PUT` em revisão de ambiente e num `POST` de deploy. Se não for, abrir item próprio.
- **Q3 — Tabela de variáveis no `comandos-cli.md`.** A seção do `sen deploy` lista `EXECUTION_MODE` e as variáveis da esteira. Se esse documento for distribuído aos devs, a tabela deve ir para uma documentação só da plataforma.
