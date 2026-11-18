## Purpose

Mostrar, sem rede, o layout do repositório da API e o JSON Schema de cada tipo de arquivo, para que agentes e desenvolvedores escrevam os YAML no formato que a CLI espera.

## ADDED Requirements

### Requirement: Comando oculto no help

O comando `sen schema` SHALL funcionar normalmente e SHALL NOT aparecer na lista de comandos do `sen --help`. O `sen schema --help` SHALL mostrar a ajuda do próprio comando, com os tipos de arquivo aceitos.

#### Scenario: Help geral
- **WHEN** o usuário roda `sen --help`
- **THEN** `schema` não aparece na lista de comandos

#### Scenario: Help do comando
- **WHEN** o usuário roda `sen schema --help`
- **THEN** a ajuda lista os tipos `basic-info`, `all`, `components`, `resource` e `operation`, e o comando termina com `exit 0`

### Requirement: Lista o layout do repositório

Sem argumento, o comando SHALL mostrar, na ordem do catálogo, cada tipo de arquivo do repositório da API, o caminho do arquivo com marcadores (`<recurso>`, `<método>`, `<path>`) e quantos desse arquivo o repositório tem. Em texto, SHALL mostrar uma árvore de pastas. Em `-o json` e `-o yaml`, a saída SHALL ser só o documento `apiops.sen-schema/v1`, com a lista `layout` e, em cada item, `type`, `file` e `occurs`.

#### Scenario: Árvore em texto
- **WHEN** o usuário roda `sen schema`
- **THEN** a saída é a árvore `<repositório da API>` com `api-basic-info.yaml`, `all.yaml`, `components.yaml` e `resources/<recurso>/` contendo `resource.yaml` e `<método>_<path>.yaml`; cada arquivo traz o tipo e a quantidade, e o comando termina com `exit 0`

#### Scenario: Listagem em JSON
- **WHEN** o usuário roda `sen schema -o json`
- **THEN** o stdout contém só o documento `apiops.sen-schema/v1`, com a lista `layout` e, em cada item, `type`, `file` e `occurs`, e o comando termina com `exit 0`

#### Scenario: Caminho de cada tipo coerente com o catálogo
- **WHEN** os marcadores do `file` de um tipo são trocados por nomes reais
- **THEN** o caminho resultante é atribuído pelo catálogo ao schema desse mesmo tipo

### Requirement: Imprime o schema de um tipo de arquivo

Com `<tipo>`, o comando SHALL imprimir o JSON Schema desse tipo de arquivo. Os tipos SHALL ser `basic-info`, `all`, `components`, `resource` e `operation`, os mesmos nomes do catálogo. A saída SHALL ser o JSON Schema sem envelope: em JSON no texto e em `-o json`, e em YAML no `-o yaml`.

#### Scenario: Recurso
- **WHEN** o usuário roda `sen schema resource`
- **THEN** a saída é o schema do `resource.yaml` e o comando termina com `exit 0`

#### Scenario: Operação
- **WHEN** o usuário roda `sen schema operation`
- **THEN** a saída é o schema dos arquivos de operação

#### Scenario: Schema em YAML
- **WHEN** o usuário roda `sen schema all -o yaml`
- **THEN** a saída é o schema do escopo `all` em YAML, sem envelope

### Requirement: Tipo desconhecido

Um valor fora dos tipos aceitos SHALL ser recusado como erro de uso, como um valor inválido de `-o`: o comando SHALL encerrar com `exit 2` e listar os tipos aceitos.

#### Scenario: Nome da pasta em vez do tipo
- **WHEN** o usuário roda `sen schema resources`
- **THEN** o comando termina com `exit 2` e a mensagem lista os tipos aceitos

### Requirement: Funciona sem sessão e sem rede

O comando SHALL funcionar sem `sen login`, sem credencial configurada e sem acesso à rede.

#### Scenario: Sem sessão e sem credencial
- **WHEN** não há sessão aberta nem `.sen` configurado
- **THEN** o `sen schema` lista o layout com `exit 0`, sem nenhuma chamada de rede

### Requirement: Schemas da versão em execução

Os schemas impressos SHALL ser os que acompanham a versão da CLI em execução, tanto rodando do código-fonte quanto do executável. O comando SHALL NOT ler schemas do repositório da API nem da pasta de instalação. Se os schemas não estiverem na instalação, o comando SHALL encerrar com `exit 1` e orientar a reinstalação.

#### Scenario: Executável
- **WHEN** o usuário roda `sen schema resource` no executável
- **THEN** a saída é igual à do código-fonte da mesma versão

#### Scenario: Instalação sem schemas
- **WHEN** a pasta de schemas não existe na instalação
- **THEN** o comando termina com `exit 1` e a mensagem diz que a instalação está incompleta e orienta reinstalar o `sen`

### Requirement: Schemas aceitam o repositório que a CLI aceita

Um repositório de exemplo, lido sem erro pela CLI, SHALL passar por inteiro nos schemas do catálogo. A suíte de testes SHALL conter esse exemplo e SHALL falhar quando um schema recusar um arquivo que a CLI aceita.

#### Scenario: Exemplo conforme
- **WHEN** a suíte de testes roda
- **THEN** cada arquivo do exemplo é validado contra o schema que o catálogo indica, sem `skip`, e nenhum problema é encontrado

#### Scenario: Schema divergente
- **WHEN** um schema recusa um campo que a CLI lê e publica
- **THEN** o teste falha, nomeando o arquivo e o campo
