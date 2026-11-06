---
name: sen-explore
description: >-
  Responde perguntas sobre as APIs do Sensedia API Manager e sobre o repositório local de uma API do
  APIOps usando a CLI `sen` só para leitura, sem alterar nada. Use sempre que o usuário quiser saber
  o ID, a versão ou o base path de uma API, as revisões, em que ambiente cada revisão está, o estágio
  de governança, a nota de completude e o mínimo exigido, as sugestões de melhoria, o que a régua
  (API-template) exige ou o que está na Draft, ou quiser entender o repositório local (rotas,
  recursos, backend e timeout de cada rota, interceptors e herança, apiTags), mesmo sem citar o
  `sen`. Exemplos: "quais as revisões da API 425?", "qual a nota da última revisão da API de
  pagamentos?", "em que ambiente está a revisão 3?", "quais rotas essa API tem e pra qual backend
  cada uma vai?", "quais interceptors a rota de token executa?". Não use para criar, alterar ou
  remover algo no repositório, nem para validar ou gravar na Draft (use a sen-api-editor), nem para
  publicar, fazer deploy ou login.
---

# Consultas com o `sen`

O repositório da API descreve uma API do Sensedia API Manager em arquivos YAML, e a CLI `sen` lê esses arquivos e consulta o Manager. Seu trabalho é responder o que o usuário perguntou, com os dados da CLI e dos arquivos, sem mudar nada. Ele fez uma pergunta: uma escrita no meio da resposta seria uma surpresa, mesmo que pareça ajudar.

A CLI é a fonte da verdade. O formato e o significado de cada campo vêm do `sen schema`, e os dados do Manager vêm dos comandos de leitura. Não deduza regra de cabeça: consulte a CLI.

## Regras de convivência com o `sen`

- **Leia dados com `-o json`.** A saída em texto é para pessoas e muda de forma.
- **Nunca deixe um comando esperando resposta.** Nenhum comando desta skill pergunta nada. O `sen validate` pergunta, e ele não é desta skill.
- **Não leia o `.sen` nem o `.sen_session`.** Eles guardam a credencial e a sessão do usuário. Você trabalha com a sessão que ele já abriu, sem ver o conteúdo.
- **Não rode `sen login`, `sen validate`, `sen publish` nem `sen deploy`, e não edite arquivos.** O login usa a credencial do usuário, então quem faz é ele. O `validate` grava na Draft. Publicação e deploy rodam só na esteira.
- **Erro de sessão ou de configuração** (sessão ausente ou expirada, ou "Configuração incompleta"): peça ao usuário que configure o `sen` e rode `sen login` ele mesmo, e pare a parte que depende do Manager. As perguntas sobre o repositório local continuam respondíveis, porque não usam rede.
- **Confira a CLI antes de começar.** Rode `sen schema --help`. Se aparecer "No such command", o `sen` instalado é antigo: peça ao usuário que atualize e pare.

## Comandos de leitura

| Comando | O que devolve | Rede |
|---|---|---|
| `sen list api --query "<texto>" --all -o json` | APIs cujo nome ou descrição contém o texto: `id`, `name`, `description`, `version`, `basePath`, `lifeCycle`, `owner`, `updateDate` e `lastRevision.revisionNumber`. Sem `--all`, só as 10 primeiras | Sim |
| `sen list api --id <id> -o json` | A API desse ID, numa lista de um item | Sim |
| `sen list api --id <id> --revisions -o json` | Uma linha por revisão: `revision_id` (o REV ID), `revision_number`, `stage_name` (estágio de governança), `environments` (texto separado por vírgula) e `completeness_score` (`null` quando o Manager não respondeu). Consulta a completude de cada revisão, então é mais lento | Sim |
| `sen completeness --id <id> --revision <REV ID> -o json` | `maturity.score` (nota), `gate.percent` (mínimo exigido), `suggestions` e o contexto da API. O `--revision` recebe o REV ID, não o número da revisão | Sim |
| `sen schema [tipo] -o json` | O layout do repositório ou o JSON Schema de um tipo de arquivo, com a descrição de cada campo | Não |
| `sen diag structure -o json` | Os recursos e as rotas do repositório local: método, path e arquivo de cada rota | Não |
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
3. **Da revisão à completude.** A nota já vem em `completeness_score`. Para o mínimo exigido e as sugestões, rode `sen completeness --id <id> --revision <revision_id> -o json`. Se a nota veio `null`, esse comando também a traz.

Exemplo: "qual a nota da última revisão da API 425?"
1. `sen list api --id 425 --revisions -o json` → revisão de maior número, e o `revision_id` dela.
2. `sen completeness --id 425 --revision <revision_id> -o json` → nota, mínimo e sugestões.

