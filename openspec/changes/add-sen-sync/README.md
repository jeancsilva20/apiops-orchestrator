# add-sen-sync

Adiciona o `sen sync`: carga inicial de uma API do Manager para as branches de ambiente do repositório (revisões 4, 2 e 3 em `main`, `develop` e `release`) e verificação (`--check`) de que repositório e Manager continuam espelho um do outro. Só `GET` no Manager, só leitura no Git, escrita atômica no disco local. Remove o versionador legado.

Especificação de origem: [`docs/feat-command-sen-sync/sen-sync.md`](../../../docs/feat-command-sen-sync/sen-sync.md).
