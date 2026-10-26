"""Dado externo com colchetes sai literal em toda tela, nunca como marcação do Rich.

`[/x]` é a tag de fechamento órfã que derrubava a renderização (MarkupError);
`[bold]` é a tag de abertura que sumiria em silêncio e estilizaria o resto.
"""

from unittest.mock import MagicMock

from rich.text import Text
from typer.testing import CliRunner

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import _literal, app
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    _translate_row,
)
from apiops_orchestrator.application.exceptions.validate_exceptions import ValidateError
from apiops_orchestrator.domain.models.catalog_revision_model import CatalogRevisionInfo
from apiops_orchestrator.domain.models.completeness_view import (
    CompletenessApi,
    CompletenessSuggestion,
    CompletenessView,
)
from apiops_orchestrator.domain.models.deploy_model import (
    SCHEMA_SEN_DEPLOY_V1,
    DeployEnvironment,
    DeployGovernance,
    DeploymentResult,
    DeployState,
    DeployView,
)
from apiops_orchestrator.domain.models.publish_view import (
    SCHEMA_SEN_PUBLISH_V1,
    PublishView,
    RevisionDeployment,
)
from apiops_orchestrator.domain.models.validate_view import (
    REPOSITORY_SCOPE,
    SCHEMA_SEN_VALIDATE_V1,
    SEVERITY_WARNING,
    Finding,
    RequiredAttribute,
    CompletenessSummary,
    GovernanceResult,
    PublicationResult,
    RulerSnapshot,
    ValidateApi,
    ValidateRevision,
    ValidateView,
)

runner = CliRunner()
LARGO = {"COLUMNS": "200"}


def _plano(resultado) -> str:
    return " ".join(resultado.output.split())


def _sem_erro_interno(resultado) -> None:
    assert "erro interno" not in resultado.output


def test_literal_devolve_o_texto_original_dentro_de_marcacao():
    value = "Basepath [/api-sga-notificacao] e [bold]negrito[/bold] \\"

    assert Text.from_markup(f"[white]{_literal(value)}[/white]").plain == value


def test_list_api_mostra_nome_e_base_path_com_colchetes():
    servico = MagicMock()
    servico.list_apis.return_value = [
        _translate_row(
            {"apiId": 1, "apiName": "API [/x]", "basePath": "/a[bold]b", "version": "1.0"}
        )
    ]

    resultado = runner.invoke(
        app, ["sen", "list", "api"], obj={"api_listing_service_factory": lambda: servico}, env=LARGO
    )

    assert resultado.exit_code == 0, resultado.output
    assert "API [/x]" in resultado.output
    assert "/a[bold]b" in resultado.output


def test_list_revisions_mostra_stage_e_ambiente_com_colchetes():
    servico = MagicMock()
    servico.api_revisions.return_value = [
        CatalogRevisionInfo(
            revision_id=10, revision_number=1, stage_name="Stage [/x]",
            environments="DEV [bold]", completeness_score=74.0,
        )
    ]

    resultado = runner.invoke(
        app,
        ["sen", "list", "api", "--id", "68", "--revisions"],
        obj={"api_listing_service_factory": lambda: servico},
        env=LARGO,
    )

    assert resultado.exit_code == 0, resultado.output
    assert "Stage [/x]" in resultado.output
    assert "DEV [bold]" in resultado.output


def test_completeness_mostra_a_sugestao_do_basepath_que_quebrava():
    view = CompletenessView(
        schema="apiops.sen-completeness/v1",
        generated_at="2026-10-21T11:24:51Z",
        api=CompletenessApi(manager_id=68, name="api-sga-notificacao [/x]", version="1.0.0"),
        revision_id=28541,
        revision_number=4,
        score=75.8,
        gate_percent=70.0,
        suggestions=[
            CompletenessSuggestion(
                index=1,
                text="Basepath [/api-sga-notificacao] is not compliant with the expected "
                "versioning format.",
            )
        ],
    )
    servico = MagicMock(get_completeness=lambda **_: view)

    resultado = runner.invoke(
        app,
        ["sen", "completeness", "--id", "68", "--revision", "28541"],
        obj={"completeness_service_factory": lambda: servico},
        env=LARGO,
    )

    assert resultado.exit_code == 0, resultado.output
    _sem_erro_interno(resultado)
    assert "Basepath [/api-sga-notificacao] is not compliant" in _plano(resultado)
    assert "api-sga-notificacao [/x]" in resultado.output


def _validate_view(**overrides) -> ValidateView:
    base = dict(
        schema=SCHEMA_SEN_VALIDATE_V1,
        generated_at="2026-10-21T12:00:00Z",
        execution_mode="local",
        api=ValidateApi(
            manager_id=68, name="Letras [/x]", version="1.0", base_path="/letras/[bold]v2"
        ),
        revision=ValidateRevision(manager_id=9161, revision_number=1),
        ruler=RulerSnapshot(template_id=414, revision_number=3, flow_hash="h[/x]", interceptors_count=8),
        findings=[
            Finding(SEVERITY_WARNING, "GET /a[/x]", "template [/x] diverge"),
            Finding(SEVERITY_WARNING, REPOSITORY_SCOPE, "repo [bold] muda"),
        ],
        governance=GovernanceResult(
            workflow_id=500, stage_id=1402, required=[RequiredAttribute(1, "Dono [/x]")]
        ),
        publication=PublicationResult(attempted=True, accepted=True, verified=True),
        completeness=CompletenessSummary(
            score=75.8, gate_percent=70.0, suggestions=["Basepath [/api-sga-notificacao] sem versão"]
        ),
    )
    base.update(overrides)
    return ValidateView(**base)


