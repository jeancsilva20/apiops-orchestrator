## Context

Motivação em `proposal.md`. O formato do erro e a decisão de saída já estão fechados na V-23 (`docs/feat-api-estructure/decisoes-refino-409/V-23-bloqueio-do-adaptive-governance.md`, 14/10/2026): envelope com `errors[].message` contendo JSON serializado; `path` identifica o workflow; `exit 3`; "enriquecer, não repassar", com degradação para o repasse bruto; nunca parsear `messages[]` para obter o faltante.

## Goals / Non-Goals

**Goals:** cumprir o `exit 3` do spec do `sen validate` para o `412` no `PUT`; nunca esconder o motivo de uma recusa de subida; manter a regra "faltante calculado, nunca extraído".

**Non-Goals:** resolver o workflow/stage efetivo pelo grupo da API para calcular o faltante no `PUT` (hipótese não confirmada, V-23 §3); tratar `ManagerApiTransportUnavailableError` no `PUT` de forma específica (cai no fallback como "indisponível").

## Decisions

### D1 — O adapter desembrulha o envelope; o caso de uso decide exibir

Conhecer o formato de erro do Manager é conhecimento de wire, portanto do adapter. Ele entrega `messages` (motivos em texto humano, sem repetição) em todo sinal de recusa e lança `ManagerApiGovernanceBlockedError` quando um `412` traz `path` de governança. Exibir ou não é decisão do caso de uso: só o `sen validate`, na recusa do `PUT`, exibe. O `HttpErrorMapper` passa a entregar o corpo parseado (`body`) para isso.

### D2 — Bloqueio no PUT degrada para o motivo literal

O pré-check calcula o faltante com o workflow/stage gravados na revisão. Um `412` no `PUT` depois de o pré-check liberar significa que o workflow que valida é outro (V-23 §3), e o stage efetivo é desconhecido. Recalcular com os mesmos dados daria o mesmo resultado. O `GovernanceBlockedError` ganha `motivos`: sem faltante calculado, a mensagem lista o motivo da plataforma como evidência (V-23 §5, item 3). `missing` fica vazio, e o `raw` carrega o envelope intacto. O mesmo `exit 3` mantém um único canal para a esteira.

Alternativa descartada: extrair o nome do atributo de "API must contain attribute X". Viola a V-23 §4 e o requisito "Governance pre-check computes the missing attributes".

### D3 — Quais recusas mostram o motivo

`400`/`409`/`412`/`422` são recusas de conteúdo: o motivo orienta a correção do repositório. `401`/`403` usam a mensagem de sessão/acesso (a ação é `sen login`, não editar o repositório). `413`/`429`/outros usam a mensagem de erro interno: o texto da plataforma não ajuda o dev.

### D4 — Fallback da CLI reconhece sinais do Manager

O helper de erro inesperado classifica `ManagerApiError` antes de cair em erro interno. Ele cobre chamadas que nenhum serviço envolve (além do `PUT`, a releitura pós-publicação), nos cinco comandos com fallback.

### D5 — Tags conferidas pelo nome no pré-check

O requisito do stage fala em `attributeId` (com `tagId`, sempre `null` nos 13 workflows da ECAD e nos 5 do consulting); o catálogo (`GET /attributes`, `GET /attributes/{id}/tags`) e as `apiTags` falam em **nomes**. Nenhuma rota acessível liga `tagId` a nome (`GET /attributes/{id}` e `GET /tags` dão 403), então exigência de tag específica não é verificável — e não existe hoje. O que **é** verificável, nome contra nome, é a tag declarada pertencer ao atributo. Medido: tag fora da lista é aceita com `200` e zera as `apiTags`; só o pré-check pode impedir. Por isso a recusa vem antes do bloqueio de governança e com `exit 1` (erro de conteúdo do repositório).

Atributo com `tags: []` conta como ausente quando o catálogo cadastra tags para ele (412 medido). Atributo sem tags no catálogo (ex.: `CLI`) continua bastando pelo nome: o comportamento da plataforma nesse caso não foi medido, e a V-23 §2 o registrou como "basta estar presente". O catálogo é lido uma vez por execução.

Alternativa descartada: aviso para requisito com `tagId` preenchido — chegou a ser escrito e foi revertido; o caso não existe e não seria verificável.

### D6 — Conferência compara o `api` aninhado

`conferir` comparava operações, interceptors, recursos e destinos, mas não o `api`, onde o basic info viaja (W-7). Passa a comparar `name`, `description` e, quando enviadas, as `apiTags` por atributo e conjunto de tags (ordem irrelevante). Verificado contra o Manager real: um envio idêntico ao estado atual não gera divergência falsa.

## Risks / Trade-offs

- **[Catálogo muda entre a leitura e o PUT]** → Janela de segundos; se ocorrer, a conferência D6 acusa a perda.
- **[Atributo fora do catálogo]** → Não tem tag conferida nem satisfaz requisito; o efeito na plataforma não foi medido.

- **[Formato do envelope muda]** → O parse é defensivo: um JSON inválido mantém a string, e um corpo não-dict não gera motivos (cai na mensagem da família).
- **[Motivo da plataforma em inglês e texto livre]** → Exibido como "motivo informado pela plataforma", nunca reinterpretado.
- **[Timeout no PUT]** → Cai em "Manager indisponível" pelo fallback, mesmo que a escrita possa ter sido aplicada. Registrado para um change futuro.
