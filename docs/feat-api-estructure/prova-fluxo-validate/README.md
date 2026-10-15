# Prova de fluxo do `sen validate`

| Meta | Valor |
|---|---|
| Natureza | **Instrumento de validação empírica.** Não é código de produção |
| Serve para | observar o comportamento real da plataforma no cenário da §6 do [plano](../plano-comandos-sen.md) antes de virar spec |
| Escreve na plataforma | **SIM** — fases 5a e 5b. Backup e `--restore` embutidos |
| Alvo configurado | `decisoes-refino-409/exemplos-gerados/saida/api-417-rev2` (API 417, `/letras/v2`) |

## Como rodar

```bash
cd CLI/apiops-orchestrator

# sessão válida é pré-requisito
.venv/Scripts/python.exe -c "import sys; sys.argv=['sen','login']; from apiops_orchestrator.main import main; main()"

# execução completa
PYTHONPATH=src .venv/Scripts/python.exe docs/feat-api-estructure/prova-fluxo-validate/provar_sen_validate.py

# outro repositório
PYTHONPATH=src .venv/Scripts/python.exe .../provar_sen_validate.py --repo caminho/do/repo

# desfazer
PYTHONPATH=src .venv/Scripts/python.exe .../provar_sen_validate.py --restore logs/<execução>/backup
```

## Configuração (topo do script)

| Constante | Valor atual | Para quê |
|---|---|---|
| `REPO_DIR` | caminho absoluto da `api-417-rev2` | repositório consumido |
| `EXECUTION_MODE` | `"local"` | `"pipeline"` dispensa o `s/n` (D-17) |
| `TEMPLATE_API_ID` | `414` | régua, quando o modo é `pipeline` |
| `REVISION_NUMBER_DRAFT` | `1` | Draft por convenção |
| `TEMPLATE_LOCAL_OVERRIDE` | `414` | **artifício do instrumento** — ver abaixo |

### Por que existe o `TEMPLATE_LOCAL_OVERRIDE`

A fixture `api-417-rev2` tem **`template: ''`** no `api-basic-info.yaml`. Rodando fiel ao YAML, o
fluxo aborta na fase 3 com a mensagem da D-12 — comportamento **correto**, mas que impediria
exercitar o resto do fluxo.

O override sobrepõe o valor sem editar a fixture (que é saída de máquina e serve de evidência):

- `TEMPLATE_LOCAL_OVERRIDE = 414` → roda o fluxo completo contra a régua;
- `TEMPLATE_LOCAL_OVERRIDE = None` → usa o YAML e prova o cenário "template ausente".

O log registra qual origem foi usada, para o resultado não ser ambíguo depois.

## O que cada execução deixa

```
logs/<AAAAMMDD-HHMMSS>/
├── execucao.txt              log completo, com cada chamada HTTP e o desfecho
└── backup/
    ├── api_417.json          estado da API antes da escrita
    └── revision_<id>.json    uma por revision
```

Última linha sempre: `RESULTADO: <SUCESSO|FALHA NA PUBLICACAO|ABORTADO|ERRO TECNICO>`.

## As fases

| Fase | Etapa do plano | Rede |
|---|---|---|
| 1 | E1 — carregar o repositório | — |
| 2 | **guarda 1** — `version` e `basePath` (D-11) | GET |
| 3 | E2 — template e conformidade (D-13) | GET |
| 4 | **guarda 2** — `s/n` (dispensada em `pipeline`, D-17) | — |
| **5a** | **E3a — `PUT /apis/{id}` (basic info)** | **ESCRITA** |
| **5b** | **E3b — `PUT /revisions/{id}` (Draft)** | **ESCRITA** |
| 6 | E4 — completeness | GET |
| 7 | relatório consolidado (D-18) | — |

### Por que 5a e 5b são separadas

É o teste da **D-14**. Os `apiTags` vivem no **basic info**, e o teste de 2026-10-14 mostrou
`PUT /revisions/{id}` passando **sem** 412 do Adaptive Governance.

| Observação | Conclusão |
|---|---|
| 412 na 5a, 5b passa | o gate do AG está no **nível da API** — a E3 **precisa** publicar o basic info |
| ambas passam | a API está conforme; repetir com uma API sem o atributo exigido |
| 412 na 5b | o gate também cobre a revision — o desenho atual basta |

## Cenários que valem simular

| Cenário | Como provocar | Esperado |
|---|---|---|
| fluxo completo | como está configurado | chega à fase 7 |
| guarda 1 barra | edite `version` ou `basePath` no `api-basic-info.yaml` | aborta na fase 2, sem escrever |
| `spec.id` divergente, resto igual | troque só o `id` por outra API de mesma version/basePath | **segue** (T-25) |
| template ausente | `TEMPLATE_LOCAL_OVERRIDE = None` | aborta na fase 3 (D-12) |
| template inalcançável | `TEMPLATE_LOCAL_OVERRIDE = 999999` | ponto em aberto **P-2** — observar o desfecho |
| recusa do usuário | responda `n` | aborta antes de escrever |
| esteira | `EXECUTION_MODE = "pipeline"` | não pergunta `s/n` |
| bloqueio do AG | API sem o atributo exigido pelo workflow do grupo | 412 — **ver em qual fase** |
| erro de sintaxe | quebre um `content` no YAML | observar o que o Manager devolve |

## Limites declarados

- A fase 5b publica o **escopo `all`**; recursos e operações seguem como estão no Draft. O objetivo é
  observar o comportamento da plataforma, não reconstruir o payload completo (isso é a onda 3).
- Interceptors do repositório são **casados** com os do remoto para reusar o `content` de `Custom`.
  O que não casa é registrado no log como "item sem correspondente" — é o caso que a implementação
  de produção terá de montar do zero.
- A classificação append × override usa `inherit` e a lista de tipos; a comparação por `content`
  completa (V-11 §4) fica para a implementação.
- **A revisão 1 da 417 tem 6 recursos; a fixture é da revisão 2, com 4.** A fase 5b altera o escopo
  `all` do Draft, não a árvore de recursos — mas o backup cobre tudo, e o `--restore` devolve.
