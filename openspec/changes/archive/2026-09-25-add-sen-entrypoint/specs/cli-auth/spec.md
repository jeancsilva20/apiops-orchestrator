## ADDED Requirements

### Requirement: Executável `sen` instalável

O pacote SHALL registrar um executável de console denominado **`sen`** que despacha a CLI (`apiops_orchestrator.main:main`) sem exigir o wrapper `python main.py`. Após instalação/atualização do ambiente (`poetry install`), o executável SHALL estar disponível no PATH do ambiente (uso direto com venv ativado ou via `poetry run sen …`), com **paridade total de comportamento e exit codes** em relação à invocação via `python main.py`.

#### Scenario: `sen login` direto

- **WHEN** o ambiente está instalado (`poetry install` executado) e o usuário executa `sen login` (venv ativado) ou `poetry run sen login`
- **THEN** o comando executa exatamente o fluxo de login da CLI (autenticação, persistência, resumo sem segredos, exit code `0`) e **não** executa o preprocessamento legacy (validação de repo, cargas, auth LEGACY, dump da API) — sem nenhuma saída/efeito do modo bare

#### Scenario: Comandos informativos sem preprocessamento

- **WHEN** o usuário executa `sen --version` ou `sen --help`
- **THEN** os textos informativos respondem imediatamente (exit `0`), sem qualquer execução do preprocessamento legacy

#### Scenario: Paridade do modo bare

- **WHEN** o usuário executa `sen` **sem argumentos**
- **THEN** o comportamento SHALL ser idêntico a `python main.py` sem argumentos (fluxo legacy da esteira executado integralmente), mantendo a paridade documentada entre os dois entry points

#### Scenario: Invocação via wrapper sem venv ativado

- **WHEN** o usuário executa `poetry run sen <cmd>` em shell sem o venv ativado
- **THEN** o comportamento é idêntico à invocação direta do executável (mesmos comandos, saídas e exit codes)