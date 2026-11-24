"""Despacho de schema por CAMINHO (catalog.json v2).

O layout canônico não pode ser despachado por `kind`: só `api-basic-info.yaml`
o carrega. Um despacho por `kind` ignoraria `all.yaml`, `resource.yaml` e os
arquivos de operação **em silêncio** — arquivo sem schema é arquivo sem
validação, e ninguém saberia.
"""

import json
import pathlib

import pytest

from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)
from apiops_orchestrator.application.services.repo_importer_service import (
    RepoCanonicalReader,
)
from apiops_orchestrator.application.services.schema_validator import (
    CatalogSchemaValidator,
    SchemaValidator,
    select_schema,
)

PASTA_SCHEMAS = (
    pathlib.Path(__file__).parents[4]
    / "src"
    / "apiops_orchestrator"
    / "domain"
    / "schemas"
)
EXEMPLO_417 = (
    pathlib.Path(__file__).parents[3] / "fixtures" / "repos" / "api-417-rev2"
)


@pytest.fixture
def catalog():
    return json.loads((PASTA_SCHEMAS / "catalog.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "file_path,schema",
    [
        ("api-basic-info.yaml", "api-basic-info.schema.json"),
        ("all.yaml", "api-root-scope.schema.json"),
        ("components.yaml", "api-components.schema.json"),
        ("resources/tarefas/resource.yaml", "api-resource.schema.json"),
        ("resources/tarefas/get_tarefas.yaml", "api-operations.schema.json"),
        (r"resources\tarefas\get_tarefas.yaml", "api-operations.schema.json"),
    ],
)
def test_cada_arquivo_do_layout_encontra_seu_schema(file_path, schema, catalog):
    assert select_schema(file_path, catalog) == schema


def test_resource_vence_o_glob_generico_de_operacao(catalog):
    """A ordem do `layout` é significativa: sem ela, todo recurso seria operação."""
    assert (
        select_schema("resources/x/resource.yaml", catalog)
        == "api-resource.schema.json"
    )


def test_arquivo_fora_do_layout_nao_tem_schema(catalog):
    """Sem schema não é erro: é arquivo que o layout não governa."""
    assert select_schema("anotacoes.yaml", catalog) is None
    assert select_schema(".github/workflows/ci.yaml", catalog) is None


def test_profundidade_extra_nao_casa(catalog):
    """`fnmatch` deixa `*` atravessar `/`; o layout é de profundidade fixa."""
    assert select_schema("resources/a/b/c.yaml", catalog) is None


def _arvore_de_referencia(catalog):
    """Le a arvore commitada e devolve (validador, arquivos) na ordem do layout."""
    importer = LocalFileImporterAdapter()
    validador = CatalogSchemaValidator(
        SchemaValidator(importer, PASTA_SCHEMAS), catalog
    )
    carregado = RepoCanonicalReader(importer).load(str(EXEMPLO_417))

    files = [
        ("api-basic-info.yaml", carregado.basic_info),
        ("all.yaml", carregado.root),
    ]
    operacoes = []
    for resource in carregado.resources:
        files.append((resource.file_path, resource.data))
        for operacao in resource.operations:
            files.append((operacao.file_path, operacao.data))
            operacoes.append(operacao.file_path)
    return validador, files, operacoes


def test_repositorio_real_passa_inteiro_pelo_catalogo(catalog):
    """Todo arquivo do layout encontra schema e so as operacoes reclamam.

    LACUNA DE PRODUTO, conferida e deliberadamente travada aqui: `materialize()`
    (o que `sen export api` escreve) emite a operacao com `path`, `destination`,
    `description` e heranca — e nunca com `responses`
    (`repo_materializer.py:256-267`), que `api-operations.schema.json:8-11` exige.
    Logo uma arvore exportada reprova no passo de schema do `sen validate`, uma
    vez por operacao, embora o README e o help do `export api` digam que ela e
    "o layout que `sen validate` le".

    O teste afirmava `validate(files) == []` e vivia `skipif`-ado num diretorio
    fora do repositorio (`/docs/`, excluido pelo .gitignore), entao a lacuna
    nunca apareceu. Preferiu-se travar a verdade medida a manter o skip: se
    alguem ligar o contrato ao materializador, este teste falha e e aqui que se
    le o porque.
    """
    validador, files, operacoes = _arvore_de_referencia(catalog)

    assert len(files) == 13
    problemas = validador.validate(files)

    # Nenhum arquivo fora das operacoes reclama: basic-info, all e os 4 resource.
    assert len(problemas) == len(operacoes) == 7
    assert {p.split(":")[0] for p in problemas} == set(operacoes)
    for problema in problemas:
        assert "'responses' is a required property" in problema


def test_problema_de_schema_e_reportado_com_o_caminho(catalog):
    importer = LocalFileImporterAdapter()
    validador = CatalogSchemaValidator(
        SchemaValidator(importer, PASTA_SCHEMAS), catalog
    )
    # `method` no conteúdo da operação: o método vem do NOME do arquivo
    problems = validador.validate(
        [("resources/x/get_x.yaml", {"path": "/x", "method": "GET"})]
    )
    assert len(problems) == 1
    assert problems[0].startswith("resources/x/get_x.yaml:")
