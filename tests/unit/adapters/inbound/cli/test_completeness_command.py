"""`sen completeness`: guardas pre-rede, render, json e as familias de erro.

Recortado de `test_cli_adapter.py`, que reunia a raiz da CLI, `sen list api` e
`sen completeness` em 744 linhas. Os corpos sao os mesmos; mudou a casa.
"""

import re
from unittest.mock import MagicMock


from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    _translate_row,
)
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.models.completeness_view import (
    CompletenessApi,
    CompletenessContext,
    CompletenessSuggestion,
    CompletenessView,
)
from sen_support.cli_invoke import runner



def _entry(raw) -> ApiCatalogEntry:
    e = _translate_row(raw)
    assert e is not None
    return e


# ---------------------------------------------------------------------------
# sen completeness — comandos, contratos de saída e matriz de erros (G1)
# ---------------------------------------------------------------------------

SAMPLE_VIEW = CompletenessView(
    schema="apiops.sen-completeness/v1",
    generated_at="2026-09-28T12:00:00Z",
    api=CompletenessApi(
        manager_id=375,
        name="Manager Training 1.0",
        version="1.0",
        context=CompletenessContext(type="organization", group_name=None, owner="trainer.sensedia"),
    ),
    revision_id=5513,
    revision_number=3,
    score=55.0,
    gate_percent=70.0,
    suggestions=[
        CompletenessSuggestion(index=1, text="Primeira sugestão integral,_sem abreviação: " + "texto longo " * 12),
        CompletenessSuggestion(index=2, text="Segunda sugestão curta."),
    ],
)


def _invoke_completeness(args, mock_service):
    from unittest.mock import MagicMock
    factory = MagicMock(return_value=mock_service)
    result = runner.invoke(
        app,
        ["sen", "completeness", *args],
        obj={"completeness_service_factory": factory},
    )
    return result, factory


def test_completeness_without_revision_fails_pre_network_guiding_revisions():
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    factory = MagicMock(return_value=mock_service)

    result = runner.invoke(
        app,
        ["sen", "completeness", "--id", "375"],
        obj={"completeness_service_factory": factory},
    )

    assert result.exit_code == 1
    assert "sen list api --id X --revisions" in " ".join(result.output.split())
    factory.assert_not_called()  # zero HTTP: nem fábrica sequer roda
    mock_service.get_completeness.assert_not_called()


def test_completeness_without_api_id_fails_pre_network():
    from unittest.mock import MagicMock
    result, factory = _invoke_completeness(["--revision", "5513"], MagicMock())

    assert result.exit_code == 1
    assert "--id" in result.output
    factory.assert_not_called()


def test_completeness_missing_service_factory_is_environment_error():
    result = runner.invoke(
        app,
        ["sen", "completeness", "--id", "375", "--revision", "5513"],
        obj={},
    )

    assert result.exit_code == 1
    assert "Serviço de completude indisponível" in result.output


def test_completeness_text_rendering_literally():
    result, _ = _invoke_completeness(
        ["--id", "375", "--revision", "5513"], MagicMock(get_completeness=lambda **kw: SAMPLE_VIEW)
    )

    assert result.exit_code == 0
    flat = result.output.replace("\n", " ")
    assert "Manager Training 1.0 (1.0) · #375" in flat
    assert "5513 (#3)" in flat
    assert "trainer.sensedia" in flat
    assert "55.0%" in flat                      # percentual puro, sem Basic/Intermediate/Advanced
    assert "(gate: ≥70%)" in flat or "(gate: >=70%)" in flat
    assert "faltam 15.0 pts para o gate" in flat
    assert "SUGESTÕES (2)" in flat
    assert "SUGESTÃO" in flat                   # cabeçalho da grade
    assert re.search(r"\b1\s*[│|]", flat) and re.search(r"\b2\s*[│|]", flat)
    assert "texto longo" in flat
    assert "Classification" not in flat and "severity" not in flat


def test_completeness_score_only_suppresses_suggestions():
    result, _ = _invoke_completeness(
        ["--id", "375", "--revision", "5513", "--score-only"],
        MagicMock(get_completeness=lambda **kw: SAMPLE_VIEW),
    )

    flat = result.output.replace("\n", " ")
    assert result.exit_code == 0
    assert "55.0%" in flat and "(gate: ≥70%)" in flat
    assert "SUGESTÕES" not in flat
    assert "texto longo" not in flat


def test_completeness_json_matches_v1_tree():
    result, _ = _invoke_completeness(
        ["--id", "375", "--revision", "5513", "-o", "json"],
        MagicMock(get_completeness=lambda **kw: SAMPLE_VIEW),
    )

    assert result.exit_code == 0
    plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
    for key in ("schema", "generatedAt", "managerId", "maturity", "gate", "suggestions"):
        assert key in plain
    assert "apiops.sen-completeness/v1" in plain
    assert "[1, 2]" not in plain  # apenas checagem anti-lixo: sem listas de posição mágicas
    banned = ("violations", "severity", "classification", "ruleId", "satellite")
    for key in banned:
        assert key not in plain


def test_completeness_404_maps_to_exit2_notfound_guidance():
    from unittest.mock import MagicMock
    from apiops_orchestrator.application.exceptions.completeness_exceptions import (
        CompletenessNotFound,
    )

    mock_service = MagicMock()
    mock_service.get_completeness.side_effect = CompletenessNotFound(5501)

    result = runner.invoke(
        app,
        ["sen", "completeness", "--id", "375", "--revision", "5501"],
        obj={"completeness_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 2
    assert "5501" in result.output
    assert "sen list api --id X --revisions" in " ".join(result.output.split())


def test_completeness_401_maps_to_exit2_guiding_sen_login():
    from apiops_orchestrator.application.exceptions.completeness_exceptions import (
        CompletenessUnauthorized,
    )
    mock_service = MagicMock()
    mock_service.get_completeness.side_effect = CompletenessUnauthorized()

    result = runner.invoke(
        app,
        ["sen", "completeness", "--id", "375", "--revision", "5513"],
        obj={"completeness_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 2
    assert "sen login" in result.output


def test_completeness_success_outputs_never_leak_credentials():
    mock_service = MagicMock()
    mock_service.get_completeness.return_value = SAMPLE_VIEW

    result = runner.invoke(
        app,
        ["sen", "completeness", "--id", "375", "--revision", "5513", "-o", "yaml"],
        obj={"completeness_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 0
    low = result.output.lower()
    for token_hint in ("bearer", "authorization", "adminaccesstoken", "accesstoken"):
        assert token_hint not in low


def test_completeness_flags_accepted_together():
    result, factory = _invoke_completeness(
        [
            "--id", "375", "--revision", "5513",
            "--score-only", "-o", "json", "-v",
        ],
        MagicMock(get_completeness=lambda **kw: SAMPLE_VIEW),
    )

    assert result.exit_code == 0
    factory.assert_called_once()
