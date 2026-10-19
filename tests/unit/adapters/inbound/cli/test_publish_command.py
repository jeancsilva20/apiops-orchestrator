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
    IdentidadeDivergenteError,
    ValidateError,
)
from apiops_orchestrator.domain.models.publish_view import (
    SCHEMA_SEN_PUBLISH_V1,
    PublishView,
)
from apiops_orchestrator.domain.models.validate_view import (
    AtributoExigido,
    GovernancaResultado,
    PublicacaoResultado,
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
        governanca=GovernancaResultado(
            workflow_id=500,
            stage_id=1402,
            required=[AtributoExigido(149, "My new")],
        ),
        publicacao=PublicacaoResultado(attempted=True, accepted=True, verified=True),
        avisos=["O `timeout` da raiz passa a 30000 ms."],
    )
    base.update(overrides)
    return PublishView(**base)


class _ServicoFake:
    def __init__(self, resultado=None, erro=None):
        self._resultado = resultado
        self._erro = erro
        self.chamado_com = None

    def publish(self, repo_path, *, confirmar, progresso=None):
        self.chamado_com = {
            "repo_path": repo_path,
            "confirmar": confirmar,
            "progresso": progresso,
        }
        if self._erro is not None:
            raise self._erro
        if progresso is not None:
            progresso("Lendo o repositório")
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


def test_confirmacao_e_progresso_sao_injetados_pela_cli():
    servico = _ServicoFake(resultado=_view())
    runner.invoke(app, ["sen", "publish", "-o", "json"], obj=_ctx(servico))
    assert callable(servico.chamado_com["confirmar"])
    assert callable(servico.chamado_com["progresso"])
    assert servico.chamado_com["repo_path"] is not None


# --- contrato JSON -------------------------------------------------------------


def test_json_conforme_ao_contrato_v1():
    servico = _ServicoFake(resultado=_view())
    resultado = runner.invoke(app, ["sen", "publish", "-o", "json"], obj=_ctx(servico))
    assert resultado.exit_code == 0

    doc = json.loads(resultado.output)
    assert doc["schema"] == "apiops.sen-publish/v1"
    assert doc["revision"] == {"managerId": 9175, "revisionNumber": 2}
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
    saida = " ".join(resultado.output.split())

    assert resultado.exit_code == 0
    assert "Publicação" in saida
    assert "#2" in saida and "9175" in saida
    assert "Revisão 2 gravada" in saida
    assert "30000 ms" in saida


def test_responder_n_encerra_sem_relatorio():
    """Recusa não produz relatório — só o desfecho."""
    view = _view(execution_mode="local", publicacao=PublicacaoResultado(attempted=False))
    resultado = runner.invoke(app, ["sen", "publish"], obj=_ctx(_ServicoFake(resultado=view)))
    saida = " ".join(resultado.output.split())

    assert resultado.exit_code == 0
    assert "Publicação cancelada. Nada foi gravado." in saida
    assert "#2" not in saida and "30000 ms" not in saida


@pytest.mark.parametrize("entrada", ["", "﻿y\n"])
def test_ctrl_c_no_prompt_interrompe_com_130(entrada):
    class _ServicoQuePergunta(_ServicoFake):
        def publish(self, repo_path, *, confirmar, progresso=None):
            confirmar("O conteúdo deste repositório será gravado.")
            raise AssertionError("o comando deveria ter sido interrompido no prompt")

    resultado = runner.invoke(
        app, ["sen", "publish"], obj=_ctx(_ServicoQuePergunta()), input=entrada
    )

    assert resultado.exit_code == 130
    assert "Publicação cancelada. Nada foi gravado." in " ".join(resultado.output.split())


# --- exit codes ----------------------------------------------------------------


@pytest.mark.parametrize(
    "erro",
    [
        ValidateError("TARGET_REVISION_NUMBER não está definida."),
        IdentidadeDivergenteError("basePath", "/letras/v9", "/letras/v2", 417),
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
