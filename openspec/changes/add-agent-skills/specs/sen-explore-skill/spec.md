## Purpose

Orientar o agente LLM a responder perguntas sobre o que está no Manager usando a CLI `sen`, sem alterar nada.

## ADDED Requirements

### Requirement: Acionada por perguntas sobre o Manager

A skill SHALL ser acionada por perguntas sobre APIs, revisões, ambientes, régua e Draft no Manager. Ela SHALL NOT ser acionada por perguntas sobre o conteúdo dos arquivos do repositório local, nem por pedidos de mudança em arquivos, validação, publicação, deploy ou login.

#### Scenario: Pergunta sobre revisões
- **WHEN** o usuário pede "me mostra as revisões da API 425"
- **THEN** a skill é acionada

#### Scenario: Pergunta sobre o repositório
- **WHEN** o usuário pergunta "pra qual backend vai cada rota dessa API?" dentro de um repositório de API
- **THEN** a skill não é acionada

#### Scenario: Pedido de mudança
- **WHEN** o usuário pede "muda o timeout do recurso token pra 30 segundos"
- **THEN** a skill não é acionada

### Requirement: Só leitura

A skill SHALL rodar apenas comandos que não alteram nada: `sen list api`, `sen schema`, `sen diag structure`, `sen diag draft` e `sen diag template`, e outro comando só se a ajuda do `sen` mostrar que ele só lê. Ela SHALL NOT rodar `sen validate`, `sen publish`, `sen deploy` nem `sen login`, SHALL NOT editar arquivos e SHALL NOT chamar a API do Manager por fora da CLI.

#### Scenario: Pergunta que levaria a uma gravação
- **WHEN** o usuário pergunta "o repositório está conforme a régua?"
- **THEN** a skill não roda o `sen validate`, explica que a conformidade exige gravar na Draft e passa o pedido para a `sen-api-developer`; sem ela instalada, diz ao usuário que ele mesmo pode rodar o `sen validate`

### Requirement: Completude e governança fora da skill

Completude e governança dependem do Adaptive Governance, que nem todo cliente tem. A skill SHALL NOT rodar `sen completeness`. Ela MAY mostrar `completeness_score` e `stage_name` quando o `sen list api --revisions` os trouxer, e SHALL NOT falar deles quando vierem nulos. A perguntas sobre o mínimo exigido, as sugestões de melhoria ou como subir a nota, SHALL responder que não são desta skill.

#### Scenario: Pedido para subir a completude
- **WHEN** o usuário pede "vê a nota dessa API e sobe a completude pra 70%"
- **THEN** a skill não roda o `sen completeness`, diz que completude e governança não são desta skill e não edita arquivos

#### Scenario: Revisões sem Adaptive Governance
- **WHEN** o `sen list api --revisions` devolve `completeness_score` e `stage_name` nulos
- **THEN** a resposta traz as revisões e os ambientes, sem falar de completude nem de estágio

### Requirement: Saída estruturada e sem interação

A skill SHALL ler os dados com `-o json` e SHALL NOT rodar comando que espere resposta no terminal.

#### Scenario: Consulta de revisões
- **WHEN** a skill consulta as revisões de uma API
- **THEN** ela roda `sen list api --id <id> --revisions -o json` e interpreta o JSON

### Requirement: Descobre os IDs pela CLI

Quando a pergunta exige um ID que o usuário não deu, a skill SHALL descobri-lo encadeando comandos da CLI. Ela SHALL perguntar ao usuário só quando a busca devolver mais de um candidato ou nenhum.

#### Scenario: Ambientes da última revisão
- **WHEN** o usuário pergunta "em que ambientes está a última revisão da API 425?"
- **THEN** a skill roda `sen list api --id 425 --revisions -o json` e responde com os `environments` da revisão de maior número

#### Scenario: Nome com mais de uma API
- **WHEN** o usuário pergunta pela API "Auth" e o `sen list api --query Auth` devolve três APIs
- **THEN** a skill lista as três, com ID, versão e base path, e pergunta qual delas

### Requirement: Resposta interpretada

A skill SHALL responder com os dados pedidos, os IDs usados e, quando houver, o próximo comando útil. Ela SHALL NOT colar o JSON bruto, a menos que o usuário peça.

#### Scenario: Revisões de uma API
- **WHEN** o usuário pergunta pelas revisões de uma API
- **THEN** a resposta traz o número, o REV ID e os ambientes de cada revisão, sem o JSON bruto

### Requirement: Aviso antes de muitas consultas

Quando responder exigir mais de 10 chamadas à CLI, a skill SHALL dizer ao usuário quantas chamadas fará e SHALL esperar o ok antes de começar.

#### Scenario: Ambientes de todas as APIs
- **WHEN** o usuário pergunta "em que ambientes está a última revisão de cada API?" e o Manager tem 40 APIs visíveis
- **THEN** a skill informa que fará uma consulta por API e espera o ok do usuário

### Requirement: Sessão e credenciais

A skill SHALL NOT ler o `.sen` nem o `.sen_session` e SHALL NOT pedir credenciais. Quando a CLI recusar por falta de sessão ou sessão expirada, a skill SHALL orientar o usuário a rodar `sen login` ele mesmo e SHALL parar.

#### Scenario: Sessão expirada
- **WHEN** o `sen list api` termina com erro de sessão expirada
- **THEN** a skill pede ao usuário que rode `sen login` e não tenta outro caminho

### Requirement: Rotas no Manager

Para as rotas de uma API no Manager, a skill SHALL usar o `sen diag draft` dentro do repositório da API e SHALL dizer que são as rotas da Draft. Fora do repositório da API, ou para uma revisão publicada, SHALL dizer que o `sen` não mostra isso hoje.

#### Scenario: Draft contra repositório
- **WHEN** o usuário pergunta "a Draft tem as mesmas rotas do repositório?"
- **THEN** a skill compara as rotas do `sen diag draft` com as do `sen diag structure` e diz o que está só de um lado

#### Scenario: Rotas de uma API no Manager
- **WHEN** o usuário pergunta "quais rotas a API 425 tem no Manager?" fora do repositório dela
- **THEN** a skill diz que o `sen` não mostra as rotas de uma API no Manager hoje e não chama a API do Manager por outro caminho

### Requirement: CLI com o comando de schema

A skill SHALL conferir que o `sen` instalado tem o `sen schema`. Se não tiver, SHALL orientar o usuário a atualizar o `sen`, sem tentar contornar.

#### Scenario: Versão antiga
- **WHEN** o `sen schema --help` termina com erro de comando inexistente
- **THEN** a skill diz que o `sen` instalado está desatualizado e orienta a atualização
