# CLI `sen` — Funcionalidades implantadas

Visão funcional da CLI do orquestrador APIOps: o que cada comando entrega,
as regras de comportamento e as decisões que sustentam o desenho atual.

Última atualização: **2026-09-29**.

---

## Visão geral

| Comando | Para que serve |
|---|---|
| `sen login` | Autentica o usuário e abre uma sessão local reaproveitada pelos demais comandos |
| `sen list api` | Consulta o catálogo de APIs do API Manager e detalha as revisões de uma API |
| `sen completeness` | Mostra o nível de completude de uma revisão de API frente ao mínimo exigido |
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
usuário descobre o **ID da revisão** usado no `sen completeness`.

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

## Limitações conhecidas e próximos passos

- **Mínimo de completude dinâmico:** hoje fixo em 70%; o objetivo é ler o
  requisito real configurado em cada estágio do workflow de governança.
- **Modo verboso (`--verbose` / `-v`):** já aceito pela CLI, mas ainda sem
  efeito.
- **Ciclo completo de APIOps via CLI:** as etapas de composição, validação,
  planejamento e aplicação de APIs ainda não estão expostas como comandos;
  estão previstas como próximos comandos da CLI.
