# Documentação do apiops-orchestrator

Índice da documentação interna do orquestrador. Última atualização: **2026-09-24**.

> **Relação com a documentação canônica do projeto:** os documentos oficiais de visão, conhecimento e decisões vivem em
> `Plataforma-Sensedia/API Ops - docs/Docs revisados/`. Os arquivos desta pasta registram as decisões e o
> entendimento técnico **do código orquestrador** de forma versionada junto ao repositório. Em caso de conflito,
> prevalece a documentação canônica e este conjunto deve ser reconciliado (ver `auth/divergencias-abertas.md`).

---

## Estrutura

| Caminho | Conteúdo |
|---|---|
| [`adr/`](adr/) | Architecture Decision Records — uma decisão por documento, formato MADR, PT-BR |
| [`auth/`](auth/) | Módulo de autenticação: doc canônica, contrato da API de auth, exploração empírica e divergências abertas |
| [`features/`](features/) | Especificações de features (feature atual: `sen login`) |

## ADRs

| ID | Título | Status |
|----|--------|--------|
| [0001](adr/0001-autenticacao-cli-base64-passthrough.md) | Autenticação da CLI via pass-through de Base64 | Aceito |
| [0002](adr/0002-ciclo-de-vida-de-tokens-dev-x-superadmin.md) | Ciclo de vida de tokens: dev × superadmin | Aceito |
| [0003](adr/0003-autorizacao-por-acao-endpoint-validation.md) | Autorização por ação via endpoint `/oauth2/token/validation` | Aceito |
| [0004](adr/0004-variavel-de-ambiente-sen-credentials.md) | Variável de ambiente `SEN_CREDENTIALS` | Aceito |
| [0005](adr/0005-padrao-de-logs-de-autenticacao.md) | Padrão de logs de autenticação herdado da observabilidade | Aceito |
| [0007](adr/0007-sen-como-casa-do-bloco-de-credenciais-e-residencia-dos-arquivos-sen.md) | `.sen` como casa do bloco de credenciais | Aceito |
| [0008](feat-command-sen-completeness/adr/0008-completeness-port-dedicada-ag-direto.md) | `sen completeness`: port dedicada + AG direto | Aceito (implementação congelada) |

## Autenticação

| Documento | Conteúdo |
|-----------|----------|
| [authenticator-module.md](auth/authenticator-module.md) | Síntese canônica do módulo (objetivo, camadas, fluxos, validações, permissões) |
| [api-orq-auth-contrato.md](auth/api-orq-auth-contrato.md) | Contrato conhecido da API de autenticação do orquestrador (`/orq-auth/v1`) |
| [exploracao-empirica-2026-09.md](auth/exploracao-empirica-2026-09.md) | Diário datado da exploração read-only (rotas OAuth2, API 400, validações) |
| [divergencias-abertas.md](auth/divergencias-abertas.md) | Divergências entre fontes + pré-requisitos externos |

## Features

| Documento | Conteúdo |
|-----------|----------|
| [sen-login.md](features/sen-login.md) | Spec da feature `sen login`: TDDs, decisões travadas, fases e critérios de aceite |
| [`feat-command-sen-list/`](feat-command-sen-list/) | Incremento `sen list` — pasta espelhando o ramo (convenção de organização) |

## Ramo `feat/command-sen-list` (incremento em curso)

| Documento | Conteúdo |
|-----------|----------|
| [features/sen-list.md](feat-command-sen-list/features/sen-list.md) | Spec do `sen list`: decisões seladas, grades com dados reais, mapa de fontes vivas e critérios de aceite |
| [sen-login-incremento-teams-jwt.md](feat-command-sen-list/sen-login-incremento-teams-jwt.md) | Incremento do login: teams do usuário no `extra_info` do JWT (requisito ao time de `/orq-auth`) |
| [adr/0006-composition-root-lazy-cli.md](feat-command-sen-list/adr/0006-composition-root-lazy-cli.md) | ADR 0006 — composition root lazy: `sen` standalone, `--help` sem `.env`, entry-point |
| [backlog/sen-list-despriorizacoes.md](feat-command-sen-list/backlog/sen-list-despriorizacoes.md) | Despriorizações legítimas (JSON -o, YAML, filtros, stage-name, audit) com contratos à espera |

## Ramo `feat/command-sen-completeness` (incremento em curso)

| Documento | Conteúdo |
|-----------|----------|
| [features/sen-completeness.md](feat-command-sen-completeness/features/sen-completeness.md) | Spec do `sen completeness`: decisões seladas em 7 categorias (gramática, escopo, dados, arquitetura, contrato, visualização, erros), grades aprovadas, mapa de fontes vivas (sondas 24/09) e critérios de aceite |
| [feat-command-sen-completeness/adr/0008-completeness-port-dedicada-ag-direto.md](feat-command-sen-completeness/adr/0008-completeness-port-dedicada-ag-direto.md) | ADR 0008 — port dedicada `CompletenessPort` + AG direto como fonte primária + satélite api-finder; contrato versionado `apiops.sen-completeness/v1`; gate 70% hardcoded (P10) |
| [feat-command-sen-completeness/backlog/sen-completeness-postergados.md](feat-command-sen-completeness/backlog/sen-completeness-postergados.md) | Postergados com contrato congelado: gate dinâmico (P10 via workflows), JWT platform-native no login (P-b), harmonização de severidade, enriquecimentos, hook do `sen validate` |

> **Convenção de organização:** cada incremento de feature/documentação ganha uma pasta `docs/<nome-do-ramo>/`, espelhando o nome da branch. Documentos pré-existentes ficam onde estão (nenhuma migração).

## Padrões

| Documento | Conteúdo |
|-----------|----------|
| [padroes-desenvolvimento.md](padroes-desenvolvimento.md) | Consolidado de padrões do projeto (variáveis de ambiente, nomenclatura, arquitetura, logs, erros, testes, CI) |

---

## Processo

- **Uma decisão por ADR.** Facilita divisão em SDDs pequenas e validação.
- **Regra de processo do projeto:** toda decisão concluída deve passar por **validação de um segundo agente revisor**
  antes de ser consolidada como normativa (conforme backlog/delivery e README da documentação canônica).
- Fontes são **citadas explicitamente** (Confluence, agendas de reunião, código da branch `develop`,
  documentação canônica) para permitir auditoria.
- Nenhum segredo, credencial ou token real é registrado nesta pasta.
