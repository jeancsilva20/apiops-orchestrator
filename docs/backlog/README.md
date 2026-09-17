# Backlog de Débitos Técnicos e Pendências

Última atualização: **2026-09-16**.

Esta pasta existe para **registrar e acompanhar o backlog de débitos técnicos, melhorias e pendências** identificados ao longo do desenvolvimento do `apiops-orchestrator`.

## Qual é o propósito?

Durante o desenvolvimento, decisões pragmáticas precisam ser tomadas: simplificações temporárias, código provisório, casos não cobertos, gaps de testes, workarounds e alterações adiadas por falta de tempo ou por dependerem de fatores externos. Estes itens **não devem se perder** — são registrados aqui para serem tratados em algum momento futuro, quando houver capacidade ou desbloqueio do fator externo.

Em resumo, a pasta serve como:

- **Registro centralizado** de débitos técnicos ("tech debt"), workarounds temporários e melhorias propostas;
- **Memória de trabalho**: evita que decisões adiadas se esqueçam conforme o projeto avança;
- **Insumo para planejamento**: os itens desta pasta alimentam discussões de backlog/delivery (cards no Jira, refinamentos, etc.).

## O que registrar aqui?

- Débitos técnicos (ex.: duplicação de lógica, código legado que precisa ser substituído);
- Falta de cobertura de testes ou de documentação para partes já entregues;
- Simplificações temporárias adotadas sob pressão de prazo, mas que devem ser revisitadas;
- Melhorias propostas que não entram no escopo da iteração atual;
- Itens bloqueados por dependência externa, com indicação do fator de desbloqueio.

## Como registrar?

Cada item vira um arquivo `.md` nesta pasta. Sugestão de convenção de nome:

```
NNN-tema-descricao.md        (ex.: 001-refatorar-coleta-de-token.md)
```

Conteúdo mínimo recomendado por item:

- **Título/resumo** do débito ou melhoria;
- **Origem** (em qual tarefa/feature surgiu);
- **Impacto** (o que acontece enquanto o item não for resolvido);
- **Critério de resolução** (como saber que está "pago");
- **Prioridade/status** (`todo` / `doing` / `done` / `blocked` — indicar o desbloqueio se aplicável).

## Regras gerais

- Nenhum débito é registrado direto no código sem ao menos um item aqui equivalente.
- Débitos ligados a decisões de arquitetura podem gerar um ADR próprio (ver [`adr/`](../adr/)); neste caso, faça a referência cruzada.
- Quando um item for resolvido, marque como `done` mantendo o registro (histórico) até eventual limpeza acordada pelo time.
