"""`sen list api`: janela, filtros, drill-down de revisoes e traducao de erro.

Recortado de `test_cli_adapter.py`, que reunia a raiz da CLI, `sen list api` e
`sen completeness` em 744 linhas. Os corpos sao os mesmos; mudou a casa.
"""

from unittest.mock import MagicMock

import pytest

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    _translate_row,
)
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.models.catalog_revision_model import CatalogRevisionInfo
from sen_support.cli_invoke import runner



def _entry(raw) -> ApiCatalogEntry:
    e = _translate_row(raw)
    assert e is not None
    return e


def test_api_list_success():
    """Test 'list api' naked: canonical grade + announced defaults footer (A3-2)."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        _entry({"apiId": 1, "apiName": "API 1", "basePath": "/api1", "version": "1.0.0"}),
        _entry({"apiId": 2, "apiName": "API 2", "basePath": "/api2", "version": "2.0.0"}),
    ]

    result = runner.invoke(app, ["sen", "list", "api"], obj={"api_listing_service_factory": lambda: mock_service})

    assert result.exit_code == 0
    assert "ID" in result.output and "BASE PATH" in result.output
    assert "LAST REV" in result.output
    assert "/api1" in result.output
    assert "usando padrões: --limit 10 --offset 0" in result.output
    assert "detalhes: sen list api --help" in result.output
    # A3-2: o default anunciado PRECISA alcançar o pipeline (janela real)
    mock_service.list_apis.assert_called_once_with(query=None, offset=0, limit=10)

def test_api_list_explicit_window_footer():
    """Explicit --limit/--offset shows effective window footer."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        _entry({"apiId": 1, "apiName": "API 1", "basePath": "/api1"})
    ]

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--offset", "90", "--limit", "5"],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 0
    assert "janela: --limit 5 --offset 90" in result.output

def test_api_list_columns_values():
    """Canonical columns render version/last rev with degradation (LIFE CYCLE removida)."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        _entry({
            "apiId": 400,
            "apiName": "Orchestrator Auth API",
            "basePath": "/orq-auth/v1",
            "version": "1.0.1",
            "lastRevision": 8882,
            "revisions": [{"id": 8882, "revisionNumber": 3}],
        }),
        _entry({"apiId": 401, "apiName": "Sem Revision", "basePath": "/x/v1"}),
    ]

    result = runner.invoke(app, ["sen", "list", "api"], obj={"api_listing_service_factory": lambda: mock_service})

    assert result.exit_code == 0
    assert "8882" not in result.output  # grade mostra número da revisão, não o id
    assert "LIFE CYCLE" not in result.output  # coluna aposentada
    assert result.output.count("-") > 0  # degradação '-' nos campos ausentes

def test_api_list_query_exclusive_with_id():
    from unittest.mock import MagicMock
    mock_service = MagicMock()

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--query", "auth", "--id", "400"],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 1
    assert "--query" in result.output and "--id" in result.output

def test_api_list_invalid_limit_fails_pre_network():
    from unittest.mock import MagicMock
    mock_service = MagicMock()

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--limit", "0"],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 1
    mock_service.list_apis.assert_not_called()

def test_api_list_negative_offset_fails_pre_network():
    """Symmetric with --limit: negative --offset must fail BEFORE any network call."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--offset", "-1"],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 1
    assert "--offset" in result.output
    mock_service.list_apis.assert_not_called()

def test_api_list_query_passes_flags_to_service():
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        _entry({"apiId": 1, "apiName": "A", "basePath": "/b"})
    ]

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--query", "auth", "--limit", "3", "--offset", "2"],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 0
    mock_service.list_apis.assert_called_once_with(
        query="auth", offset=2, limit=3
    )

