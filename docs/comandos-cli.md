# CLI `sen` — Funcionalidades implantadas

Visão funcional da CLI do orquestrador APIOps: o que cada comando entrega,
as regras de comportamento e as decisões que sustentam o desenho atual.

Última atualização: **2026-11-13**.

---

## Visão geral

| Comando | Para que serve |
|---|---|
| `sen login` | Autentica o usuário e abre uma sessão local reaproveitada pelos demais comandos |
| `sen whoami` | Mostra os dados da sessão aberta (perfil, usuário, grupos, escopo e validade), sem tokens |
| `sen list api` | Consulta o catálogo de APIs do API Manager e detalha as revisões de uma API |
| `sen completeness` | Mostra o nível de completude de uma revisão de API frente ao mínimo exigido |
| `sen deploy` | Coloca no ar, no ambiente da esteira, a revisão fixa correspondente (só na esteira) |
| `sen sync` | Traz uma API do Manager para o repositório (carga inicial) ou confere se repositório e Manager continuam iguais (`--check`) |
| `sen --version` / `sen --help` | Versão da CLI e ajuda geral |

Fluxo típico de uso:

1. `sen login` — abre a sessão;
2. `sen list api` — localiza a API desejada;
3. `sen list api --id <ID> --revisions` — descobre a revisão a analisar;
4. `sen completeness --id <ID> --revision <REV ID>` — avalia a completude.

---

## Decisões transversais

Valem para todos os comandos.

- **Sessão única e local.** O login é feito uma vez e a sessão fica salva na
  máquina do usuário. Todos os comandos que consultam a plataforma exigem essa
  sessão; sem ela, orientam o usuário a rodar `sen login`.
- **Credenciais de múltiplas origens.** A CLI aceita credenciais de três
  origens, nesta ordem de prioridade: variáveis de ambiente do processo, o
  arquivo de configuração próprio da CLI (`.sen`) e o `.env` do projeto. O
  desenvolvedor usa o `.sen`; a esteira monta o `.env` a partir dos seus
  secrets.
- **Cada um vê só as APIs a que tem acesso.** A CLI aplica a visibilidade da
  API (organização, grupo ou usuário) em todo comando que recebe o id de uma
  API. Uma API que o usuário não enxerga responde como se não existisse. A
  esteira enxerga todas.
- **Cliente sem Adaptive Governance.** A CLI descobre sozinha, a cada
  execução, se o cliente contratou o Adaptive Governance; não há configuração
  para isso. Sem ele, nada trava por governança: o que é do Adaptive
  Governance (governança do stage, completude, `apiTags`) é ignorado ou
  ocultado, e só o `sen completeness` recusa, porque a completude não existe
  sem ele. Se não der para saber, a CLI age como se ele estivesse contratado.
- **Validação antes de ir à rede (fail fast).** Combinações inválidas de
  parâmetros são recusadas localmente, com mensagem clara, sem gastar
  chamada à plataforma.
- **Saída para humanos e para máquinas.** Os comandos de consulta têm modo
  texto (padrão, com tabelas e painéis) e modos estruturados **JSON** e
  **YAML**, voltados a pipelines e automações. No modo estruturado a saída
  contém só os dados, sem elementos visuais.
- **Funciona em qualquer terminal.** Em terminais sem suporte a caracteres
  especiais, a apresentação degrada automaticamente para ASCII.
- **Compatível com CI.** Em execução não interativa (logs, pipelines), as
  animações de espera viram uma linha única de status.
- **Códigos de saída previsíveis.** `0` em sucesso; código de erro diferente
  de zero em falha, permitindo uso em scripts.

---

## `sen login`

**Função:** autenticar o usuário na plataforma e abrir a sessão da CLI.

**Comportamento:**

- Usa as credenciais configuradas para a CLI e obtém uma sessão válida;
- Salva a sessão localmente para os demais comandos;
- Ao final, exibe um painel com os dados da sessão:
  - **Superadmin:** perfil, escopo de acesso e validade da sessão
    (não exibe identidade pessoal nem tokens);
  - **Demais perfis:** usuário, e-mail e validade da sessão.

| Parâmetro | Função |
|---|---|
| `--output` / `-o` | Formato: texto (padrão), JSON ou YAML |

