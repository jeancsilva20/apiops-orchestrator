## Purpose

Orientar o agente LLM a responder sobre os arquivos do repositório da API e a alterá-los no formato que a CLI `sen` aceita, com a confirmação do usuário antes de uma mudança com risco e antes de gravar na Draft do Manager.

## ADDED Requirements

### Requirement: Acionada por perguntas e mudanças no repositório

A skill SHALL ser acionada por perguntas sobre o conteúdo dos arquivos do repositório da API e por pedidos de mudança neles: dados da API, rotas, responses, request bodies, parâmetros, timeout, backend, interceptors, apiTags e componentes. Ela SHALL NOT ser acionada por perguntas que dependem do Manager (APIs, revisões, ambientes, completude, régua, Draft), nem por publicação, deploy ou login.

#### Scenario: Mudança de response
- **WHEN** o usuário pede "edita o response de sucesso do GET /users/{username} pra retornar username, nome e email"
- **THEN** a skill é acionada

#### Scenario: Pergunta sobre o repositório
- **WHEN** o usuário pergunta "quais rotas essa API tem?" dentro de um repositório de API
- **THEN** a skill é acionada e responde sem escrever

#### Scenario: Pergunta sobre o Manager
- **WHEN** o usuário pergunta "qual a nota da última revisão da API 425?"
- **THEN** a skill não é acionada

#### Scenario: API nova
- **WHEN** o usuário pede para criar uma API do zero
- **THEN** a skill diz que ainda não cobre a criação, porque o `sen validate` só trabalha com uma API que já existe no Manager, e para sem escrever

### Requirement: Schema antes de escrever

Antes de criar ou alterar um arquivo, a skill SHALL ler o `sen schema <tipo>` do tipo desse arquivo, e o arquivo escrito SHALL passar nesse schema.

#### Scenario: Rota nova
- **WHEN** a skill vai criar um arquivo de operação
- **THEN** ela roda `sen schema operation` antes de escrever, e o arquivo criado passa no schema

### Requirement: Plano e confirmação antes de mudança com risco

Antes de escrever uma mudança com algum dos riscos do requisito "Riscos nomeados no plano", a skill SHALL apresentar o plano: os arquivos que cria ou altera, o que muda em cada um e os riscos. Ela SHALL escrever só depois do ok do usuário. Uma mudança sem risco, com alvo identificado e com tudo o que ela precisa no pedido ou nos arquivos, a skill MAY aplicar direto e SHALL mostrar no resumo o que mudou.

#### Scenario: Mudança sem risco
- **WHEN** o usuário pede "aumenta o timeout do GET /users/{username} pra 30 segundos"
- **THEN** a skill altera só o timeout da rota e mostra no resumo o que mudou, sem esperar um ok

#### Scenario: Usuário pede para ver sempre o plano
- **WHEN** o usuário pediu para ver o plano antes de toda mudança e depois pede uma mudança sem risco
- **THEN** a skill mostra o plano e espera o ok antes de escrever

#### Scenario: Usuário confirma
- **WHEN** a skill apresenta o plano de uma mudança com risco e o usuário confirma
- **THEN** a skill aplica exatamente o que o plano descreveu

#### Scenario: Usuário recusa
- **WHEN** a skill apresenta o plano de uma mudança com risco e o usuário recusa
- **THEN** nenhum arquivo do repositório muda

### Requirement: Informação faltando

Quando o pedido e os arquivos não trazem tudo o que a mudança precisa, a skill SHALL perguntar em vez de supor, porque um valor suposto vira contrato.

#### Scenario: Rota nova sem backend
- **WHEN** o usuário pede "adiciona a rota GET /users/{username}/roles", sem dizer o backend nem o response
- **THEN** a skill pergunta o backend e o response antes de criar o arquivo, sem copiar um valor suposto para o contrato

### Requirement: Riscos nomeados no plano

O plano SHALL nomear cada risco presente: componente usado por outras rotas, `inherit: false` (a rota deixa de executar o fluxo herdado), remoção de conteúdo (rota, response, apiTags com lista vazia) e campo cuja alteração não é publicada (`apiResponsible`).

#### Scenario: Rota deixa de herdar
- **WHEN** a mudança põe `inherit: false` numa rota
- **THEN** o plano lista os interceptors herdados que deixam de executar e os que a rota passa a declarar

### Requirement: Identidade da API intocada

A skill SHALL NOT alterar o `id`, a `version` nem o `basePath` do `api-basic-info.yaml`, porque o `sen validate` aborta quando eles divergem do Manager. Diante de um pedido assim, SHALL explicar que a mudança é feita no Manager.

#### Scenario: Pedido de nova versão
- **WHEN** o usuário pede "muda a versão da API pra 2.0"
- **THEN** a skill não altera o arquivo e explica que versão e base path vêm do Manager

### Requirement: Componente compartilhado

Quando a mudança atinge um componente do `components.yaml` referenciado por outras rotas, a skill SHALL listar essas rotas e SHALL perguntar se a mudança vale para todas ou se cria um componente novo só para a rota pedida.

#### Scenario: Schema usado por duas rotas
- **WHEN** o usuário pede para mudar o response de sucesso de uma rota cujo schema é `$ref` para um componente usado por outra rota
- **THEN** a skill nomeia a outra rota e pergunta entre mudar o componente ou criar um novo

### Requirement: Alvo ambíguo

