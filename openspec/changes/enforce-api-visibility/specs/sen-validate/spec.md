## ADDED Requirements

### Requirement: Target API must be visible to the session

Logo após o `GET /apis/{spec.id}` da E2, o comando SHALL aplicar a regra de `api-visibility` ao
objeto `visibility` da resposta, sem chamada nova. API invisível e API inexistente (`404` nesse
`GET`) MUST encerrar com `exit 1` e a mesma mensagem, "API X não encontrada ou sem permissão de
acesso. Nada foi publicado.", antes da guarda de identidade, do `GET /revisions/{id}`, da leitura da
API-template e de qualquer `PUT`. Outras recusas desse `GET` mantêm o tratamento atual.

#### Scenario: Dev valida API de grupo alheio
- **WHEN** a sessão de dev roda `sen validate` num repositório cujo `spec.id` é uma API `GROUP` de um grupo que ela não tem
- **THEN** o comando encerra com `exit 1` e a mensagem de API não encontrada, sem ler a template e sem `PUT`

#### Scenario: API inexistente
- **WHEN** o `GET /apis/{spec.id}` responde `404`, qualquer que seja o perfil da sessão
- **THEN** o comando encerra com `exit 1` e a mesma mensagem da API invisível, e não o erro interno

#### Scenario: Dev compartilhado numa API ME
- **WHEN** a API é `ME` de outro `owner` e `visibility.users[]` traz o usuário da sessão
- **THEN** o comando segue a cascata normalmente

#### Scenario: Esteira
- **WHEN** a sessão é de super admin
- **THEN** a verificação não recusa nenhuma API
