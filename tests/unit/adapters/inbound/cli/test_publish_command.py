"""Testes da BORDA do `sen publish`.

Gramática do comando, contrato JSON, exit codes e saída em texto. O serviço é
injetado por `ctx.obj` — a CLI é testada sem rede.
"""

import json

import pytest
from typer.testing import CliRunner

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from apiops_orchestrator.application.exceptions.validate_exceptions import (
    GovernanceBlockedError,
    IdentityMismatchError,
    ValidateError,
)
from apiops_orchestrator.application.services.publish_service import (
    PUBLISH_PIPELINE_ONLY,
)
from apiops_orchestrator.domain.models.deploy_model import DeployEnvironment
from apiops_orchestrator.domain.models.publish_view import (
    SCHEMA_SEN_PUBLISH_V1,
    PublishView,
    RevisionDeployment,
)
from apiops_orchestrator.domain.models.validate_view import (
    DOCUMENTATION_NOT_UPDATED,
    DocumentationResult,
    RequiredAttribute,
    GovernanceResult,
    PublicationResult,
    ValidateApi,
    ValidateRevision,
)

runner = CliRunner()


def _view(**overrides) -> PublishView:
    base = dict(
        schema=SCHEMA_SEN_PUBLISH_V1,
        generated_at="2026-10-16T14:00:00Z",
        execution_mode="pipeline",
        api=ValidateApi(
            manager_id=417, name="Servico de Letras", version="1.0.0", base_path="/letras/v2"
        ),
        revision=ValidateRevision(manager_id=9175, revision_number=2),
        governance=GovernanceResult(
            workflow_id=500,
            stage_id=1402,
            required=[RequiredAttribute(149, "My new")],
        ),
        publication=PublicationResult(attempted=True, accepted=True, verified=True),
        warnings=["O `timeout` da raiz passa a 30000 ms."],
    )
    base.update(overrides)
    return PublishView(**base)


class _ServicoFake:
    def __init__(self, resultado=None, erro=None):
        self._resultado = resultado
        self._erro = erro
        self.chamado_com = None

    def publish(self, repo_path, *, progress=None):
        self.chamado_com = {"repo_path": repo_path, "progresso": progress}
        if self._erro is not None:
            raise self._erro
        if progress is not None:
            progress("Lendo o repositório")
        return self._resultado


def _ctx(servico):
    return {"publish_service_factory": lambda: servico}


# --- gramática ---------------------------------------------------------------


def test_comando_registrado_com_as_flags_do_contrato():
    resultado = runner.invoke(app, ["sen", "publish", "--help"])
    assert resultado.exit_code == 0
    for flag in ("--repo", "--output", "--verbose"):
        assert flag in resultado.output


def test_comando_aparece_no_help_do_sen():
    resultado = runner.invoke(app, ["sen", "--help"])
    assert "publish" in resultado.output


def test_servico_ausente_no_contexto_encerra_com_1():
    resultado = runner.invoke(app, ["sen", "publish"], obj={})
    assert resultado.exit_code == 1
    assert "indisponível" in resultado.output


def test_progresso_e_injetado_pela_cli_sem_confirmacao():
    servico = _ServicoFake(resultado=_view())
    runner.invoke(app, ["sen", "publish", "-o", "json"], obj=_ctx(servico))
    assert set(servico.chamado_com) == {"repo_path", "progresso"}
    assert callable(servico.chamado_com["progresso"])
    assert servico.chamado_com["repo_path"] is not None


# --- contrato JSON -------------------------------------------------------------


def test_json_conforme_ao_contrato_v1():
    servico = _ServicoFake(resultado=_view())
    resultado = runner.invoke(app, ["sen", "publish", "-o", "json"], obj=_ctx(servico))
    assert resultado.exit_code == 0

    doc = json.loads(resultado.output)
    assert doc["schema"] == "apiops.sen-publish/v1"
    assert doc["executionMode"] == "pipeline"
    assert doc["revision"] == {"managerId": 9175, "revisionNumber": 2, "deployments": []}
    assert doc["publication"]["verified"] is True
    assert doc["warnings"] == ["O `timeout` da raiz passa a 30000 ms."]


@pytest.mark.parametrize("formato", ["json", "yaml"])
def test_progresso_nao_contamina_saida_legivel_por_maquina(formato):
    servico = _ServicoFake(resultado=_view())
    resultado = runner.invoke(app, ["sen", "publish", "-o", formato], obj=_ctx(servico))
    assert resultado.exit_code == 0
    assert "Lendo o repositório" not in resultado.output
    assert resultado.output.lstrip().startswith("{" if formato == "json" else "schema")


# --- texto -------------------------------------------------------------------


