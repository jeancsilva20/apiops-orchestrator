"""Contrato `apiops.sen-sync/v1` nos dois modos."""

from apiops_orchestrator.domain.models.sync_view import (
    MODE_CHECK,
    MODE_LOAD,
    SCHEMA_SEN_SYNC_V1,
    SyncView,
)
from apiops_orchestrator.domain.models.validate_view import ValidateApi, ValidateRevision
from apiops_orchestrator.domain.services.revision_diff import Difference


def _view(mode, **overrides):
    base = dict(
        schema=SCHEMA_SEN_SYNC_V1,
        generated_at="2026-11-13T12:00:00Z",
        mode=mode,
        api=ValidateApi(manager_id=425, name="Lab", version="1.0.0", base_path="/lab/v1"),
        revision=ValidateRevision(manager_id=9999, revision_number=4),
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
        "schema", "generatedAt", "mode", "api", "revision", "files", "counts", "longestPath", "warnings",
    ]
    assert doc["mode"] == "load"
    assert doc["counts"] == {"files": 4, "resources": 1, "operations": 1}
    assert doc["longestPath"] == "resources/a/resource.yaml"
    assert "differences" not in doc


def test_documento_da_verificacao_com_diferencas():
    diff = Difference("all.yaml", "destination.timeout", "30", "99")
    doc = _view(MODE_CHECK, files=[], differences=[diff]).to_document()
    assert list(doc) == [
        "schema", "generatedAt", "mode", "api", "revision", "inSync", "differences", "warnings",
    ]
    assert doc["inSync"] is False
    assert doc["differences"] == [
        {"file": "all.yaml", "field": "destination.timeout", "repository": "30", "manager": "99"}
    ]
    assert "files" not in doc


def test_verificacao_sem_diferencas_esta_em_sincronia():
    view = _view(MODE_CHECK, files=[])
    assert view.in_sync is True
    assert view.to_document()["inSync"] is True
