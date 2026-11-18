## 1. Envelope de erro e sinais do port

- [x] 1.1 `HttpErrorMapper` entrega o corpo parseado (`body`); `HttpClient4xxError` e `HttpClient` o repassam
- [x] 1.2 `ManagerApiTransportRejectedError` ganha `messages`; novo `ManagerApiGovernanceBlockedError(workflow_id, raw)`
- [x] 1.3 Adapter desembrulha o envelope (V-23 §1), com parse defensivo, e lança o sinal de governança para `412` com `path` de governança
- [x] 1.4 Testes em `test_manager_api_adapter.py` com o corpo real do `412` (caderno T03), `412` sem governança e envelopes variados

## 2. Fallback da CLI

- [x] 2.1 `_exit_on_unexpected` classifica `ManagerApiError` e usa a mensagem da família, mantendo o exit do comando
- [x] 2.2 Testes em `test_cli_adapter.py`: 401/403/indisponível/413 não traduzidos; exit 2 preservado no completeness

## 3. Recusa do PUT no `sen validate`

- [x] 3.1 `GovernanceBlockedError` aceita `motivos` (repasse literal quando não há faltante calculado) e `stage_id` opcional
- [x] 3.2 Novo `PublicacaoRecusadaError` (exit 1), com o motivo da plataforma ou a mensagem da família
- [x] 3.3 `validate_service._e3_publicar` envolve o `update_revision` conforme a tabela do spec
- [x] 3.4 Testes em `test_validate_service.py`: governança (exit 3, motivo, workflow, raw, sem releitura), 400/409/422 com motivo, 401/403/413/429 pela família, 422 sem motivo

## 4. Tags no pré-check e conferência do basic info

- [x] 4.1 Sondas somente leitura: requisitos sem `tagId` preenchido (ECAD e consulting); catálogo e `attributes/{id}/tags` só com nomes; `attributes/{id}` e `tags` → 403
- [x] 4.2 Testes de escrita na Draft 9161 (consulting, autorizados): tag inexistente → 200 e `apiTags` zeradas; `tags: []` → 412; atributo ausente → bloqueio do pré-check. Restaurado do backup e conferido
- [x] 4.3 Pré-check: `tags_invalidas` (nome contra o catálogo), atributo com tags cadastradas exige ao menos uma tag, catálogo lido uma vez; aviso de `tagId` revertido
- [x] 4.4 `TagInvalidaError` (exit 1) antes do bloqueio de governança; avisos do pré-check viram achados `WARNING`
- [x] 4.5 `conferir` compara `name`, `description` e `apiTags`
- [x] 4.6 Testes: `test_governance_precheck_service.py`, `test_revision_payload.py`, `test_validate_service.py`
- [x] 4.7 Verificação real: tag inválida e `tags: []` bloqueiam antes do PUT; baseline publica sem divergência falsa; estado final idêntico ao backup

## 5. Verificação

- [x] 5.1 `poetry run pytest tests/unit`: 613 passam; as mesmas 7 falhas e 2 erros de coleta da linha de base. Execução real só na API 417 do consulting (autorizada), nunca no tenant da ECAD
- [x] 5.2 `openspec validate handle-manager-rejections-in-validate-publish --strict`

## Workflow follow-up

- Commit só de `src/` e `tests/`, quando o autor pedir; nada de `docs/` ou `openspec/`
- Arquivamento junto com a volta da documentação (ou quando o autor pedir)
