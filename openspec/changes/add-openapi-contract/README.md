# add-openapi-contract

APIOPS-115. O repositório da API passa a versionar o contrato OpenAPI (contato, tags, segurança, modelos, operationId, parâmetros, corpo e respostas), e o `sen validate` e o `sen publish` ganham uma etapa de contrato depois da gravação do fluxo: leem o swagger da revisão, aplicam o contrato do repositório e gravam com `PUT /revisions/{id}/swagger`, sem tocar no runtime. Erro no contrato declarado aborta antes de qualquer escrita; problema da plataforma vira warning e o fluxo gravado fica.