Quando a rota, o recurso ou o código de response não estiver identificado sem ambiguidade, a skill SHALL listar os candidatos e perguntar, em vez de escolher.

#### Scenario: Dois códigos de sucesso
- **WHEN** o usuário pede para editar o response de sucesso e a rota declara 200 e 201
- **THEN** a skill pergunta qual dos dois editar

### Requirement: Mudança mínima

A skill SHALL alterar só o que o pedido exige e SHALL manter o resto de cada arquivo como estava, inclusive os outros códigos de response, as descrições e os comentários.

#### Scenario: Response de sucesso
- **WHEN** a skill troca o schema do response 200 de uma rota que também declara 401
- **THEN** o 401 e a `description` do 200 continuam iguais

### Requirement: Estrutura informada pelo usuário

Quando o usuário informar uma estrutura (payload de exemplo, lista de campos ou classe), a skill SHALL convertê-la em schema OpenAPI com os tipos inferidos. SHALL marcar como obrigatórios só os campos que o usuário indicar, e SHALL manter o payload informado como `example`.

#### Scenario: Payload de exemplo
- **WHEN** o usuário informa o payload `{"username": "ana", "ativo": true}` para o response
- **THEN** o schema escrito tem `username` string e `ativo` boolean, sem `required`, e o payload como `example`

### Requirement: Conferência depois de escrever

Depois de escrever, a skill SHALL rodar o `sen diag structure` e o pré-check `echo n | sen validate`, que não grava nada. Ela SHALL corrigir os erros nos arquivos que alterou e repetir até passar, ou relatar o que não conseguiu corrigir. Sem sessão, SHALL dizer que o pré-check não rodou e por quê.

#### Scenario: Pré-check acusa erro
- **WHEN** o pré-check recusa um campo que a skill escreveu
- **THEN** a skill corrige o arquivo e roda o pré-check de novo

#### Scenario: Sem sessão
- **WHEN** o pré-check termina com erro de sessão
- **THEN** a skill informa que só a conferência local rodou e orienta o usuário a fazer `sen login` para o pré-check

### Requirement: Gravação na Draft só com confirmação

A skill SHALL rodar o `sen validate` que grava na Draft só quando o usuário pedir. Antes, SHALL explicar que a gravação vai para a revisão alvo no Manager da sessão aberta, que o conteúdo dessa Draft passa a refletir o repositório e que nada recebe deploy, e SHALL esperar a confirmação.

Depois da gravação, a skill SHALL resumir a conformidade com a régua e, só quando vierem no resultado, a governança e a completude, que dependem do Adaptive Governance.

#### Scenario: Sem Adaptive Governance
- **WHEN** o resultado da gravação não traz governança nem completude
- **THEN** o resumo traz a conformidade com a régua e não fala das duas

#### Scenario: Usuário pede a validação completa
- **WHEN** o usuário pede "valida de verdade e me mostra o veredito"
- **THEN** a skill mostra a revisão alvo e os riscos, espera a confirmação e só então roda o `sen validate` respondendo sim

#### Scenario: Sem pedido explícito
- **WHEN** o usuário não pediu a gravação
- **THEN** a skill para no pré-check e indica o `sen validate` como próximo passo

### Requirement: Comandos e arquivos proibidos

A skill SHALL NOT rodar `sen publish`, `sen deploy` nem `sen login`, e SHALL NOT ler o `.sen` nem o `.sen_session`. Ela SHALL conferir que o `sen` instalado tem o `sen schema` e, se não tiver, SHALL orientar a atualização.

#### Scenario: Pedido de publicação
- **WHEN** o usuário pede "publica essa mudança em produção"
- **THEN** a skill explica que publicação e deploy rodam só na esteira e não executa nenhum dos dois

### Requirement: Respostas pelo repositório

A skill SHALL responder perguntas e ler o estado atual da API pelos arquivos do repositório, sem consultar o Manager, e SHALL dizer ao usuário que os dados vêm do repositório. Quando a resposta depender de um campo, ela SHALL se basear no `sen schema` do tipo de arquivo. Uma pergunta SHALL NOT virar mudança: a skill pode sugerir uma mudança, mas só entra no ciclo de mudança se o usuário pedir.

#### Scenario: Rotas e backends
- **WHEN** o usuário pergunta "quais rotas essa API tem e pra qual backend cada uma vai?" dentro de um repositório de API
- **THEN** a skill lista cada rota com método, path e URL de backend efetiva, inclusive as herdadas do recurso ou do `all.yaml`, sem chamada de rede, diz que os dados vêm do repositório local e não altera nenhum arquivo

#### Scenario: Consulta seguida de mudança
- **WHEN** o usuário pede "vê o timeout do recurso token e aumenta pra 30"
- **THEN** a skill informa o timeout que está no repositório, sem consultar o Manager, e segue o ciclo de mudança

### Requirement: Pedido sem comando

A skill SHALL preferir os comandos que cita. Se o pedido precisar de algo que eles não cobrem, SHALL conferir a ajuda do `sen` e, sem comando que atenda, SHALL dizer ao usuário que o `sen` não faz isso hoje e parar. Um comando achado na ajuda que grava algo SHALL rodar só depois de perguntar ao usuário. A skill SHALL NOT chamar a API do Manager por fora da CLI.

#### Scenario: Cadastro de app
- **WHEN** o usuário pede "cadastra um app pra consumir essa API"
- **THEN** a skill confere a ajuda do `sen`, diz que o `sen` não faz isso hoje e não escreve nada nem chama a API do Manager
