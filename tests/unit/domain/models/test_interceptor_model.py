"""Modelos de interceptor: ida e volta pelo wire e o Custom guardado no `content`."""

import json
import pathlib

from apiops_orchestrator.domain.models.api_model import Revision
from apiops_orchestrator.domain.models.interceptor_model import CustomInterceptor, Interceptor

FIXTURES = pathlib.Path(__file__).parents[3] / "fixtures" / "manager"


def _revision_wire():
    return json.loads((FIXTURES / "api-417-rev2.json").read_text(encoding="utf-8"))["revision"]


def test_interceptor_volta_ao_wire_sem_perder_campos():
    for item in _revision_wire()["interceptors"]:
        assert Interceptor.model_validate(item).to_wire() == item


def test_revisao_com_interceptors_volta_ao_wire_sem_perder_campos():
    wire = _revision_wire()
    assert Revision.model_validate(wire).to_wire() == wire


def test_custom_do_catalogo_guarda_o_que_nao_declara():
    wire = {"id": 32, "name": "Release Notes", "script": "//release", "abort": False, "tags": ["APIOps"]}
    custom = CustomInterceptor.model_validate(wire)
    assert (custom.id, custom.name) == (32, "Release Notes")
    assert custom.to_wire() == wire


def test_custom_guardado_como_texto_no_content():
    item = Interceptor.model_validate({
        "type": "Custom",
        "customInterceptorId": 125,
        "content": '{"id":125,"name":"Release notes","script":"//x"}',
    })
    assert (item.custom.id, item.custom.name, item.custom.script) == (125, "Release notes", "//x")


def test_custom_guardado_como_objeto_no_content():
    item = Interceptor.model_validate(
        {"type": "Custom", "customInterceptorId": 32, "content": {"id": 32, "name": "Release Notes"}}
    )
    assert item.custom.name == "Release Notes"


def test_sem_custom_quando_o_item_nao_e_custom_ou_o_content_nao_serve():
    assert Interceptor.model_validate({"type": "Log", "content": '{"acceptedTerms": true}'}).custom is None
    for content in ("não é json", "[1, 2]", '{"id": "abc"}', None):
        item = Interceptor.model_validate({"type": "Custom", "customInterceptorId": 32, "content": content})
        assert item.custom is None, content
