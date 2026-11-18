## ADDED Requirements

### Requirement: Single visibility rule for the session

A visibilidade de uma API para a sessão SHALL ser decidida por uma regra única, a mesma em todos os
comandos: `ORGANIZATION` é visível para todos; `ME`, para o `owner` e para os usuários da
visibilidade; `GROUP`, só para quem tem o grupo — `owner` e usuários não influem; tipo ausente ou
desconhecido, para ninguém. Comparações de usuário e de grupo SHALL ignorar espaços nas pontas, caixa
e acento.

#### Scenario: API de organização
- **WHEN** a API é `ORGANIZATION` e a sessão é de dev
- **THEN** a API é visível, independentemente dos grupos da sessão

#### Scenario: API ME do próprio usuário
- **WHEN** a API é `ME` e o `owner` é o usuário da sessão
- **THEN** a API é visível

#### Scenario: API ME compartilhada com o usuário
- **WHEN** a API é `ME`, o `owner` é outro usuário e o usuário da sessão está entre os usuários da visibilidade
- **THEN** a API é visível

#### Scenario: API ME de outro usuário
- **WHEN** a API é `ME`, o `owner` é outro usuário e o usuário da sessão não está entre os usuários da visibilidade
- **THEN** a API não é visível

#### Scenario: API de grupo da sessão
- **WHEN** a API é `GROUP` com grupo `APIOps` e a sessão tem o grupo ` apiops `
- **THEN** a API é visível

#### Scenario: API de grupo alheio
- **WHEN** a API é `GROUP` com um grupo que a sessão não tem, mesmo sendo o usuário o `owner`
- **THEN** a API não é visível

#### Scenario: Tipo desconhecido
- **WHEN** a visibilidade está ausente ou tem tipo fora de `ORGANIZATION`/`ME`/`GROUP`
- **THEN** a API não é visível para sessão de dev

### Requirement: Super admin sees every API

A sessão de super admin SHALL enxergar todas as APIs, qualquer que seja o tipo de visibilidade e o
modo de execução. A regra depende do perfil da sessão, não do `EXECUTION_MODE`.

#### Scenario: Esteira
- **WHEN** a sessão é de super admin e a API é `GROUP` de um grupo que ela não tem
- **THEN** a API é visível

#### Scenario: Tipo desconhecido para super admin
- **WHEN** a sessão é de super admin e a visibilidade da API está ausente
- **THEN** a API é visível

### Requirement: Both platform sources yield the same visibility

A regra SHALL aceitar a visibilidade nos dois formatos em que a plataforma a entrega, normalizados no
mesmo objeto de domínio:

| Fonte | Tipo | Owner | Grupo | Usuários |
|---|---|---|---|---|
| catálogo (api-finder) | `contextType` | `owner` | `contextGroupName` | `contextUserLogins` |
| `GET /apis/{id}` | `visibility.visibilityType` | `visibility.owner` | `visibility.groupVisibility.name` | `visibility.users[].username` |

#### Scenario: Mesma API nas duas fontes
- **WHEN** a mesma API é lida pelo catálogo e pelo `GET /apis/{id}`
- **THEN** a decisão de visibilidade para a sessão é a mesma

#### Scenario: Payload sem visibilidade
- **WHEN** o `GET /apis/{id}` não traz `visibility`
- **THEN** o tipo é considerado ausente e a API não é visível para sessão de dev

### Requirement: Invisible API answers like a missing one

Todo comando que recebe o id de uma API SHALL aplicar a regra logo após a primeira leitura da API e
antes de qualquer outra chamada sobre ela. API invisível MUST receber a mesma mensagem e o mesmo exit
code que o comando usa para API inexistente, e a saída MUST NOT conter nome, versão, revisões,
completeness ou qualquer outro dado dela. A verificação MUST NOT ser delegada ao servidor: o token das
chamadas administrativas é de super admin.

#### Scenario: Mensagem igual à de API inexistente
- **WHEN** a sessão de dev roda o mesmo comando com o id de uma API invisível e com um id que não existe
- **THEN** as duas saídas têm o mesmo texto, exceto o id, e o mesmo exit code

#### Scenario: Nenhuma chamada além da leitura da API
- **WHEN** a API é invisível para a sessão
- **THEN** nenhuma chamada sobre revisões, completeness, workflows ou escrita é feita
