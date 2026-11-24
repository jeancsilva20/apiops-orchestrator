"""`SEN_READ_ONLY`: a trava de escrita que vive dentro do binario.

Por que no binario e nao so na camada de permissao de quem o chama: allowlist de
linha de comando casa prefixo de string, e nao cobre caminho absoluto do
executavel, `cmd /c sen validate`, espaco duplo, `./sen.exe` nem prefixo de
variavel de ambiente. Aqui a recusa e por construcao — e acontece ANTES de
montar o adapter, de modo que nem autentica.

Os tres comandos que gravam sao `validate` (PUT na revisao Draft, apesar do
nome), `publish` e `deploy`. `publish` e `deploy` ja recusavam fora da esteira;
`validate` nao tinha guarda nenhuma alem do prompt interativo.
"""

from unittest.mock import MagicMock

import pytest

import apiops_orchestrator.main as main_mod
from apiops_orchestrator.adapters.inbound.cli.cli_adapter import CliError

CONSTRUTORAS_DE_ESCRITA = (
    "build_validate_service_factory",
    "build_publish_service_factory",
    "build_deploy_service_factory",
)


@pytest.fixture
def nao_pode_autenticar(monkeypatch):
    """Falha ruidosa se a recusa deixar o fluxo chegar na rede."""
    monkeypatch.setattr(
        main_mod,
        "_build_admin_token",
        MagicMock(side_effect=AssertionError("recusa tardia: autenticou antes de recusar")),
    )
    monkeypatch.setattr(
        main_mod,
        "_load_settings",
        MagicMock(side_effect=AssertionError("recusa tardia: leu settings antes de recusar")),
    )


@pytest.mark.parametrize("construtora", CONSTRUTORAS_DE_ESCRITA)
@pytest.mark.parametrize("valor", ["1", "true", "TRUE", "yes", "on", " 1 "])
def test_factory_de_escrita_recusa_quando_somente_leitura(
    monkeypatch, nao_pode_autenticar, construtora, valor
):
    monkeypatch.setenv("SEN_READ_ONLY", valor)

    with pytest.raises(CliError) as capturado:
        getattr(main_mod, construtora)()()

    assert capturado.value.exit_code == 1
    assert "somente leitura" in capturado.value.message
    assert "SEN_READ_ONLY" in capturado.value.message


@pytest.mark.parametrize("construtora", CONSTRUTORAS_DE_ESCRITA)
@pytest.mark.parametrize("valor", ["0", "false", "no", "", "   "])
def test_factory_de_escrita_segue_quando_a_trava_esta_desligada(
    monkeypatch, construtora, valor
):
    """Desligada, a trava sai do caminho: quem recusa depois e a guarda da esteira."""
    monkeypatch.setenv("SEN_READ_ONLY", valor)
    monkeypatch.setattr(
        main_mod, "_load_settings", MagicMock(side_effect=RuntimeError("chegou nas settings"))
    )

    with pytest.raises(RuntimeError, match="chegou nas settings"):
        getattr(main_mod, construtora)()()


@pytest.mark.parametrize("construtora", CONSTRUTORAS_DE_ESCRITA)
def test_variavel_ausente_nao_liga_a_trava(monkeypatch, construtora):
    monkeypatch.delenv("SEN_READ_ONLY", raising=False)
    monkeypatch.setattr(
        main_mod, "_load_settings", MagicMock(side_effect=RuntimeError("chegou nas settings"))
    )

    with pytest.raises(RuntimeError, match="chegou nas settings"):
        getattr(main_mod, construtora)()()


def test_a_mensagem_aponta_o_caminho_de_leitura(monkeypatch, nao_pode_autenticar):
    """Recusa que nao diz o que fazer vira laco de retentativa em quem chama."""
    monkeypatch.setenv("SEN_READ_ONLY", "1")

    with pytest.raises(CliError) as capturado:
        main_mod.build_validate_service_factory()()

    mensagem = capturado.value.message
    assert "sen list" in mensagem and "sen get" in mensagem


def test_leitura_nao_e_afetada_pela_trava(monkeypatch):
    """A trava desliga escrita, nao o CLI: as factories de leitura seguem montando."""
    monkeypatch.setenv("SEN_READ_ONLY", "1")
    monkeypatch.setattr(
        main_mod, "_load_settings", MagicMock(side_effect=RuntimeError("chegou nas settings"))
    )

    for construtora in (
        "build_login_service_factory",
        "build_listing_service_factory",
        "build_navigation_service_factory",
        "build_completeness_service_factory",
    ):
        with pytest.raises(RuntimeError, match="chegou nas settings"):
            getattr(main_mod, construtora)()()
