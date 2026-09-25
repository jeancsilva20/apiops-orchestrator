# Backlog — despriorizações legítimas do `sen list`

> Itens deliberadamente FORA da fatia atual, com seus contratos congelados por escrito para que a retomada seja cópia, não reconstrução.

## 1. Canal de máquina `-o json` (despriorização B2)

**Contrato negociado e à espera:** saída = conjunto completo por padrão (sem janela silenciosa); `--limit`/`--offset` sempre explícitos; campos mínimos estáveis: `id`, `name`, `internal_name`, `version`, `state`, `owners[]`; consistência dev×esteira (mesmo shape). A esteira não depende deste canal hoje — consome `API_ID` explícito (regra A2).

## 2. YAML (C3)

Wire existente em `output_display.py` permanece **dormente**: sem promoção pública nesta fatia; quando o canal de máquina acordar, YAML reaparece na mesma conversa.

## 3. Filtros de listagem (`--domain`, `--tag`, server-side search)

Reavaliam juntos com o canal JSON — são refinamentos de consumo de máquina. `--query` já cobre o cedo principal (name+description, client-side; nome validado pelo Paulo em 16/09).

## 4. Workflow-stage-name na listagem principal

Enriquecer `LIFE CYCLE` com o nome real da etapa ("Stage One") demandaria 1 chamada a `/api-governance/api/v3/workflows/{id}/stages` **por API da lista** — caro para 107. No drill-down o nome JÁ vem (catálogo cacheável por sessão). Evolução possível: cache persistente de catálogos ou exibição condicional.

## 5. Visualizador de `suggestions` do completeness

`GET /revisions/{rid}/completeness` retorna `completenessScore` + `suggestions[]` (12 dicas REST na API 400). Candidato natural a **`sen audit`** — feature própria; não polui a tabela de revisões.

## 6. Adoção generalizada do `filter=BASIC_INFO`

Comprovado: corta interceptors/resources dos payloads de detail/revisões. Vale re-visitar clientes HTTP do orquestrador em fatias futuras de performance (fora do escopo do `sen list` em si, que já usa a recomendação no desenho).

## Não-apagados do radar, sem urgência

- Ordenação alternativa client-side (`--sort name|version`) — hoje: `id asc` fixo (decisão A3-1a);
- Export do resultado da listagem em arquivo (ex.: `--out json`) — candidato a acompanhar o canal de máquina.

---

## Pendências registradas no fechamento do change `add-sen-list` (25/09/2026)

> Sobras de tasks do change, com nota do bloqueio comum: **nenhum smoke com credencial real foi executado** (sessão `.sen_session` expirada; `sen login` dependente de `SEN_CREDENTIALS` — mesmo bloqueio registrado no change irmão `add-sen-entrypoint`, task 2.2).

### Bloqueadas pelo smoke de login (executar quando houver credencial)

- **[task 7.2]** Smoke read-only E2: `sen list api --limit 5` + drill-down da API 400 (somente GETs). Evidência parcial já colhida: sem sessão válida, a CLI apresenta a mensagem educativa "Sessão inválida ou ausente: faça `sen login`…" com **rc 1** (comportamento correto, validado em 25/09).

### Trabalho remanescente fora da fatia (D3/E1)

- **[task 3.1]** Extrair o fluxo legacy para `scripts/generate_api_json.py` (com `--repo`/`--revision`: validação de estrutura + schema + conversão `ApiFull`), tirando-o de `main.py`. Fluxo bare permanece em `run_bare_pipeline` até lá (decisão D3).
- **[task 3.2]** Auditar `pipeline.yaml`/`bitbucket-pipelines.yml` atrás de `python main.py` pelados e ajustar para o ponto de entrada definitivo após a extração.
- **[task 6.3]** Catálogo humano de erros E1: 403 (permissão), 404 já live no drill-down (fundido educativo), rede caída → todos `exit 1` com texto amigável. Depende de resgatar a infra de `HttpCallError` (leva descartada); o 401 já está homogeneizado via `AuthenticationRejectedError`.

### Qualidade global (transversal, não exclusiva do sen list)

- **[task 7.1 — débito]** `mypy` nunca foi configurado no projeto (sem `[tool.mypy]`/`py.typed`): 132 erros pré-existentes em 31 arquivos ao tipar `src`. Precisa de setup próprio (cards/config) antes de virar gate.
- **[task 7.1 — débito]** `black --check` reprova em 45 arquivos (formatação histórica divergente). Sanabilidade com um `poetry run black .` isolado, mas gera diff grande — agendar em leva separada.
- `ruff` ficou limpo no fechamento (21 débits pontuais sanados: F401/F541/F841/E731).