Em JSON/YAML a saída é só o documento `apiops.sen-login/v1`, sem logo nem
animação, com os mesmos dados do painel: `user` (nome e e-mail) para os demais
perfis; `profile` e `scope` para o superadmin; e `expiresAt` em UTC.

**Decisão:** nenhum token é mostrado na tela, em nenhum perfil e em nenhum
formato.

---

## `sen whoami`

**Função:** mostrar quem está logado, com os dados da sessão aberta pelo
`sen login`.

**Comportamento:**

- Lê só a sessão local: não acessa a rede e não exige o `.sen`;
- Exibe um painel com os dados da sessão:
  - **Superadmin:** perfil, escopo e validade da sessão;
  - **Demais perfis:** usuário e e-mail, perfil, grupos, escopo e validade da
    sessão;
- Sem sessão válida (ausente, expirada ou ilegível), orienta o `sen login` e
  termina com código `1`.

| Parâmetro | Função |
|---|---|
| `--output` / `-o` | Formato: texto (padrão), JSON ou YAML |

Em JSON/YAML a saída é só o documento `apiops.sen-whoami/v1`: `profile`,
`scope` e `expiresAt` em UTC em todos os perfis, mais `user` (nome e e-mail) e
`groups` para os demais perfis. Sem sessão, o documento traz só
`authenticated: false`.

**Decisões:**

- Nenhum token é mostrado, em nenhum perfil e em nenhum formato.
- A validade é a gravada na sessão. O `whoami` não pergunta ao servidor se o
  token ainda vale.

---

## `sen list api`

**Função:** consultar as APIs cadastradas no API Manager e, para uma API
específica, listar suas revisões.

**Listagem de APIs** — colunas: ID, nome, versão, base path e última revisão.

| Parâmetro | Função |
|---|---|
| `--id` | Mostra uma única API pelo seu ID no Manager |
| `--query` | Busca por nome ou descrição |
| `--limit` | Quantidade de itens exibidos (padrão 10) |
| `--offset` | A partir de qual item exibir (padrão 0) |
| `--revisions` / `-r` | Troca a listagem pelas revisões da API informada em `--id` |
| `--output` / `-o` | Formato: texto (padrão), JSON ou YAML |

**Detalhe de revisões** (`--id` + `--revisions`) — colunas: número da
revisão, ID da revisão, estágio, ambientes e completude. É por aqui que o
usuário descobre o **ID da revisão** usado no `sen completeness`. Quando o
cliente não tem o Adaptive Governance contratado, as colunas de estágio e
completude não aparecem; no JSON/YAML, `stage_name` e `completeness_score`
saem nulos.

**Regras:**

- `--id` e `--query` não podem ser usados juntos;
- `--revisions` exige `--id`;
- `--limit` precisa ser maior que zero e `--offset` não pode ser negativo;
- Sem filtros, a tela informa os padrões aplicados (10 itens a partir do 0).

---

## `sen completeness`

**Função:** mostrar o quanto uma revisão de API está completa frente ao
mínimo exigido pela governança, e o que falta melhorar.

| Parâmetro | Função |
|---|---|
| `--id` | ID da API no Manager (**obrigatório**) |
| `--revision` | ID da revisão (**obrigatório** — é o ID da revisão, não o número dela) |
| `--score-only` | Mostra só a nota e a barra, sem as sugestões |
| `--output` / `-o` | Formato: texto (padrão), JSON ou YAML |

Sem `--id` ou `--revision`, a CLI orienta o usuário a descobrir os IDs com
`sen list api --id <ID> --revisions`.

**O que é exibido:**

- **Identificação:** nome e versão da API, revisão analisada e, quando
  disponíveis, contexto, grupo e responsável;
- **Barra de progresso** proporcional à nota, com a marca do mínimo exigido;
- **Alerta** quando a nota está abaixo do mínimo, informando quantos pontos
  faltam;
- **Sugestões de melhoria** numeradas (ou aviso de que não há sugestões).

