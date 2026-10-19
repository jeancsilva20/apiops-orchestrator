## Why

A rota `POST /orq-auth/v1/oauth2/token` da Orchestrator Auth API foi ajustada no lado da plataforma e passará a devolver os dados de identidade embutidos em um envelope `extra_info`, com dois perfis distintos — `developer` (user_name, user_email, user_groups, scope) e `super-admin` (source, profile, scope, admin_access_token). O `sen login` atual espera os campos antigos no topo do JSON (`username`, `user_email`, `user_groups`) e não conhece `profile` nem `scope`: sem adaptar, todo login quebra. Precisamos agora porque o payload novo entra em vigor na rota e a credencial super-admin passará a alimentar a esteira.

## What Changes

- **BREAKING** Parse da resposta de login migrado do formato flat antigo para o envelope `extra_info`, com discriminação de perfil pelo campo `extra_info.profile` (`developer` | `super-admin`).
- Validação do payload **por perfil** no `LoginService`: matriz de campos obrigatórios distintos para dev (user_name, user_email, user_groups não-vazio, scope) e super-admin (scope, admin_access_token); núcleo comum exigido em ambos (access_token, token_type Bearer, expires_in, extra_info presente, profile válido).
- `LoginSession` atualizado para incluir `profile` e `scope`, com campos condicionais por perfil; nenhuma sessão é gerada sem perfil conhecido.
- `scope` passa a ser **persistido** no arquivo de sessão para ambos os perfis; `admin_access_token` fica **apenas em memória** durante a execução corrente (esteira efêmera) e NÃO é gravado em disco.
- Resumo de sucesso do `sen login` ciente de perfil: dev mostra username/e-mail/expiração (grupos continuam ocultos); super-admin mostra perfil/escopo; nenhum token — muito menos `admin_access_token` — é exibido.
- Erros de payload ausentes/tipo incompatível continuam categorizados (`LoginProtocolError`) com mensagem genérica ao usuário, detalhes apenas em log interno.

## Capabilities

### New Capabilities
- (nenhuma)

### Modified Capabilities
- `cli-auth`: as requirements "Comando `sen login`" (resumo por perfil sem vazamento do admin token) e "Sessão persistida em arquivo e legível por execuções posteriores" (nova composição de campos com `profile`/`scope` e exclusão do `admin_access_token` do disco) são alteradas; é adicionada a requirement "Validação por perfil do payload de login" (perfil obrigatório, matriz de campos obrigatórios por perfil, falha tipada com mensagem genérica).

## Impact

- **Código**: `application/services/login_service.py` (matriz de validação por perfil em `_parse_response`); `domain/models/login_session_model.py` (novos campos/perfil); `infrastructure/secure_storage/session_store.py` (serialização omite `admin_access_token`); `adapters/inbound/cli` (resumo por perfil). O adapter HTTP de auth não muda (continua devolvendo o dict bruto).
- **Compatibilidade**: **BREAKING** frente à rota antiga — respostas sem `extra_info.profile` passam a ser rejeitadas (falha antes de escrever sessão). Execuções subsequentes que lerem sessão sem `profile` tratam-na como ausente (re-login natural).
- **Segurança**: `admin_access_token` de alto privilégio viva só em memória; `.gitignore` já cobre o arquivo de sessão — sem novas superfícies de vazamento.
- **Esteira**: login super-admin passa a executar ponta a ponta (fluxo único in-process), alinhado ao ADR 0002 (ciclo de vida dev × super admin).
- **Dependências**: nenhuma nova; testes existentes de login/persistência recebem fixtures atualizadas.
