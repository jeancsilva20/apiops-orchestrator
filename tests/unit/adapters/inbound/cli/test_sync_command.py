"""Borda do `sen sync`: gramática, exit codes, documento e ausência de token na saída."""

import json

import pytest
from typer.testing import CliRunner

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from apiops_orchestrator.application.exceptions.login_exceptions import (
    AuthenticationRejectedError,
)
from apiops_orchestrator.application.exceptions.sync_exceptions import (
    ApiNotFoundError,
    RevisionNotFoundError,
    SyncError,
    WriteFailedError,
)
from apiops_orchestrator.domain.models.sync_view import (
    MODE_CHECK,
    MODE_LOAD,
    SCHEMA_SEN_SYNC_V1,
    SyncView,
)
from apiops_orchestrator.domain.models.validate_view import ValidateApi, ValidateRevision
from apiops_orchestrator.domain.services.revision_diff import Difference

runner = CliRunner()


def _view(mode=MODE_LOAD, **overrides):
    base = dict(
        schema=SCHEMA_SEN_SYNC_V1,
        generated_at="2026-11-13T12:00:00Z",
        mode=mode,
        api=ValidateApi(manager_id=425, name="API Lab", version="1.0.0", base_path="/lab/v1"),
        revision=ValidateRevision(manager_id=9999, revision_number=4),
        files=["all.yaml", "api-basic-info.yaml", "resources/a/get_a.yaml", "resources/a/resource.yaml"],
        resources=1,
        operations=1,
        warnings=["recurso Quebra: Log próprio repete um herdado idêntico"],
    )
    base.update(overrides)
    return SyncView(**base)


class _ServiceFake:
    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error
        self.calls = []

    def _run(self, name, repo_path, *, api_id, revision_number, progress=None):
        self.calls.append((name, api_id, revision_number))
        if progress is not None:
            progress("Consultando a API no Manager")
        if self._error is not None:
            raise self._error
        return self._result

    def sync(self, repo_path, **kw):
        return self._run("sync", repo_path, **kw)

    def check(self, repo_path, **kw):
        return self._run("check", repo_path, **kw)


def _ctx(service):
    return {"sync_service_factory": lambda: service}


def test_carga_com_id_e_revisao():
    service = _ServiceFake(_view())
    result = runner.invoke(app, ["sen", "sync", "425", "--revision", "4"], obj=_ctx(service))
    assert result.exit_code == 0, result.output
    assert service.calls == [("sync", 425, 4)]
    assert "API Lab" in result.output and "resources/a/get_a.yaml" in result.output
    assert "Próximo passo" in result.output


def test_sem_id_passa_none_ao_servico():
    service = _ServiceFake(_view())
    result = runner.invoke(app, ["sen", "sync", "-r", "2"], obj=_ctx(service))
    assert result.exit_code == 0, result.output
    assert service.calls == [("sync", None, 2)]


def test_revision_e_obrigatoria():
    service = _ServiceFake(_view())
    result = runner.invoke(app, ["sen", "sync", "425"], obj=_ctx(service))
    assert result.exit_code == 2 and service.calls == []


def test_saida_json_so_com_o_documento():
    result = runner.invoke(
        app, ["sen", "sync", "425", "--revision", "4", "-o", "json"], obj=_ctx(_ServiceFake(_view()))
    )
    assert result.exit_code == 0, result.output
    document = json.loads(result.stdout)
    assert document["schema"] == SCHEMA_SEN_SYNC_V1 and document["mode"] == "load"
    assert document["counts"] == {"files": 4, "resources": 1, "operations": 1}


def test_check_em_sincronia_sai_zero():
    service = _ServiceFake(_view(MODE_CHECK, files=[]))
    result = runner.invoke(app, ["sen", "sync", "--check", "--revision", "2"], obj=_ctx(service))
    assert result.exit_code == 0, result.output
    assert service.calls == [("check", None, 2)]
    assert "iguais" in result.output


def test_check_com_diferenca_sai_oito_e_lista_arquivo_campo_e_valores():
    diff = Difference("resources/a/get_a.yaml", "destination.timeout", "30", "99")
    service = _ServiceFake(_view(MODE_CHECK, files=[], differences=[diff]))
    result = runner.invoke(app, ["sen", "sync", "--check", "-r", "2"], obj=_ctx(service))
    assert result.exit_code == 8
    for piece in ("resources/a/get_a.yaml", "destination.timeout", "30", "99"):
        assert piece in result.output


def test_check_com_diferenca_em_json_tambem_sai_oito():
    diff = Difference("all.yaml", "destination.timeout", "30", "45")
    service = _ServiceFake(_view(MODE_CHECK, files=[], differences=[diff]))
    result = runner.invoke(
        app, ["sen", "sync", "--check", "-r", "4", "-o", "json"], obj=_ctx(service)
    )
    assert result.exit_code == 8
    document = json.loads(result.stdout)
    assert document["inSync"] is False and document["differences"][0]["field"] == "destination.timeout"


@pytest.mark.parametrize(
    "error, code",
    [
        (SyncError("x"), 1),
        (ApiNotFoundError(425), 3),
        (RevisionNotFoundError(425, 4, [1, 2]), 4),
        (WriteFailedError("caminho longo", "resources/x.yaml"), 6),
        (AuthenticationRejectedError("Sessão inválida ou ausente: faça `sen login`."), 2),
    ],
)
def test_exit_codes_por_categoria(error, code):
    result = runner.invoke(
        app, ["sen", "sync", "425", "--revision", "4"], obj=_ctx(_ServiceFake(error=error))
    )
    assert result.exit_code == code, result.output
    assert "Erro:" in result.output


def test_factory_ausente():
    result = runner.invoke(app, ["sen", "sync", "425", "--revision", "4"], obj={})
    assert result.exit_code == 1 and "indisponível" in result.output


def test_nenhum_token_na_saida():
    service = _ServiceFake(_view())
    result = runner.invoke(app, ["sen", "sync", "425", "-r", "4"], obj=_ctx(service))
    assert "Bearer" not in result.output and "eyJ" not in result.output
