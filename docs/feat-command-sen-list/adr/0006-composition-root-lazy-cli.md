# ADR 0006 — Composition root lazy da CLI (destrava `sen` como executável standalone)

| Meta | Valor |
|---|---|
| Status | Aceito (documentado; **implementação congelada** pela regra de processo do projeto) |
| Data | 2026-09-15 |
| Feature | [`features/sen-list.md`](../features/sen-list.md) |

## Contexto

`src/apiops_orchestrator/main.py` executa **efeitos colaterais no escopo do módulo** (linhas 29–93):

- `repo_path` com caminho gravado em disco (`C:\Users\Sensedia\Downloads\…\apiops_newstruct`) — main.py:29-31;
- `Settings()` obrigatório na carga — exige `.env` completo antes de qualquer comando;
- chamada HTTP **real de autenticação durante o import** — main.py:75-78;
- varredura completa de schemas + conversão + dump do `ApiFull` — main.py:88-93.

Consequências: `sen list api` só roda na máquina do caminho gravado; `sen --help` exige `.env`; a esteira gasta auth+conversão antes de falhar em comando inexistente. Além disso `pyproject.toml` **não registra console-script** para `sen` (sem `[tool.poetry.scripts]`).

Fonte do grill: sessão 15/09/2026 (leitura forense dos arquivos; testes existentes não importam `main` — apenas `test_cli_adapter.py` importa `app`).

## Decisão

1. **Composition root lazy**: `main.py` passa a montar dependências **sob demanda** (registry que entrega `ctx.obj["api_listing_service"]` apenas quando o comando exige rede). `Settings()` e autenticação migram para dentro do builder.
2. **Entry-point registrado**: `[tool.poetry.scripts] sen = "apiops_orchestrator.main:main"` + declaração explícita do pacote (`packages = [{ include = "apiops_orchestrator", from = "src" }]`).
3. **Metadados livres de `.env`** (D1-a): qualquer `--help` responde sem configuração.
4. **Degradação educativa** (D1-b): comando de rede sem chaves ⇒ mensagem curta + como resolver + sub-help, `exit 1`.
5. Fluxo legacy (validação de estrutura + normalização + conversão `ApiFull`) extrai-se para utilitário **fora do pacote** (`scripts/generate_api_json.py`, com `--repo`/`--revision`) — *[D3 pendente de placa]*.

## Consequências

| Positivas | Negativas/neutras |
|---|---|
| `sen --help` instantâneo com ou sem `.env` | `python main.py sen create revision` na esteira PoC falha **rápido** ("comando inexistente") em vez de falhar tardiamente — *[D2 pendente de placa: ganho aceitável]* |
| Contrato atual dos comandos (`ctx.obj.get("api_listing_service")`) preservado — zero churn em `cli_adapter.py` | Registry adiciona uma camada de indireção (custo cognitivo mínimo, testável com mocks na port) |
| As decisões A2/B2 continuam válidas (comando único `sen list api --id <id>`; esteira recebe `API_ID` explícito) | Números/ids: nenhum |

## Fontes citadas

- `src/apiops_orchestrator/main.py` (linhas 29–31, 35–37, 52–93, 96–123);
- `src/apiops_orchestrator/adapters/inbound/cli/cli_adapter.py` (consumo `ctx.obj`);
- `pyproject.toml` (ausência de `[tool.poetry.scripts]`);
- Grill `sen list` 15/09/2026 — decisões D1-a/b, D2, D3 (pendente), E3 (pendente).
