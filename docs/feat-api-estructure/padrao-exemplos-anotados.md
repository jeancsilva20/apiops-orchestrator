# Padrão de exemplos anotados — convencionação da feature feat-api-estructure

**Criado em:** 2026-09-29 (refinamento com o responsável)  
**Autoridade:** este padrão disciplina APENAS arquivos de exemplo. A autoridade normativa de cada contrato permanece nas decisões (D-001, D-002, D-003 — moldes de `d003-layout-repo.md`). Em conflito, vence a decisão.

## 1. Quando gerar

Sempre que um arquivo do layout fechar no refinamento, o fechamento **inclui** a geração de um exemplo anotado espelhando a árvore canônica (D-003 §2, revisada pela **D-005 §4**). Desde 2026-10-14 os exemplos são **gerados a partir de APIs reais** em [`decisoes-refino-409/exemplos-gerados/`](decisoes-refino-409/exemplos-gerados/README.md), pelo extrator determinístico `extrair_estrutura.py`. O exemplo nasce na hora do fechamento do contrato — nunca antes (nada de exemplo especulativo) nem depois de esfriar (registra rastreabilidade imediata).

## 2. Formato obrigatório de um exemplo

1. **Todos os campos versionáveis do arquivo** presentes com **dado de exemplo realista**, preferencialmente reutilizando valores reais já observados no tenant (ex.: pares `My new`/`CLI: [Sensedia]` de `evidencia-tags-e-atributos.md`). Dados claramente fictícios (IDs, hosts) devem ficar coerentes entre os arquivos do exemplo e ser sinalizados no README do diretório.
2. **Comentário ACIMA de cada campo** (nunca à direita), com três informações, nesta ordem:
   - **Função:** uma linha dizendo o que o campo significa para o contrato;
   - **Obrigatoriedade:** obrigatório ou não **no arquivo versionado** (não confundir com o payload remoto);
   - **ReadOnly:** se o usuário comum pode alterar via YAML/CLI (influencia o validador/imutabilidade);
   - **Regime de omissão**, quando aplicável: *ausente preserva / `[]` remove / `""` limpa*;
   - **Origem esperada:** Usuário, Orquestrador, Manager ou Hidratado no publish.
3. **Cabeçalho obrigatório** no topo de cada exemplo: bloco de comentário listando o que **não aparece** naquele arquivo e o porquê de cada classe de omissão (hidratado por GET, preservado pelo Manager quando omitido, suprimido por decisão);
4. **Rastreabilidade:** o cabeçalho cita a(s) decisão(ões) que fecharam aquele contrato (ex.: "D-003 §3") e a evidência empírica quando houver.

## 3. Vigilância anti-drift

- Os moldes vivos da decisão normativa (`d003-layout-repo.md`) continuam sendo a **primeira** referência; os exemplos são segunda referência ilustrativa.
- Se um contrato evoluir (ex.: nova decisão D-004), o exemplo correspondente **precisa** ser atualizado no mesmo commit do incremento da decisão.
- Divergência entre exemplo e decisão = defeito documental; corrija o exemplo ou abra o débito explicitamente no README da feature.

## 4. Arquivos já cobertos

| Arquivo do exemplo | Contrato fechado em | Suporte empírico |
|---|---|---|
| `api-basic-info.yaml` | D-003 §3 + refinamento 2026-09-29 | API 405 + [varredura 110 APIs](evidencia-tags-e-atributos.md) |
| `resources/<slug>/resource.yaml` | D-003 §5 + D-005 §3 | APIs reais do tenant (409, 417) |
| `resources/<slug>/<método>_<path>.yaml` | D-003 §4 + D-005 §4/§6 | APIs reais do tenant (409, 417) |
| [`all.yaml`](all-yaml-exemplo-anotado.yaml) | **V-18** (2026-10-15) + V-01 §5 | API 417, revision 9175 |

Próximos arquivos entrarão nesta tabela ao fecharem.
