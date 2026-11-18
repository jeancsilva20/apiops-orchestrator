# D-004 — Golden Path: template da plataforma, congelamento e cenário de validação

**Status:** Fechada em pontos, no grill de validação ponto a ponto iniciado em 2026-10-13.
**Premissa de evidência:** varredura read-only e simulação da API 204 (`simulacao-api-cep-real/README.md`).

> ⚠️ **Revisada pela [D-005](d005-layout-revisado.md) em 2026-10-14.** §2.1 mantida e detalhada (binding de `spec.template`); §2.2 parcialmente descongelada — a conformidade com a régua é implementável, a remoção seletiva continua congelada (V-25).
> A premissa acima cita `simulacao-api-cep-real/README.md`, que **não existe** nesta pasta — referência quebrada, registrada no refino.

## 1. Contexto

A D-003 adotou o Golden Path aprovado na reunião de 2026-09-28: template canônico no Manager, resolvido por GET. A simulação com dados reais provou (D-a) que a chave `template` **não existe** no contrato da plataforma: não vem em `GET /apis/204` nem `GET /apis/290`, está `null` no payload de criação documentado, e nenhum endpoint de template aparece nas fontes empíricas. O papel do fluxo-base é hoje exercido pelos `interceptors` do escopo revision.

## 2. Decisões fechadas

### 2.1 Contrato permanece com `spec.template` obrigatório

A intenção da reunião (template canônico na plataforma) **permanece como meta e como contrato** do manifesto. O layout continua especulativo em relação a essa peça; o tempo exposto da plataforma (feature flag, rota v3, ou wherever a Sensedia expõe) definirá quando o publish poderá resolver `spec.template` por GET real.

### 2.2 Congelamento do ciclo de fluxos

Itens de implementação **dependentes** do fluxo-base ficam suspensos até o template existir na plataforma:

- resolução de herança ascendente até a raiz (append × override);
- ~~heurística diff-vs-template do import~~ → **D-005 §8**: o diff passou a ser contra o fluxo da própria revision, e está descongelado;
- cálculo global contínuo de `position` sobre o fluxo montado;
- publish end-to-end completo.

Itens **independentes** do fluxo-base permanecem elegíveis para implementação por change proposal (schema de basic info, schema de resource — que a **D-005 §3** ampliou com `destination`/`timeout`/`inherit` —, nomenclatura/descoberta, regimes de apiTags/escalares, import de operações desacompanhadas).

### 2.3 Cenário de validação ambiental

Para o ambiente de validação (sandbox do tenant), o responsável **provisionará o template da API localmente no ambiente** (gestão fora do contrato v3, enquanto a plataforma não expõe a feature). Com isso os pontos dependentes de fluxo-base tornam-se validáveis em meio controlado, sem alterar a decisão de contrato. O `exemplo-layout-final/` será refeito alinhado a esse arranjo.

## 3. Consequências

- A matriz de validação (emitida no grill) vale como **roteiro de revalidação** no dia em que a plataforma expor o template oficial: cada ponto validado com surrogate/carregado à mão deve ser re-testado no modo real.
- A D-003 §1 e §6 continuam válidas **no papel**; qualquer divergência encontrada no ambiente preparado retorna aqui como incremento desta decisão antes de tocar a D-003.
- Itens restantes da fila de templates/schemas (`fila-templates-schemas.md`) devem ser triados em "liberados" (independentes) × "congelados" (dependentes do fluxo).

## 4. Pontos do grill ainda em curso (registro ao vivo)

| # | Ponto | Estado |
|---|---|---|
| 1 | Template/fluxo-base (D-a) | **Fechado** — ver §2 |
| 2 | Position global contínua (D-c) | **Fechado** — D-003 §9 item 4 reescrito: cálculo global e contínuo sobre a revision montada (wire real: 1..10, 11..17, …; FIRST/SECOND compartilham numeração) |
| 3 | Escalares vazios no import (D-d) | Respondido: **import fiel** (transparência do `""`); risco de republicação destrutiva aceito conscientemente pelo responsável — selar com salvaguarda em questão |
| 4 | Nome de pasta de resource com espaço (D-b) | Pendente |
| 5 | Environments / Env-Variables (D-e) | Pendente |
| 6 | `null` dentro de `content` tipado | Pendente |
| 7 | YAML só de comentários (op vacia) | Pendente |
| 8 | Custom duplicado no mesmo fluxo | Pendente |
