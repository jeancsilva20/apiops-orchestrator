## Context

A motivação está no `proposal.md` (Why). O estado de hoje:

- O `sen schema` (change `add-sen-schema`) mostra o layout do repositório e o JSON Schema de cada tipo de arquivo, sem rede. As descrições dos schemas já trazem as regras de cada campo para quem preenche: herança, `url` vazia, `timeout`, `x-*`, identidade da API.
- Os comandos de leitura são `sen list api` (`--query`, `--id`, `--revisions`, `--all`), `sen completeness` e os ocultos `sen diag structure` (sem rede), `sen diag draft` e `sen diag template`. Todos aceitam `-o json`.
- O `sen validate` roda as checagens que não gravam (leitura, contrato, identidade, régua, apiTags) e só depois pergunta "Deseja prosseguir?" para gravar na Draft. Com `n` na entrada, ele sai sem gravar e com `exit 0`. Sem entrada, sai com `exit 130`.
- O `publish` e o `deploy` só rodam na esteira, e a própria CLI recusa fora dela.
- O agente usa a sessão aberta pelo desenvolvedor e não deve ver credenciais (`consumidores-projetados.md`, seção 4).

## Goals / Non-Goals

**Goals**

- O agente escreve arquivos que a CLI aceita na primeira tentativa, guiado pelo `sen schema`.
- Nenhuma escrita, local ou no Manager, acontece sem o usuário saber o que muda e quais são os riscos.

**Non-Goals**

- Copiar para as skills regras que a CLI já aplica. Se a regra muda na CLI, a skill não pode ficar desatualizada.
- Substituir as guardas da CLI. A skill reforça, mas a recusa de `publish`/`deploy` fora da esteira continua no código.

## Decisions

**D1 — As skills ficam em `skills/<nome>/`, na raiz do orquestrador, sem build.**
- Quem quer usar copia a pasta da skill para `.claude/skills/` do repositório da API ou para `~/.claude/skills/`. O `skills/README.md` explica isso.
- Alternativa: `.claude/skills/` neste repositório. Rejeitada porque quem usa as skills trabalha no repositório da API, não no orquestrador.
- Alternativa: plugin do Claude Code. Adiada para quando houver mais skills e um canal de distribuição.

**D2 — A fronteira entre as duas skills é "repositório" contra "Manager"** (revista pelo responsável em 09/11; antes, "pergunta" contra "mudança").
- A `sen-api-developer` cobre o repositório local: responde o que está nos arquivos e os altera. A `sen-explore` responde o que só o Manager sabe: APIs, revisões, ambientes, régua e Draft (completude e governança ficam fora, D12), inclusive a comparação das rotas da Draft com as do repositório.
- A developer é quem conhece o repositório (formato, herança, valores efetivos), então essa explicação fica só nela.
- Na developer, uma pergunta não vira mudança: ela responde sem editar e só entra no ciclo de mudança se o usuário pedir. O Manager só aparece nela dentro do ciclo de mudança (pré-check e gravação na Draft), nunca para responder pergunta.
- A `description` de cada skill diz quando usar e quando não usar, citando a outra. Os pedidos mistos ("vê o timeout e aumenta pra 30") pertencem à developer.
- Alternativa: "pergunta" contra "mudança", com a explore respondendo também sobre o repositório. Rejeitada porque repetia nas duas skills a explicação do repositório e separava quem lê os arquivos de quem os altera.

**D3 — A CLI é a fonte da verdade.**
- Layout e campos vêm do `sen schema`, cujas descrições trazem as regras de cada campo. A correção de um erro vem do texto da mensagem da CLI, que diz o que fazer.
- A skill guarda só o que a CLI não ensina: o ciclo de trabalho, os riscos de cada tipo de mudança e quando parar para perguntar.
- As skills citam os comandos ocultos `sen schema` e `sen diag` (decisão do responsável em 06/11).
- Alternativa: copiar os schemas para `references/` da skill. Rejeitada porque a cópia desatualiza a cada versão da CLI.

