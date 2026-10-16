# ADR 0006 — Armazenamento da sessão do `sen login` na raiz do projeto

| | |
|---|---|
| **Status** | Aceito (com riscos explicitados e mitigados abaixo) |
| **Data** | 2026-09-17 |
| **Supersede** | ADR 0002 **no aspecto de storage** (temp do SO → raiz do projeto); o restante do ADR 0002 (ciclo dev × superadmin, guard, expiração) segue vigente |
| **Correlatos** | `openspec/changes/move-session-storage-to-project-root` · ADR 0004 (`SEN_CREDENTIALS`) · backlog de distribuição (`docs/auth/distribuicao-e-fontes-de-credenciais-backlog.md`) |

## Contexto

A fase 1 gravava a sessão em `%TEMP%/.sen_session` (ADR 0002). O time decidiu que o arquivo deve viver **na raiz do projeto** (`<checkout>/.sen_session`), visível ao dev, com os riscos dessa convivência formalmente registrados — este ADR é a peça exigida de governança. Importante: a raiz é **derivada do módulo** (`config/settings.py` → 4 níveis acima), não do CWD do shell — o arquivo é único e estável por clone, independentemente de onde o comando é chamado (incl. `src/`).

## Decisão

1. `SessionStore` continua genérico (diretório injetado); o **composition root** (`main.py`) passa `settings.PROJECT_ROOT`.
2. O arquivo permanece **oculto** (`.sen_session`), com **escrita atômica** (tmp + `os.replace`), `chmod 0o600` (POSIX) e atributo **Hidden** (Windows, best-effort).
3. Guard-rail de versionamento vira **requisito de spec**: padrão `.sen_session*` no `.gitignore` (adicionado **antes** do primeiro arquivo existir).
4. Sem migração do `%TEMP%/.sen_session` legado (arquivo órfão; limpeza natural do SO).

## Riscos identificados × mitigações

| # | Risco | Mitigação aplicada | Residual |
|---|---|---|---|
| R1 | Token commitado por descuido (`git add .`) | `.sen_session*` no `.gitignore` (padrão inclui variantes `.tmp`); Hidden atrai pouco; aviso no README; scanners do Bitbucket como 2ª camada | Baixo — exige `add -f` explícito |
| R2 | Histórico já contendo sessão | `git log --all -- '*.sen_session*'` verificado vazio **antes** do primeiro login na raiz (task 1.2) | Nenhum |
| R3 | Esteira publicando a sessão em artefatos do pipeline | Hoje `artifacts: test-results/**` não alcança a raiz; ADR **proíbe** ampliar globs de artefatos sem conferir `.sen_session*` | Controlado por disciplina de revisão |
| R4 | Ferramentas de sync/backup (OneDrive etc.) replicando o token junto com a pasta do projeto | Aceito nesta fase: projeto roda em pasta de trabalho local, não sincronizada; token expira em 12h e `expires_at` invalida a sessão | Médio — restrição de onde clonar (não sincronizar repo com sessão) |
| R5 | Multiusuário na mesma pasta compartilhada | Projetos `apiops` são por pessoa (1 clone/1 identidade); `chmod 0o600` protege leitura no POSIX; sessão não é multi-tenant | Baixo no modelo de uso adotado |
| R6 | Scanners de segredos acusando arquivo na árvore | Falso-positivo **esperado pelo desenho**; sinalizar ao time de security com referência a este ADR | Nenhum |
| R7 | `git clean -xdf` apagando a sessão | Comportamento colateral aceitável: força `sen login` orientado; nenhum outro efeito | Nenhum |

## Alternativas consideradas e rejeitadas

| Alternativa | Motivo da rejeição (nesta fase) |
|---|---|
| Manter `%TEMP%` (ADR 0002) | Perde visibilidade/governabilidade que o time passou a exigir; repetido em outros contextos (VMs/temp limpos) |
| `~/.sen/.sen_session` (home do usuário) | Destino preferido para a fase de **distribuição** (wheel/executável, machine-global); adiado conforme backlog — não resolve a visibilidade pedida agora |
| Variável de ambiente para o caminho (ex. `SEN_SESSION_DIR`) | Afasta a sessão da raiz exigida e complica o guard-rail do `.gitignore` |

## Consequências

**Positivas:** sessão visível e auditável junto ao projeto; raiz determinística multi-CWD; contratos novos exercitáveis por spec (status Git limpo).
**Negativas:** ciclo de vida do arquivo passa a ser manual (re-login/purge em vez de rotação do SO); atenção obrigatória aos riscos R1–R7 acima em futuros changes (principalmente qualquer glob de artefatos ou empacotamento — o arquivo NUNCA entra no wheel).

## Fontes

- Discussão 16-17/09/2026 (fase 1 encerrada; decisão: "trocar para raiz do projeto + registrar riscos em docs").
- Spec `openspec/changes/move-session-storage-to-project-root` (delta MODIFIED+ADDED, validate --strict).
- `SessionStore` (`infrastructure/secure_storage/session_store.py`) — escrita atômica/permissões já implementadas.