class _ValidateFake:
    def __init__(self, resultado=None, erro=None):
        self._resultado = resultado
        self._erro = erro

    def validate(self, repo_path, *, confirm, progress=None):
        if self._erro is not None:
            raise self._erro
        return self._resultado


def _invoke_validate(servico):
    return runner.invoke(
        app, ["sen", "validate"], obj={"validate_service_factory": lambda: servico}, env=LARGO
    )


def test_validate_mostra_dados_e_sugestoes_com_colchetes():
    resultado = _invoke_validate(_ValidateFake(_validate_view()))

    assert resultado.exit_code == 0, resultado.output
    _sem_erro_interno(resultado)
    plano = _plano(resultado)
    for trecho in (
        "Letras [/x]",
        "/letras/[bold]v2",
        "h[/x]",
        "template [/x] diverge",
        "repo [bold] muda",
        "Basepath [/api-sga-notificacao] sem versão",
    ):
        assert trecho in plano, trecho


def test_validate_mostra_faltantes_e_divergencias_com_colchetes():
    view = _validate_view(
        governance=GovernanceResult(
            workflow_id=500,
            stage_id=1402,
            required=[RequiredAttribute(1, "Dono [/x]")],
            missing=[RequiredAttribute(1, "Dono [/x]")],
        ),
        publication=PublicationResult(
            attempted=True, accepted=True, verified=False, divergences=["campo [/x] difere"]
        ),
    )

    resultado = _invoke_validate(_ValidateFake(view))

    _sem_erro_interno(resultado)
    plano = _plano(resultado)
    assert "falta: Dono [/x]" in plano
    assert "campo [/x] difere" in plano


def test_mensagem_de_erro_com_colchetes_sai_inteira():
    resultado = _invoke_validate(_ValidateFake(erro=ValidateError("Arquivo [/x] e [bold] inválido")))

    assert resultado.exit_code == 1
    assert "Erro: Arquivo [/x] e [bold] inválido" in _plano(resultado)


class _PublishFake:
    def __init__(self, resultado):
        self._resultado = resultado

    def publish(self, repo_path, *, progress=None):
        return self._resultado


def test_publish_mostra_api_avisos_e_ambientes_com_colchetes():
    view = PublishView(
        schema=SCHEMA_SEN_PUBLISH_V1,
        generated_at="2026-10-21T12:00:00Z",
        execution_mode="pipeline",
        api=ValidateApi(manager_id=68, name="Letras [/x]", version="1.0", base_path="/l[bold]"),
        revision=ValidateRevision(manager_id=9175, revision_number=2),
        governance=GovernanceResult(workflow_id=500, stage_id=1402),
        publication=PublicationResult(attempted=True, accepted=True, verified=True),
        warnings=["timeout [/x] muda"],
        deployments=[
            RevisionDeployment(
                deployment_id=1,
                environment=DeployEnvironment(manager_id=7, name="ECAD [/x] Dev"),
                deployed_at="2026-10-21",
            )
        ],
    )

    resultado = runner.invoke(
        app, ["sen", "publish"], obj={"publish_service_factory": lambda: _PublishFake(view)}, env=LARGO
    )

    assert resultado.exit_code == 0, resultado.output
    plano = _plano(resultado)
    for trecho in ("Letras [/x]", "/l[bold]", "timeout [/x] muda", "ECAD [/x] Dev"):
        assert trecho in plano, trecho


class _DeployFake:
    def __init__(self, resultado):
        self._resultado = resultado

    def deploy(self, repo_path, *, progress=None):
        return self._resultado


def test_deploy_mostra_ambiente_e_avisos_com_colchetes():
    view = DeployView(
        schema=SCHEMA_SEN_DEPLOY_V1,
        generated_at="2026-10-21T12:00:00Z",
        execution_mode="pipeline",
        api=ValidateApi(manager_id=68, name="Letras [/x]", version="1.0", base_path="/l"),
        revision=ValidateRevision(manager_id=9327, revision_number=3),
        environment=DeployEnvironment(manager_id=7, name="ECAD [/x] Dev"),
        governance=DeployGovernance(workflow_id=500, stage_id=1402, deployable_environments=[7]),
        previous_state=DeployState(268, 9175, 2, "ontem [/x]"),
        new_state=DeployState(269, 9327, 3, "hoje"),
        deployment=DeploymentResult(
            attempted=True, accepted=True, deployment_id=269, verified=True, status="SUCCESS"
        ),
        warnings=["aviso [bold] do deploy"],
    )

    resultado = runner.invoke(
        app, ["sen", "deploy"], obj={"deploy_service_factory": lambda: _DeployFake(view)}, env=LARGO
    )

    assert resultado.exit_code == 0, resultado.output
    plano = _plano(resultado)
    for trecho in ("Letras [/x]", "ECAD [/x] Dev", "ontem [/x]", "aviso [bold] do deploy"):
        assert trecho in plano, trecho