**D4 — Confirmação antes de mudança com risco e antes de gravar na Draft** (decisão do responsável em 06/11, revista em 09/11).
- **Repositório local:** a mudança sem risco é aplicada direto e aparece no resumo, porque é local e o usuário a revisa no diff. A mudança com risco (componente compartilhado, `inherit: false`, remoção, `apiResponsible`) passa pelo plano (arquivos, o que muda, riscos) e só é escrita depois do ok. O pedido de permissão da ferramenta de edição do agente não basta nesses casos: ele mostra o diff, mas não o risco de domínio, como as outras rotas que usam o componente.
- Alternativa: plano e ok antes de qualquer escrita, a regra de 06/11. Revista depois do primeiro teste com o Haiku: o responsável quer que a mudança local possa ser automática, e um plano para trocar um timeout é cerimônia.
- **Draft no Manager:** o pré-check `echo n | sen validate` não grava e roda sem perguntar. A gravação (`echo y | sen validate`) só roda a pedido do usuário. Antes dela, a skill mostra a revisão alvo (`sen diag draft`) e explica que a Draft passa a refletir o repositório e que nada recebe deploy.
- A skill não sabe qual Manager está na sessão, porque não lê o `.sen`. Ela diz "o Manager da sessão aberta", e o usuário sabe onde fez login.

**D5 — Regras comuns repetidas em cada skill.**
- As regras são: usar `-o json`; não rodar comando que espere resposta; não ler `.sen` nem `.sen_session`; não rodar `login`, `publish` nem `deploy`; diante de erro de sessão, pedir ao usuário o `sen login`; conferir que o `sen schema` existe; preferir os comandos da skill e chamar a API do Manager só pela CLI (D11).
- Cada skill pode ser instalada sozinha, então cada uma traz o bloco inteiro, que é curto.
- Alternativa: um arquivo comum referenciado pelas duas. Rejeitada porque quebraria quem instala só uma.

**D6 — A versão da CLI é conferida pelo próprio comando.** A skill roda `sen schema --help`: se o comando não existir, o `sen` está desatualizado.
- Alternativa: comparar o `sen --version` com uma versão mínima. Rejeitada porque exige manter um número na skill.

**D7 — Formato e escrita.**
- O `SKILL.md` tem `name` e `description` no frontmatter e corpo com menos de 500 linhas. `references/` só entra se os testes mostrarem falta.
- `name` em inglês (`sen-explore`, `sen-api-developer`). `description` e corpo em português: os pedidos chegam em português, como nas descrições dos schemas.
- O corpo explica o porquê de cada regra, em vez de ordens em caixa alta.

**D8 — O responsável testa as skills com outro agente** (revista em 06/11).
- O responsável roda as skills com um agente à parte, que lê o `SKILL.md` e executa os pedidos. Por ora, as skills não levam a pasta `evals/`.
- O plano original era ter casos de teste no formato do skill-creator, em `skills/<nome>/evals/<caso>/`, rodados com e sem a skill. Os cinco casos da developer chegaram a ser escritos e foram retirados a pedido do responsável. Eles podem voltar quando a skill estabilizar. Os casos e o ambiente abaixo ficam como roteiro de teste.
- Os testes usam o executável isolado, sem `.sen`, com os schemas dentro (grupo 4 da `add-sen-schema`). Assim não usam o `sen` do PATH nem a sessão do desenvolvedor.
- **Developer, sem rede:** cópia do `tests/fixtures/api-repo-400`. Casos iniciais:
  - response de sucesso com componente exclusivo;
  - o mesmo pedido com componente compartilhado (variante com duas rotas no mesmo `$ref`);
  - timeout do recurso;
  - rota nova;
  - rota que deixa de herdar um interceptor;
  - pergunta sobre rotas e backends, respondida sem escrever (D2).
  
  Sem sessão, o pré-check cai no caso "sem sessão", que também é testado.
- **Explore:** o caso de sessão ausente roda sem rede. Os casos do Manager rodam depois que o responsável fizer login no consulting, no executável isolado, e consultam a API-lab 425. Nenhum dado do ECAD entra nos casos.
- No fim, vale testar o acionamento com as duas skills instaladas juntas, com pedidos mistos e pedidos parecidos que não devem acionar nenhuma das duas.
- A documentação oficial de skills recomenda testar com os modelos que vão usá-las, incluindo um modelo menor: o que basta para um modelo grande pode faltar para um pequeno.