def test_api_list_drilldown_single_row():
    """--id keeps one-line grade without window footer."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        _entry({"apiId": 400, "apiName": "Orchestrator Auth API", "basePath": "/orq-auth/v1", "version": "1.0.1"})
    ]

    result = runner.invoke(app, ["sen", "list", "api", "--id", "400"], obj={"api_listing_service_factory": lambda: mock_service})

    assert result.exit_code == 0
    assert "Orchestrator Auth API" in result.output
    assert "usando padrões" not in result.output
    mock_service.list_apis.assert_called_once_with(api_id=400)

def test_api_list_insufficient_session_translates_error():
    from unittest.mock import MagicMock
    from apiops_orchestrator.application.exceptions.listing_exceptions import (
        InsufficientSessionError,
    )
    mock_service = MagicMock()
    mock_service.list_apis.side_effect = InsufficientSessionError()

    result = runner.invoke(app, ["sen", "list", "api"], obj={"api_listing_service_factory": lambda: mock_service})

    assert result.exit_code == 1
    assert "grupos de acesso" in result.output

def test_api_list_no_apis_when_none_returned():
    """Test 'list api' when no APIs are returned."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = []

    result = runner.invoke(app, ["sen", "list", "api"], obj={"api_listing_service_factory": lambda: mock_service})

    assert result.exit_code == 0
    assert "Nenhuma API encontrada." in result.output

def test_api_list_vazio_em_json_e_lista_vazia():
    """A regressao que este teste tranca.

    A checagem do vazio ficava ANTES do `display_output`, entao `-o json`
    imprimia "Nenhuma API encontrada." e saia 0: texto em portugues onde quem
    consome por maquina espera JSON, com codigo de sucesso. Um agente le isso
    como "a ferramenta quebrou", nao como "zero resultados" — e cai nisso no
    primeiro filtro que nao casa.
    """
    mock_service = MagicMock()
    mock_service.list_apis.return_value = []

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--query", "nao-existe", "-o", "json"],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == "[]"
    assert "Nenhuma API encontrada" not in result.stdout


def test_api_list_revisoes_vazias_em_json_e_lista_vazia():
    """Mesmo early return, no drill-down de revisoes (`--revisions`)."""
    mock_service = MagicMock()
    mock_service.api_revisions.return_value = []

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--id", "409", "--revisions", "-o", "json"],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == "[]"
    assert "Nenhuma revis" not in result.stdout


