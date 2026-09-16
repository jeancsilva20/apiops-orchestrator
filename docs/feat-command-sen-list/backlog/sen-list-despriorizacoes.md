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
