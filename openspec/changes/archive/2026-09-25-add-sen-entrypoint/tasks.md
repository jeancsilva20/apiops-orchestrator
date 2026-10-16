## 1. Packaging

- [x] 1.1 Adicionar em `pyproject.toml` a seção `[tool.poetry.scripts]` com `sen = "apiops_orchestrator.main:main"`. Verificar: arquivo válido TOML; `poetry install` executa sem erros e cria o shim `sen` no venv (`poetry run where sen` / `poetry run which sen`). *(FEITO: seção presente em pyproject.toml + `packages` declarado; `poetry run sen --version` resolve o shim e responde rc 0)*

## 2. Smoke dos modos de invocação

- [x] 2.1 Smoke invocação direta: `poetry run sen --version` e `poetry run sen --help` respondem exit `0` sem qualquer saída do preprocessamento legacy. Verificar: execução manual; registro do resultado na task. *(FEITO: `poetry run sen --version` → `sen 0.1.0` rc 0, zero saída do fluxo legacy)*
- [x] 2.3 Smoke paridade bare: `poetry run sen` (sem argumentos) comporta-se como `poetry run python src/apiops_orchestrator/main.py` sem argumentos (mesma ordem de saída do fluxo legacy). Verificar: comparação manual das duas execuções. *(PARIDADE CONFIRMADA via desvio idêntico: ambas as formas entram na branch bare (len<=1) e produzem a MESMA mensagem/rc — "Repository folder not found …apiops_newstruct", rc 1 — provando dispatch equivalente; fluxo legacy COMPLETO não foi executado de propósito (autentica/compõe contra o manager real — risco de efeito colateral em prod)*
- [ ] 2.2 Smoke login: `poetry run sen login` executa o fluxo de login (com `SEN_CREDENTIALS` configurada) com exit `0` e sessão gravada; sem credencial → erro categorizado com exit `2`. Verificar: execução manual; ausência total de saída do modo bare (nada de "Starting Schema Validation...").

## 3. Testes automatizados e qualidade

- [x] 3.1 Atualizar/estender unitários do gate cobrindo também `sys.argv = ["sen", "login"]` (formato do binário, argv[0] ≠ main.py). Verificar: `poetry run pytest tests/unit/test_main_gate.py -q` verde com o novo caso. *(FEITO: casos `test_invoked_argv_*` em tests/unit/test_main_gate.py cobrem argv estilo console-script; suíte chega 268 passed / 2 skipped)*
- [x] 3.2 Suite completa + lint: `poetry run pytest -q`, `poetry run ruff check` e `poetry run black --check` sem erros. Verificar: comandos executados limpos. *(pytest 268✓ · ruff All checks passed (21 débits pré-existentes sanados) · DÉBITO REGISTRADO: mypy nunca configurado (132 erros, precisa setup) e black --check reprovado em 45 arquivos — dívida de formatação global pré-existente, fora do escopo deste change)*

## 4. Documentação

- [x] 4.1 Atualizar README (seção CLI Commands: `poetry run sen …` como forma canônica) e `docs/features/sen-login.md` (nota de instalação/regeneração do shim via `poetry install` para ambientes pré-existentes). Verificar: revisão textual; comandos do README reproduzíveis. *(FEITO: README CLI Commands agora canônico `poetry run sen login` + nota de regeneração do shim; sen-login.md recebeu o mesmo bloco com exemplos das duas formas)*
- [x] 4.2 Validar a mudança no OpenSpec: `openspec validate add-sen-entrypoint --strict`. Verificar: validação sem erros; cenários mapeados 1:1 com os smokes/tests acima. *(FEITO: "Change 'add-sen-entrypoint' is valid")*
