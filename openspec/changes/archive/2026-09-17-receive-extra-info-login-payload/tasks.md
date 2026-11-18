## 1. Modelo de domÃ­nio

- [x] 1.1 Estender `LoginSession` com `profile` (literal `developer`/`super-admin`), `scope`, campos condicionais (`username`, `user_email`, `user_groups`, `admin_access_token`) e propriedade `is_super_admin`
- [x] 1.2 Adicionar guarda de consistÃªncia no modelo (dev exige username/email/groups; super-admin exige `admin_access_token`; combinaÃ§Ã£o impossÃ­vel vira erro de modelo)

## 2. Service de login (validaÃ§Ã£o por perfil)

- [x] 2.1 Definir `PROFILE_REQUIRED_FIELDS` (matriz por perfil) e extrair nÃºcleo comum (`access_token`, `token_type` Bearer, `expires_in`, `extra_info` dict, `profile` reconhecido) no `_parse_response`
- [x] 2.2 Iterar campos obrigatÃ³rios do perfil sobre `extra_info`, elevando `LoginProtocolError` com mensagem genÃ©rica e detalhe completo apenas em log interno
- [x] 2.3 Incluir `scope` (obrigatÃ³rio para ambos os perfis) na validaÃ§Ã£o e popular o `LoginSession` a partir do envelope
- [x] 2.4 Atualizar `REQUIRED_SESSION_FIELDS` para o novo nÃºcleo (remover `user_groups`/`user_email`/`username` do nÃ­vel de topo)

## 3. PersistÃªncia (store)

- [x] 3.1 Serializar `model_dump(exclude={"admin_access_token"})` quando perfil `super-admin` â€” nunca gravar o token privilegiado
- [x] 3.2 No load, tratar sessÃ£o sem `profile`, com perfil desconhecido ou sem `admin_access_token` (super-admin) como estado vÃ¡lido/pausÃ¡vel conforme regra: legado/perfil desconhecido â‡’ tratada como ausente; admin token ausente â‡’ sessÃ£o carrega, token indisponÃ­vel

## 4. Display (CLI)

- [x] 4.1 Resumo por perfil: `developer` â†’ username/e-mail/expiraÃ§Ã£o (grupos ocultos); `super-admin` â†’ perfil/escopo; nenhum token (`admin_access_token` incluso) em stdout/stderr/logs

## 5. Testes

- [x] 5.1 Fixtures de contrato: payload dev completo, payload super-admin completo, variaÃ§Ãµes quebradas (sem `extra_info`, sem `profile`, perfil desconhecido, campo faltando por perfil, `user_groups` vazio, `token_type` invÃ¡lido)
- [x] 5.2 Unit service: matriz por perfil dispara os cenÃ¡rios do delta; mensagens genÃ©ricas com detalhe sÃ³ no log
- [x] 5.3 Unit store: save omite `admin_access_token`; load legÃ­timo (com e sem admin token) + sessÃ£o legada tratada como ausente
- [x] 5.4 Unit display: resumos por perfil sem valores de token

## 6. ConsistÃªncia e fechamento

- [x] 6.1 Atualizar fixtures/testes existentes de login que assumem formato flat antigo
- [x] 6.2 Rodar `npx openspec validate receive-extra-info-login-payload` e a suite de testes (lint/typecheck inclusos)
- [x] 6.3 Registrar no CHANGELOG a nota de BREAKING (payload flat â†’ `extra_info`)
