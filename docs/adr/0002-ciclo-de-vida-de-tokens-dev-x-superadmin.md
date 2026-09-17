# ADR 0002 — Ciclo de vida de tokens: dev × superadmin

| | |
|---|---|
| **Status** | Aceito |
| **Data** | 2026-09-15 |
| **Supersede** | Comportamento atual do `SensediaAuthenticationAdapter` (token por request, sem sessão) |
| **Correlatos** | [ADR 0003](0003-autorizacao-por-acao-endpoint-validation.md), [ADR 0005](0005-padrao-de-logs-de-autenticacao.md), [spec `sen login`](../features/sen-login.md) |

## Contexto

Os TDDs do recurso de autenticação definem dois perfis com necessidades opostas:

- **Dev (CLI local):** executa ações repetidamente (`sen list`, `sen validate`); não pode fazer deploy/edição
  direta; o orquestrador precisa agir em APIs administrativas **sem jamais guardar o token de superadmin**;
- **Esteira (superadmin):** token com poder total deve existir **apenas em memória** durante a execução.

A documentação canônica reforça que a CLI é ferramenta local de validação na V1 — o dev não publica/deploya
diretamente — e que segredos nunca podem vazar para console, logs ou arquivos.

## Decisão

Adotar **dois ciclos de vida distintos**, ambos orientados a não-vazamento:

### Perfil dev

```
sen login
  → POST /orq-auth/v1/oauth2/token      (Base64 intacto; server decodifica/valida)
  ← JWT com SCOPES (read/write/admin) + perfil
  → token gravado em ARQUIVO TEMPORÁRIO E OCULTO na máquina do dev

Ação (ex.: sen list api)
  → GUARD LOCAL: ação ∈ scopes do token?
      ├─ NÃO → mensagem de negação. NEM CHAMA A API DE AUTH.
      └─ SIM → envia dev token para /orq-auth/v1
              ← SUPER ADMIN TOKEN efêmero (uma ação)
       → usa nas APIs administrativas (api-manager etc.)
       → DESCARTA imediatamente (nunca loga, nunca persiste, nunca reutiliza)
```

- **Guardar:** somente o **token do dev** (com scopes), em arquivo temporário oculto com permissões restritas.
- **Nunca guardar:** super admin token. Cada nova ação requer nova emissão via API de auth.

### Perfil superadmin (esteira)

- Token vive **apenas em memória/sessão do processo** (`sen login --service` → execução → fim).
- **Nada** em arquivo, console ou log — em nenhuma das fases.

### Expiração

- Guard local verifica expiração (claim `exp` ou 401 recebido) e **orienta re-login** (`sen login`) —
  não envia token sabidamente expirado.

## Alternativas consideradas e rejeitadas

| Alternativa | Motivo da rejeição |
|---|---|
| Keyring do SO (Credential Locker/libsecret) para o token dev | Dependência de plataforma e complexidade desnecessárias para a V1 |
| Persistir token dev em arquivo de configuração permanente | Risco elevado de vazamento em backups/repos |
| Reutilizar o super admin token por um período (cache TTL) | Viola regra do TDD ("uma nova ação gera novo permissionamento"); amplia janela de exposição |
| Resolver toda autorização 100% local no login | Servidor deixa de ser autoridade; permissões podem ficar obsoletas (ver [ADR 0003](0003-autorizacao-por-acao-endpoint-validation.md)) |

## Consequências

**Positivas**
- Superfície de vazamento mínima (token efêmero + storage com ACL restritiva);
- autorização sempre atualizada (servidor a cada ação);
- comportamento previsível nos dois perfis.

**Negativas / pontos de atenção**
- Latência adicional por ação (uma chamada de autorização + uma administrativa);
- exige módulo de storage seguro (escrita atômica, permissões restritas, purge em logout/expiração);
- token efêmero depende do endpoint `/validation` disponível (pré-requisito externo).

## Fontes

- TDDs fornecidos por Jean Carlos da Silva (cenários dev e devops, chat 15/09/2026).
- Documento Confluence `Módulo: Auth` (Nexus) — permissões `read/write/admin` no `extra info` do JWT.
- Documentação canônica — `Docs revisados/knowledge/autenticacao-e-seguranca-da-cli.md` e
  `comandos-cli-sen.md` (CLI como ferramenta local de validação na V1).
- Reunião `[ECAD] - API OPS` 15/09/2026 — fluxos de pipeline e developer apresentados por Paulo de Oliveira.
