# Proposal: store-admin-token-in-sen-session

## Why

A esteira executa `sen login` (perfil super-admin) e depois comandos (`sen list api`) **em processos subsequentes** — mas o contrato atual do `sen login` proíbe persistir o `adminAccessToken`: o token privilegiado vive apenas em memória da execução do login e morre com o processo. Consequência prática: cada comando posterior precisaria refazer a emissão administrativa (hoje, via `ADMIN_SEN_CREDENTIALS`), multiplicando chamadas de autenticação e mantendo uma credencial de super admin residente em arquivo (`.sen`) onde bastaria o token efêmero da sessão. Guardar o `adminAccessToken` no `.sen_session` alinha o armazenamento com o consumo real da esteira, mantendo o token dev (perfil `developer`) intocado.

## What Changes

- **BREAKING (comportamento interno, não contrato público)**: a sessão `super-admin` gravada em `.sen_session` passa a conter `adminAccessToken` (revisão do ADR 0002 no ponto de persistência — o privilégio passa a residir no arquivo de sessão com as mesmas salvaguardas da sessão: escrita atômica, permissões restritivas, exclusão do versionamento, expiração respeitada).
- Perfil `developer` **não muda**: sem `adminAccessToken` (campo inexistente para o perfil), mesma persistência atual.
- `SessionStore.save()` passa a serializar `adminAccessToken` quando a sessão é super-admin (remove o `exclude` atual); `SessionStore.load()` devolve a sessão completa para perfil super-admin.
- Rejeição sessão-malformada continua: arquivo sem `profile` ou com perfil desconhecido tratado como ausente (re-login).
- **Fora do escopo** (mudanças subsequentes/separadas): consumo do token persistido pelo `sen list` (o provider atual continua usando `ADMIN_SEN_CREDENTIALS` até a leva de integração); guard de escopo `list→read`.

## Capabilities

### New Capabilities

### Modified Capabilities
- `cli-auth`: a requirement "Sessão persistida em arquivo e legível por execuções posteriores" muda para permitir (super-admin: com token; developer: sem) e em vez de proibir explicitamente o `adminAccessToken` no arquivo — texto completo re-specificado no delta, incluindo a instrução in-place do comentário no `SessionStore` e no modelo `LoginSession`.

## Impact

- `src/apiops_orchestrator/infrastructure/secure_storage/session_store.py` — remoção do `exclude={"adminAccessToken"}` (condição por perfil super-admin preservada: perfil developer nunca tem o campo).
- `src/apiops_orchestrator/domain/models/login_session_model.py` — docstring do campo ajustada (não mais "memory only"); validação de inconsistência de perfil fica intata.
- `tests/unit/infrastructure/secure_storage/test_session_store.py` — casos novos/ajustados: super-admin persiste e recarrega com `adminAccessToken`; developer persiste sem o campo.
- `docs/adr/0002-ciclo-de-vida-de-tokens-dev-x-superadmin.md` — ganha nota de revisão (persistência da sessão super-admin em `.sen_session`, salvaguardas presentes), sem reescrever o ADR.
- Segurança: expansão do que já é persistido (sessão dev em texto claro no mesmo arquivo, mesma máquina, permissões equivalentes); nenhum novo log/eco do valor; `.gitignore` já cobre.
