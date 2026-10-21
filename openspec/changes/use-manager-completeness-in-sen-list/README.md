# use-manager-completeness-in-sen-list

A coluna COMPLETE do `sen list api --id X --revisions` passa a vir do Manager (`GET /revisions/{id}/completeness`), a mesma fonte do `sen completeness`, do `sen deploy` e da interface do Manager; o bloco `completeness[]` do api-finder deixa de ser lido.
