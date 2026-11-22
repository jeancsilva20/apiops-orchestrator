"""Contrato `apiops.sen-sync/v1` nos dois modos."""

from apiops_orchestrator.domain.models.sync_view import (
    MODE_CHECK,
    MODE_LOAD,
    SCHEMA_SEN_SYNC_V1,
    SyncView,
)
from apiops_orchestrator.domain.models.interceptor_model import CustomInterceptor
from apiops_orchestrator.domain.models.validate_view import ValidateApi, ValidateRevision
from apiops_orchestrator.domain.services.revision_diff import ABSENT, Difference


def _view(mode, **overrides):
    base = dict(
        schema=SCHEMA_SEN_SYNC_V1,
        generated_at="2026-11-13T12:00:00Z",
        mode=mode,
        api=ValidateApi(manager_id=425, name="Lab", version="1.0.0", base_path="/lab/v1"),
        revision=ValidateRevision(manager_id=9999, revision_number=4),
        repository="C:/repos/lab",
        files=["all.yaml", "api-basic-info.yaml", "resources/a/get_a.yaml", "resources/a/resource.yaml"],
        resources=1,
        operations=1,
        warnings=["aviso"],
    )
    base.update(overrides)
    return SyncView(**base)


def test_documento_da_carga():
    doc = _view(MODE_LOAD).to_document()
    assert list(doc) == [
        "schema", "generatedAt", "mode", "api", "revision", "repository", "files", "counts", "warnings",
    ]
    assert doc["mode"] == "load"
    assert doc["counts"] == {"files": 4, "resources": 1, "operations": 1}
    assert doc["repository"] == "C:/repos/lab"
    assert "differences" not in doc


def test_documento_da_verificacao_com_diferencas():
    diff = Difference("all.yaml", "destination.timeout", "30", "99")
    doc = _view(MODE_CHECK, files=[], differences=[diff]).to_document()
    assert list(doc) == [
        "schema", "generatedAt", "mode", "api", "revision", "inSync", "differences",
        "customInterceptors", "warnings",
    ]
    assert doc["inSync"] is False
    assert doc["differences"] == [
        {"file": "all.yaml", "field": "destination.timeout", "repository": "30", "manager": "99"}
    ]
    assert doc["customInterceptors"] == []
    assert "files" not in doc and "repository" not in doc


def test_verificacao_traz_nome_e_catalogo_dos_customs_das_diferencas():
    diff = Difference(
        "all.yaml", "interceptors_request", [{"type": "Custom", "id": 32}, {"type": "Custom", "id": 125}], ABSENT
    )
    customs = [
        CustomInterceptor(id=32, name="Release Notes", script="//release"),
        CustomInterceptor(id=125, name="Release notes"),
    ]
    view = _view(
        MODE_CHECK, files=[], differences=[diff], custom_interceptors=customs, outside_catalog=[125]
    )
    # The script stays out of the document: id, name and catalog presence only.
    assert view.to_document()["customInterceptors"] == [
        {"id": 32, "name": "Release Notes", "inCatalog": True},
        {"id": 125, "name": "Release notes", "inCatalog": False},
    ]


def test_catalogo_nao_lido_deixa_a_presenca_em_aberto():
    view = _view(MODE_CHECK, files=[], custom_interceptors=[CustomInterceptor(id=32)])
    assert view.in_catalog(32) is None
    assert view.to_document()["customInterceptors"] == [{"id": 32, "name": None, "inCatalog": None}]


def test_verificacao_sem_diferencas_esta_em_sincronia():
    view = _view(MODE_CHECK, files=[])
    assert view.in_sync is True
    assert view.to_document()["inSync"] is True
