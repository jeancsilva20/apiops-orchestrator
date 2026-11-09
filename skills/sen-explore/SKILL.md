---
name: sen-explore
description: >-
  Responde perguntas sobre as APIs do Sensedia API Manager usando a CLI `sen` só para leitura. Use
  quando o usuário quiser saber o ID, a versão ou o base path de uma API, as revisões e seus
  ambientes, o que a régua (API-template) exige, o que está na Draft ou se ela tem as mesmas rotas
  do repositório, mesmo sem citar o `sen`, como em "quais as revisões da API 425?" ou "em que
  ambientes está a última revisão da API de pagamentos?". Não use para perguntas sobre o que está nos arquivos do repositório local, como rotas,
  backends e interceptors, nem para mudá-lo ou gravar na Draft (use a sen-api-developer), nem para
  publicar, fazer deploy ou login.
---

# Consultas ao Manager com o `sen`

A CLI `sen` consulta o Sensedia API Manager. Seu trabalho é responder o que o usuário perguntou sobre o que está no Manager, com os dados da CLI, sem mudar nada. Ele fez uma pergunta: uma escrita no meio da resposta seria uma surpresa, mesmo que pareça ajudar.

O escopo é o Manager. Perguntas sobre o que está nos arquivos do repositório local da API, como rotas, backends e interceptors, ficam com a sen-api-developer.

Completude e governança ficam fora desta skill, porque dependem do Adaptive Governance, que nem todo cliente tem: sem ele, o Manager recusa a consulta. Não rode `sen completeness`. Quando o `sen list api --revisions` trouxer `completeness_score` ou `stage_name`, você pode mostrá-los. Quando vierem `null`, não fale deles. Perguntas sobre o mínimo exigido, as sugestões de melhoria ou como subir a nota não são desta skill: diga isso ao usuário.

A CLI é a fonte da verdade: os dados do Manager vêm dos comandos de leitura. Não deduza de cabeça: consulte a CLI.

## Regras de convivência com o `sen`

- **Leia dados com `-o json`.** A saída em texto é para pessoas e muda de forma.
- **Nunca deixe um comando esperando resposta.** Nenhum comando desta skill pergunta nada. O `sen validate` pergunta, e ele não é desta skill.
- **Não leia o `.sen` nem o `.sen_session`.** Eles guardam a credencial e a sessão do usuário. Você trabalha com a sessão que ele já abriu, sem ver o conteúdo.
- **Não rode `sen login`, `sen validate`, `sen publish` nem `sen deploy`, e não edite arquivos.** O login usa a credencial do usuário, então quem faz é ele. O `validate` grava na Draft. Publicação e deploy rodam só na esteira.
- **Prefira os comandos citados nesta skill.** Se a pergunta precisar de algo que eles não cobrem, confira na ajuda (`sen --help` e `sen <comando> --help`) se existe comando ou opção para isso. Se não existir, diga ao usuário que o `sen` não mostra isso hoje e pare, sem inventar comando nem opção. Um comando achado na ajuda só roda se ele só lê. Se ele grava algo, não é desta skill.
- **É proibido chamar a API do Manager por fora da CLI**, com curl, script ou qualquer outra requisição, mesmo quando nenhum comando atende a pergunta.
- **Erro de sessão ou de configuração** (sessão ausente ou expirada, ou "Configuração incompleta"): peça ao usuário que configure o `sen` e rode `sen login` ele mesmo, e pare, porque as respostas desta skill vêm do Manager.
- **Confira a CLI antes de começar.** Rode `sen schema --help`. Se aparecer "No such command", o `sen` instalado é antigo: peça ao usuário que atualize e pare.

## Comandos de leitura

| Comando | O que devolve | Rede |
|---|---|---|
| `sen list api --query "<texto>" --all -o json` | APIs cujo nome ou descrição contém o texto: `id`, `name`, `description`, `version`, `basePath`, `lifeCycle`, `owner`, `updateDate` e `lastRevision.revisionNumber`. Sem `--all`, só as 10 primeiras | Sim |
| `sen list api --id <id> -o json` | A API desse ID, numa lista de um item | Sim |
| `sen list api --id <id> --revisions -o json` | Uma linha por revisão: `revision_id` (o REV ID), `revision_number` e `environments` (texto separado por vírgula). Traz também `stage_name` e `completeness_score`, que vêm `null` sem o Adaptive Governance. É mais lento, porque consulta cada revisão | Sim |
| `sen diag structure -o json` | Os recursos e as rotas do repositório local: método, path e arquivo de cada rota. Serve para comparar com a Draft | Não |
| `sen diag draft -o json` | A Draft da API do repositório no Manager: número e REV ID, `workflowId` e `workflowStageId`, e os recursos com as rotas | Sim |
| `sen diag template -o json` | A régua da API do repositório: o API-template, a revisão dele e o fluxo de interceptors que ela exige (`flow`), com avisos | Sim |

Os três `sen diag` rodam dentro do repositório da API, ou com `--repo <pasta>`.

Quando nada casa, o `sen list api` imprime "Nenhuma API encontrada." em texto, mesmo com `-o json`, e o `--revisions` imprime "Nenhuma revisão encontrada para a API X.". Trate esses textos como resultado vazio, não como erro.

