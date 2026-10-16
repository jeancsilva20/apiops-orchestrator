# Decisões do refino da `api-letras-409/` — área isolada

| Meta | Valor |
|---|---|
| Aberta em | 2026-10-13 |
| Origem | `../validacao-api-letras-409.md` (itens `V-01`…`V-21`) |
| Estado | **Consolidado em 2026-10-14** na [D-005](../d005-layout-revisado.md) |

## Por que esta pasta existe

As decisões tomadas neste refino **não entram direto** na D-003 nem na D-004.
Elas ficam aqui, uma por arquivo, até a consolidação final — assim nada se mistura
com as decisões já fechadas da feature e a consolidação pode ser feita de uma vez.

**Consolidado.** Estas decisões foram reunidas na [`d005-layout-revisado.md`](../d005-layout-revisado.md),
que é a autoridade a partir de 2026-10-14 nos pontos que revisa. Os arquivos aqui permanecem como
registro detalhado: evidência, alternativas avaliadas e procedência de cada decisão.

## Protocolo

1. Um arquivo por item fechado: `V-xx-<assunto>.md`.
2. Cada arquivo traz: pergunta, opções avaliadas, **decisão**, justificativa,
   o que ela revoga/altera nas decisões existentes e o que ela destrava.
3. Fechado o item, o status dele muda para `FECHADO` em `../validacao-api-letras-409.md`,
   com ponteiro para o arquivo daqui.
4. Nenhum arquivo de `api-letras-409/` é alterado durante o refino — a pasta é evidência.
5. Na consolidação: estes arquivos viram incremento da D-003/D-004 → atualização da
   `fila-templates-schemas.md` → change proposal OpenSpec.

## Procedência

Todas as chamadas usadas para comprovar os itens — token, bases, endpoint a endpoint e o que cada um
entregou — estão em [CAMINHOS-DE-VALIDACAO.md](CAMINHOS-DE-VALIDACAO.md). Somente leitura, sem nenhuma
escrita na plataforma.

## Itens fechados

| ID | Assunto | Arquivo | Fechado em | Altera |
|---|---|---|---|---|
| V-01 | `destination`/`timeout`: escopos, presença e herança | [V-01-destination-timeout-escopos.md](V-01-destination-timeout-escopos.md) | 2026-10-14 | D-f, D-m (3 pendências), D-e, D-003 §3/§5 |
| V-07…V-10 | Releitura da 409: quais valores da pasta vieram da 417 | [V-07-a-V-10-dados-409-reconfirmados.md](V-07-a-V-10-dados-409-reconfirmados.md) | 2026-10-14 | decide V-19; resolve V-04 |
| V-01 · V-02 · V-03 | Molde YAML dos 3 escopos (Forma B) validado campo a campo no wire da 417 + campos preservados por GET | [V-01-molde-yaml-validado-417.md](V-01-molde-yaml-validado-417.md) | 2026-10-14 | D-003 §4/§5 (molde), D-e, fila de schemas |
| V-22 | Estado não governado (campos + interceptors fora de FIRST/SECOND) preservado por GET | [V-22-estado-nao-governado.md](V-22-estado-nao-governado.md) | 2026-10-14 | D-003 §4, schema de interceptors, `set_interceptor_positions()` |
| V-23 | Bloqueio do AG (412) no publish: anatomia do erro, cálculo do faltante e saída para a esteira | [V-23-bloqueio-do-adaptive-governance.md](V-23-bloqueio-do-adaptive-governance.md) | 2026-10-14 | tratamento de erro do publish; insumo do `validate` |
| V-11 (a) | Conformidade com a régua 414: append = INFO, override = WARNING, nunca bloqueia | [V-11-conformidade-com-a-regua.md](V-11-conformidade-com-a-regua.md) | 2026-10-14 | D-003 §6, D-004 §2.2 (descongelamento), comando `validate` |
| V-11 (b) | Binding do template: `spec.template` local × variável de ambiente na esteira, com chave de modo | [V-11-binding-do-template.md](V-11-binding-do-template.md) | 2026-10-14 | D-003 §1, D-004 §2.1, `config/settings.py` |
| V-12 (a) | Identidade no repo: nenhum id além do da API; chave = `(método, path)` | [V-12-identidade-sem-ids.md](V-12-identidade-sem-ids.md) | 2026-10-14 | D-001/D-003 (identidade), importer, publisher |
| V-24 | Revisão alvo do publish: número por variável de ambiente; local só na Draft (rev 1) | [V-24-revisao-alvo-do-publish.md](V-24-revisao-alvo-do-publish.md) | 2026-10-14 | PRD §3.3 (revisions fixas), `config/settings.py`, publisher |
| V-12 (b) · V-13 | Árvore por recurso, espelhando o Manager; pasta não precisa casar com `name` | [V-12-arvore-por-recurso.md](V-12-arvore-por-recurso.md) | 2026-10-14 | D-003 §2 e §5, D-a, importer, validador |
| V-16 · V-17 | Nome da pasta do recurso e do arquivo de operação, validados materializando 6 APIs | [V-16-V-17-nomes-de-pasta-e-arquivo.md](V-16-V-17-nomes-de-pasta-e-arquivo.md) | 2026-10-14 | D-003 §2/§7, importer, validador |
| V-26 | `inherit` substitui `override` — herança declarada sempre | [V-26-inherit.md](V-26-inherit.md) | 2026-10-14 | **D-003 §4**, schema de interceptors, import/publish |
| V-18 | Arquivo do escopo raiz: `all.yaml`, gramática e ausência aborta | [V-18-arquivo-do-escopo-raiz.md](V-18-arquivo-do-escopo-raiz.md) | 2026-10-15 | D-003 §4, importer, `sen validate` |
| V-25 | Tombstone: a lista completa explícita é a única forma expressável (T06) | [V-25-tombstone.md](V-25-tombstone.md) | 2026-10-15 | D-2/P-4, importer, conformidade |
| V-27 | **O fluxo efetivo é resolvido no repositório, não na plataforma** | [V-27-fluxo-resolvido-no-repositorio.md](V-27-fluxo-resolvido-no-repositorio.md) | 2026-10-15 | **V-26** (publicação), V-25 (generalizada), publisher |
