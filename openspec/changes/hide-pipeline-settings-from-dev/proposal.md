## Why

Rodando `sen deploy` na máquina local, o dev lê: *"O deploy é feito só pela esteira: o comando não roda na máquina local (EXECUTION_MODE=local)."* A mensagem entrega o nome e o valor da variável que separa a máquina do dev da esteira. Quem a definir como `pipeline` na própria máquina passa pelas travas do `sen deploy` e do `sen publish`, e tira a confirmação do `sen validate`.

A varredura de 21/10/2026 achou o mesmo problema em outros pontos visíveis fora da esteira:

- `sen deploy --help` e `sen publish --help` citam `TARGET_REVISION_NUMBER` e `TARGET_ENVIRONMENT_ID`;
- os painéis de texto do validate, publish e deploy mostram a linha "Modo: local";
- o JSON/YAML do validate, publish e deploy traz `"executionMode": "local"`;
- o validate e o publish locais, com `TARGET_REVISION_NUMBER` ≠ 1, respondem "Em modo local… TARGET_REVISION_NUMBER está em N";
- a falha de carga da configuração lista qualquer chave inválida, inclusive `EXECUTION_MODE`.

Além disso, o `sen publish` local grava na Draft, o mesmo que o `sen validate` já faz. Pela decisão de 17/08/2026 (*"o dev não publica nem deploya diretamente via CLI para nenhum ambiente"*), publicar é papel da esteira.

## What Changes

- **BREAKING** `sen publish` passa a rodar só na esteira. Fora dela, aborta com `exit 1` antes de autenticar e de qualquer chamada HTTP, e aponta o `sen validate` para quem quer conferir o repositório na Draft. A confirmação interativa do publish deixa de existir.
- `sen validate` na máquina local usa sempre a revisão 1 (Draft) e ignora `TARGET_REVISION_NUMBER`. Na esteira nada muda.
- Mensagens, `--help` e saídas estruturadas exibidas fora da esteira MUST NOT citar o modo de execução nem variáveis da esteira. `EXECUTION_MODE` não é citado em nenhuma saída, nem na esteira.
- Mensagens que só disparam na esteira continuam citando `TARGET_REVISION_NUMBER`, `TARGET_ENVIRONMENT_ID` e `TEMPLATE_API_ID`: é ali que o time da plataforma descobre o que falta, já que os logs da CLI ficam desligados.
- `executionMode` sai das saídas `json`/`yaml` fora da esteira; na esteira continua. A linha "Modo" sai dos painéis de texto.
- A falha de carga da configuração continua nomeando `SEN_CREDENTIALS`, `AUTH_HOST` e `AUTH_LOGIN_PATH` (o dev recebe as três no `.sen`, ADR 0007); variáveis da esteira só são nomeadas quando o modo é `pipeline`, e `EXECUTION_MODE` nunca.
- O texto de ajuda de todos os comandos, subcomandos e opções passa para português.

## Capabilities

### New Capabilities

- `cli-user-messages`: regra transversal do que as saídas da CLI podem revelar sobre a configuração da esteira, e idioma do `--help`.

### Modified Capabilities

- `sen-publish`: passa a rodar só na esteira; sai a confirmação local; `executionMode` condicionado ao modo. Depende de `add-sen-publish` ser arquivada antes desta change.
- `sen-deploy`: a recusa local deixa de citar a variável; `executionMode` condicionado ao modo.
- `sen-validate`: local sempre na Draft; `executionMode` condicionado ao modo.

## Impact

- Código: `application/services/publish_service.py` (trava local, sem confirmação), `deploy_service.py` (mensagem local), `validate_service.py` (Draft fixa no local), `regua_service.py` (aviso de divergência sem "variável de ambiente"), `domain/models/{validate_view,publish_view,deploy_model}.py` (`executionMode` condicional), `adapters/inbound/cli/cli_adapter.py` (help em português, sem linha "Modo", publish sem confirmação), `main.py` (mensagem de configuração inválida), `adapters/outbound/http/orchestrator_auth_api/orchestrator_auth_adapter.py` (sem mudança de texto, só coberto pela regra).
- Testes: `test_publish_service.py`, `test_publish_command.py`, `test_validate_service.py`, `test_validate_command.py`, `test_deploy_service.py`, `test_deploy_command.py`, `test_cli_adapter.py`, testes de settings; novo teste de guarda das mensagens.
- Documentação: V-24 revisada (local não publica mais), `comandos-cli.md`.
- Esteira: nenhuma mudança de configuração; o contrato `json` da esteira mantém `executionMode`.
