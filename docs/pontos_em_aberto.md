# Pontos em Aberto

> Registro vivo de decisões técnicas e pontos pendentes de discussão/execução do apiops-orchestrator.
> Cada entrada deve registrar: contexto, decisão (ou opções pendentes) e gatilho de revisão.
> **Regra de manutenção:** nenhum item aqui substitui spec/openspec — a spec normativa continua sendo
> fonte; este arquivo guarda o raciocínio de decisão e os sinais de revisão.

---

## Índice

| # | Tema | Status | Data |
|---|---|---|---|
| 1 | Cache da listagem de APIs (`sen list api`) | DECIDIDO — sem cache | 2026-09-21 |

---

## 1. Cache de listagem de APIs (`sen list api`)

### Contexto

Durante o desenho da fatia `sen list api` (21/09/2026), surgiu se a listagem (2 chamadas por execução:
`GET /api-manager/api/v3/apis` ~80KB + `GET .../revisions/basic` ~8KB) deveria ficar armazenada
entre execuções, para que `--offset`/`--query`/`--limit` percorram dados locais em vez de re-bater
na plataforma.

### Constrangimentos que moldaram a decisão

- **Cada comando `sen` é um processo novo.** Caches in-process do Python (`functools.lru_cache`,
  variáveis de módulo) morrem junto — para atravessar execuções o estado obrigatoriamente
  precisa materializar-se em disco (JSON/SQLite), não existe alternativa em memória.
- Custo atual sem cache: 2 chamadas (~1-2s de latência) por comando — trivial para uso esparso.
- Cache teria que ser invalidado por: TTL, troca de sessão/usuário, host e mudança de grupos
  (visibilidade depende deles) — complexidade de state para benefício de latência baixa.

### Decisão

**NÃO cachear a listagem** (Opção 1): frescor garantido a cada comando, complexidade zero.
Cada execução paga 2 chamadas; a janela/ordenação/visibilidade permanecem 100% client-side
em memória, por execução.

### Gatilhos para reabrir

Registrar cache quando algum destes eventos ocorrer:
1. Esteira CI começar a executar `sen list` em sequência (martelada de chamadas);
2. Latência percebida no dia a dia tornar-se incômodo consistente;
3. Surge secundário que consuma o mesmo dataset (ex.: `sen audit` sobre revisões).

### Desenho de referência (para ressuscitação — não implementar hoje)

- **Onde:** `C:\Users\<user>\AppData\Local\Sensedia\sen\cache\` (Windows) / `~/.cache/sensedia/sen/` (*nix)
  — código separado de estado; upgrade de pacote não apaga cache e vice-versa.
  (Alternativa considerada e descartada: irmão do `.sen_session` em `PACKAGE_ROOT`, que cai
  dentro de `site-packages` quando distribuído como pacote.)
- **Chave:** fingerprint de `HOST + userName + hash(userGroups)` no nome do arquivo — sem
  vazamento cross-conta/perfil.
- **Payload:** `{captured_at, apis: [...], revisions_basic: [...]}` — nenhum segredo (mesma
  regra da ADR 0005).
- **Escrita:** mesmo padrão do `SessionStore` (write atômico tempfile+os.replace, chmod 600,
  atributo hidden no Windows).
- **Controles:** TTL default 5 min; flag `--no-cache`/`--refresh` na CLI; miss → 2 chamadas + grava.
- **Estimativa:** ~120-150 linhas + 8-10 tests + delta de spec (~half day).

---
