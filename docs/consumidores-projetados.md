# Consumidores projetados da CLI `sen`

Quem vai usar a CLI do orquestrador APIOps, como cada um vai usá-la e quais
decisões de desenho existem por causa deles.

Complementa [comandos-cli.md](comandos-cli.md), que descreve **o que** a CLI
já faz. Este documento explica **para quem** e **por quê**.

Última atualização: **2026-09-29**.

> **Legenda de status**
> - ✅ **Implantado** — já existe e funciona hoje.
> - 🔶 **Projetado** — direção acordada, ainda não construído.
> - ❓ **Em aberto** — depende de decisão.

---

## 1. Os consumidores

| Consumidor | Quem é | Como dispara a CLI | Status |
|---|---|---|---|
| **Esteira** | Pipelines de CI/CD que publicam e governam APIs | Automaticamente, a cada execução do pipeline | 🔶 Projetado |
| **Desenvolvedor** | Pessoa que desenvolve ou mantém APIs | Manualmente, no próprio computador | ✅ Implantado (via Python) · 🔶 Projetado (via executável) |
| **Agente LLM** | Assistente de IA que opera a CLI em nome de uma pessoa | Sob demanda, a pedido do usuário | 🔶 Projetado |

A premissa central é **uma única CLI para os três consumidores**. Não há
uma ferramenta para a esteira e outra para o desenvolvedor: o mesmo comando
responde a todos. Por isso a CLI precisa ser boa para humanos e para
máquinas ao mesmo tempo.

Os três se diferenciam em dois eixos:

- **Como disparam:** o desenvolvedor e o agente usam a CLI localmente e sob
  demanda; a esteira usa em ambiente automatizado e descartável.
- **O que precisam da saída:** o desenvolvedor lê a tela; a esteira e o
  agente interpretam dados estruturados.

Por isso o agente LLM, embora **dispare** como um desenvolvedor, **precisa**
de quase tudo o que a esteira precisa.

---

## 2. Esteira (CI/CD)

**Quem é:** o pipeline que valida, publica e governa APIs sem intervenção
humana. É o consumidor mais exigente em previsibilidade.

**Como obtém a CLI:** instalada no ambiente do pipeline a cada execução
(ou numa imagem pronta). 🔶

**Como se autentica:** o pipeline monta o `.env` a partir dos seus secrets,
e a CLI lê as credenciais dele. ✅ A CLI aceita credenciais de três origens,
nesta ordem de prioridade: variáveis de ambiente do processo, arquivo `.sen`
e arquivo `.env`. Assim a mesma CLI serve ao desenvolvedor (`.sen`) e à
esteira (`.env` ou variáveis de ambiente), sem nenhum ajuste.

**Como executa:** nada interativo, uma chamada por etapa, sessão aberta a
cada execução (o ambiente é descartado ao final).

**O que espera da saída:**

- Dados estruturados (JSON/YAML) em formato estável;
- Código de saída que indique sucesso ou falha, usado como gate do pipeline;
- Log legível, sem animações.

**Decisões já implantadas que atendem a esteira:**

| Decisão | Por que importa para a esteira |
|---|---|
| ✅ Saída JSON/YAML | O pipeline interpreta os dados sem ler a tela |
| ✅ Formato de saída versionado | Evoluções da CLI não quebram pipelines existentes |
| ✅ Animações viram linha única fora do terminal | Logs de CI limpos |
| ✅ Códigos de saída previsíveis | Falha da CLI interrompe o pipeline |
| ✅ Validação de parâmetros antes de chamar a plataforma | Erro de configuração falha rápido e barato |
| ✅ Credenciais aceitas via `.env` e variáveis de ambiente | O pipeline injeta os secrets sem precisar de arquivo próprio da CLI |

**Lacunas:**

- ❓ Completude abaixo do mínimo **não** gera código de erro hoje: o comando
  mostra o alerta e termina com sucesso. A esteira não consegue bloquear
  uma API incompleta só pelo código de saída (D3);
- 🔶 Comandos do ciclo APIOps (compor, validar, planejar, aplicar), que são
  o uso principal da esteira, ainda não existem.

---

## 3. Desenvolvedor

**Quem é:** quem cria ou mantém APIs e quer consultar o catálogo, ver
revisões e checar a completude antes de avançar na governança.

**Como obtém a CLI:**

- ✅ **Hoje:** clonando o repositório e instalando com Python;
- 🔶 **Projetado:** baixando um **executável único** com a CLI já
  empacotada. O desenvolvedor não precisa do repositório nem de Python:
  baixa, configura o seu `.sen` e roda os comandos.

**Como se autentica:** configura as próprias credenciais no `.sen` uma
vez e roda `sen login`. A sessão fica salva e é reaproveitada até expirar. ✅

**Como executa:** interativo, no terminal, comando a comando.

**O que espera da saída:** tabelas e painéis legíveis, mensagens de erro
que digam o que fazer a seguir.

