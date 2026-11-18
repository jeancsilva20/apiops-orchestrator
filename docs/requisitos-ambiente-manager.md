---
id: apiops.requisitos-ambiente-manager
type: knowledge
status: in_review
authority: proposal
owner: team-apiops
title: Requisitos de Ambiente no API Manager para o APIOps
last_verified: 2026-10-29
related:
  - apiops.autenticacao
  - apiops.mapeamento
  - apiops.ag-completeness
supersedes: []
---

# Requisitos de Ambiente no API Manager para o APIOps

> **Rascunho.** Consolida o que precisa existir no Manager do cliente para o APIOps funcionar. Depois de validado, entra no memory bank (`arquitetura-apiops-memory-bank`).

Os requisitos estão em três níveis:

1. **Ambiente:** feito uma vez por cliente.
2. **API:** feito para cada API que entra no APIOps.
3. **Usuário:** feito para cada pessoa que vai usar a CLI `sen`.

---

## 1. Requisitos do ambiente

O ambiente do cliente precisa estar no **API Manager v5**.

### 1.1 API Orchestrator OAuth publicada e deployada

O orquestrador autentica os usuários por essa API. A fonte é [`orchestrator_oauth_api.yaml`](../orchestrator_oauth_api.yaml), e os interceptors vêm junto na importação.

| Item | Valor |
|---|---|
| Título | `Orchestrator Auth API` |
| basePath | `/orq-auth/v1` |
| `POST /oauth2/token` | Login: emite o token do developer ou do super admin |
| `POST /oauth2/token/validation` | Valida o token e devolve o token de super admin |

A CLI chega na API por duas chaves do arquivo `.sen`:

- `AUTH_HOST`: host do gateway.
- `AUTH_LOGIN_PATH`: caminho completo do login, incluindo o prefixo do ambiente. Exemplo no consulting: `/cli-2/orq-auth/v1/oauth2/token`.

A rota de validação é derivada como `AUTH_LOGIN_PATH + /validation`.

#### Autenticação RFC e contrato

O YAML base usa a **autenticação RFC, padrão do ECAD**: o interceptor `Bearer Token - ECAD - RFC6750` na validação e a API de OAuth `oauth-rfc/v1/access-token` como destination do login.

A lógica de obter e validar o token pode mudar conforme a arquitetura do cliente. **O contrato da API precisa ser mantido**, senão o orquestrador deixa de funcionar:

| Rota | O orquestrador envia | O orquestrador espera |
|---|---|---|
| Login | Header `Authorization: Basic <Base64 de client_id:client_secret>` e corpo `{"grantType":"client_credentials","scope":"apis/all"}` | `access_token`, `token_type` = `bearer`, `expires_in` e um objeto `extra_info` (detalhado abaixo) |
| Validação | Header `Authorization: Bearer <access_token>` e corpo `{}` | HTTP 200 com `autorizado: true` e `extra_info.admin_access_token` |

O `extra_info` do login precisa ter:

- `profile`: `developer` ou `super-admin`.
- `scope`.
- No perfil `developer`: `user_name`, `user_email` e `user_groups` (lista não vazia).
- No perfil `super-admin`: `admin_access_token`.

Se faltar qualquer campo, o login é recusado.

#### Variáveis de ambiente

Precisam existir no ambiente do gateway onde a API está deployada.

| Variável | Valor |
|---|---|
| `platform_token_url` | `https://platform-production.sensedia.com/user-management/v1/oauth2/token` |
| `user_management_url` | `https://platform-production.sensedia.com/user-management/v1/users` |
| `basic_esteira_super_admin` | Basic de acesso às APIs do produto, usado para obter o token super admin (ver 1.3). Criado a partir do access control |
| `client_id_esteira_super_admin` | `client_id` do App da esteira (ver 1.3). Quando o login usa esse `client_id`, o perfil vira super admin |

#### API de OAuth (destination do login)

O login encaminha para a API de OAuth do gateway do cliente, que emite o access token do App. No ECAD é `https://api-prd.ecad.org.br/oauth-rfc/v1/access-token`.

- A API de OAuth precisa existir no Manager do cliente.
- Os Apps da esteira e dos usuários precisam de plano com acesso a ela (ver 1.3 e 3.1).

### 1.2 Time `APIOps`

O ambiente do cliente precisa ter um time `APIOps` (menu **Teams** do Manager). Os usuários do APIOps ficam associados a ele (ver 3.1).

A API de auth compara o nome ignorando maiúsculas e espaços nas pontas. `APIOps`, `apiops` e `ApiOps` são aceitos; `API Ops`, com espaço no meio, não.

### 1.3 Credenciais da esteira

São duas credenciais distintas.

**Token super admin para as APIs do produto**

- Criar uma credencial super admin de acesso às APIs do produto Sensedia.
- O Basic dela vai em `basic_esteira_super_admin`.
- A API de auth usa esse Basic em `platform_token_url` para obter o token super admin, que é o token com que o orquestrador opera no Manager.

**App da esteira**

