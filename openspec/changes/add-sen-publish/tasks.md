## 1. Configuração

- [x] 1.1 Tornar `TARGET_REVISION_NUMBER` opcional em `config/settings.py` (`int | None = None`), mantendo o `validate` com ausente ⇒ 1
- [x] 1.2 Atualizar o teste de settings para "ausente é `None`"

## 2. Peça compartilhada

- [x] 2.1 Criar `application/services/revision_writer.py` com carga do repositório, guarda de identidade, `Custom` referenciados, revisão por número e gravação com conferência
- [x] 2.2 Fazer o `ValidateService` delegar a essa peça, com a suíte do `validate` passando sem alteração
- [x] 2.3 `PublicacaoRecusadaError` recebe o alvo da gravação, preservando o texto do `validate`

## 3. Serviço e contrato

- [x] 3.1 Criar `domain/models/publish_view.py` com `to_document()` emitindo `apiops.sen-publish/v1`
- [x] 3.2 Criar `application/services/publish_service.py` com o fluxo do design §1
- [x] 3.3 Testes do serviço: revisão por número em pipeline, P-1, P-2, P-3, P-10, guarda de identidade, `Custom` inexistente, tag inválida, bloqueio no pré-check, recusa do dev, 412 no `PUT`, recusa 4xx, 200 com perda, ausência de leitura da régua e do completeness, ausência de `POST`

## 4. Borda

- [x] 4.1 Adicionar `sen publish` em `cli_adapter.py`, com renderização de texto e `json`/`yaml` da mesma árvore
- [x] 4.2 Registrar `build_publish_service_factory()` em `main.py`
- [x] 4.3 Testes da CLI: flags, factory ausente, exit 0/1/3, saída JSON sem progresso

## 5. Verificação

- [x] 5.1 Suíte unitária sem regressão em relação à linha de base (8 falhas e 2 erros de coleta preexistentes) — 662 passam, mesmas 8 falhas
- [x] 5.2 Smoke contra o Manager real — autorizado em 2026-10-16, revisão 2 (id 9175) da API 417, sem restauração por decisão do usuário; backup antes de cada rodada. Rodada final: 16 cenários de escrita e 6 negativos conforme o esperado

## 6. Correções vindas do smoke

- [x] 6.1 `content` de interceptor nativo existente vem do YAML; `Custom` mantém o do Manager (design §7)
- [x] 6.2 Ordem por execution point segue o YAML, redistribuindo as `position` do escopo sem renumerar 1..N
- [x] 6.3 Conferência compara o publicado com o fluxo declarado — tipo, ordem e `content` normalizado
- [x] 6.4 Aviso de rotas removidas e texto novo do aviso de recursos removidos (design §6)
- [x] 6.5 Em `local`, avisos de remoção na caixa de confirmação e não no resultado; em `pipeline`, no resultado
- [x] 6.6 Mensagem de `Custom` inexistente sem a frase sobre ids entre ambientes
- [x] 6.8 Recusa (`n`) encerra sem relatório, exit 0; Ctrl+C interrompe, exit 130 — `validate` e `publish` (design §6.1, T-21 corrigido no plano)
- [x] 6.9 Conformidade: item que só mudou de posição gera um achado de posição, não o par "ausente" + "acréscimo"
- [x] 6.10 Conformidade: escopo que só herda não repete o achado do escopo acima; o achado sai uma vez, com "vale também para N recursos e M rotas"
- [x] 6.11 Resultado lista os ambientes em que a revisão alvo está no ar (`revision.deployments[]`, design §9); helpers de leitura de deploy extraídos do `deploy_service` para `domain/services/deployments.py`
- [ ] 6.7 Versionador: a rota com `inherit: true` + itens volta do Manager como `inherit: false` com a lista resolvida — mesma execução, forma diferente no Git (registrar no change do versionador)
