# ADR 0007 — `.sen` como casa do bloco de credenciais e residência dos arquivos sen

## Metadados

| Campo | Valor |
|---|---|
| Status | Aceito |
| Data | 2026-09-17 |
| Supersedes | — (estende ADR 0004; não invalida) |
| Correlatos | [ADR 0004](0004-variavel-de-ambiente-sen-credentials.md), [ADR 0006](0006-armazenamento-da-sessao-raiz-do-projeto.md), change `migrate-sen-files-to-package-root` (spec `cli-auth`), doc de padrões §4.3 |

## Contexto

O desenho de distribuição define dois perfis de execução: **esteira** (headless; configuração vinda de `.env` gerado em runtime ou variáveis do pipeline) e **executável entregue ao dev** — para o qual não existe raiz de repositório nem `.env` garantidos. Hoje as três chaves de autenticação da CLI (`SEN_CREDENTIALS`, `AUTH_HOST`, `AUTH_LOGIN_PATH`) só são lidas do `.env` da raiz (ou processo), inviabilizando o executável. A sessão persistida (`.sen_session`, ADR 0006) por sua vez derivava de diretório temporário/raiz do projeto, sem co-residência previsível com a credencial. Também consta no desejo do time: com o `.sen` consolidado, o `.env` tende a deixar de existir, e o `.env.example` deve voltar a não falar de `sen login` (restaurado em 17/09).

Decisões complementares registradas pelo responsável (Isaac, 17/09): as três chaves migram **juntas**; **nenhuma** delas admite default/fallback em código (auditado: `build_login_url` falha com `RuntimeError` pré-rede; `resolve_credential` eleva `CredentialNotFoundError` pré-rede); a mensagem de credencial ausente orienta **somente** para o `.sen`.

## Decisão

1. **`PACKAGE_ROOT`** (diretório do pacote — em dev, `src/apiops_orchestrator/`; no binário futuro, pasta do executável) passa a hospedar dois arquivos:
   - **`.sen`** — sintaxe dotenv, contendo o bloco de credenciais de login completo (`SEN_CREDENTIALS`, `AUTH_HOST`, `AUTH_LOGIN_PATH`); chaves extras são ignoradas (`extra="ignore"`);
   - **`.sen_session`** — sessão persistida (mesmo contrato do ADR 0006: oculta, escrita atômica, permissões restritivas, nunca `adminAccessToken`).
2. **Precedência de fontes:** variáveis de processo > `.sen` (pacote) > `.env` (raiz). Implementada por `load_dotenv` gap-fill na ordem inversa + `SettingsConfigDict(env_file=(.env, .sen))`.
3. **Governança de repositório:** `.sen` ignorado (match exato, + provisórios `.sen_session.*.tmp`); gabarito **`.sen.example` versionado** junto ao arquivo real, com placeholders e zero segredo; `.env.example` restaurado ao estado anterior ao `sen login`.
4. **Mensagem de credencial ausente** aponta o `.sen` do diretório do aplicativo (mono-fonte na orientação; a mecânica de precedência continua aceitando as demais fontes).
5. **Visibilidade:** log `config.sources.active` (booleans sen/env/processo, sem valores) no início do fluxo de login.

## Alternativas consideradas e rejeitadas

| Alternativa | Motivo da rejeição |
|---|---|
| Manter apenas o `.env` | incompatible com executável distribuído; raiz de repo não existe no pacote |
| `.sen` com TODA a configuração do dev | expõe ao executável variáveis pertencentes à esteira (HOST, API_ID, WORKFLOW_*) e alarga o contrato sem demanda registrada |
| Precedência `.env` > `.sen` | um `.env` esquecido sobrescreveria a configuração "da casa nova" no executável; ordem tomada preserva o ganho da migração |
| Renomear sessão para `.sen-session` (hífen do to-do) | churn de arquivo/permissões/docs sem ganho funcional;underscore já establecido (ADR 0006) |
| Resolver caminhos por `cwd` | frágil: quebra o cenário "local independente do diretório corrente" e não funciona em esteira headless |
| Adaptar `sys._MEIPASS`/diretório do `.exe` agora | distribuição congelada ainda não existe; PACKAGE_ROOT por `__file__` atende dev e o follow-up fica registrado (Consequências) |

## Consequências

**Positivas**
- Executável do dev autocontido: um único diretório (pacote) guarda credencial, sessão e gabarito.
- Esteira 100% preservada (sem `.sen` tudo segue como hoje); o eventual fim do `.env` torna-se incremental.
- Precedência determinística e observável por log; gabarito versionado evita "adivinhar o formato".
- Reuso pleno do aparato de segurança do ADR 0006 (atômica, 0o600, hidden, git-ignored).

**Negativas / limitações**
- **Binário congelado:** `PACKAGE_ROOT = Path(__file__).resolve().parents[1]` vale para o ambiente Poetry/`pip install`; ao empacotar (PyInstaller e similares) será necessário apontar para o diretório do executável — registrado como follow-up (junto do §4.3 da doc de padrões).
- Dupla fonte (`processo`/`sen`/`env`) exige disciplina em explicar "quem mandou" — mitigado pelo log de fontes, sem exigir ferramenta extra.
- Sessões antigas em tempdir ficam órfãs (aceito: re-login repovoa o destino novo; coerente com D6 do change `receive-extra-info-login-payload`).

## Fontes

- Código: `config/settings.py` (PACKAGE_ROOT/parents[1]; env_file tuplo; gap-fill dotenv), `infrastructure/secure_storage/session_store.py` (default PACKAGE_ROOT; co-locada), `main.py:47` (wiring), `application/services/login_service.py` (mensagem mono-fonte + `config.sources.active`), `.gitignore:160-166`, `.env.example` (restaurado), `src/apiops_orchestrator/.sen.example`.
- Especificação: `openspec/changes/migrate-sen-files-to-package-root/` (proposal/design/spec cli-auth), validada em 17/09/2026.
- Confirmações de produto: Isaac Machado em 17/09/2026 (3 chaves juntas; sem fallback — auditado; mensagem mono-fonte; `.env.example` restaurado; `.env` tende a cessar).
