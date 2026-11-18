## 1. Fidelidade dos schemas

- [x] 1.1 Gerar o exemplo do layout em `tests/fixtures/api-repo-400/` a partir do payload da 400 (materializador, sem rede) e completá-lo com o contrato da D7; verificar que o `sen validate` lê o exemplo e que o validador de contrato não acusa erro nem aviso
- [x] 1.2 Trocar, no `test_catalog_schema_dispatch.py`, o exemplo de `docs/` pelo de `tests/fixtures/`; verificar que o teste roda sem `skip` (14 passam)
- [x] 1.3 Corrigir os schemas que divergirem do que a CLI aceita, num commit `fix:` próprio; verificar que o teste da 1.2 passa. Corrigido: item de `apiTags` sem tag ou com `tags: []` (o pré-check recusa desde 05/11); `apiTags` ausente e `apiTags: []` seguem válidos, com teste. `x-*` dentro dos campos do contrato (a CLI recusa em qualquer nível, os schemas só no primeiro): por decisão do responsável em 06/11, a regra fica escrita na descrição dos schemas de basic-info, resource, operação e components, sem regra recursiva
- [x] 1.4 Reescrever `title` e `description` dos cinco schemas do catálogo para quem preenche o arquivo (D8), sem citar decisões, refino ou variáveis da esteira; verificar por busca que nenhuma referência sobrou e que os testes de schema passam

## 2. Pasta dos schemas

- [x] 2.1 Criar a constante da pasta resolvida a partir do pacote (D4) e remover o `ORCHEST_SCHEMA_FOLDER`; verificar com um teste unitário que a pasta existe e tem o `catalog.json`

## 3. Comando `sen schema`

- [x] 3.1 Listagem em árvore no texto e, em `-o json`/`-o yaml`, o documento `apiops.sen-schema/v1` com `type`, `file` e `occurs` de cada item (`file` e `occurs` no `catalog.json`); verificar com testes de CLI nos três formatos e com o teste de `file` coerente com o `pattern`
- [x] 3.2 `sen schema <tipo>` (D2 revista): `name` em cada entrada do `catalog.json`, `Enum` `RepoFileType` e saída sem envelope em JSON e em YAML; verificar com testes dos cinco tipos, de `-o yaml` e do `Enum` igual aos nomes do catálogo
- [x] 3.3 Tipo desconhecido (`resources`, `resource.yaml`, `Resource`) recusado com `exit 2`, listando os tipos; verificar com teste. O `--repo` e a conversão de caminho absoluto saíram com a D2 revista
- [x] 3.4 `hidden=True`; verificar com teste que `schema` não aparece no `sen --help` e que o `sen schema --help` lista os tipos
- [x] 3.5 Sem sessão e sem credencial: verificar com teste que, com o `PACKAGE_ROOT` temporário vazio, o comando termina com `exit 0` e não faz chamada de rede
- [x] 3.6 Instalação sem schemas: `exit 1`, com a mensagem de instalação incompleta; verificar com teste apontando a pasta para um diretório vazio
- [x] 3.7 Suíte de unidade: verificar que não há falha nova em relação à linha de base da `feat/executable`

## 4. Executável

- [x] 4.1 `--add-data` da pasta de schemas no `build-exe.ps1` e no `build-linux.sh`, mais a conferência de que todo schema do `catalog.json` entrou no binário; verificar listando o conteúdo do binário e conferindo que o build falha sem o `--add-data`. Feito em 06/11: os dois builds passam na conferência, e uma cópia de cada script sem o `--add-data` falhou na etapa 3, listando os 6 arquivos
- [x] 4.2 Teste isolado do executável, no Windows e no Linux via WSL, sem `.sen`: verificar que `sen schema` e `sen schema resource` dão a mesma saída que no código-fonte. Feito em 06/11: 13 saídas (listagem e os cinco tipos, em texto, JSON e YAML) iguais ao código-fonte nos dois sistemas, todas com `exit 0`, e nenhum arquivo criado na pasta isolada. Só passou depois do modo UTF-8 (D5)

## 5. Docs

- [ ] 5.1 Registrar o `sen schema` como comando oculto, para uso das skills, em `docs/comandos-cli.md`; verificar que os exemplos documentados rodam como escritos

## Workflow follow-up

- Abrir a change das skills depois desta.
- Arquivar esta change depois da revisão.