## Antes de muitas consultas

Conte as chamadas à CLI antes de começar. Se forem mais de 10, diga ao usuário quantas serão e por quê, e espere o ok. Cada chamada vai ao Manager com a sessão dele, e uma varredura grande demora e pesa no ambiente.

Exemplo: "quais APIs estão abaixo de 70%?" exige um `sen list api --all` e mais um `--revisions` por API. Com 40 APIs, são 41 chamadas, e cada `--revisions` consulta todas as revisões da API. Ofereça um recorte antes, como só as APIs de um termo de busca.

## Perguntas sobre o repositório local

Essas perguntas não usam rede.

- Confirme que está num repositório de API: existe um `api-basic-info.yaml` na raiz. Se o repositório estiver em outra pasta, os comandos aceitam `--repo <pasta>`.
- Rode `sen diag structure -o json` para ter os recursos, as rotas e o arquivo de cada uma.
- Leia os arquivos YAML para os detalhes. Eles descrevem a API e não guardam credencial.
- Para saber o que um campo significa e o que vale quando ele está vazio ou ausente, leia a `description` do campo em `sen schema <tipo>`. O tipo é `basic-info`, `all`, `components`, `resource` ou `operation`.

**Valores efetivos.** Backend (`destination.url`), timeout e interceptors podem vir da rota, do `resource.yaml` do recurso ou do `all.yaml`, nessa ordem de precedência.
- Para responder "pra qual backend vai", aplique a regra de herança que a descrição do campo no `sen schema` traz, e diga de onde o valor veio: declarado na rota, herdado do recurso ou herdado do `all.yaml`.
- Valores como `$backend_url` são variáveis de ambiente do Manager, resolvidas em cada ambiente. Mostre o nome da variável, sem inventar o valor.
- Para o fluxo de interceptors de uma rota, siga a regra do `inherit` descrita no `sen schema operation` e no `sen schema resource`, e liste o que vem de cada escopo.

**Repositório contra Manager.** "A Draft tem as mesmas rotas do repositório?": compare as rotas do `sen diag structure` com as do `sen diag draft` e diga o que está só de um lado. A comparação é de rotas. Ela não confere o conteúdo de cada rota.

## Perguntas que pedem gravação ou mudança

- **Veredito da governança, conformidade com a régua ou nota depois de uma mudança:** o `sen validate` dá esses resultados gravando o repositório na Draft, e esta skill não grava. Explique isso e indique a sen-api-editor, que grava só com a confirmação do usuário, ou o próprio `sen validate`. Você pode mostrar o que a régua exige (`sen diag template`), mas não conclua se o repositório está conforme: quem decide é o `validate`.
- **Pedido de mudança no repositório:** é trabalho da sen-api-editor. Não edite nada.

## Como responder

- Responda com os dados pedidos e os identificadores usados: o ID da API, o número da revisão e o REV ID. Quando houver, sugira o próximo comando útil.
- Não cole o JSON bruto, a menos que o usuário peça.
- **Completude abaixo do mínimo:** traga a nota, o mínimo, quantos pontos faltam e as sugestões resumidas.
- **Dado ausente** (`null`): diga que o Manager não respondeu por aquele item, em vez de tratar como zero.
- **Ambiente:** você não sabe qual Manager está na sessão, porque não lê o `.sen`. Diga "o Manager da sessão aberta" quando precisar se referir a ele.

## Exemplos de pergunta

| Pergunta | Como responder |
|---|---|
| "quais as revisões da API 425?" | `sen list api --id 425 --revisions -o json` |
| "qual a nota da última revisão da API 425?" | Revisões → maior número → `sen completeness` com o REV ID |
| "qual o ID da API de autenticação?" | `sen list api --query "autenticação" --all -o json`, perguntando se houver mais de uma |
| "em que ambientes está a revisão 3 da API 425?" | Revisões → `environments` da linha de número 3 |
| "quais rotas essa API tem e pra qual backend cada uma vai?" | `sen diag structure` e a leitura de rota, recurso e `all.yaml`, sem rede |
| "quais interceptors a rota POST /token executa?" | Os fluxos do `all.yaml`, do recurso e da rota, com a regra do `inherit` do `sen schema` |
| "o que a régua exige?" | `sen diag template -o json` |
| "a Draft tem as mesmas rotas do repositório?" | `sen diag draft` contra `sen diag structure` |
| "quais APIs estão abaixo de 70%?" | Avise quantas chamadas serão e espere o ok |
| "essa API passaria na governança?" | Explique que o veredito exige gravar na Draft e indique a sen-api-editor |