**Códigos de saída:** `0` sucesso · `1` parâmetro ausente ou inválido · `2`
recusa ou falha da plataforma · `3` o cliente não tem o Adaptive Governance
contratado ("A checagem de completude não está disponível: cliente não
possui o Adaptive Governance contratado.").

**Decisões:**

- **Fonte dos dados:** a completude é lida diretamente da Governança
  Adaptativa, que é a fonte primária da informação;
- **Mínimo exigido fixo em 70%** nesta versão, conforme a regra normativa de
  governança vigente. A plataforma ainda não expõe esse valor por API/estágio;
- **Fidelidade ao dado original:** valores fora da faixa 0–100% são ajustados
  apenas na barra visual; a saída estruturada preserva o valor recebido;
- **Contrato de saída versionado:** a saída JSON/YAML segue um formato
  versionado, para que consumidores automatizados não quebrem com evoluções.

---

## `sen deploy`

**Função:** colocar no ar, num ambiente do API Manager, a revisão fixa que a
CI acabou de gravar com o `sen publish`. Não grava conteúdo na revisão.

**Quem roda:** só a esteira de CD — DEV e HML logo após a CI, PRD depois da
aprovação de deploy. Na máquina do dev o comando recusa, com uma mensagem
que não cita o modo de execução nem as variáveis da esteira.

| Parâmetro | Função |
|---|---|
| `--repo` | Repositório da API (padrão: diretório atual); só o `api-basic-info.yaml` é lido |
| `--output` / `-o` | Formato: texto (padrão), JSON ou YAML |

| Variável | Função |
|---|---|
| `EXECUTION_MODE` | Precisa ser `pipeline` |
| `TARGET_REVISION_NUMBER` | Número da revisão que vai para o ar (2 = DEV, 3 = HML, 4 = PRD); 1 é recusado |
| `TARGET_ENVIRONMENT_ID` | Id, no Manager, do ambiente que recebe o deploy |

**Antes do deploy, o comando recusa sem colocar nada no ar quando:**

- o manifesto não existe, não tem `spec.id` ou a `version`/`basePath` divergem do Manager;
- a API não tem a revisão do número informado (a mensagem lista as disponíveis);
- a API não está ligada ao ambiente informado (a mensagem lista os ligados);
- a governança do stage da revisão não libera: ambiente fora dos permitidos,
  completeness abaixo do exigido ou atributo obrigatório ausente. Todos os
  critérios violados aparecem juntos. Quando o cliente não tem o Adaptive
  Governance contratado, esses critérios não se aplicam e o bloco de
  governança sai vazio.

**Resultado:** API, revisão, ambiente, governança avaliada, o que estava no ar
antes e o que ficou no ar depois. O deploy é conferido relendo a API. Em
JSON/YAML a saída é o documento `apiops.sen-deploy/v1`; quando o deploy é
tentado e falha, o documento sai mesmo assim, com `deployment.status = FAILED`.

**Códigos de saída:** `0` sucesso · `1` configuração, recusa da plataforma ou
falha técnica · `3` bloqueio de governança.

**Decisões:**

- O ambiente é informado pelo **id**, que é do tenant e serve a todas as APIs;
- O deploy é feito mesmo quando a revisão já está no ar: é ele que leva ao
  gateway o conteúdo que o `publish` acabou de gravar;
- Rollback, undeploy, smoke test e tag ficam fora do comando.

---

## `sen sync`

**Função:** trazer uma API que já existe no API Manager para o repositório Git
da API, na estrutura de arquivos do APIOps (carga), e, depois, conferir se o
repositório e o Manager continuam espelho um do outro (`--check`). Substitui o
protótipo `extrair_estrutura.py` e o `sen version sync` previsto no memory bank.

```
sen sync --id <api-id> --revision <n> [--repo <pasta>] [--template <id>] [--check] [-o text|json|yaml]
```

| Parâmetro | Função |
|---|---|
| `--id` | Id da API no Manager. Se o `spec.id` do `api-basic-info.yaml` já está preenchido, os dois precisam ser iguais |
| `--revision` / `-r` | Número da revisão (`revisionNumber`, como aparece no Manager) que vai para o repositório |
| `--repo` | Repositório local de destino (padrão: diretório atual) |
| `--template` | Id da API template, gravado em `spec.template`. Conferido no Manager antes da gravação (inexistente ou invisível: exit 3). Sem a opção, o valor que já está no arquivo é mantido. Não se aplica ao `--check` |

Em cliente sem Adaptive Governance, a carga grava o `api-basic-info.yaml` sem `apiTags` e o
`--check` não compara esse campo; o resto é igual.
| `--check` | Só compara o repositório com a revisão informada; não grava nada. Mostra só as diferenças, e `apiTags` é comparado como conjunto |
| `--output` / `-o` | Formato: texto (padrão), JSON ou YAML |

**Carga.** Roda na raiz do repositório da API e só faz `GET` no Manager: lê a
API, aplica a regra de visibilidade da sessão, procura a revisão pelo número,
lê o estado completo dela e o swagger (só OpenAPI 3; Swagger 2.0 é recusado).
Gera `api-basic-info.yaml`, `all.yaml`, `components.yaml` e
`resources/<slug>/{resource.yaml,<método>_<path>.yaml}` em memória e grava tudo
de uma vez: a área gerenciada é substituída por inteiro, o `spec.template` do
arquivo existente é preservado e o `spec.id` é gravado com o id da API. Arquivos
fora da área gerenciada não são tocados. Nada é escrito até todas as leituras
terem passado, e nenhuma falha deixa árvore parcial.

Passo a passo da entrada de uma API no APIOps, uma branch por vez e antes de
ativar as proteções: na `main`, `sen sync --id <api-id> --revision 4` e commit;
criar a `develop` a partir da `main`, `sen sync --revision 2` e commit; criar a
`release` a partir da `main`, `sen sync --revision 3` e commit; push das três
e ativação das proteções. Nesta versão o comando não consulta o Git: a revisão
é escolhida por quem roda, e a correspondência branch × revisão fica a cargo de
quem conduz o onboarding.

**Verificação.** `sen sync --check --revision <n>` lê a árvore local para o
modelo do Manager e compara com a revisão informada por conteúdo, não por
texto: comentários, ordem de chaves e formatação do YAML não contam. Cada
diferença sai com arquivo, campo, valor no repositório e valor no Manager.
Diferença nem sempre é problema (o repositório fica à frente entre o merge e a
publicação); quem interpreta é o time, e a correção segue pelo fluxo normal.

**Contrato OpenAPI.** O swagger da revisão entra na mesma árvore: as seis seções
de `components` em `components.yaml` (escrito sempre, `{}` quando vazio),
`contact`, `tags` e `security` da raiz no `api-basic-info.yaml`, e em cada
arquivo de operação `summary`, `operationId`, `tags`, `security`, `parameters`,
`requestBody` e `responses` da rota, com os parâmetros do path mesclados, `$ref`
de parâmetro expandido e chaves `x-*` removidas. Rota fora do swagger ou sem
`responses` fica sem esses campos, com aviso: o `sen validate` barra até o dev
declarar. O `--check` compara o contrato também.

**Códigos de saída:** `0` sucesso (no `--check`, sem diferença) · `1`
argumento ausente ou inválido, repositório ilegível ou falha técnica · `2` sem
sessão, token expirado ou recusado · `3` API inexistente ou fora da
visibilidade · `4` revisão inexistente, sem recursos ou com swagger que não é
OpenAPI 3 · `5` `spec.id`
diferente do `<api-id>` · `6` caminho longo demais ou erro de escrita · `7`
Manager inacessível · `8` o `--check` encontrou diferença.

Em JSON/YAML a saída é o documento `apiops.sen-sync/v1`: `api`, `revision` e,
na carga, `repository` (pasta absoluta da carga), `files` e `counts`; na verificação, `inSync` e
`differences[]`. Avisos (recursos homônimos, nome de arquivo truncado,
marcação de remoção fora do fluxo herdado, interceptor próprio igual a um
herdado, `$ref` inexistente, rota fora do swagger ou sem `responses`) saem em
`warnings[]` e nunca mudam o código de saída.

**Decisões:**

- O formato dos arquivos é o do orquestrador: strings numéricas (`"1000"`)
  ficam citadas, porque sem aspas o round-trip as transforma em inteiro. Os
  comentários são fixos e não citam nada que varie entre branches.
- Nunca `PUT` ou `POST` no Manager, nunca `add`, `commit` ou `push` no Git.
- A parte de Git da especificação (branch atual, aviso de revisão inesperada,
  recusa de carga já publicada no remoto) fica para uma próxima fase.

---

## Limitações conhecidas e próximos passos

- **Mínimo de completude dinâmico:** hoje fixo em 70%; o objetivo é ler o
  requisito real configurado em cada estágio do workflow de governança.
- **Modo verboso (`--verbose` / `-v`):** já aceito pela CLI, mas ainda sem
  efeito.
- **Ciclo completo de APIOps via CLI:** as etapas de composição, validação,
  planejamento e aplicação de APIs ainda não estão expostas como comandos;
  estão previstas como próximos comandos da CLI.
