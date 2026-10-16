## Why

Hoje qualquer invocação da CLI exige o prefixo `poetry run python src/apiops_orchestrator/main.py …` — frágil, verboso e acoplado ao layout de diretórios, o que impede o consumo natural do `sen login` (e futuramente `sen list`, `sen validate`) como ferramenta. Discutimos no encerramento da fase 1 (`docs/auth/distribuicao-e-fontes-de-credenciais-backlog.md`, item "entrypoint") e a decisão foi especificar este ajuste **isolado** antes de abordar onde as credenciais vivem.

## What Changes

- Registro de **console entry point** `sen` no `pyproject.toml` apontando para o composition root existente (`apiops_orchestrator.main:main`), tornando `sen login`, `sen list api`, `sen --version`/`--help` executáveis diretos do venv/pacote.
- **Sem mudança de comportamento** dos comandos: o gate por argv já implementado em `main.py` governa os modos — `sen login` (invoked, standalone) e `sen` pelado (bare, equivale a `python main.py` da esteira).
- Regeneração do ambiente (`poetry install`) para o Poetry criar o shim executável; validação documentada de PATH (venv ativado ou `poetry run sen …`).
- Testes de fumaça cobrindo os três modos (`sen` pelado / `sen <cmd>` / `python main.py` bare) e o fato de o binário iniciar **sem** executar o preprocessamento legacy nos comandos.

## Capabilities

### New Capabilities
<!-- Nenhuma: o binário expõe comandos da capability existente `cli-auth`. -->
- (nenhuma)

### Modified Capabilities
- `cli-auth`: nova requirement (ADDED) — **executável `sen`**: o pacote SHALL instalar o comando `sen` capaz de despachar os comandos da CLI sem o wrapper `python main.py`, com paridade total de exit codes e sem disparar o preprocessamento legacy em `sen <cmd>`.

## Impact

- **Código**: `pyproject.toml` (`[tool.poetry.scripts]`); nenhum arquivo de `src/` precisa mudar (entry point aponta para `main()` já existente e gate-tested).
- **Instalação**: `poetry install` após a mudança de config; contribuidores com ambiente já instalado precisam rodar de novo (instrução no README/`docs/features`).
- **Esteira**: sem impacto — `python main.py` (bare) segue funcionando identicamente; a migração dela para env vars/secrets é outro change (backlog).
- **Dependências**: nenhuma nova.