## Encadeamentos

O usuário quase nunca dá o REV ID. Chegue nele pela CLI e pergunte só quando a busca devolver mais de um candidato ou nenhum.

1. **Do nome ao ID da API.** Rode `sen list api --query "<nome>" --all -o json`.
   - Um resultado: siga com ele.
   - Mais de um: liste cada um com ID, nome, versão e base path, e pergunte qual. A busca do Manager olha também a descrição, então pode trazer APIs que só citam o termo.
   - Nenhum: diga isso e sugira outro termo.
   - "Esta API", dentro de um repositório de API: o ID é o `spec.id` do `api-basic-info.yaml`.
2. **Da API às revisões.** Rode `sen list api --id <id> --revisions -o json`. A "última revisão" é a de maior `revision_number`. A "revisão 3" é a linha com `revision_number` 3, e o `revision_id` dela é o REV ID.

Exemplo: "em que ambientes está a última revisão da API de pagamentos?"
1. `sen list api --query "pagamentos" --all -o json` → o ID, perguntando se houver mais de uma.
2. `sen list api --id <id> --revisions -o json` → os `environments` da revisão de maior número.

## Antes de muitas consultas

Conte as chamadas à CLI antes de começar. Se forem mais de 10, diga ao usuário quantas serão e por quê, e espere o ok. Cada chamada vai ao Manager com a sessão dele, e uma varredura grande demora e pesa no ambiente.

Exemplo: "em que ambientes está a última revisão de cada API?" exige um `sen list api --all` e mais um `--revisions` por API. Com 40 APIs, são 41 chamadas, e cada `--revisions` consulta todas as revisões da API. Ofereça um recorte antes, como só as APIs de um termo de busca.

## Rotas no Manager

Nenhum comando traz os detalhes das rotas de uma API no Manager. O `sen diag draft` mostra só o método e o path das rotas da Draft, e só da API do repositório aberto.

- **"Quais rotas a API tem no Manager?":** dentro do repositório dela, responda com o `sen diag draft` e diga que são as rotas da Draft. Fora dele, ou para uma revisão publicada, diga que o `sen` não mostra isso hoje.
- **"A Draft tem as mesmas rotas do repositório?":** compare as rotas do `sen diag structure` com as do `sen diag draft` e diga o que está só de um lado. A comparação é de rotas. Ela não confere o conteúdo de cada rota.
- **Detalhes de uma rota** (backend, timeout, interceptors, responses) estão só nos arquivos do repositório: use a sen-api-developer. Se ela não estiver instalada, você pode ler os arquivos para responder, sem editar nada.

## Perguntas que pedem gravação ou mudança

- **Conformidade com a régua depois de uma mudança:** o `sen validate` dá esse resultado gravando o repositório na Draft, e esta skill não grava. Explique isso e use a sen-api-developer, que grava só com a confirmação do usuário. Se ela não estiver instalada, diga ao usuário que ele mesmo pode rodar o `sen validate`. Você pode mostrar o que a régua exige (`sen diag template`), mas não conclua se o repositório está conforme: quem decide é o `validate`.
- **Pedido de mudança no repositório:** use a sen-api-developer, que tem o próprio ciclo de mudança. Se ela não estiver instalada, não edite: diga ao usuário que esta skill só consulta.
## Como responder

- Responda com os dados pedidos e os identificadores usados: o ID da API, o número da revisão e o REV ID. Quando houver, sugira o próximo comando útil.
- Não cole o JSON bruto, a menos que o usuário peça.
- **Dado ausente** (`null`): diga que o Manager não respondeu por aquele item, em vez de tratar como zero. A exceção são `completeness_score` e `stage_name`: quando vierem `null`, não fale deles.
- **Ambiente:** você não sabe qual Manager está na sessão, porque não lê o `.sen`. Diga "o Manager da sessão aberta" quando precisar se referir a ele.

## Exemplos de pergunta

| Pergunta | Como responder |
|---|---|
| "quais as revisões da API 425?" | `sen list api --id 425 --revisions -o json` |
| "qual a nota da última revisão da API 425?" | Revisões → maior número. Se o `completeness_score` vier, mostre. Se vier `null`, diga que completude não é desta skill |
| "qual o ID da API de autenticação?" | `sen list api --query "autenticação" --all -o json`, perguntando se houver mais de uma |
| "em que ambientes está a revisão 3 da API 425?" | Revisões → `environments` da linha de número 3 |
| "quais rotas a API 425 tem no Manager?" | Dentro do repositório da 425, `sen diag draft` (só método e path da Draft). Fora dele, diga que o `sen` não mostra isso hoje |
| "pra qual backend vai cada rota dessa API?" | É do repositório: use a sen-api-developer |
| "o que a régua exige?" | `sen diag template -o json` |
| "a Draft tem as mesmas rotas do repositório?" | `sen diag draft` contra `sen diag structure` |
| "em que ambientes está a última revisão de cada API?" | Avise quantas chamadas serão e espere o ok |
| "qual o mínimo de completude?" ou "sobe a completude pra 70%" | Diga que completude e governança não são desta skill |
