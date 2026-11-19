# Estado atual do repositório

Retrato do `apiops-orchestrator` em **2026-11-19**: o que está em cada branch, o que já foi entregue e o que falta.

## Branches

### Visão geral

| Branch | Papel |
|---|---|
| `feat/executable` | Versão estável, a que é entregue aos clientes |
| `feat/skills` | Skills para LLMs e comando `sen schema` (APIOPS-125) |
| `feat/sen-sync` | Comando `sen sync` (APIOPS-122) |
| `feat/detect-adaptive-governance` | Cliente sem Adaptive Governance; já contém a `feat/sen-sync` |

### `feat/executable` — versão estável

É a branch de onde saem os pacotes do `sen` entregues aos clientes.

Ela faz o papel de estável porque a `main` e a `develop` ficaram em um estado antigo, com muitas diferenças para o
código atual. Enquanto não se decide o que fazer com as duas, a `feat/executable` é a referência.

Já reúne os comandos `login`, `whoami`, `list api`, `completeness`, `validate`, `publish` e `deploy`, e os scripts
de geração do executável. Em relação às últimas entregas ao ECAD, tem ajustes novos, entre eles:

- `sen whoami`, que mostra os dados da sessão aberta;
- verificação das `apiTags` no `validate`: atributo fora do catálogo, sem tag ou sem tags no catálogo vira erro;
- checagem do time APIOps, do escopo `write` e da credencial da esteira na sessão.

**Pendência:** decidir o destino da `main` e da `develop`.

### `feat/skills` — skills para LLMs (APIOPS-125)

Origem: em conversas com a MAG surgiu a necessidade de LLMs consumirem os comandos da CLI, para tirar do
desenvolvedor a responsabilidade de conhecê-los. O card pede skills para demonstração ao cliente.

O que a branch tem:

- duas skills em `skills/`: `sen-explore` e `sen-api-developer`;
- o comando `sen schema`, que mostra os schemas de repositório esperados pela versão do orquestrador em uso. É o
  comando que a LLM consulta para saber como montar e editar o repositório da API;
- os builders do executável ajustados para incluir os schemas junto do `sen`, sem o que o `sen schema` não
  funciona no pacote entregue.

Pendências:

- validar se as skills serão disponibilizadas como estão, voltadas à CLI, ou se haverá outra versão para consumo
  por HTTP/MCP (relacionado a [`backlog/002`](backlog/002-entrada-e-saida-json-via-rest.md));
- uso via CLI com o cliente;
- incluir o `sen sync` nas skills;
- criar mais skills conforme a necessidade, mantendo responsabilidade única;
- atualizar com a `feat/executable`, que recebeu commits depois (`sen whoami`, documentação, pacote por cliente).

### `feat/sen-sync` — comando `sen sync` (APIOPS-122)

O `sen sync` está implementado conforme a especificação do card: traz uma API do Manager para o repositório e, com
`--check`, confere se os dois continuam iguais. Foi testado em vários fluxos, com interceptors diferentes e tipos
de herança diferentes, e está funcionando.

A branch também trouxe os modelos tipados do Manager e removeu o versionador legado.

Pendências:

- entrega ao cliente;
- merge com a versão estável (`feat/executable`).

### `feat/detect-adaptive-governance` — (APIOPS-124)

Detecta, a cada execução, se o cliente contratou o Adaptive Governance e oculta ou ignora o que depende dele.

Esta branch já recebeu a `feat/sen-sync` inteira e a `feat/executable` até o commit `7db5b9d`. Por cima disso tem
três commits próprios: a detecção, a ocultação dos avisos e citações de governança, e o `sen sync` sem `apiTags`
quando o cliente não tem o Adaptive Governance.

Na prática é a branch mais completa: um merge dela na `feat/executable` leva junto o `sen sync`.

**Status:** testado e sem impacto para o ECAD, que é cliente com Adaptive Governance. Ainda não houve teste em
cliente sem Adaptive Governance, por falta de um ambiente assim.

Pendências:

