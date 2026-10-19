## Why

Na fase 1 a sessão do `sen login` fica no diretório temporário do SO — invisível ao dia a dia do dev. Ficou acordado mover o arquivo para a **raiz do projeto**, tornando-o visível/governável junto ao repositório em uso. A decisão contraria deliberadamente parte do ADR 0002 (storage em temp): os riscos então identificados (vazamento por Git/sync/backup, esteira, multiusuário, `git clean`, scanners) SHALL ser formalmente registrados em ADR próprio com suas mitigações, e o armazenamento acompanha o projeto onde o dev opera.

## What Changes

- Local da sessão passa a ser a **raiz do projeto** (derivada do código, `PROJECT_ROOT` — funciona com o Python rodando de qualquer CWD), permanecendo **arquivo oculto** (`.sen_session`), atômico e com permissões de dono.
- **Imutável** desta mudança: todos os demais comportamentos (conteúdo, `expires_at`, leitura com expiração, substituição, sigilosidade, exit codes 5).
- **Guard-rail de versionamento**: inclusão de `.sen_session*` no `.gitignore` (impede commit/scan do token por Git) — fronteira garantida por spec, já que o arquivo passa a conviver com a árvore do repo.
- **Riscos documentados** em novo ADR (0006) supersedendo o aspecto de storage do ADR 0002, com matriz risco × mitigação; `docs/features/sen-login.md` e backlog atualizados.

## Capabilities

### New Capabilities
<!-- Nenhuma: mudança dentro da capability existente cli-auth. -->
- (nenhuma)

### Modified Capabilities
- `cli-auth`: (1) **MODIFIED** — "Sessão persistida em arquivo e legível por execuções posteriores": local passa de "diretório temporário do SO" para "raiz do projeto" (cénarios revisados na íntegra no delta); (2) **ADDED** — "Sessão excluída do rastreamento de versionamento" (`.gitignore` cobre o arquivo e variantes provisórias).

## Impact

- **Código**: composition root (`main.py`) passa o diretório ao `SessionStore` (que já aceita `directory` — nenhum comportamento do store muda); um caso de teste ajustado para refletir o novo default injetado.
- **Versionamento**: `.gitignore` recebe o padrão `.sen_session*`; exigência de que devrasters novo/repositórios existentes mantenham a entrada.
- **Arquivo legado**: o `%TEMP%/.sen_session` pré-existente torna-se órfão (inofensivo, limpeza natural do SO; sem migração necessária — o `sen login` seguinte grava na raiz).
- **Esteira**: sem consumo atual do `sen login`; risco de artefatos publicando a sessão fica registrado no ADR como atenção (hoje `artifacts: test-results/**`).
- **Docs**: novo ADR 0006; atualização de README/docs/features/backlog.
