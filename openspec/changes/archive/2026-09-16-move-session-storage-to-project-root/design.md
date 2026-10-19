## Context

`SessionStore` já aceita `directory` injetável (testes usam isso); a mudança é **somente na composição** (`main.py` passa `settings.PROJECT_ROOT`) — o store permanece genérico e agnóstico de configuração. Sobre a dúvida "o Python roda na src": o interpretador **não** decide a raiz pela pasta do processo — o código deriva a raiz do caminho do módulo (`config/settings.py`, 4 níveis acima = raiz do repo). Assim, executando de qualquer CWD (raiz, `src/`, ou até de outro terminal), a sessão cai sempre na **mesma raiz do projeto**, eliminando sessões duplicadas. Riscos da mudança já debatidos e aceitos: vazamento via Git/sync/backup, esteira (artefatos), `git clean -xdf`, multiusuário em pasta compartilhada, scanners de segredos — todos registrados no ADR 0006 com mitigações.

## Goals / Non-Goals

**Goals:**

- Sessão em `PROJECT_ROOT/.sen_session` com os mesmos garantias da fase 1 (oculto, atômico, dono).
- Barreira de versionamento garantida por spec: `.gitignore` com `.sen_session*`.
- Riscos formalmente documentados (ADR 0006) — requisitos do time, não opinião de design.

**Non-Goals:**

- Migração/limpeza do arquivo legado em `%TEMP%` (órfito inofensivo; SO limpa).
- Perfis diferenciados (superadmin sem persistência), CWD→HOME para credenciais (changes separadas).

## Decisions

**D1 — Injeção na composição, não no store.** `SessionStore` segue aceitando `directory`; `build_login_service_factory` passa `settings.PROJECT_ROOT`. Alternativa (store conhece `Settings`) acoplaria infraestrutura a configuração e complicaria testes. Benefício adicional: a spec pode exigir "raiz derivada da aplicação" sem mencionar classes.

**D2 — Guard-rail Git é requisito, não detalhe.** Como o arquivo deixa de viver fora da árvore, a exclusão via `.gitignore` (`​.sen_session*`) vira behaviour observável com cenários próprios (status limpo, variantes provisórias cobertas). Single line, mas com contrato.

**D3 — Tempo de vida passa a ser manual.** No temp, o SO rotacionava; na raiz, o arquivo persiste até re-login/purge. Para a V1 é aceito (tok de 12h, máquina pessoal), mitigação de revisão: `expires_at` já invalida a sessão na leitura. Evolução `~/.sen` permanece no backlog como destino preferido para a distribuição (wheel).

**D4 — Sem migração do arquivo legado.** `%TEMP%/.sen_session` antigo é abandonado; `sen login` seguinte grava na raiz. `git clean -xdf` e limpezas de temp ficam sem efeito colateral documentado.

## Risks / Trade-offs

[Mitigações detalhadas e responsáveis: ver ADR 0006]

- [Token commitado por descuido] → mitigado por `.sen_session*` no `.gitignore` (spec), Hidden attr, e aviso no README; scanners do Bitbucket como segunda camada.
- [Esteira publicando a sessão em artefatos] → hoje `artifacts: test-results/**` não inclui a raiz; ADR registra proibição de ampliar glob de artefatos sem conferir.
- [Multiusuário em pasta compartilhada] → aceito na V1 (documento: sessão é pessoal, repositórios individuais); chmod 600 no POSIX protege leitura.
- [Scanner de segredos acusando o arquivo na árvore] → registrado no ADR como falso-positivo esperado pelo desenho; exceção a tratar junto ao time de security.

## Migration Plan

1. `.gitignore` primeiro (guard-rail deve existir ANTES do primeiro arquivo existir).
2. Mudança de composição + testes; suite verde.
3. ADR 0006 + docs (features/README/backlog) no mesmo commit de código.
4. Rollback: reverter (não há migração de dados; volta ao temp imediatamente).

## Open Questions

- Necessidade futura de `purge()` de sessão ao trocar de ambiente (AUTH_HOST diferente no mesmo repo) — abre com a fase de multi-perfil; hoje host único por projeto.
