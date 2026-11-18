# Caminhos de validação — como cada decisão deste refino foi comprovada

| Meta | Valor |
|---|---|
| Data | 2026-10-14 |
| Tenant | consulting (`HOST` do `.env` do CLI) |
| Natureza | **somente leitura** — apenas `GET`, mais o POST de login e o POST de validação de token |
| Escritas | **nenhuma**. O HTTP 412 registrado no V-23 veio de uma tentativa do usuário, não desta sessão |

> Receita reproduzível: qualquer item fechado aqui pode ser reconferido repetindo as chamadas abaixo.

## 1. Obter o token

A credencial do `.env` (`AUTHORIZATION`, Basic) devolveu **401** — não serve mais. O caminho que funciona
é a sessão do CLI:

```bash
# 1. login (lê a credencial do arquivo .sen; grava .sen_session no diretório do pacote)
#    não há `sen.exe` no venv — chamar pelo entrypoint:
.venv/Scripts/python.exe -c "import sys; sys.argv=['sen','login']; from apiops_orchestrator.main import main; main()"
```

```python
# 2. trocar o accessToken da sessão pelo token administrativo
from apiops_orchestrator.infrastructure.secure_storage.session_store import SessionStore
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.adapters.outbound.http.orchestrator_auth_api.orchestrator_auth_adapter import (
    OrchestratorAuthAdapter,
)

settings = Settings()
session = SessionStore().load()                       # None => sessão expirada, refazer o login
data = OrchestratorAuthAdapter(settings).validate_access_token(session.accessToken)
token = data["extra_info"]["admin_access_token"]      # <- é este que o api-manager aceita
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
```

Detalhes que custaram tempo e vale registrar:

- a sessão **expira** (a desta validação valia até 14/10 22:29 UTC); `SessionStore().load()` devolve
  `None` quando expirada — é o sinal para refazer o login;
- o perfil da sessão é `developer` e **não** traz `adminAccessToken` no `.sen_session`; o token
  privilegiado vem do `/validation`, dentro de `extra_info.admin_access_token`;
- usar o `accessToken` da sessão direto no `api-manager` devolve **401**.

⚠️ **Segurança:** num dos passos o `admin_access_token` saiu impresso no log da sessão. Expira em ~24 h,
mas conta como exposto — soma-se à rotação de credencial já pendente no `AGENTS.md`. Ao reproduzir,
nunca imprima `extra_info` inteiro.

## 2. Bases

| Base | Uso |
|---|---|
| `{HOST}/api-manager/api/v3` | APIs, revisions, recursos, operações, interceptors |
| `{HOST}/api-governance/api/v3` | workflows, stages, atributos (Adaptive Governance) |

## 3. Chamadas por item fechado

| Chamada | Itens que ela sustenta | O que entregou |
|---|---|---|
| `GET /apis/409` · `GET /revisions/9103` | V-07 … V-10 | 6 recursos, 7 operações, **todos** `destination`/`timeout` de recurso e operação `null`; chaves **ausentes** na raiz da revision — provou que 4 valores da pasta `api-letras-409/` vieram da 417 |
| `GET /apis/417` · `GET /revisions/9175` | V-01, V-02, V-03, V-22 | `destination`/`timeout` nos três escopos, com valores divergentes e nulos convivendo; a op 9184 sem destino; o interceptor `Custom` em `THIRD` |
| `GET /apis/414` · `GET /revisions/9131` | V-11 | a régua: 0 recursos, 8 interceptors; e a confirmação de que a chave `template` **não existe** em nenhum payload |
| busca recursiva por `template` nos 3 payloads | V-11 | zero ocorrências — 8ª confirmação de ausência |
| comparação das assinaturas de interceptors (409 × 414 × 417) | V-11, V-22 | 409 idêntica à régua; 417 idêntica + 1 item em `THIRD` com `customInterceptorId: null` |
| `GET /api-governance/api/v3/workflows` | V-23 | workflow 139 (ORGANIZATION) e 500 (TEAM, `groupId: APIOps`) |
| `GET /api-governance/api/v3/workflows/500` (e `/stages`) | V-23 | `attributesRequisites` do stage 1402: atributos 149 e 96, `mustHave`, `tagId: null` |
| `GET /api-governance/api/v3/attributes` | V-23 | catálogo `id ↔ name`: `96 = CLI`, `149 = My new`, `231 = teste giroto`, `146 = Teste` (`inUse: false`) |
| releitura de `GET /revisions/9175` após o erro | V-23 §3 | `workflowId` continua `139`, enquanto a validação rodou no `500` — o workflow efetivo vem do **grupo** da API |

## 4. Documentação oficial usada

| Fonte | O que sustentou |
|---|---|
| [FAQ de timeout](https://docs-legacy.sensedia.com/en/faqs/Latest/consumption/timeout.html) | hierarquia API→recurso→operação; *"If no value is entered, the gateway will consider the next value in the hierarchy"*; gateway 60 s inalterável e como teto; unidade em segundos; erro 504 |
| [Guia de Flows](https://docs-legacy.sensedia.com/pt/api-management-guide/Latest/apis/flows.html) | destino por `All`/recurso/operação; o ícone de backend configura destino, certificado e timeout; erro 502 (diverge da FAQ) |
| [Variáveis de ambiente](https://docs-legacy.sensedia.com/pt/api-management-guide/Latest/environments/environment-variables.html) | `$variável` no **Target** e no **Timeout** — o caminho de promoção entre ambientes |

## 5. O que permanece sem prova possível por GET

| Ponto | Por quê | Fecha com |
|---|---|---|
| herança de `destination`/`timeout` em runtime | 9175 e 9103 têm `deployments: []` — nunca implantadas, sem tráfego | deploy + chamada real |
| equivalência `''` ↔ `null` na escrita | só se observa publicando | publish (write) |
| resolução do workflow efetivo pelo grupo | inferido da divergência 139 × 500 | revisão do `validate` |
| stage usado na validação (o 1402, com requisitos) | inferido do `path` do erro | revisão do `validate` |
