## Why

O `sen validate` grava na Revision 1 (Draft) para obter o veredito da governança, mas a Draft não é
ambiente: nada ali chega a DEV, HML ou PRD. Falta o comando que a esteira chama depois do merge para
gravar o estado do repositório na revisão fixa do ambiente — 2 em `develop`, 3 em `release`, 4 em
`main` ([V-24](../../../docs/feat-api-estructure/decisoes-refino-409/V-24-revisao-alvo-do-publish.md)).

O desenho está fechado no [plano dos comandos](../../../docs/feat-api-estructure/plano-comandos-sen.md)
§7, e a mecânica de escrita (`PUT /revisions/{id}`, hidratação, preservação do não governado,
conferência pós-gravação) já foi provada e entregue dentro da E3 do `sen validate`.

## What Changes

- Novo comando `sen publish`, com a mesma borda do `sen validate`: `--repo`, `--output
  text|json|yaml`, `--verbose`, factory preguiçosa no composition root e exceções tipadas que a CLI
  só traduz em `exit_code`.
- A revisão alvo vem de `TARGET_REVISION_NUMBER`, pelo **número**. Em `EXECUTION_MODE=pipeline` a
  variável é **obrigatória**: ausente é falha de configuração (P-1). Em `local`, só a 1 é aceita
  (P-2), com confirmação `s/n` (D-9).
- O comando **não roda a régua nem o completeness**: isso é do `validate`. Roda apenas o que impede
  uma escrita errada — carga e gramática do repositório (P-8), guarda de identidade (P-4, D-11),
  existência dos `Custom`, pré-check de tags e de governança (P-5) — e depois um único `PUT` seguido
  da conferência por `GET` (W-7, W-8).
- Saída `apiops.sen-publish/v1`. Exit codes `0` sucesso, `1` falha técnica ou de configuração, `3`
  bloqueio do Adaptive Governance.
- **Refatoração:** a carga do repositório, a guarda de identidade, a resolução da revisão por número
  e a gravação com conferência saem do `ValidateService` para uma peça compartilhada, sem mudar o
  comportamento do `validate`.

## Capabilities

### New Capabilities

- `sen-publish`: gramática do comando, resolução da revisão alvo, pré-condições, escrita única com
  conferência, contrato `apiops.sen-publish/v1` e exit codes.

### Modified Capabilities

Nenhuma. O `sen validate` mantém os seus requisitos; só passa a delegar a escrita à peça
compartilhada.

## Impact

**Código novo** — `application/services/publish_service.py`,
`application/services/revision_writer.py`, `domain/models/publish_view.py`.

**Código alterado** — `validate_service.py` (delega à peça compartilhada),
`validate_exceptions.py` (mensagem de recusa nomeia o alvo), `config/settings.py`
(`TARGET_REVISION_NUMBER` opcional, para distinguir "ausente" de "1"), `cli_adapter.py` (comando e
renderização) e `main.py` (factory).

**Rede** — `GET` da API, da revisão, do workflow, dos atributos e dos `Custom`; um `PUT
/revisions/{id}`; um `GET` de conferência. Nunca `POST /revisions`.

**Correção em código compartilhado** — o smoke contra a API 417 mostrou que alterar o `content` ou a
ordem de interceptors existentes era descartado sob HTTP 200, no `validate` e no `publish`.
`interceptor_flow.py` e `revision_payload.py` passam a fazer o repositório prevalecer, e a
conferência compara com o fluxo declarado (design §7).

**Fora deste change** — `sen deploy` (sem desenho ainda) e a ligação das esteiras
(`pipeline.yaml`, `bitbucket-pipelines.yml`) ao novo comando.
