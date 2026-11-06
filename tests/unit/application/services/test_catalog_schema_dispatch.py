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
from apiops_orchestrator.application.services.revision_writer import RevisionWriter
from apiops_orchestrator.application.services.schema_validator import (
    CatalogSchemaValidator,
    SchemaValidator,
    select_schema,
)
from apiops_orchestrator.domain.services import openapi_contract_validator

PASTA_SCHEMAS = (
    pathlib.Path(__file__).parents[4]
    / "src"
    / "apiops_orchestrator"
    / "domain"
    / "schemas"
)
# API 400 materialized from tests/fixtures/manager/api-400-rev4.json, plus the contract.
EXAMPLE_REPO = pathlib.Path(__file__).parents[3] / "fixtures" / "api-repo-400"


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


def _load_example():
    return RevisionWriter(None, LocalFileImporterAdapter(), "validate").load(EXAMPLE_REPO)


def _example_files(loaded):
    files = [
        ("api-basic-info.yaml", loaded.basic_info),
        ("all.yaml", loaded.root),
        ("components.yaml", loaded.components),
    ]
    for resource in loaded.resources:
        files.append((resource.file_path, resource.data))
        files.extend((operation.file_path, operation.data) for operation in resource.operations)
    return files


def _schema_validator(catalog):
    return CatalogSchemaValidator(SchemaValidator(LocalFileImporterAdapter(), PASTA_SCHEMAS), catalog)


def test_cli_accepts_the_example_repository():
    """Reads the example the way `sen validate` does, with no contract error."""
    loaded = _load_example()
    result = openapi_contract_validator.validate(
        basic_info=loaded.basic_info,
        components=loaded.components,
        resources=loaded.resources,
        ignored=loaded.ignored,
    )

    assert loaded.ignored == []
    assert result.errors == []
    assert result.warnings == []


def test_example_repository_passes_the_catalog_schemas(catalog):
    files = _example_files(_load_example())

    assert len(files) == 9
    assert _schema_validator(catalog).validate(files) == []


@pytest.mark.parametrize(
    "api_tag",
    [{"attributeName": "My new"}, {"attributeName": "My new", "tags": []}],
)
def test_api_tag_without_tag_is_refused_like_the_cli(catalog, api_tag):
    """The pre-check refuses an attribute declared without tag in every case."""
    loaded = _load_example()
    basic_info = json.loads(json.dumps(loaded.basic_info))
    basic_info["spec"]["apiTags"] = [api_tag]

    problems = _schema_validator(catalog).validate([("api-basic-info.yaml", basic_info)])

    assert len(problems) == 1
    assert "apiTags" in problems[0]


@pytest.mark.parametrize("api_tags", ["absent", []])
def test_api_tags_absent_or_empty_stays_valid(catalog, api_tags):
    """Absent keeps the Manager apiTags; an empty list removes them. Both are accepted by the CLI."""
    loaded = _load_example()
    basic_info = json.loads(json.dumps(loaded.basic_info))
    if api_tags == "absent":
        del basic_info["spec"]["apiTags"]
    else:
        basic_info["spec"]["apiTags"] = api_tags

    assert _schema_validator(catalog).validate([("api-basic-info.yaml", basic_info)]) == []


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
