## Why

As skills de agente que vêm na branch `feat/skills` vão editar os YAML do repositório da API. Para escrever cada arquivo no formato certo de primeira, o agente precisa do schema do arquivo; hoje ele só descobre o formato errando no `sen validate`.

Os JSON Schemas já existem em `domain/schemas/`, um por arquivo do layout, mas não chegam a quem usa a CLI: nenhum comando os mostra e o executável não os leva. E nada confere hoje que eles batem com o que a CLI aceita: o `validate` e o `publish` não os aplicam (D4 do change `tighten-api-tags-precheck`), e o teste que valida um repositório real contra eles está pulado desde que a pasta `docs/` saiu do repositório, em 22/10/2026 (`SKIPPED ... exemplo gerado ausente`).

## What Changes

- **Novo comando `sen schema`, oculto no `sen --help`.** Por decisão do responsável, por enquanto só as skills o citam.
  - Sem argumento: mostra o layout do repositório como árvore de pastas, com o tipo de cada arquivo e quantos dele o repositório tem.
  - `sen schema <tipo>`: imprime o JSON Schema do tipo de arquivo. Os tipos são `basic-info`, `all`, `components`, `resource` e `operation`.
  - Funciona sem sessão, sem credencial e sem rede, e não lê o repositório da API.
- **O executável passa a levar os schemas.** É uma exceção pontual à regra do build de não coletar dados do pacote, restrita à pasta `domain/schemas/`.
- **Teste de fidelidade:** um repositório de exemplo dentro de `tests/` é validado contra os schemas, sem depender de `docs/`. Os schemas que divergirem do que a CLI aceita são corrigidos.
- **`ORCHEST_SCHEMA_FOLDER`**, que é relativo e não é usado, é substituído pela pasta resolvida a partir do pacote.

## Capabilities

### New Capabilities

- `sen-schema`: mostrar, sem rede, o layout do repositório da API e o JSON Schema de cada arquivo, na versão da CLI em execução.

### Modified Capabilities

Nenhuma. O `validate`, o `publish` e os demais comandos não mudam.

## Fora do escopo

- As skills: elas ganham uma change própria, depois desta.
- Aplicar os schemas no `validate` e no `publish`.
- `api-environment.schema.json` e `env-variables.schema.json`, que não estão no `catalog.json`.

## Impact

- **Código:** `adapters/inbound/cli/cli_adapter.py` (comando), `application/services/schema_catalog.py` (layout e leitura dos schemas), `config/settings.py` (pasta dos schemas), `domain/schemas/catalog.json` (cada entrada ganha o `name` do tipo) e `domain/schemas/*` (correções que o teste apontar).
- **Build:** `scripts/build-exe.ps1` e `scripts/build-linux.sh` ganham o `--add-data` e a conferência de que os schemas entraram no binário.
- **Testes:** um exemplo novo em `tests/fixtures/`, e o `test_catalog_schema_dispatch.py` deixa de depender de `docs/`.
- **Usuário:** nada muda no help nem nos comandos existentes.