- App de gateway com plano de acesso à **API de OAuth** e à **API Orchestrator OAuth**.
- O `client_id` dele vai em `client_id_esteira_super_admin`.
- A esteira faz login com `SEN_CREDENTIALS` = Base64 de `client_id:client_secret` desse App.

### 1.4 API template

**O que é.** Uma API no Manager cujo fluxo all-all contém os interceptors que as outras APIs devem seguir como padrão. Ela define só interceptors; atributos ficam com o Adaptive Governance.

**Para que serve.** O `sen validate` compara o fluxo efetivo de cada API com a template, em cada caminho (raiz, recurso e operação), já resolvendo a herança:

- Interceptor a mais que a template vira `INFO`.
- Interceptor da template ausente, removido ou alterado vira `WARNING`, indicando onde.

A comparação não bloqueia publish nem deploy; quem decide é o code review.

**Como configurar.**

1. Criar a API template no Manager do cliente.
2. Montar o fluxo all-all com os interceptors padrão. O `sen` lê sempre a **última revisão** da template.
3. Informar o id da template em dois lugares:
   - **Local:** no campo `spec.template` do `api-basic-info.yaml` de cada API. O campo é obrigatório, e vazio é erro.
   - **Esteira:** na variável `TEMPLATE_API_ID`, vinda do cofre. Se divergir do `spec.template`, a variável vence e o `sen` emite `WARNING`.

Se a template estiver inacessível, o `sen` aborta, tanto local quanto na esteira.

### 1.5 Configuração da esteira

Variáveis que o `sen` lê na esteira, injetadas pelo cofre:

| Variável | Valor |
|---|---|
| `EXECUTION_MODE` | `pipeline` |
| `SEN_CREDENTIALS` | Base64 de `client_id:client_secret` do App da esteira |
| `AUTH_HOST` / `AUTH_LOGIN_PATH` | Endereço da API Orchestrator OAuth |
| `TEMPLATE_API_ID` | Id da API template. Sem ele, a esteira falha por configuração |
| `TARGET_REVISION_NUMBER` | Número da revisão-alvo (2, 3 ou 4) conforme a branch |
| `TARGET_ENVIRONMENT_ID` | Id, no Manager, do ambiente que recebe o `sen deploy` |

---

## 2. Requisitos por API

### 2.1 Quatro revisões

| Revisão | Uso | Deploy | Branch |
|---|---|---|---|
| 1 — Draft | Só validações e rascunho (`sen validate`) | Nenhum | `feat/*` |
| 2 — DEV | Desenvolvimento | Pode estar deployada no ambiente de desenvolvimento do cliente | `develop` |
| 3 — HML | Homologação | Ambiente de homologação | `release` |
| 4 — PRD | Produção | Ambiente de produção | `main` |

O número usado é o que aparece na interface do Manager, não o id interno da revisão.

### 2.2 Stages do Adaptive Governance (se o cliente tiver AG)

| Revisão | Stage | Bloqueio |
|---|---|---|
| 1 | Draft | Nenhum, só diagnóstico |
| 2 | DEV | Nenhum, completeness informativo |
| 3 | HML | Bloqueia abaixo do mínimo |
| 4 | PRD | Bloqueia abaixo do mínimo |

O mínimo de 70% é configurado no próprio AG (`completenessRequisite`). O orquestrador não altera esse valor.

### 2.3 Contrato em OpenAPI 3.0

A API precisa estar em OpenAPI 3.0. Se estiver em Swagger 2.0, é preciso migrar antes. O extrator (`extrair_estrutura_v2.py`) já interrompe a execução em Swagger 2.0.

O requisito não vale para a API Orchestrator OAuth.

### 2.4 Visibilidade

A API precisa estar visível para quem vai trabalhar nela (ver 3.2).

---

## 3. Requisitos por usuário

### 3.1 Cadastro

1. **Usuário ativo no API Manager.** A API de auth recusa usuário com `enabled = false`.
2. **Usuário associado ao time `APIOps`.** Fora do time, a API de auth recusa o login com HTTP 403.
3. **App com nome igual ao username do usuário.** A API de auth identifica o usuário pelo `app.name`.
4. **Extra field `scope` com valor `write` no App.** Sem esse campo, o login é recusado ("App sem permissões de acesso ao API Ops").
5. **App com plano de acesso à API de OAuth e à API Orchestrator OAuth.** Sem esse plano, o `Client ID Validation` recusa o login.

O usuário configura o `.sen` com:

- `SEN_CREDENTIALS`: Base64 de `client_id:client_secret` do App.
- `AUTH_HOST` e `AUTH_LOGIN_PATH`.

### 3.2 Alcance

O usuário só enxerga e opera as APIs que já vê no Manager. A CLI aplica a mesma regra de visibilidade do Manager:

| Visibilidade da API | Quem enxerga |
|---|---|
| Organização | Todos |
| Me (privada) | O dono e os usuários listados |
| Time | Quem pertence ao time dono da API |

O super admin (esteira) enxerga tudo.
