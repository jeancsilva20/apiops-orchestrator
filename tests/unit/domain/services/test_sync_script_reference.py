"""Referência contra o `extrair_estrutura.py`: a mesma árvore, no YAML relido.

O script roda offline, com um swagger vazio, sobre as fixtures reais 417 e 400.
Diferenças aceitas, de propósito: strings numéricas (`"1000"`) ficam citadas no
orquestrador porque sem aspas o round-trip as transforma em inteiro; a
`description` vazia que o script escreve como `""` aqui é omitida; o `template`
vem do repositório, não do script.
"""

import importlib.util
import json
import pathlib
import re

import pytest
import yaml

from apiops_orchestrator.domain.models.api_model import Api, Revision
from apiops_orchestrator.domain.services.repo_materializer import materialize

ROOT = pathlib.Path(__file__).parents[3]
FIXTURES = ROOT / "fixtures" / "manager"
SCRIPT = ROOT.parent.parent / "apiops-versioner" / "extrair_estrutura.py"
CASES = ["api-417-rev2", "api-400-rev4"]


def _script():
    spec = importlib.util.spec_from_file_location("extrair_estrutura", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _readable(text):
    """Contorna o defeito conhecido do script: `replaceChar: *****` sem aspas não parseia
    (reparo 23 da fila). O orquestrador já cita o escalar; aqui só se cita para comparar."""
    return re.sub(r"^(\s*[\w-]+: )(\*+)\s*$", r'\1"\2"', text, flags=re.M)


def _swagger(revision):
    """OpenAPI 3 sintético: contact, tags, security, components e uma rota documentada por operação."""
    paths = {}
    for resource in revision["resources"]:
        for op in resource.get("operations") or []:
            paths.setdefault(op["path"], {"parameters": [{"name": "tenant", "in": "header", "schema": {"type": "string"}}]})
            paths[op["path"]][op["method"].lower()] = {
                "summary": f"Rota {op['method']} {op['path']}",
                "parameters": [{"$ref": "#/components/parameters/Pagina"}, None],
                "responses": {"200": {"description": "OK", "x-flag": True}},
                "x-interceptors": {},
            }
    return {
        "openapi": "3.0.1",
        "info": {"title": "Lab", "contact": {"name": "Time", "x-slack": "#lab"}},
        "tags": [{"name": "Lab"}],
        "security": [{"Token": []}],
        "components": {
            "schemas": {"Tarefa": {"type": "object", "properties": {"x-id": {"type": "string"}}}},
            "parameters": {"Pagina": {"name": "page", "in": "query", "schema": {"type": "integer"}}},
            "securitySchemes": {"Token": {"type": "http", "scheme": "bearer"}},
        },
        "paths": paths,
    }


def _canonical(value):
    """Forma comparável: números e strings numéricas iguais; descrição vazia some."""
    if isinstance(value, dict):
        return {
            k: _canonical(v)
            for k, v in value.items()
            if not (k == "description" and v in ("", None))
        }
    if isinstance(value, list):
        return [_canonical(v) for v in value]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return value
    return value


@pytest.mark.parametrize("name", CASES)
@pytest.mark.skipif(not SCRIPT.is_file(), reason="extrair_estrutura.py ausente")
@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_mesma_arvore_que_o_script_no_yaml_relido(name, tmp_path):
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    script = _script()
    script.avisos.clear()
    swagger = _swagger(data["revision"])
    script.gerar(data["api"], data["revision"], swagger, str(tmp_path))
    from_script = {
        str(p.relative_to(tmp_path)).replace("\\", "/"): yaml.safe_load(_readable(p.read_text(encoding="utf-8")))
        for p in tmp_path.rglob("*.yaml")
    }

    result = materialize(Api.model_validate(data["api"]), Revision.model_validate(data["revision"]), swagger=swagger)
    from_orchestrator = {f.file_path: yaml.safe_load(f.text) for f in result.files}

    assert set(from_orchestrator) == set(from_script)
    for path in sorted(from_script):
        assert _canonical(from_orchestrator[path]) == _canonical(from_script[path]), path