def test_api_list_json():
    """Test 'list api --output json'."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        _entry({"apiId": 1, "apiName": "API 1", "basePath": "/api1"})
    ]

    result = runner.invoke(app, ["sen", "list", "api", "--output", "json"], obj={"api_listing_service_factory": lambda: mock_service})

    assert result.exit_code == 0
    # The output contains rich syntax highlighting, so we check for key parts
    assert '"id": 1' in result.output
    assert '"name": "API 1"' in result.output

def test_api_list_yaml():
    """Test 'list api --output yaml'."""
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.list_apis.return_value = [
        _entry({"apiId": 1, "apiName": "API 1", "basePath": "/api1"})
    ]

    result = runner.invoke(app, ["sen", "list", "api", "-o", "yaml"], obj={"api_listing_service_factory": lambda: mock_service})

    assert result.exit_code == 0
    assert "id: 1" in result.output
    assert "name: API 1" in result.output


# ---------------------------------------------------------------------------
# Drill-down de revisões (task 6, opção A) — grade canônica do §3
# ---------------------------------------------------------------------------

def test_revisions_drill_down_renders_canonical_grade():
    from unittest.mock import MagicMock
    mock_service = MagicMock()
    mock_service.api_revisions.return_value = [
        CatalogRevisionInfo(
            revision_id=8862, revision_number=1, stage_name="Stage One",
            environments="Default", completeness_score=85.0,
        ),
        CatalogRevisionInfo(
            revision_id=8948, revision_number=4, stage_name="Stage One",
            environments="-", completeness_score=85.0,
        ),
    ]

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--id", "400", "--revisions"],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 0
    for col in ("REV ID", "REV #", "STAGE", "ENVS", "COMPLETE"):
        assert col in result.output
    assert "Stage One" in result.output
    assert "85.0%" in result.output
    assert "sem completeness" not in result.output
    mock_service.api_revisions.assert_called_once_with(400)
    mock_service.list_apis.assert_not_called()


def _revisions_with_one_failure():
    mock_service = MagicMock()
    mock_service.api_revisions.return_value = [
        CatalogRevisionInfo(
            revision_id=5976, revision_number=1, stage_name="Production",
            environments="Default", completeness_score=74.3,
        ),
        CatalogRevisionInfo(
            revision_id=23625, revision_number=3, stage_name="Production",
            environments="", completeness_score=None,
        ),
    ]
    return mock_service


def test_revisions_note_explains_missing_completeness():
    mock_service = _revisions_with_one_failure()

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--id", "68", "--revisions"],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 0
    output = " ".join(result.output.split())
    assert "74.3%" in output
    assert "1 revisão sem completeness: o Manager não respondeu." in output
    assert "sen completeness --id 68 --revision <REV ID>" in output


def test_revisions_note_counts_in_plural():
    mock_service = _revisions_with_one_failure()
    mock_service.api_revisions.return_value[0] = CatalogRevisionInfo(
        revision_id=5976, revision_number=1, stage_name="Production",
        environments="Default", completeness_score=None,
    )

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--id", "68", "--revisions"],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    assert "2 revisões sem completeness" in " ".join(result.output.split())


def test_revisions_json_has_null_score_and_nothing_but_the_document():
    import json

    mock_service = _revisions_with_one_failure()

    result = runner.invoke(
        app,
        ["sen", "list", "api", "--id", "68", "--revisions", "-o", "json"],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 0
    document = json.loads(result.output)
    assert [row["completeness_score"] for row in document] == [74.3, None]


def test_revisions_requires_id_pre_network():
    from unittest.mock import MagicMock
    mock_service = MagicMock()

    result = runner.invoke(
        app, ["sen", "list", "api", "--revisions"], obj={"api_listing_service_factory": lambda: mock_service}
    )

    assert result.exit_code == 1
    assert "--id" in result.output
    mock_service.api_revisions.assert_not_called()
    mock_service.list_apis.assert_not_called()
# --- Fallback de erro inesperado padronizado (sen-list E1 / sen-completeness) --

def _unexpected_list_service():
    mock_service = MagicMock()
    mock_service.list_apis.side_effect = RuntimeError("KeyError: 'contextType' at row 42")
    return mock_service


def test_api_list_unexpected_error_shows_internal_message_without_raw_text():
    from apiops_orchestrator.application.exceptions.manager_failure_messages import (
        INTERNAL_ERROR_MESSAGE,
    )

    result = runner.invoke(
        app, ["sen", "list", "api"],
        obj={"api_listing_service_factory": _unexpected_list_service},
    )

    assert result.exit_code == 1
    output = " ".join(result.output.split())
    assert INTERNAL_ERROR_MESSAGE in output
    assert "KeyError" not in output and "row 42" not in output
    assert "Traceback" not in result.output


def test_completeness_unexpected_error_keeps_exit2_bucket():
    from apiops_orchestrator.application.exceptions.manager_failure_messages import (
        INTERNAL_ERROR_MESSAGE,
    )
    mock_service = MagicMock()
    mock_service.get_completeness.side_effect = ValueError("could not convert 'abc'")

    result = runner.invoke(
        app,
        ["sen", "completeness", "--id", "375", "--revision", "5513"],
        obj={"completeness_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 2
    output = " ".join(result.output.split())
    assert INTERNAL_ERROR_MESSAGE in output
    assert "could not convert" not in output


def test_api_list_incomplete_config_keeps_educational_message():
    """CliError da factory (config ausente) não vira erro interno."""
    from apiops_orchestrator.adapters.inbound.cli.cli_adapter import CliError

    def failing_factory():
        raise CliError("Configuração incompleta (ausente/inválida): HOST.", exit_code=1)

    result = runner.invoke(
        app, ["sen", "list", "api"], obj={"api_listing_service_factory": failing_factory}
    )

    assert result.exit_code == 1
    assert "Configuração incompleta" in result.output


def test_api_list_admin_token_refusal_keeps_login_guidance():
    """Recusa da rota validate (LoginError) segue orientando `sen login`."""
    from apiops_orchestrator.application.exceptions.login_exceptions import (
        AuthenticationRejectedError,
    )

    def failing_factory():
        raise AuthenticationRejectedError("Sessão inválida: faça `sen login` e tente novamente.")

    result = runner.invoke(
        app, ["sen", "list", "api"], obj={"api_listing_service_factory": failing_factory}
    )

    assert result.exit_code == 1
    assert "sen login" in result.output


# --- sen list api --all ------------------------------------------------------

def _listing_service_returning(entries):
    mock_service = MagicMock()
    mock_service.list_apis.return_value = entries
    return mock_service


def test_api_list_all_reads_without_window_and_announces_it():
    mock_service = _listing_service_returning([
        _entry({"apiId": 1, "apiName": "A", "contextType": "ORGANIZATION"}),
        _entry({"apiId": 2, "apiName": "B", "contextType": "ORGANIZATION"}),
    ])

    result = runner.invoke(
        app, ["sen", "list", "api", "--all"],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 0
    mock_service.list_apis.assert_called_once_with(query=None, offset=0, limit=None)
    assert "todas as APIs visíveis (--all)" in result.output


def test_api_list_all_keeps_query():
    mock_service = _listing_service_returning([])

    runner.invoke(
        app, ["sen", "list", "api", "--all", "--query", "pagamentos"],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    mock_service.list_apis.assert_called_once_with(
        query="pagamentos", offset=0, limit=None
    )


@pytest.mark.parametrize(
    "extra",
    [["--limit", "5"], ["--offset", "3"], ["--id", "400"]],
)
def test_api_list_all_is_exclusive_with_window_and_drill_down(extra):
    mock_service = _listing_service_returning([])

    result = runner.invoke(
        app, ["sen", "list", "api", "--all", *extra],
        obj={"api_listing_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 1
    assert "--all" in result.output
    mock_service.list_apis.assert_not_called()
    mock_service.api_revisions.assert_not_called()


def test_api_list_query_help_says_search_runs_on_the_manager():
    result = runner.invoke(app, ["sen", "list", "api", "--help"])

    help_text = " ".join(result.output.split())
    assert "Busca por nome ou descrição, feita" in help_text
    assert "--all" in help_text


# --- Fallback reconhece sinais do Manager não traduzidos ----------------------

def _service_raising(method_name, error):
    mock_service = MagicMock()
    getattr(mock_service, method_name).side_effect = error
    return mock_service


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        ("unauthorized", "Faça `sen login` novamente"),
        ("forbidden", "Acesso negado pelo Manager"),
        ("unavailable", "Manager indisponível"),
        ("too_large", "erro interno"),
    ],
)
def test_untranslated_manager_signal_gets_family_message(error, expected):
    from apiops_orchestrator.domain.ports.manager_api_port import (
        ManagerApiResponseTooLargeError,
        ManagerApiTransportRejectedError,
        ManagerApiTransportUnavailableError,
    )
    errors = {
        "unauthorized": ManagerApiTransportRejectedError(401, "Unauthorized"),
        "forbidden": ManagerApiTransportRejectedError(403, "Forbidden"),
        "unavailable": ManagerApiTransportUnavailableError("timeout"),
        "too_large": ManagerApiResponseTooLargeError(413, "BACKEND_RESPONSE_TOO_LARGE"),
    }
    mock_service = _service_raising("list_apis", errors[error])

    result = runner.invoke(
        app, ["sen", "list", "api"], obj={"api_listing_service_factory": lambda: mock_service}
    )

    output = " ".join(result.output.split())
    assert result.exit_code == 1
    assert expected in output
    assert "HTTP" not in output and "BACKEND_RESPONSE_TOO_LARGE" not in output


def test_untranslated_manager_signal_keeps_command_exit_code():
    from apiops_orchestrator.domain.ports.manager_api_port import (
        ManagerApiTransportRejectedError,
    )
    mock_service = _service_raising(
        "get_completeness", ManagerApiTransportRejectedError(401, "Unauthorized")
    )

    result = runner.invoke(
        app,
        ["sen", "completeness", "--id", "375", "--revision", "5513"],
        obj={"completeness_service_factory": lambda: mock_service},
    )

    assert result.exit_code == 2
    assert "sen login" in result.output
