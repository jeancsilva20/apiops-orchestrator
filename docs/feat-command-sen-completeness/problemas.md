# Problemas — histórico de revisões no Adaptive Governance

*(observações empíricas em produção, 2026-09-24)*

## O problema

O `sen completeness --api-id X --revision <REV ID>` precisa consultar o report de maturidade de uma revisão específica da API. Porém, o Adaptive Governance **só mantém report da última revisão** do catálogo: as revisões antigas são invisíveis para a CLI — não existe rota conhecida que liste ou filtre o histórico de maturidade por revisão.

## O que foi sondado (produção, 2026-09-24)

1. **`GET /adaptive-governance/api/v1/search`** — a row traz apenas o estado atual (id do catálogo, `maturity`, `issues[]`); sem lista de revisões e sem `originId` confiável da API do Manager (ver [`backlog/observacoes_filtros.md`](backlog/observacoes_filtros.md)).
2. **`GET /adaptive-governance/api/v1/maturity-reports?catalogIds={uuid}`** — array sempre com **1 único item**. Testado com `&limit=5` (limite alto não revela histórico) e com `&fullReport=true` (delta só preenche `violations[]` da revisão vigente).
3. **Combinações testadas sem efeito**: `last=false`, limites/paginação variados. Nenhum parâmetro (`revisionOriginId`, `originId`, etc.) honrado por esse endpoint como filtro de revisão.

## O mesmo limite existe no produto

Na tela do Manager (Overview da API), o seletor de revisões para a visão de completude **também só oferece a última revisão** — o dropdown exibe somente `Revision 4` (a vigente), sem as anteriores. Ou seja, o comportamento observado na CLI espelha a própria plataforma: completude é consultável apenas da revisão vigente.

## Regra selada decorrente (para a Fatia 3 / G1-B2)

> 🔁 **REVOGADA (2026-09-28, change `add-sen-completeness`):** a regra abaixo NUNCA chegou a ser implementada — foi desenhada para o consumo via AG. Com a troca de fonte para `GET /api-manager/api/v3/revisions/{rid}/completeness` (Manager), **qualquer revisão alcançável na plataforma é consultável** (histórico incluso); recusas só acontecem quando a própria plataforma recusa (404 → exit 2 orientando `sen list api --id X --revisions`; sem recusa sintética de "revisão antiga"). Registro mantido como histórico do raciocínio da época.

```
--revision == revision.originId do report atual  → segue (único caminho feliz)
--revision ≠ originId (revisão antiga)           → exit 2 + mensagem honesta:
  "O Adaptive Governance só mantém report da revisão atual (<originId>).
   Consulte sen list api --id X --revisions para ver o histórico."
```

Isso elimina a preocupação do ADR 0008 de "1 varredura de reports a mais quando a revisão não é a last" — não existe varredura a fazer; é um `if` no service, não custo de rede.

## Pendência associada

- **P-f** (nova): apurar com a Plataforma se o histórico de maturidade por revisão existe/é planejado (ou se o Connect Catalog expõe rota de revisões consultáveis). **Atualização 28/09:** o HISTÓRICO por revisão deixou de bloquear o usuário — hoje é atendido via endpoint do Manager (`revisions/{rid}/completeness`, fonte da change `add-sen-completeness`); o P-f permanece ABERTO com recorte reduzido: se/quando o AG expuser histórico estruturado (ruleId/severity/range por violação), a granularidade rica deste ADR pode ser reativada numa change futura.