- aguardar as configurações no ambiente da MAG para testar em cliente sem Adaptive Governance;
- merge com a `feat/executable`.

## Pendências do projeto

### 1. Entrada e saída em JSON por REST — prioritário

Registrado em [`backlog/002`](backlog/002-entrada-e-saida-json-via-rest.md). Além da CLI, o orquestrador passa a
receber requisições REST em JSON e a responder em JSON, com os mesmos casos de uso. O documento traz o que já está
pronto, o que precisa se adequar, as rotas propostas e as decisões tomadas e em aberto.

### 2. Solução de débito técnico em validate, publish e deploy

Registrado em [`backlog/001`](backlog/001-comandos-nos-modelos-do-manager.md). O `sen sync` já usa os modelos
tipados do Manager; os outros comandos ainda convertem de volta para dicionário. O item migra os três comandos de
escrita e remove a ponte transitória. Depende de a `feat/sen-sync` estar na estável, porque os modelos nasceram
nela.

### 3. Revisão da branch de navegação do Manager

Há uma branch só no remoto, `ccr-489d3c40-kwd87n` (Jean Silva, 2026-11-01), que acrescenta à CLI a consulta ao
ambiente do Manager sem repositório local. Ela foi construída sobre a `feat/claude-plugin` e ainda não foi
revisada.

O que ela traz, pelos commits e pelo código:

- `sen get` para API, recursos, interceptors, swagger, app, plano, ambiente, time, usuário, papel, workflow,
  governança, impacto, tipos de interceptor, trace e analytics;
- `sen list` ampliado, incluindo chamadas (`sen list calls`);
- `sen export api`;
- listagens de variáveis sempre mascaradas e `sen reveal variable`;
- os arquivos `COMMANDS.md` e `PLANO-NAVEGACAO.md` na raiz.

São cerca de 9 mil linhas em 31 arquivos, com testes. A branch parte de um ponto da `feat/executable` anterior ao
`sen whoami`, à checagem de acesso da sessão e à verificação das `apiTags`.

Pendências:

- **Estrutura do repositório:** a branch cria um conceito de "navegação" que não existe na estrutura do projeto,
  com um módulo de CLI à parte (`navigation_cli.py`) e um serviço único (`ApiNavigationService`) para todos os
  comandos. Os comandos devem ficar no adapter de CLI, como os demais, e a lógica deve ser dividida em serviços por
  assunto, em vez de um serviço para tudo. A divisão dos serviços fica a definir.
- **Controle de acesso:** As listagens do
  tenant (apps, planos, tokens, usuários, times, papéis, variáveis), as chamadas e o `sen reveal variable` não possuem verificações de acesso do usuário, com isso qualquer usuário conseguiria acessar a qualquer uma dessas listagens sem mesmo ter acesso a elas no manager. Necessária a checagem de permissionamento do usuário para executar esses passos, bem como a verificação da viabilidade de nem exibir esses comandos no help caso o usuário não tenha acesso a ele.
- **Modelos tipados:** os métodos novos do port devolvem o JSON do Manager como dicionário, e o serviço e o domínio
  leem as chaves da API direto. Adequar aos modelos tipados que nasceram na `feat/sen-sync`, na mesma linha do
  [`backlog/001`](backlog/001-comandos-nos-modelos-do-manager.md).
- **Padrões do projeto:** docstrings em inglês, commits sem escopo, e `COMMANDS.md` e `PLANO-NAVEGACAO.md` dentro
  de `docs/`.
- atualizar a branch com a `feat/executable` e aplicar a checagem de acesso da sessão, que entrou na estável
  depois;
- decidir se entra na versão estável, inteira ou em partes.

A `feat/claude-plugin` em si tem três commits próprios, todos de 2026-11-01: um ajuste que remove aspas das
variáveis de autenticação vindas do ambiente e dois de documentação. Entram na mesma revisão.

### 4. Pendências das branches

Detalhadas na seção "Branches": o destino da `main` e da `develop`, a entrega e o merge do `sen sync`, o teste da
detecção de Adaptive Governance em cliente sem o produto e as definições das skills.
