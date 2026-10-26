"""Testes da borda do `sen deploy`: gramática, contrato JSON, exit codes e texto."""

import json

import pytest
from typer.testing import CliRunner

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from apiops_orchestrator.application.exceptions.deploy_exceptions import (
    DeployError,
    DeployFailedError,
    DeployGovernanceBlockedError,
)
from apiops_orchestrator.domain.models.deploy_model import (
    SCHEMA_SEN_DEPLOY_V1,
    DeployEnvironment,
    DeployGovernance,
    DeploymentResult,
    DeployState,
    DeployView,
)
from apiops_orchestrator.domain.models.validate_view import ValidateApi, ValidateRevision

runner = CliRunner()


def _view(**overrides) -> DeployView:
    base = dict(
        schema=SCHEMA_SEN_DEPLOY_V1,
        generated_at="2026-10-19T18:00:00Z",
        execution_mode="pipeline",
        api=ValidateApi(
            manager_id=417, name="Servico de Letras", version="1.0.0", base_path="/letras/v2"
        ),
        revision=ValidateRevision(manager_id=9327, revision_number=3),
        environment=DeployEnvironment(manager_id=7, name="DEV-APIOPS"),
        governance=DeployGovernance(workflow_id=500, stage_id=1402, deployable_environments=[7]),
        previous_state=DeployState(268, 9175, 2, "2026-10-19T17:00:00Z"),
        new_state=DeployState(269, 9327, 3, "2026-10-19T18:00:00Z"),
        deployment=DeploymentResult(
            attempted=True, accepted=True, deployment_id=269, verified=True, status="SUCCESS"
        ),
    )
    base.update(overrides)
    return DeployView(**base)


class _ServicoFake:
    def __init__(self, resultado=None, erro=None):
        self._resultado = resultado
        self._erro = erro
        self.chamado_com = None

    def deploy(self, repo_path, *, progress=None):
        self.chamado_com = {"repo_path": repo_path, "progresso": progress}
        if progress is not None:
            progress("Lendo o manifesto")
        if self._erro is not None:
            raise self._erro
        return self._resultado


def _ctx(servico):
    return {"deploy_service_factory": lambda: servico}


def _failure():
    view = _view(
        new_state=None,
        deployment=DeploymentResult(
            attempted=True, status="FAILED", reason="O Manager recusou o deploy"
        ),
    )
    return DeployFailedError("O Manager recusou o deploy:\n\n  - Environment not found.", view)


# --- gramática ---------------------------------------------------------------


def test_comando_registrado_com_as_flags_do_contrato():
    resultado = runner.invoke(app, ["sen", "deploy", "--help"])
    assert resultado.exit_code == 0
    for flag in ("--repo", "--output", "--verbose"):
        assert flag in resultado.output


def test_comando_aparece_no_help_do_sen():
    assert "deploy" in runner.invoke(app, ["sen", "--help"]).output


def test_servico_ausente_no_contexto_encerra_com_1():
    resultado = runner.invoke(app, ["sen", "deploy"], obj={})
    assert resultado.exit_code == 1
    assert "indisponível" in resultado.output


def test_progresso_e_repo_sao_injetados_pela_cli():
    servico = _ServicoFake(resultado=_view())
    runner.invoke(app, ["sen", "deploy", "-o", "json"], obj=_ctx(servico))
    assert callable(servico.chamado_com["progresso"])
    assert servico.chamado_com["repo_path"] is not None


# --- contrato ----------------------------------------------------------------


def test_json_conforme_ao_contrato_v1():
    resultado = runner.invoke(app, ["sen", "deploy", "-o", "json"], obj=_ctx(_ServicoFake(_view())))
    assert resultado.exit_code == 0

    doc = json.loads(resultado.output)
    assert doc["schema"] == "apiops.sen-deploy/v1"
    assert doc["environment"] == {"managerId": 7, "name": "DEV-APIOPS"}
    assert doc["previousState"]["revisionNumber"] == 2
    assert doc["newState"]["revisionNumber"] == 3
    assert doc["deployment"]["status"] == "SUCCESS"


@pytest.mark.parametrize("formato", ["json", "yaml"])
def test_progresso_nao_contamina_saida_legivel_por_maquina(formato):
    resultado = runner.invoke(
        app, ["sen", "deploy", "-o", formato], obj=_ctx(_ServicoFake(_view()))
    )
    assert resultado.exit_code == 0
    assert "Lendo o manifesto" not in resultado.output
    assert resultado.output.lstrip().startswith("{" if formato == "json" else "schema")


# --- texto -------------------------------------------------------------------


def test_texto_mostra_ambiente_estados_e_resultado():
    resultado = runner.invoke(app, ["sen", "deploy"], obj=_ctx(_ServicoFake(_view())))
    output = " ".join(resultado.output.split())

    assert resultado.exit_code == 0
    assert "DEV-APIOPS" in output and "#3" in output and "9327" in output
    assert "revisão #2" in output and "revisão #3" in output
    assert "Revisão 3 deployada no ambiente DEV-APIOPS" in output


def test_texto_sem_estado_anterior():
    resultado = runner.invoke(
        app, ["sen", "deploy"], obj=_ctx(_ServicoFake(_view(previous_state=None)))
    )
    assert "nenhuma revisão desta API deployada" in " ".join(resultado.output.split())


# --- exit codes --------------------------------------------------------------


def test_exit_1_para_falha_antes_da_escrita_sem_documento():
    erro = DeployError("A API 417 não está ligada ao ambiente 9.")
    resultado = runner.invoke(app, ["sen", "deploy", "-o", "json"], obj=_ctx(_ServicoFake(erro=erro)))

    assert resultado.exit_code == 1
    assert "ambiente 9" in resultado.output
    assert '"schema"' not in resultado.output


def test_exit_3_para_bloqueio_de_governanca():
    erro = DeployGovernanceBlockedError(500, 1402, ["A completeness da revisão é 65.0, e o stage exige 70.0."])
    resultado = runner.invoke(app, ["sen", "deploy"], obj=_ctx(_ServicoFake(erro=erro)))
    assert resultado.exit_code == 3
    assert "70.0" in resultado.output


def test_falha_da_escrita_em_json_emite_o_documento_com_failed():
    resultado = runner.invoke(
        app, ["sen", "deploy", "-o", "json"], obj=_ctx(_ServicoFake(erro=_failure()))
    )
    assert resultado.exit_code == 1
    doc = json.loads(resultado.output)
    assert doc["deployment"]["status"] == "FAILED"


def test_falha_da_escrita_em_texto_mostra_a_mensagem():
    resultado = runner.invoke(app, ["sen", "deploy"], obj=_ctx(_ServicoFake(erro=_failure())))
    assert resultado.exit_code == 1
    assert "Environment not found." in resultado.output


def test_erro_inesperado_encerra_com_1_sem_stack():
    resultado = runner.invoke(
        app, ["sen", "deploy"], obj=_ctx(_ServicoFake(erro=RuntimeError("boom")))
    )
    assert resultado.exit_code == 1
    assert "Traceback" not in resultado.output