**D9 — A skill de mudança se chama `sen-api-developer`** (decisão do responsável em 09/11; antes, `sen-api-editor`).
- A criação de API, quando entrar, fica na mesma skill. Ela segue o mesmo ciclo da edição: schema, plano com riscos, ok, edição mínima, conferência e gravação na Draft só a pedido. Duas skills repetiriam o ciclo e disputariam o acionamento ("cria o recurso" contra "cria a API").
- Os passos próprios da criação vão para `references/` dentro da skill, um nível abaixo do `SKILL.md`, lidos só quando o pedido for de criação.
- Enquanto a criação não entra, a skill diz que não cobre API nova: o `sen validate` só trabalha com uma API que já existe no Manager.
- Alternativa: uma `sen-new-api` separada. Rejeitada pelos motivos acima.

**D10 — Os detalhes de rota vêm do repositório local** (decisão do responsável em 09/11).
- Nenhum comando traz os detalhes das rotas de uma API no Manager. O `sen list api` não traz rotas, e o `sen diag draft` traz só o método e o path das rotas da Draft da API do repositório.
- A developer responde perguntas sobre rotas, backend, timeout e interceptors pelos arquivos do repositório, e diz que os dados vêm dele. Ela lê o estado atual nos arquivos também nos pedidos que consultam antes de mudar.
- A explore responde "quais rotas a API tem no Manager?" com o `sen diag draft`, dentro do repositório da API, dizendo que são as rotas da Draft. Fora dele, ou para uma revisão publicada, diz que o `sen` não mostra isso hoje.

**D11 — Pedido que os comandos da skill não cobrem** (decisão do responsável em 09/11).
- A skill prefere os comandos que cita. Se o pedido precisar de outro, ela confere a ajuda (`sen --help` e `sen <comando> --help`). Se não houver comando, ela diz ao usuário que o `sen` não faz isso hoje e para, sem inventar comando nem opção.
- Um comando achado na ajuda roda sem perguntar só se ele só lê. Na explore, um comando que grava não roda. Na developer, ele roda depois de perguntar ao usuário.
- É proibido chamar a API do Manager por fora da CLI, mesmo quando nenhum comando atende o pedido.

**D12 — Completude e governança fora das duas skills** (decisão do responsável em 09/11).
- Completude, estágio e veredito da governança dependem do Adaptive Governance, que nem todo cliente tem. Sem ele, o endpoint de completude responde 403. Esses assuntos vão para uma skill própria, mais tarde.
- A explore não roda `sen completeness`. Ela mostra `completeness_score` e `stage_name` só quando o `sen list api --revisions` os traz, e não fala deles quando vêm nulos. Perguntas sobre o mínimo, as sugestões ou como subir a nota recebem a resposta de que não são desta skill.
- A developer resume a conformidade com a régua depois da gravação na Draft, e a governança e a completude só quando vierem no resultado do `sen validate`.
- Alternativa: manter o `sen completeness` na explore e tratar o erro. Rejeitada porque o cliente sem AG veria uma recusa a cada pergunta, e o comando traduz o 403 como revisão inexistente, o que confunde.

## Risks / Trade-offs

- [O agente pula a confirmação] → A skill explica o porquê da confirmação. O pedido de permissão da ferramenta e as guardas da CLI continuam valendo.
- [Pedido misto aciona a skill errada] → D2 põe os pedidos mistos na developer, e o teste de acionamento cobre esses pedidos.
- [Pergunta sobre o repositório cai numa skill que escreve] → A developer responde sem editar e só entra no ciclo de mudança se o usuário pedir (D2).
- [A gravação vai para o Manager errado] → A skill mostra a revisão alvo antes de pedir a confirmação e lembra que o destino é o Manager da sessão aberta.
- [A skill desatualiza com a CLI] → A skill não copia regras de domínio. Quando um comando citado mudar de opção, os casos de teste da skill rodam de novo.
- [Mudança num componente compartilhado afeta outras rotas] → A developer procura os usos do `$ref` antes e pergunta (requisito "Componente compartilhado").
- [`-o json` com a confirmação do `validate`] → Hoje a confirmação vem num quadro de texto. A tarefa 1.2 verifica o que o `validate` imprime ao receber `y` pela entrada com `-o json`, antes de a skill depender disso.

## Migration Plan

Não há migração: nada muda na CLI. Para reverter, basta remover a pasta `skills/`.
