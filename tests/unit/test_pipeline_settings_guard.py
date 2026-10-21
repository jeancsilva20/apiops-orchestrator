"""Guarda: fora da esteira, nenhuma saída nomeia o modo nem as variáveis da esteira.

Cobre o que o dev vê na própria máquina — `--help`, recusas de configuração,
painel e documento do `validate`, falha de carga das settings — e, na esteira,
que o modo nunca é nomeado (change `hide-pipeline-settings-from-dev`).
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pydantic
import pytest
from typer.testing import CliRunner

import apiops_orchestrator.main as main_mod
from apiops_orchestrator.adapters.inbound.cli.cli_adapter import CliError, app
from apiops_orchestrator.application.exceptions.deploy_exceptions import DeployError
from apiops_orchestrator.application.exceptions.validate_exceptions import (
    ValidateError,
)
from apiops_orchestrator.application.services import deploy_service, publish_service
from apiops_orchestrator.domain.models.validate_view import (
    SCHEMA_SEN_VALIDATE_V1,
    PublicacaoResultado,
    ReguaSnapshot,
    ValidateApi,
    ValidateRevision,
    ValidateView,
)

runner = CliRunner()

PROIBIDOS_FORA_DA_ESTEIRA = (
    "EXECUTION_MODE",
    "TARGET_REVISION_NUMBER",
    "TARGET_ENVIRONMENT_ID",
    "TEMPLATE_API_ID",
    "pipeline",
    "executionMode",
    "modo local",
)

FORA_DA_ESTEIRA = SimpleNamespace(modo_pipeline=False)


def _sem_proibidos(texto: str) -> None:
    for nome in PROIBIDOS_FORA_DA_ESTEIRA:
        assert nome not in texto, nome


# --- help ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["sen", "--help"],
        ["sen", "list", "--help"],
        ["sen", "list", "api", "--help"],
        ["sen", "login", "--help"],
        ["sen", "completeness", "--help"],
        ["sen", "validate", "--help"],
        ["sen", "publish", "--help"],
        ["sen", "deploy", "--help"],
    ],
)
def test_help_nao_nomeia_a_configuracao_da_esteira(argv):
    resultado = runner.invoke(app, argv)

    assert resultado.exit_code == 0
    _sem_proibidos(resultado.output)


# --- recusas fora da esteira ---------------------------------------------------


def test_recusa_do_publish_nao_nomeia_a_esteira_por_dentro():
    with pytest.raises(ValidateError) as capturado:
        publish_service.exigir_esteira(FORA_DA_ESTEIRA)

    assert "não roda na sua máquina" in capturado.value.message
    _sem_proibidos(capturado.value.message)


def test_recusa_do_deploy_nao_nomeia_a_esteira_por_dentro():
    with pytest.raises(DeployError) as capturado:
        deploy_service.exigir_esteira(FORA_DA_ESTEIRA)

    assert "não roda na sua máquina" in capturado.value.message
    _sem_proibidos(capturado.value.message)


@pytest.mark.parametrize(
    "construtora,erro",
    [
        ("build_publish_service_factory", ValidateError),
        ("build_deploy_service_factory", DeployError),
    ],
)
def test_factory_recusa_fora_da_esteira_antes_de_autenticar(monkeypatch, construtora, erro):
    monkeypatch.setattr(main_mod, "_load_settings", MagicMock(return_value=FORA_DA_ESTEIRA))
    monkeypatch.setattr(
        main_mod,
        "_build_admin_token",
        MagicMock(side_effect=AssertionError("não pode autenticar fora da esteira")),
    )

    with pytest.raises(erro):
        getattr(main_mod, construtora)()()


# --- validate na máquina do dev -------------------------------------------------


def _view_local() -> ValidateView:
    return ValidateView(
        schema=SCHEMA_SEN_VALIDATE_V1,
        generated_at="2026-10-21T12:00:00Z",
        execution_mode="local",
        api=ValidateApi(manager_id=417, name="Letras", version="1.0.0", base_path="/letras"),
        revision=ValidateRevision(manager_id=9161, revision_number=1),
        regua=ReguaSnapshot(template_id=414, revision_number=3, flow_hash="ab", interceptors_count=1),
        publicacao=PublicacaoResultado(attempted=True, accepted=True, verified=True),
    )


class _ValidateFake:
    def validate(self, repo_path, *, confirmar, progresso=None):
        return _view_local()


@pytest.mark.parametrize("formato", ["text", "json", "yaml"])
def test_saidas_do_validate_local_nao_mostram_o_modo(formato):
    resultado = runner.invoke(
        app,
        ["sen", "validate", "-o", formato],
        obj={"validate_service_factory": _ValidateFake},
    )

    assert resultado.exit_code == 0, resultado.output
    assert "Modo" not in resultado.output
    _sem_proibidos(resultado.output)


def test_documento_local_nao_tem_a_chave_do_modo():
    assert "executionMode" not in json.dumps(_view_local().to_document())


# --- falha de carga da configuração --------------------------------------------


def _settings_invalidas(monkeypatch, chaves):
    erro = pydantic.ValidationError.from_exception_data(
        title="Settings",
        line_errors=[{"type": "missing", "loc": (c,), "input": {}} for c in chaves],
    )
    monkeypatch.setattr(main_mod, "Settings", MagicMock(side_effect=erro))


def _mensagem_de_carga() -> str:
    with pytest.raises(CliError) as capturado:
        main_mod._load_settings()
    assert capturado.value.exit_code == 1
    return capturado.value.message


def test_credencial_ausente_e_nomeada(monkeypatch):
    monkeypatch.delenv("EXECUTION_MODE", raising=False)
    _settings_invalidas(monkeypatch, ["SEN_CREDENTIALS"])

    mensagem = _mensagem_de_carga()

    assert "SEN_CREDENTIALS" in mensagem
    assert main_mod.OUTRA_CONFIGURACAO_INVALIDA not in mensagem


@pytest.mark.parametrize("modo", ["xyz", "local", ""])
def test_fora_da_esteira_so_chaves_da_esteira_viram_mensagem_generica(monkeypatch, modo):
    monkeypatch.setenv("EXECUTION_MODE", modo)
    _settings_invalidas(monkeypatch, ["EXECUTION_MODE", "TARGET_REVISION_NUMBER"])

    mensagem = _mensagem_de_carga()

    assert mensagem == main_mod.CONFIGURACAO_INVALIDA
    _sem_proibidos(mensagem)


def test_chave_do_dev_e_chave_da_esteira_juntas(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", "xyz")
    _settings_invalidas(monkeypatch, ["SEN_CREDENTIALS", "EXECUTION_MODE"])

    mensagem = _mensagem_de_carga()

    assert "SEN_CREDENTIALS" in mensagem
    assert mensagem.endswith(main_mod.OUTRA_CONFIGURACAO_INVALIDA)
    _sem_proibidos(mensagem)


def test_na_esteira_a_variavel_e_nomeada_mas_o_modo_nao(monkeypatch):
    monkeypatch.setenv("EXECUTION_MODE", " Pipeline ")
    _settings_invalidas(monkeypatch, ["TARGET_REVISION_NUMBER", "EXECUTION_MODE"])

    mensagem = _mensagem_de_carga()

    assert "TARGET_REVISION_NUMBER" in mensagem
    assert "EXECUTION_MODE" not in mensagem
    assert mensagem.endswith(main_mod.OUTRA_CONFIGURACAO_INVALIDA)
