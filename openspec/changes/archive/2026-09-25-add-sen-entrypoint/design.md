## Context

A CLI despacha via `main()` em `src/apiops_orchestrator/main.py`, que já implementa o **gate por argv** testado (bare = fluxo legacy integral; `sen <cmd>` = standalone, só o necessário no `ctx.obj`). O bloqueio para o uso direto é apenas de *packaging*: nenhum console entry point está registrado no `pyproject.toml`. Restrições: Poetry (sem Setuptools directo), Python 3.12, e esteira intocada (o pipeline continua chamando `python main.py`). O restante do backlog (fonte de `.env` CWD→HOME, secrets da esteira) está deliberadamente FORA deste change.

## Goals / Non-Goals

**Goals:**

- `sen` instalável via Poetry, despachando para o composition root atual **sem novo código de inicialização**.
- Paridade total dos três modos de invocação (`sen` / `sen <cmd>` / `python main.py` bare) garantida por testes.
- Documentação de uso e PATH (venv ativo × `poetry run`).

**Non-Goals:**

- Publicação de wheel/index interno e PyInstaller (fase de distribuição — backlog).
- Mudança no local de leitura de credenciais (CWD/HOME) — change separada.
- Novos comandos ou alteração de exit codes existentes.

## Decisions

**D1 — `main()` como console script (sem wrapper novo).** `[tool.poetry.scripts] sen = "apiops_orchestrator.main:main"`. O gate por argv já diferencia bare/invoked usando apenas `len(sys.argv)`, que se comporta igual no binário e no `python main.py`. Alternativas rejeitadas: criar módulo `__main__.py`/wrapper dedicado (duplicaria o composition root e colocaria `python -m` na mesa sem ganho); migrar o dispatcher para ferramentas extras do `pyproject` (saída de escopo).

**D2 — Regeneração do ambiente como passo de rollout.** `poetry install` após o bump de config (o Poetry reescreve os shims do venv). Instruções entram em README + `docs/features/sen-login.md`. Contribuidor com ambiente pré-existente recebe isso como passo único de upgrade.

**D3 — Smoke tests manuais são o critério de aceite do PATH; unitários protegem a lógica.** Unitários já cobrem o gate com `argv` simulado (vazio / `sen login` / `sen list api`) e o `_main` introspectável; para o shim propriamente dito, o aceite é executar `poetry run sen --version`/`sen login` pós-install (runtime real do Poetry). Alternativa rejeitada: testar o binário dentro do pytest (acoplamento a PATH do CI, frágil no Windows).

**D4 — Mensagem para o caso `sen` pelado.** Bare via `sen` (sem argumentos) dispara o fluxo legacy — paridade deliberada; sem correção de UX aqui (ex.: transformar em help) para não alterar comportamento contratual fora do escopo. Registrado como candidato de melhoria futura.

## Risks / Trade-offs

- [Shim não regenerado para quem já tem venv instalado] → instruções explícitas (`poetry install`) no README e no docs/features; commit message cita o passo.
- [Confusão `sen` pelado = esteira] → documentado nos Goals e nas tasks (nota para o time); mudança de UX fica para trás do aprovado em D4.
- [PATH invisível em shells especiais (wsl remotos, containers)] → caminho suportado e documentado é `poetry run sen …`, independente de PATH global.
- [Concorrência com futura distribuição wheel] → escolha do Poetry scripts é compatível com wheel posterior (entry points standard); nada descartado.

## Migration Plan

1. Land do `pyproject.toml` (+2 linhas).
2. `poetry install` (local e CI), smoke: `poetry run sen --version`, `poetry run sen --help`, `poetry run sen login`.
3. Comunicar no time a nova forma de invocar (README/docs/features já atualizados).
4. Rollback: reverter o commit (nenhum estado persistente criado; o `sen` pelado/bare é idêntico ao fluxo existente).

## Open Questions

- Nome final do executável: `sen` conforme proposto — confirmar que não há colisão de binário nos ambientes-alvo (baixo risco, única CLI do projeto).
- Prazo da distribuição wheel (fora deste change) para conciliar com `tbump`/CI de release.
