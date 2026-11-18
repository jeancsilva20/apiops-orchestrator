## Why

O agente LLM é um consumidor projetado da CLI (`docs/consumidores-projetados.md`, seção 4), e o "guia de uso da CLI voltado a agentes" consta lá como lacuna. Sem esse roteiro, o agente não sabe que deve ler o schema antes de escrever um arquivo, que o `sen validate` grava na Draft do Manager, nem como chegar ao ID de uma revisão.

Com o `sen schema` (change `add-sen-schema`), o agente já tem o formato de cada arquivo. Falta o roteiro de uso, escrito como skill de agente.

## What Changes

- **Pasta `skills/` na raiz do orquestrador**, com duas skills no formato `SKILL.md`. Elas não entram no build: quem quiser usar copia a pasta da skill para a pasta de skills do agente.
- **`sen-explore`**: responde perguntas sobre o que está no Manager (APIs, revisões, ambientes, régua, Draft), sem mudar nada. Completude e governança ficam fora, porque dependem do Adaptive Governance.
- **`sen-api-developer`**: responde perguntas sobre os arquivos do repositório local da API (rotas, backends, interceptors) e aplica neles a mudança que o usuário pede (rota, response, timeout, backend, interceptors, apiTags, componentes).
  - Uma pergunta não vira mudança: a skill responde sem escrever.
  - Mudança sem risco é aplicada direto e aparece no resumo. Antes de uma mudança com risco, como um componente usado por outras rotas, mostra o plano com os riscos e espera o ok do usuário.
  - Escreve conforme o `sen schema` e confere com o `sen diag structure` e com o pré-check do `sen validate`, que não grava nada.
  - Só roda o `sen validate` que grava na Draft com a confirmação do usuário, depois de explicar os riscos.
- **Teste das skills pelo responsável**, com outro agente e pedidos reais. As skills não levam casos de teste por ora.
- **Nenhuma mudança na CLI.**

## Capabilities

### New Capabilities

- `sen-explore-skill`: roteiro do agente para consultar o Manager pela CLI, sem alterar nada.
- `sen-api-developer-skill`: roteiro do agente para responder sobre os arquivos do repositório da API e alterá-los no formato que a CLI aceita, com confirmação do usuário antes de escrever e antes de gravar na Draft.

### Modified Capabilities

Nenhuma.

## Fora do escopo

- Uma skill de governança, para completude, estágio e veredito. Eles dependem do Adaptive Governance, que nem todo cliente tem, e por isso ficam fora das duas skills (decisão do responsável em 09/11).
- A `sen-pipeline-triage`.
- A criação de API do zero. Quando entrar, fica na própria `sen-api-developer` (D9), não numa skill separada.
- Distribuir as skills como plugin ou gerá-las no build.
- Códigos de erro estáveis na CLI (descartados pelo responsável): a skill lê o texto das mensagens.

## Impact

- **Repositório do orquestrador:** pasta nova `skills/`, com o README de instalação e as duas skills. Nada muda em `src/`.
- **Dependência:** para usar as skills com o executável, o grupo 4 da `add-sen-schema` (schemas dentro do binário) precisa estar concluído.
- **Docs:** a lacuna do guia para agentes em `docs/consumidores-projetados.md` passa a apontar para as skills.