**Decisões já implantadas que atendem o desenvolvedor:**

| Decisão | Por que importa para o desenvolvedor |
|---|---|
| ✅ Login único com sessão salva | Não precisa se autenticar a cada comando |
| ✅ Tabelas, painéis e barra de completude | Leitura rápida no terminal |
| ✅ Mensagens orientadas | Ex.: sem ID da revisão, a CLI indica como descobri-lo |
| ✅ Degradação para ASCII | Funciona em qualquer terminal, inclusive o padrão do Windows |
| ✅ Credenciais em arquivo próprio da CLI | Separa segredos da configuração geral |

**Lacunas do executável (🔶):**

- ❓ Onde ficam o `.sen` e a sessão. Hoje ficam dentro das pastas do
  projeto, o que não funciona para um executável distribuído (D2);
- ❓ Plataformas suportadas: só Windows, ou também Mac e Linux?
- ❓ Como o desenvolvedor sabe que há versão nova e como atualiza;
- ❓ Assinatura do executável: executáveis sem assinatura costumam ser
  bloqueados por antivírus corporativos.

---

## 4. Agente LLM

**Quem é:** um assistente de IA (por exemplo, um agente de código) que
executa a CLI em nome de uma pessoa: consulta APIs, avalia completude e,
no futuro, opera o ciclo APIOps.

**Como obtém a CLI:** a mesma do desenvolvedor, na máquina dele. 🔶

**Como se autentica:** usa a sessão aberta pelo desenvolvedor. O agente
**não deve ter acesso às credenciais**, só à sessão já aberta. 🔶

**Como executa:** não interativo, lendo a saída estruturada, encadeando
comandos (ex.: listar revisões → pegar o ID → consultar completude).

**O que espera da saída:**

- Dados estruturados em formato estável, para não precisar interpretar a tela;
- Mensagens de erro que digam **o que fazer**, porque o agente usa a
  mensagem para decidir o próximo passo;
- Nenhuma pergunta interativa, que travaria o agente.

**Decisões já implantadas que atendem o agente:**

| Decisão | Por que importa para o agente |
|---|---|
| ✅ Saída JSON/YAML com formato versionado | O agente lê dados, não a tela |
| ✅ Mensagens orientadas | O agente sabe qual comando rodar a seguir |
| ✅ Nenhum token exibido na tela | O agente não vê segredos na saída |
| ✅ Comandos atuais apenas consultam | Hoje não há risco de alteração indevida |

**Lacunas:**

- 🔶 Guardrails para comandos que **alteram** a plataforma, quando existirem
  (planejar/aplicar): separação clara entre consulta e alteração, modo de
  simulação (dry-run) e confirmação explícita (D4);
- 🔶 Um guia de uso da CLI voltado a agentes: quais comandos existem, em que
  ordem usá-los, como interpretar a saída;
- 🔶 No futuro, avaliar expor as mesmas funções como servidor MCP. Para a
  primeira versão, a CLI com saída estruturada é suficiente.

---

## 5. Matriz consumidor × requisito

| Requisito | Esteira | Desenvolvedor | Agente LLM |
|---|---|---|---|
| **Interatividade** | Nenhuma | Total | Nenhuma |
| **Formato de saída** | JSON/YAML | Texto | JSON/YAML |
| **Estabilidade do formato** | Crítica | Baixa | Crítica |
| **Origem das credenciais** | `.env` montado a partir dos secrets ✅ | Arquivo `.sen` ✅ | Sessão do desenvolvedor 🔶 |
| **Sessão** | Nova a cada execução | Salva e reaproveitada | Reaproveita a do desenvolvedor |
| **Código de saída** | Gate do pipeline | Pouco relevante | Sinal de sucesso/falha |
| **Mensagens de erro** | Para log | Para pessoa | Para decisão do próximo passo |
| **Distribuição** | Instalação no pipeline 🔶 | Repositório ✅ / executável 🔶 | Igual ao desenvolvedor |
| **Segurança** | Secrets isolados | Credencial pessoal | Sem acesso a credenciais; guardrails em alterações |

---

## 6. Decisões em aberto

| # | Decisão | Consumidor afetado | Opções |
|---|---|---|---|
| **D2** | Onde ficam `.sen` e sessão no executável | Desenvolvedor, Agente | (a) pasta do usuário; (b) ao lado do executável; (c) caminho configurável |
| **D3** | Completude abaixo do mínimo deve falhar o comando? | Esteira, Agente | (a) sempre falha; (b) falha só com um parâmetro explícito (ex.: modo "estrito"); (c) nunca falha, e a esteira lê a nota na saída estruturada |
| **D4** | Guardrails para comandos que alteram a plataforma | Agente, Esteira | Dry-run obrigatório antes de aplicar; confirmação explícita; separação entre comandos de consulta e de alteração |
| **D5** | Plataformas e distribuição do executável | Desenvolvedor | Sistemas suportados, canal de distribuição, atualização e assinatura |
