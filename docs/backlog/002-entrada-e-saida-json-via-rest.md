# 002 — Entrada e saída em JSON por REST

**Status:** `todo` · **Prioridade sugerida:** a definir · **Registrado em:** 2026-11-18 · **Base:** `feat/executable` em `7db5b9d`

## Resumo

Hoje o orquestrador tem uma única entrada: a CLI `sen`. A proposta é ter uma segunda entrada, REST, que recebe a
requisição em JSON e responde em JSON, executando os mesmos casos de uso. A saída para o Manager e para a API de
autenticação não muda.

Este documento analisa o que o código já oferece, o que está preso à CLI e o esforço para chegar lá.

**Conclusão.** A arquitetura comporta a segunda entrada sem reescrever serviço: os casos de uso não imprimem, não
leem `stdin` e já devolvem o documento JSON versionado. O trabalho está em quatro pontos que hoje só existem na
borda da CLI ou no processo: o contrato de erro, a identidade de quem chama, o repositório da API como entrada e os
alvos que vêm de variável de ambiente. 

## Origem

Necessidade de, além da CLI, expor o orquestrador por REST com entrada e saída em JSON. A pasta
`adapters/inbound/http/` já existe reservada com `.keep` (`padroes-desenvolvimento.md` §2), e
`consumidores-projetados.md` §4 já previa "expor as mesmas funções" a agentes por outro canal.

## O que já está pronto

| Ponto | Onde | Por que ajuda |
|---|---|---|
| Serviços recebem ports no construtor | `application/services/*` | A entrada REST monta os mesmos serviços |
| Serviços devolvem o documento da saída | `to_document()` em `ValidateView`, `PublishView`, `DeployView`, `CompletenessView` | A resposta REST é o mesmo documento `apiops.sen-*/v1` do `-o json` |
| Confirmação e progresso são funções recebidas | `ValidateService.validate(confirm=, progress=)` | O serviço nunca lê `stdin` nem escreve na tela |
| Cliente HTTP não imprime nem encerra o processo | `infrastructure/utils/http_client.py` | Pode rodar dentro de um servidor |
| Erros categorizados com mensagem orientada | `application/exceptions/*` | Base para o corpo de erro |
| Regras de acesso fora da CLI | `domain/services/session_access.py`, `ApiAccessGuard` | Visibilidade, time APIOps, `write` e esteira valem para as duas entradas |

## O que precisará se adequar

### 1. Não existe contrato de erro em JSON

Atualmente, mesmo com o comando da CLI passando `-o json`, o erro sai como texto (`_print_error` em `cli_adapter.py`). Dois casos de sucesso também saem como
texto no modo estruturado: `sen list api` sem resultado ("Nenhuma API encontrada.") e o `validate` não confirmado.

O código de saída não basta para escolher o status HTTP, pois apesar de termos as classes de exceptions, os erros não são tipados para fazer um de-para para status HTTP.
É preciso um catálogo que dê a cada exceção um código estável (`API_NOT_VISIBLE`, `GOVERNANCE_BLOCKED`…) e uma
categoria, da qual saem o status HTTP e o código de saída da CLI.

