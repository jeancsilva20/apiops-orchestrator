# CHANGELOG

Summary of recent changes in the project. Each item includes date, category, title and author.

## Recent History
- 2026-11-23 — Infra — "CI roda em pull request e em main (antes só em `release`): step Quality sem segredo com ruff, checagem de documentação, árvore de referência, suíte e piso de cobertura; `.github/workflows/quality.yml` criado porque os PRs acontecem no GitHub; o smoke do pipeline deixa de chamar `main.py` sem argumentos, que saía com 2 e matava o step antes do pytest" — Author: Jean Silva — Type: Infra
- 2026-11-23 — CLI/Docs — "Referência de comandos do README.md e do COMMANDS.md passa a ser gerada da árvore Typer (`scripts/gen_cli_docs.py`), com teste que falha se divergir: corrige 11 comandos com flag errada ou ausente (`--repo` de publish/deploy, `sen get environment --id` no lugar de `--env`, 7 flags de `list calls`, `--point`, `--no-headers`, `--top`, o `--id` obrigatório de `export api`) e documenta os 3 comandos de `sen diag`" — Author: Jean Silva — Type: Documentação
- 2026-11-23 — CLI — "`--verbose/-v` passa a dizer a verdade no `--help` (não altera a saída) e fica oculto nos 4 comandos onde é aceito e ignorado; continua aceito, para não quebrar script de esteira" — Author: Jean Silva — Type: Correção
- 2026-11-23 — Tests — "Contrato dos 44 comandos conferido pela árvore Typer: ajuda, `help=` das 148 opções, `-o` em toda folha, `--help` das 50 superfícies, encoding da ajuda, matriz declarativa de opções (chegada ao serviço, exclusividade, limite, obrigatória, saída de máquina, fábrica ausente, não-vazamento) e cobertura de `sen diag template`, que não tinha teste nenhum; cobertura da borda da CLI de 91% para 96% (93% por ramo)" — Author: Jean Silva — Type: Testes
- 2026-11-23 — Tests — "Suíte volta a rodar: 2 módulos abortavam a coleta inteira (`SessionStorageError` renomeado) e 10 testes estavam vermelhos — contrato tipado dos ports, guarda obsoleta do admin token e a árvore de referência do materializador, que apontava para `docs/`, excluído do repositório pelo .gitignore; a árvore passa a ser versionada em `tests/fixtures/repos/` com script de regeneração" — Author: Jean Silva — Type: Correção
- 2026-11-23 — CLI — "`sen --help` deixa de sair com código 1 quando o stdout não é UTF-8 (pipe, redirecionamento, console cp1252): `harden_stdio()` endurece os streams no entrypoint e o `UnicodeEncodeError` ganha mensagem honesta, em vez de \"erro interno na consulta\"" — Author: Jean Silva — Type: Correção
- 2026-11-23 — CLI — "sen list api: a varredura do catálogo despacha as leituras de apiTags sem esperá-las (16 em paralelo, sobrepostas à busca da próxima página) e o comando passa a mostrar feedback de espera; --all --attribute cai de ~8s para ~3s no bench de 127 APIs" — Author: Jean Silva — Type: Performance
- 2026-11-23 — CLI — "sen list api --attribute \"<nome>\": lista as APIs que declaram um atributo de governança nos apiTags (nome conferido contra sen list attributes, leitura de /apis/{id} por linha visível, em paralelo)" — Author: Jean Silva — Type: Nova funcionalidade
- 2026-11-01 — CLI — "Trace e analytics: sen list calls (chamadas dos últimos 7 dias com filtros), sen get trace --id (pipeline e headers mascarados) e sen get analytics (volumetria, erros, latência, rankings sobre amostra); credenciais da chamada nunca exibidas" — Author: Jean Silva — Type: Nova funcionalidade
- 2026-11-01 — CLI/Docs — "Plano de navegação completo (PLANO-NAVEGACAO.md): sen list api com filtros por dono/time/contexto/workflow/stage e --wide; sen list owners; Access Control em profundidade (sen get user|team|role, sen list roles|permissions); interceptors em FIRST/SECOND/THIRD com --point e bloco outros pontos; referência de content por tipo (sen get interceptor-type) e conferência no --item; helps atualizados" — Author: Jean Silva — Type: Nova funcionalidade
- 2026-11-01 — CLI — "Variáveis de ambiente sempre mascaradas nas listagens; sen reveal variable desmascara uma variável por vez, de propósito, com registro em log" — Author: Jean Silva — Type: Nova funcionalidade
- 2026-11-01 — CLI/Docs — "Navegação de consumo e infra: sen list apps|plans|tokens|variables|users|teams|inbounds|gateway-pools e sen get app|plan|environment (credenciais nunca exibidas, variáveis sensíveis mascaradas); COMMANDS.md com a referência de todos os comandos" — Author: Jean Silva — Type: Nova funcionalidade
- 2026-11-01 — CLI — "Catálogos do tenant e governança a partir do mapeamento APIM/AG: sen list environments|workflows|attributes|interceptors, sen get workflow (requisitos por stage), sen get governance (revisão contra o stage atual e o próximo) e sen get impact (rotas, planos e apps); get api mostra o nome do stage" — Author: Jean Silva — Type: Nova funcionalidade
- 2026-11-01 — CLI — "Navegação do ambiente sem repositório local: sen get api|resources|interceptors|custom|swagger e sen export api, com níveis de detalhe crescentes e saída json/yaml (uso por humanos e agentes de código)" — Author: Jean Silva — Type: Nova funcionalidade
- 2026-11-01 — CLI/Auth — "Settings remove aspas de variaveis de auth vindas do ambiente do processo; README, .env.example e .sen.example alinhados ao codigo (comandos, precedencia de fontes, local do .sen_session, HOST vs AUTH_HOST)" — Author: Jean Silva — Type: Correção
- 2026-09-24 — CLI — "Spec sen completeness: decisões seladas (grill + sondas 24/09), ADR 0008 (port dedicada + AG direto), backlog — sem código" — Author: Jean Silva — Type: Documentação
- 2026-09-17 — CLI/Auth — "Credenciais de login migram para .sen no pacote; sessao .sen_session co-residente (precedencia processo > .sen > .env)" — Author: Isaac Machado — Type: Nova funcionalidade
- 2026-09-17 — CLI/Auth — "sen login: resposta migrada para envelope extra_info com validação por perfil (BREAKING)" — Author: Isaac Machado — Type: Nova funcionalidade
- 2025-10-01 — Tests — "Testes" — Author: Augusto — Type: Testes
- 2025-10-01 — CLI — "Repo param obrigatório" — Author: Augusto — Type: Correção
- 2025-09-30 — CLI — "CLI & Testes" — Author: Augusto — Type: Nova funcionalidade
- 2025-09-30 — CLI — "CLI & Testes" — Author: Augusto — Type: Nova funcionalidade
- 2025-09-30 — Scaffold — "Implementação vazia de CLI & Testes" — Author: Augusto — Type: Infra/Scaffold
- 2025-09-26 — Environment — "Merged in APIO-10-criacao-de-arquivo-com-variaveis-de-ambiente (pull request #6)" — Author: Matheus Alves Giroto — Type: Nova funcionalidade
- 2025-09-24 — Architecture — "Merged in feature/hex-scaffold (pull request #4)" — Author: Danilo Amaral — Type: Arquitetura
- 2025-09-24 — Architecture — "Merged in feature/hex-scaffold (pull request #3)" — Author: Danilo Amaral — Type: Arquitetura
- 2025-09-24 — Bootstrap — "Merged in feature/repo-bootstrap (pull request #1)" — Author: Danilo Amaral — Type: Infra/Bootstrap
- 2025-09-24 — Setup — "Initial commit" — Author: Danilo Amaral — Type: Inicialização

Notes
- The classification by type was inferred from commit/PR titles.
- For a more complete automated changelog, it is recommended to adopt Conventional Commits.