def test_texto_mostra_a_revisao_alvo_e_o_resultado():
    servico = _ServicoFake(resultado=_view())
    resultado = runner.invoke(app, ["sen", "publish"], obj=_ctx(servico))
    output = " ".join(resultado.output.split())

    assert resultado.exit_code == 0
    assert "Publicação" in output
    assert "#2" in output and "9175" in output
    assert "Revisão 2 gravada" in output
    assert "30000 ms" in output
    assert "Modo" not in output and "pipeline" not in output



_NO_AR = [
    RevisionDeployment(
        deployment_id=269,
        environment=DeployEnvironment(manager_id=7, name="DEV-APIOPS"),
        deployed_at="2026-10-19T14:02:11Z",
    )
]


def test_json_traz_os_ambientes_com_a_revisao_no_ar():
    servico = _ServicoFake(resultado=_view(deployments=_NO_AR))
    resultado = runner.invoke(app, ["sen", "publish", "-o", "json"], obj=_ctx(servico))

    assert json.loads(resultado.output)["revision"]["deployments"] == [
        {
            "deploymentId": 269,
            "environment": {"managerId": 7, "name": "DEV-APIOPS"},
            "deployedAt": "2026-10-19T14:02:11Z",
        }
    ]


def test_texto_mostra_onde_a_revisao_esta_deployada():
    servico = _ServicoFake(resultado=_view(deployments=_NO_AR))
    resultado = runner.invoke(app, ["sen", "publish"], obj=_ctx(servico))
    output = " ".join(resultado.output.split())

    assert "deployada em DEV-APIOPS (id 7) · deploy em 2026-10-19T14:02:11Z" in output


def test_texto_ambiente_sem_nome_mostra_so_o_id():
    sem_nome = [RevisionDeployment(deployment_id=271, environment=DeployEnvironment(9))]
    servico = _ServicoFake(resultado=_view(deployments=sem_nome))
    resultado = runner.invoke(app, ["sen", "publish"], obj=_ctx(servico))
    output = " ".join(resultado.output.split())

    assert "deployada em (id 9)" in output


def test_texto_revisao_fora_do_ar_avisa():
    servico = _ServicoFake(resultado=_view())
    resultado = runner.invoke(app, ["sen", "publish"], obj=_ctx(servico))
    output = " ".join(resultado.output.split())

    assert "não está deployada em nenhum ambiente" in output


def test_recusa_fora_da_esteira_encerra_com_1():
    erro = ValidateError(PUBLISH_PIPELINE_ONLY)
    resultado = runner.invoke(app, ["sen", "publish"], obj=_ctx(_ServicoFake(erro=erro)))
    output = " ".join(resultado.output.split())

    assert resultado.exit_code == 1
    assert "A publicação é feita só pela esteira" in output
    assert "Deseja prosseguir?" not in output


# --- exit codes ----------------------------------------------------------------


@pytest.mark.parametrize(
    "erro",
    [
        ValidateError("TARGET_REVISION_NUMBER não está definida."),
        IdentityMismatchError("basePath", "/letras/v9", "/letras/v2", 417),
    ],
)
def test_exit_1_para_falha_de_configuracao_ou_tecnica(erro):
    resultado = runner.invoke(app, ["sen", "publish"], obj=_ctx(_ServicoFake(erro=erro)))
    assert resultado.exit_code == 1
    assert "Erro:" in resultado.output


def test_exit_3_para_bloqueio_de_governanca():
    erro = GovernanceBlockedError(500, 1402, [{"attributeId": 149, "name": "My new"}])
    resultado = runner.invoke(app, ["sen", "publish"], obj=_ctx(_ServicoFake(erro=erro)))
    assert resultado.exit_code == 3
    assert "My new" in resultado.output


def test_erro_inesperado_encerra_com_1_sem_stack():
    resultado = runner.invoke(
        app, ["sen", "publish"], obj=_ctx(_ServicoFake(erro=RuntimeError("boom")))
    )
    assert resultado.exit_code == 1
    assert "Traceback" not in resultado.output


def test_text_shows_why_the_documentation_was_not_updated_apart_from_the_flow_warnings():
    reason = "O Manager recusou a gravação do contrato: Swagger inválido"
    short = "Estas descrições têm menos caracteres que o mínimo"
    view = _view(
        documentation=DocumentationResult(status=DOCUMENTATION_NOT_UPDATED, reason=reason, warnings=[short]),
        warnings=["O `timeout` da raiz passa a 30000 ms.", short, reason],
    )

    resultado = runner.invoke(app, ["sen", "publish"], obj=_ctx(_ServicoFake(resultado=view)))
    output = " ".join(resultado.output.split())

    assert resultado.exit_code == 0
    assert "O que vai mudar no Manager 1 aviso(s)" in output
    assert "Documentação atualizada não" in output
    assert output.count("Swagger inválido") == 1
    assert output.count("menos caracteres que o mínimo") == 1
