## 1. Packaging

- [ ] 1.1 Adicionar em `pyproject.toml` a seção `[tool.poetry.scripts]` com `sen = "apiops_orchestrator.main:main"`. Verificar: arquivo válido TOML; `poetry install` executa sem erros e cria o shim `sen` no venv (`poetry run where sen` / `poetry run which sen`).

## 2. Smoke dos modos de invocação

- [ ] 2.1 Smoke invocação direta: `poetry run sen --version` e `poetry run sen --help` respondem exit `0` sem qualquer saída do preprocessamento legacy. Verificar: execução manual; registro do resultado na task.
- [ ] 2.2 Smoke login: `poetry run sen login` executa o fluxo de login (com `SEN_CREDENTIALS` configurada) com exit `0` e sessão gravada; sem credencial → erro categorizado com exit `2`. Verificar: execução manual; ausência total de saída do modo bare (nada de "Starting Schema Validation...").
- [ ] 2.3 Smoke paridade bare: `poetry run sen` (sem argumentos) comporta-se como `poetry run python src/apiops_orchestrator/main.py` sem argumentos (mesma ordem de saída do fluxo legacy). Verificar: comparação manual das duas execuções.

## 3. Testes automatizados e qualidade

- [ ] 3.1 Atualizar/estender unitários do gate cobrindo também `sys.argv = ["sen", "login"]` (formato do binário, argv[0] ≠ main.py). Verificar: `poetry run pytest tests/unit/test_main_gate.py -q` verde com o novo caso.
- [ ] 3.2 Suite completa + lint: `poetry run pytest -q`, `poetry run ruff check <arquivos alterados>` e `poetry run black --check <arquivos alterados>` sem erros. Verificar: comandos executados limpos.

## 4. Documentação

- [ ] 4.1 Atualizar README (seção CLI Commands: `poetry run sen …` como forma canônica) e `docs/features/sen-login.md` (nota de instalação/regeneração do shim via `poetry install` para ambientes pré-existentes). Verificar: revisão textual; comandos do README reproduzíveis.
- [ ] 4.2 Validar a mudança no OpenSpec: `openspec validate add-sen-entrypoint --strict`. Verificar: validação sem erros; cenários mapeados 1:1 com os smokes/tests acima.