Já definido: o bloqueio de governança responde com erro tipado, com código próprio e mensagem (ver "Decisões
tomadas").

### 2. Montagem de alguns serviços acoplada à CLI

As factories ficam em `main.py` e levantam `CliError`, importada do adapter da CLI. O tratamento de falha não
categorizada (`_exit_on_unexpected`), os documentos de `login` e `whoami` (`_login_document`, `_whoami_document`) e
as validações de parâmetro do `list api` (`--id` com `--query`, `--limit`, `--offset`, `--revisions` sem `--id`)
vivem em `cli_adapter.py`. A entrada REST precisaria duplicar tudo isso; o caminho é levar para um lugar neutro.

O `list api` devolve uma lista solta (`to_listing_dict`, `to_dict`), sem `schema` nem versão, diferente dos outros
comandos.

### 3. Identidade de quem chama

A CLI tem um usuário por instalação: uma credencial no `.sen` e uma sessão no arquivo `.sen_session` e as guardas leem essa sessão.

Num servidor, cada requisição tem um chamador. O `SessionStorePort` permite trocar o arquivo por uma sessão da
requisição, mas falta definir de onde ela vem. `LoginSession` precisa de perfil, grupos, escopo e validade; hoje
esses dados chegam na resposta do login. 

Sugestão: Como paliativo, receber o basic do app na requisição e a partir daí seguir com o fluxo de validação e obtenção de token via API orquestrador.

### 4. O repositório da API é lido do disco

`validate`, `publish` e `deploy` recebem `repo_path` e leem os YAML por `LocalFileImporterPort`, que trabalha com
caminhos do sistema de arquivos (`read`, `exists`, `list_directories`, `glob_files`). `RepoImporterService` resolve
caminhos com `Path.resolve()`. Nesses três fluxos o port é usado só pelo `RepoCanonicalReader`, em duas chamadas:
`glob_files`, para listar os arquivos, e `read`, que devolve o conteúdo de cada um já como dicionário.

Por REST, o conteúdo do repositório chega no corpo da requisição, como um mapa de caminho para conteúdo
(`{"files": {"api-basic-info.yaml": {...}, "resources/pedidos/get_pedidos.yaml": {...}}}`). Os caminhos são
necessários porque o layout é descoberto pelos nomes de pasta e de arquivo. Para quem chama, a requisição é a mesma
nas duas opções; o que muda é o que o servidor faz com o corpo recebido:

| Opção | O que o servidor faz com o corpo | Custo | Observação |
|---|---|---|---|
| A | Grava os arquivos numa pasta temporária do servidor e chama o serviço apontando para ela, como a CLI faz com o repositório local | Baixo | Exige sanear os caminhos e limitar o tamanho |
| B | Um novo adapter do port entrega ao serviço o conteúdo que veio no corpo, já no formato esperado pelos serviços | Baixo | Nada é gravado em disco; os caminhos servem só para a descoberta do layout |

Sugestão: B, para seguir os princípios da arquitetura hexagonal e deixar com o adapter a responsabilidade de converter para o formato esperado.

### 5. Alvos e modo vêm de variável de ambiente

As variáveis de esteira `EXECUTION_MODE`, `TARGET_REVISION_NUMBER`, `TARGET_ENVIRONMENT_ID`, `TEMPLATE_API_ID` e `HOST` são lidas de
`Settings`, uma vez por processo. Os serviços consultam `settings.pipeline_mode` e os alvos direto.

Necessária definição de como ficariam esses comandos da esteira e também como seria a passagem de parâmetro para publish, deploy e etc.

### 6. Confirmação do `validate`

Fora da esteira, o `validate` pergunta antes de gravar o rascunho. O serviço monta o texto e chama `confirm`. Se a
resposta é não, devolve um resultado sem publicação, e a CLI descarta o relatório.

Por REST não há pergunta ou confirmação, então precisará ser ajustado o fluxo para executar a ação sem confirmação nesse caso.

Atenção: fora da esteira, os avisos do repositório e da documentação aparecem só no texto da confirmação e não se
repetem no resultado. Sem a pergunta, eles precisam ir para o documento de resposta, como já acontece na esteira.

### 7. Duração e concorrência

- O `validate` faz várias chamadas ao Manager em sequência. `HttpClient` usa timeout de 30 s e repete até 3 vezes
  em 5xx, com 5 s de espera, então uma única chamada pode levar mais de 100 s no pior caso. A duração real por REST
  não foi medida. Se passar do timeout do gateway, a operação precisa virar assíncrona (`202` e consulta do
  resultado).
- A CLI roda um comando por processo. Num servidor, duas escritas na mesma revisão podem se cruzar; é preciso uma
  trava por API.
- O contexto de log é `threading.local` (`observability/logging.py`). Funciona com uma thread por requisição, não
  com handlers `async`.

### 8. Empacotamento e superfície de rede

- `pyproject.toml` não tem framework web. O servidor não deve entrar no executável do dev (PyInstaller): as
  dependências ficam num grupo opcional, com ponto de entrada próprio.
- O `Dockerfile` existe, mas atualmente não é utilizado.
- Hoje nada escuta em rede. A entrada REST traz o que a CLI não precisava: autenticação por requisição, limite de tamanho do corpo, limite de taxa e a garantia de que tokens não aparecem em resposta nem em log. 

## Rotas propostas

Proposta inicial, para discutir. A resposta de sucesso é o documento que o `-o json` já emite.

| Comando | Rota | Entrada |
|---|---|---|
| `sen whoami` | `GET /v1/session` | — |
| `sen list api` | `GET /v1/apis` | `query`, `limit`, `offset`, `all` |
| `sen list api --id` | `GET /v1/apis/{apiId}` | — |
| `sen list api --id --revisions` | `GET /v1/apis/{apiId}/revisions` | — |
| `sen completeness` | `GET /v1/apis/{apiId}/revisions/{revisionId}/completeness` | — |
| `sen validate` | `POST /v1/validations` | arquivos do repositório |
| `sen publish` | `POST /v1/publications` | arquivos do repositório, revisão alvo |
| `sen deploy` | `POST /v1/deployments` | `api-basic-info`, revisão alvo, ambiente alvo |

Fora da base analisada: `sen sync` (`feat/sen-sync`) devolveria os arquivos gerados em JSON, e o `--check` receberia
os arquivos do repositório; `sen diag` pode ficar só na CLI. `sen login` não vira rota se a credencial vier por
requisição (ver decisões).

## Sugestões

| Decisão | Definição
|---|---
| Bloqueio de governança | Responde com erro tipado, com código próprio e mensagem; não com `200` e o veredito no documento 
| De onde vem o modo esteira | Da credencial do chamador; nunca de campo da requisição 

## Decisões em aberto

| # | Decisão | Recomendação |
|---|---|---|
| 1 | Como o chamador se identifica | Paliativo: credencial Basic do app a cada requisição; o servidor faz o login e a validação na API do orquestrador e mantém a sessão só durante a requisição, sem gravar em disco. Definitivo: a decidir |
| 2 | Como será consumido (esteira, agente, portal) e onde o servidor roda | Definir antes do início pois muda o planejamento |
| 3 | Como o repositório chega | Opção B (arquivos no corpo, entregues ao serviço por um adapter, sem disco) |
| 4 | Um servidor por cliente ou Manager de destino sendo identificado via credenciais | -|
| 5 | Formato do erro | `application/problem+json` (RFC 7807), já usado no mapeamento de erro HTTP de saída, mais o campo `code` |
| 6 | YAML na entrada REST | Não: só JSON. YAML segue na CLI |

## Pontos de atenção

- Uma só regra para as duas entradas. Validação de parâmetro, mensagem e código de erro não podem existir em duas
  versões; por isso a etapa 1 vem antes do servidor.
- O documento de saída é contrato versionado. A entrada REST reusa `apiops.sen-*/v1` sem alterar campo.
- Os caminhos e o conteúdo enviados no corpo são dado não confiável: validar o formato e limitar o tamanho antes de
  entregar ao serviço.
- As mensagens de erro orientam comandos da CLI ("faça `sen login`"). Por REST, o campo `code` é o que o consumidor
  usa; o texto precisa ser revisto para não citar comando que o chamador não tem.
- Escrita em teste só na API-lab 425 (nunca 417, 400 ou ECAD), também pela entrada REST.

## Critério de resolução

- As rotas definidas respondem com o mesmo documento que o `-o json` do comando equivalente, provado por teste que
  compara as duas saídas.
- Todo erro, nas duas entradas, sai em JSON com código estável; o status HTTP e o código de saída derivam da mesma
  categoria.
- Nenhuma regra de negócio duplicada entre `adapters/inbound/cli` e `adapters/inbound/http`.
- Cada requisição roda com a identidade do próprio chamador; nenhuma sessão compartilhada em disco.
- Baterias de validate, publish e deploy verdes pela entrada REST na API-lab 425.
- O executável do dev não carrega as dependências do servidor.

## Referências

- `docs/padroes-desenvolvimento.md` — §2 (arquitetura e pastas reservadas), §4.3 (perfis de execução), §5 (erros e
  códigos de saída), §14 (`Dockerfile`)
- `docs/consumidores-projetados.md` — §4 (agente) e decisão D4
- `docs/comandos-cli.md` — contratos de saída por comando
- `docs/auth/api-orq-auth-contrato.md` e ADR 0003 — rota de validação do token
- `src/apiops_orchestrator/main.py` — montagem atual dos serviços
- `src/apiops_orchestrator/adapters/inbound/cli/cli_adapter.py` — o que hoje vive só na borda
