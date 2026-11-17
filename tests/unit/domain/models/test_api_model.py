"""Modelos do Manager: tipados no que o domínio lê, intactos no resto (round-trip)."""

import json
import pathlib

import pytest

from apiops_orchestrator.domain.models.api_model import Api, Revision
from apiops_orchestrator.domain.models.interceptor_model import Interceptor

FIXTURES = pathlib.Path(__file__).parents[3] / "fixtures" / "manager"
CASES = ["api-417-rev2", "api-400-rev4"]


def _fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", CASES)
@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_round_trip_da_api_real(name):
    raw = _fixture(name)["api"]
    assert Api.model_validate(raw).to_wire() == raw


@pytest.mark.parametrize("name", CASES)
@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_round_trip_da_revisao_real(name):
    raw = _fixture(name)["revision"]
    assert Revision.model_validate(raw).to_wire() == raw


def test_campos_desconhecidos_viajam_intactos():
    raw = {
        "id": 9175,
        "revisionNumber": 2,
        "workflowId": 500,
        "workflowStageId": 1402,
        "resources": [
            {
                "name": "Tarefas",
                "certificateId": 7,
                "operations": [{"method": "GET", "path": "/tarefas", "connector": {"a": 1}}],
            }
        ],
        "interceptors": [{"id": 1, "type": "Log", "executionPoint": "FIRST", "async": True}],
    }
    revision = Revision.model_validate(raw)
    assert revision.resources[0].operations[0].route == ("GET", "/tarefas")
    assert revision.interceptors[0].execution_point == "FIRST"
    assert revision.to_wire() == raw


def test_listas_nulas_viram_vazias_na_leitura():
    revision = Revision.model_validate({"id": 1, "interceptors": None, "resources": None})
    assert revision.interceptors == [] and revision.resources == []


def test_tipos_instaveis_do_manager_sao_aceitos():
    item = Interceptor.model_validate(
        {"type": "Rate limit", "content": '{"quota": "1000"}', "customInterceptorId": None,
         "parent": {"id": 19422, "idTemp": 19422}, "status": "REMOVED"}
    )
    assert item.parent_id == 19422 and item.label == "Rate limit"
    assert Interceptor.model_validate({"type": "Custom", "customInterceptorId": 32}).label == "Custom#32"
    assert Revision.model_validate({"timeout": "30"}).timeout == "30"
    assert Revision.model_validate({"timeout": 30}).timeout == 30


def test_api_resolve_a_revisao_pelo_numero():
    api = Api.model_validate(
        {"id": 425, "apiTags": None, "revisions": [{"id": 9692, "revisionNumber": 4}, {"revisionNumber": 5}]}
    )
    assert api.revision_by_number(4).id == 9692
    assert api.revision_by_number(5) is None
    assert api.revision_numbers == [4, 5]
    assert api.api_tags is None
