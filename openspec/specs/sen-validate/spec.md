# sen-validate Specification

## Purpose
TBD - created by archiving change handle-manager-rejections-in-validate-publish. Update Purpose after archive.

## Requirements

### Requirement: Recusa da gravação do rascunho

Quando o Manager recusar o `PUT` do rascunho na E3, o comando SHALL encerrar sem conferência pós-publicação, com a mensagem terminando em "Nada foi publicado.". O `412` do Adaptive Governance SHALL sair com `exit 3`; as demais recusas, com `exit 1`. Recusas de conteúdo (`400`, `409`, `412`, `422`) SHALL exibir o motivo da plataforma; `401`/`403` SHALL orientar `sen login`; as demais, ou sem motivo, SHALL usar a mensagem padrão de erro interno.

#### Scenario: Governança bloqueia só no PUT
- **WHEN** o pré-check libera, mas o `PUT` responde `412` com `messages: ["API must contain attribute My new"]` e `path` `/api-governance/api/v3/workflows/500/validate`
- **THEN** o comando exibe o bloqueio de governança com o motivo `API must contain attribute My new` e o `workflow 500`, e encerra com `exit 3`

#### Scenario: Recusa de validação mostra o motivo
- **WHEN** o `PUT` responde `422` com o motivo `basePath must start with /`
- **THEN** o comando exibe "O Manager recusou a gravação do rascunho" com esse motivo e encerra com `exit 1`

#### Scenario: Sessão expirada no PUT
- **WHEN** o `PUT` responde `401`
- **THEN** o comando orienta `sen login`, informa que nada foi publicado e encerra com `exit 1`

#### Scenario: Recusa sem motivo útil
- **WHEN** o `PUT` responde `413` ou `429`
- **THEN** o comando exibe a mensagem padrão de erro interno, sem o texto da plataforma nem o status, e encerra com `exit 1`

### Requirement: Motivo da recusa lido do envelope como evidência

O motivo SHALL ser lido do envelope de erro, incluindo o JSON serializado em `errors[].message`; se o segundo parse falhar, o texto cru SHALL ser mantido. No bloqueio detectado só no `PUT`, o faltante MUST NOT ser extraído de `messages[]`: o motivo é exibido literalmente e o envelope original acompanha o erro. Status, título e código HTTP crus MUST NOT aparecer na saída.

#### Scenario: JSON aninhado no envelope
- **WHEN** `errors[].message` contém `{"messages":["API must contain attribute My new"], ...}` serializado
- **THEN** o motivo exibido é `API must contain attribute My new`, e o erro de bloqueio carrega o envelope original

#### Scenario: Segundo parse falha
- **WHEN** `errors[].message` contém texto que não é JSON válido
- **THEN** esse texto é exibido como motivo, sem descartar a recusa

### Requirement: Pré-check confere as tags declaradas em apiTags

Antes de qualquer escrita, o pré-check SHALL comparar cada tag de `apiTags` com a lista de tags do atributo no catálogo do Adaptive Governance. Uma tag fora da lista SHALL abortar o comando com `exit 1`, nomeando a tag, o atributo e as tags válidas. Um atributo com tags cadastradas e declarado sem nenhuma tag SHALL contar como ausente no cálculo do faltante. Avisos do pré-check SHALL aparecer na saída como achados `WARNING`.

#### Scenario: Tag que não pertence ao atributo
- **WHEN** o repositório declara `My new` com a tag `TagInexistente` e o catálogo lista `Tag1` e `Tag2`
- **THEN** o comando aborta com `exit 1`, cita `TagInexistente`, `My new` e as tags válidas, e nenhum `PUT` é emitido

#### Scenario: Atributo obrigatório sem tag
- **WHEN** o stage exige `My new` e o repositório o declara com `tags: []`
- **THEN** o pré-check calcula `My new` como faltante e o comando aborta com `exit 3`, sem emitir `PUT`

#### Scenario: Atributo sem tags cadastradas
- **WHEN** o catálogo não lista nenhuma tag para o atributo declarado
- **THEN** a presença do atributo basta e nenhuma tag é recusada

### Requirement: Conferência pós-publicação inclui o basic info

A conferência após o `PUT` SHALL comparar também o objeto `api` aninhado: `name`, `description` e, quando enviadas, as `apiTags` (por atributo e conjunto de tags, sem depender da ordem). Qualquer diferença SHALL ser divergência de publicação, com `exit 1`.

#### Scenario: Plataforma apaga as apiTags sob 200
- **WHEN** o `PUT` responde `200` e a releitura mostra `apiTags: []`, embora `My new` e `teste giroto` tenham sido enviados
- **THEN** o comando reporta divergência citando os atributos ausentes e encerra com `exit 1`

#### Scenario: apiTags ausentes no repositório
- **WHEN** o `api-basic-info.yaml` não declara `apiTags`
- **THEN** as `apiTags` do Manager não entram na conferência
