"""CLI edge of `sen schema`: hidden command, repository layout and the JSON Schema of each file type."""

import json
import re
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from apiops_orchestrator.application.services.schema_catalog import RepoFileType
from apiops_orchestrator.application.services.schema_validator import select_schema
from apiops_orchestrator.config import settings as settings_module

runner = CliRunner()

SCHEMAS = settings_module.SCHEMAS_ROOT
LAYOUT = [
    {"type": "basic-info", "file": "api-basic-info.yaml", "occurs": "um na raiz, obrigatório"},
    {"type": "all", "file": "all.yaml", "occurs": "um na raiz, obrigatório"},
    {"type": "components", "file": "components.yaml", "occurs": "um na raiz, opcional"},
    {
        "type": "resource",
        "file": "resources/<recurso>/resource.yaml",
        "occurs": "um por pasta, ao menos uma pasta",
    },
    {
        "type": "operation",
        "file": "resources/<recurso>/<método>_<path>.yaml",
        "occurs": "um por rota, ao menos um na pasta",
    },
]
SCHEMA_OF = {
    "basic-info": "api-basic-info.schema.json",
    "all": "api-root-scope.schema.json",
    "components": "api-components.schema.json",
    "resource": "api-resource.schema.json",
    "operation": "api-operations.schema.json",
}


def _schema(name):
    return json.loads((SCHEMAS / name).read_text(encoding="utf-8"))


def _run(*args):
    return runner.invoke(app, ["sen", "schema", *args])


def test_file_types_match_the_catalog_names():
    catalog = _schema("catalog.json")

    assert [rule["name"] for rule in catalog["layout"]] == [t.value for t in RepoFileType]


def test_file_of_each_type_matches_its_catalog_pattern():
    """The `file` shown to people, with real names in the placeholders, picks the same schema."""
    catalog = _schema("catalog.json")

    for rule in catalog["layout"]:
        example = re.sub(r"<[^>]+>", "x", rule["file"])
        assert select_schema(example, catalog) == rule["schema"], rule["name"]


def test_schema_is_hidden_from_the_general_help():
    result = runner.invoke(app, ["sen", "--help"])

    assert result.exit_code == 0
    assert "schema" not in result.output


def test_schema_help_lists_the_file_types():
    result = _run("--help")

    assert result.exit_code == 0
    for entry in LAYOUT:
        assert entry["type"] in result.output


def test_layout_in_text_is_a_tree_with_type_and_occurrence():
    result = _run()

    assert result.exit_code == 0
    assert "<repositório da API>" in result.output
    assert "resources/" in result.output
    assert "<recurso>/" in result.output
    lines = result.output.splitlines()
    for entry in LAYOUT:
        name = entry["file"].split("/")[-1]
        [line] = [line for line in lines if name in line]
        assert entry["type"] in line
        assert entry["occurs"] in line
    assert "schema.json" not in result.output


@pytest.mark.parametrize("output", ["json", "yaml"])
def test_layout_document_follows_the_catalog(output):
    result = _run("-o", output)

    assert result.exit_code == 0
    document = json.loads(result.output) if output == "json" else yaml.safe_load(result.output)
    assert document == {"schema": "apiops.sen-schema/v1", "layout": LAYOUT}


@pytest.mark.parametrize("file_type,schema_file", SCHEMA_OF.items())
def test_prints_the_schema_of_the_type_without_envelope(file_type, schema_file):
    result = _run(file_type)

    assert result.exit_code == 0
    assert json.loads(result.output) == _schema(schema_file)


def test_json_output_is_the_same_schema():
    result = _run("resource", "-o", "json")

    assert result.exit_code == 0
    assert json.loads(result.output) == _schema("api-resource.schema.json")


def test_yaml_output_is_the_schema_in_yaml():
    result = _run("all", "-o", "yaml")

    assert result.exit_code == 0
    assert yaml.safe_load(result.output) == _schema("api-root-scope.schema.json")


@pytest.mark.parametrize("value", ["resources", "resource.yaml", "Resource"])
def test_unknown_type_is_a_usage_error(value):
    result = _run(value)

    assert result.exit_code == 2
    assert "basic-info" in result.output


def test_works_without_session_and_credentials(tmp_path, monkeypatch):
    for name in ("SEN_CREDENTIALS", "AUTH_HOST", "AUTH_LOGIN_PATH"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(settings_module, "PACKAGE_ROOT", tmp_path)

    def no_network(*_args, **_kwargs):
        raise AssertionError("sen schema must not touch the network")

    monkeypatch.setattr("socket.socket.connect", no_network)

    result = _run()

    assert result.exit_code == 0
    assert "resource.yaml" in result.output


@pytest.mark.parametrize("args", [(), ("all",)])
def test_installation_without_schemas(tmp_path, monkeypatch, args):
    monkeypatch.setattr(settings_module, "SCHEMAS_ROOT", Path(tmp_path))

    result = _run(*args)

    assert result.exit_code == 1
    assert "instalação" in result.output
    assert "reinstale" in result.output
