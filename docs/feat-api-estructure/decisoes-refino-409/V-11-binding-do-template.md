# V-11 · Binding do template — onde o id da régua mora

| Meta | Valor |
|---|---|
| Status | **FECHADO** — 2026-10-14. Com isso o V-11 fecha por inteiro |
| Complementa | [V-11-conformidade-com-a-regua.md](V-11-conformidade-com-a-regua.md) (severidades) |
| Fonte | `GET /apis/414` (somente leitura) + `src/apiops_orchestrator/config/settings.py` |

## 1. Decisão

O id da régua tem **duas origens, escolhidas pelo modo de execução**:

| Modo | Origem do id | Por quê |
|---|---|---|
| **local** (CLI na máquina do dev) | `spec.template` no `api-basic-info.yaml` | o dev precisa validar antes de abrir o PR, sem depender de infraestrutura |
| **esteira** (CI/CD) | **variável de ambiente**, alimentada pelo cofre do GitHub | o usuário não pode alterar a régua por um commit — o valor fica fora do alcance do PR |

Para isso entra uma **chave de configuração que declara o modo**, também lida do ambiente.

Regras do campo no manifesto (mantidas): **chave sempre declarada, vazio permitido**
(`template: ''` = esta API não tem régua, a validação não roda), **valor = id numérico**.

## 2. Chaves propostas

```bash
# .env — modo de execução
EXECUTION_MODE=local          # local | pipeline

# só usado quando EXECUTION_MODE=pipeline; na esteira vem do cofre, nunca do arquivo
TEMPLATE_API_ID=414
```

```yaml
# exemplo de step de esteira (GitHub Actions)
env:
  EXECUTION_MODE: pipeline
  TEMPLATE_API_ID: ${{ secrets.APIOPS_TEMPLATE_API_ID }}
```

> Hoje o repo tem `pipeline.yaml` (Azure) e `bitbucket-pipelines.yml`; **não existe `.github/workflows`**.
> O mecanismo é idêntico nos três — o cofre injeta variável de ambiente no processo.

## 3. Por que isso já funciona na arquitetura atual

`config/settings.py` define a precedência de configuração:

```
process environment > .sen (package dir) > .env (repo root)
```

Na esteira, o secret vira variável do **processo** — a faixa de maior precedência. Ou seja, um `.env`
versionado no repo **não consegue** sobrescrever o valor vindo do cofre. A proteção pedida já é
consequência do que está implementado; não exige mecanismo novo.

## 4. Casos de borda

| Situação | Comportamento | Origem |
|---|---|---|
| `EXECUTION_MODE` ausente | assume **`local`** | proposta |
| modo `pipeline` **sem** `TEMPLATE_API_ID` | **falha de configuração** (erro técnico, exit `1`) — validar contra nada numa esteira é pior do que parar | proposta |
| modo `pipeline` com `spec.template` **diferente** da variável | a **variável vence**, e o orquestrador emite `WARNING` apontando a divergência | proposta |
| modo `local` com `template: ''` | validação não roda; `INFO` no log | decidido (§1) |
| modo `local` sem a chave no YAML | erro de schema | decidido (§1) |

> Os três itens marcados como proposta seguem a filosofia já fechada nos outros documentos
> (informar sem bloquear, exceto falha técnica). Reabrir é barato enquanto não virar código.

## 5. Limite declarado

A proteção é **organizacional, não técnica**: quem edita o arquivo da esteira pode declarar
`EXECUTION_MODE=local` e voltar a ler o id do YAML. O que a decisão garante é que isso exige mexer no
workflow — arquivo com dono e revisão própria —, não num manifesto de API qualquer.

E o limite já conhecido do valor: o id `414` só existe neste tenant. Entre os ambientes
`Default`, `DEV-APIOPS` e `HMG-APIOPS` ele é estável (os três são do mesmo Manager,
`api-consulting.sensedia.com`, confirmado nos `environments` da própria 414). Levar o repo para o
Manager de outro cliente exige outro id — e, de fato, outra régua.

## 6. Como o orquestrador resolve a régua

```
1. modo = EXECUTION_MODE (default: local)
2. id   = TEMPLATE_API_ID            se modo == pipeline
          spec.template              se modo == local
3. se id vazio -> validação não roda (INFO)
4. GET /apis/{id} -> lastRevision.interceptors    # 1 chamada basta
5. compara com o fluxo efetivo da API -> INFO / WARNING (V-11 conformidade)
```

O passo 4 vale registrar: `GET /apis/414` **já devolve `lastRevision` com os 8 interceptors completos**
(tipo, posição, `customInterceptorId` e `content`). Não é preciso um segundo GET em `/revisions/{id}`.
Isso também responde *qual* revision da régua vale: **a última**, que é o que `lastRevision` entrega —
"a implantada" não serviria, já que a 414 tem `deployments: []`.
