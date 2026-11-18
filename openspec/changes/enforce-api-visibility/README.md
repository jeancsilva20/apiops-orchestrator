# enforce-api-visibility

A regra de visibilidade que hoje só filtra a listagem do `sen list api` passa a valer em todo comando que recebe o id de uma API: o drill-down do `sen list api --id`, o `sen completeness`, o `sen validate` e o `sen diag draft`. API invisível para a sessão responde como API inexistente.
