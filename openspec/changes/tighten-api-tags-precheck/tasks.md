## 1. Sonda

- [x] 1.1 `GET /attributes` no consulting com `page`, `size` e `limit`: lista simples, sem paginação (05/11/2026)

## 2. Pré-check

- [x] 2.1 `ApiTagProblem` com os quatro tipos; `PrecheckResult.api_tag_problems` substitui `invalid_tags`
- [x] 2.2 Sugestão por nome igual sem acento e sem diferença de maiúscula
- [x] 2.3 `InvalidApiTagsError` (`exit 1`) substitui `InvalidTagError` no `validate` e no `publish`, antes do bloqueio de governança
- [x] 2.4 Comentário do `validate_service` sem a menção a "tag específica"

## 3. Testes

- [x] 3.1 `test_governance_precheck_service.py`: os quatro tipos, chave `tags` ausente, sugestão (acento, maiúscula, letra diferente, espaço), um problema por atributo sem tags no catálogo
- [x] 3.2 `test_validate_service.py`: todos os problemas numa mensagem, sem `PUT`; `test_publish_service.py` com o nome novo
- [x] 3.3 Suíte de unidade: 10 falhas, as mesmas da linha de base sem a mudança

## 4. Verificação real

- [x] 4.1 API-lab 425, revisão 13, consulting, com o Manager embrulhado num proxy que recusa escrita e a confirmação respondendo "não": caso válido chega à confirmação; `MY NEW`, `My news`, `CLI: Sensedia`, `My new: []`, `My new: Tag3` e os quatro juntos abortam com `exit 1` e a mensagem esperada; nenhuma chamada de escrita

## 5. Docs

- [x] 5.1 Delta do `sen-validate`
- [x] 5.2 Ajustar a pré-condição do spec do `sen-publish` no change `add-sen-publish`
