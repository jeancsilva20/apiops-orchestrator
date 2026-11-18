## 1. Pré-requisitos

- [x] 1.1 Concluir as tarefas 4.1 e 4.2 da `add-sen-schema` (schemas dentro do executável); verificar que `sen schema resource` no executável isolado, sem `.sen`, dá a mesma saída que no código-fonte
- [x] 1.2 Conferir como o `sen validate -o json` se comporta com `y` e com `n` pela entrada padrão (o que vai para o stdout, o código de saída e onde aparece o texto da confirmação); verificar com teste de CLI no `test_validate_command.py`, sem gravar em nenhum Manager. Feito em 06/11, com dois testes novos:
  - com `n`, sai com `exit 0` e "Validação cancelada. Nada foi gravado.", sem documento;
  - com `y`, sai com `exit 0` e o documento `apiops.sen-validate/v1` no fim;
  - nos dois casos, o quadro de confirmação e a pergunta saem no stdout antes do JSON, e a skill lê o documento a partir do primeiro `{` depois de "Deseja prosseguir?";
  - sem `.sen`, os comandos de rede param com "Configuração incompleta", e a skill trata isso como falta de sessão.

## 2. Estrutura

- [x] 2.1 Criar `skills/README.md` com o que são as skills, como instalar (copiar a pasta para `.claude/skills/` do repositório da API ou para `~/.claude/skills/`) e a regra de permissão que bloqueia a leitura do `.sen` e do `.sen_session`; verificar copiando uma skill para uma pasta `.claude/skills/` temporária e conferindo que o agente a lista. A sintaxe das regras de permissão foi conferida na documentação do Claude Code em 06/11. Falta conferir a descoberta da skill numa sessão nova

## 3. `sen-api-developer`

- [x] 3.1 Escrever o `SKILL.md` (D3 a D7): `description` com quando usar e quando não usar, o ciclo (schema → plano com riscos → ok → edição mínima → `sen diag structure` → pré-check), a gravação na Draft só a pedido e com confirmação, e as regras comuns; verificar que o corpo tem menos de 500 linhas e que o frontmatter tem só `name` e `description`
- [x] 3.2 ~~Criar os casos de teste da D8 em `skills/sen-api-developer/evals/`~~. Os cinco casos foram escritos e retirados em 06/11, a pedido do responsável (D8 revista)
- [ ] 3.3 O responsável testa a skill com outro agente (roteiro e ambiente em `bateria-de-testes.md`, casos D e A), nos casos da D8 (inclusive rotas e backends do repositório local, respondidos sem escrever) e num pedido sem comando ("cadastra um app pra consumir essa API", D11); ajustar a skill até ele aprovar (arquivo escrito passa no `sen schema`, plano antes de mudança com risco, pergunta no componente compartilhado, pergunta sem escrita, nenhuma chamada à API do Manager por fora da CLI)
- [x] 3.4 Mover para a developer as perguntas sobre o repositório local (D2 revista em 09/11): seção "Como ler o repositório" com os valores efetivos e a herança, seção "Perguntas" com "pergunta não vira mudança", e `description` com os dois lados

## 4. `sen-explore`

- [x] 4.1 Escrever o `SKILL.md` (D3 a D7): `description` com quando usar e quando não usar, os encadeamentos (busca → ID → revisões → completude), o aviso antes de mais de 10 chamadas, as perguntas sobre o repositório local e as regras comuns; verificar como na 3.1. Feito em 06/11, com 113 linhas, frontmatter só com `name` e `description`, e aprovado no `quick_validate`. Opções e campos de JSON conferidos no código da CLI:
  - o `--revision` do `sen completeness` recebe o REV ID, não o número;
  - o `--revisions` já traz a nota de cada revisão (`null` quando o Manager não responde);
  - sem `--all`, a busca mostra só 10 APIs;
  - sem resultado, o `sen list api` imprime texto mesmo com `-o json`.
- [ ] 4.2 O responsável testa a skill com outro agente (casos E de `bateria-de-testes.md`), nos casos da D8: sessão ausente, revisões da 425, pergunta de completude (D12), busca com mais de um candidato, Draft contra repositório e rotas da 425 no Manager fora do repositório dela (D10); verificar que nenhum comando fora da lista de leitura foi executado
- [x] 4.4 Tirar completude e governança da explore e só resumi-las na developer quando vierem no resultado (D12, 09/11)
- [x] 4.3 Tirar da explore as perguntas sobre o repositório local (D2 revista em 09/11): fica só a seção "Rotas no Manager", com a comparação entre a Draft e o repositório, e a `description` aponta a developer para o repositório

## 5. Integração

- [ ] 5.1 Com as duas skills instaladas juntas (casos A de `bateria-de-testes.md`), conferir que pedidos mistos e pedidos parecidos acionam a skill esperada, ou nenhuma delas; ajustar as `description`s se não acionarem
- [ ] 5.2 Atualizar a lacuna do guia para agentes em `docs/consumidores-projetados.md`, apontando para as skills; verificar que o texto cita as duas skills e o README de instalação

## Workflow follow-up

- Commitar só a pedido do responsável, um commit por responsabilidade.
- Arquivar esta change depois da revisão.
- Abrir changes próprias para a `sen-governance` e a `sen-pipeline-triage`.
