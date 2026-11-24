"""Nenhuma excecao de transporte atravessa um port.

Os dois ports declaram isso na propria assinatura (`manager_api_port.py:12`,
`orchestrator_auth_port.py:28-36`): quem chama conhece apenas os sinais tipados.
A deriva que este arquivo impede ja aconteceu uma vez — havia teste exigindo
`HttpClient4xxError` na saida do adapter, contra o contrato — e e o tipo de
regressao que so aparece quando alguem a depura em producao.

A assercao e deliberadamente ampla: o metodo pode devolver normalmente (ha
rotas que tratam 404 como ausencia) ou levantar um sinal do port. O que NAO
pode, nunca, e deixar vazar `HttpClient*`, `requests.*` ou excecao crua.
"""

import pytest
import requests
from unittest.mock import Mock, patch

from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    ManagerApiAdapter,
)
from apiops_orchestrator.adapters.outbound.http.orchestrator_auth_api.orchestrator_auth_adapter import (
    OrchestratorAuthAdapter,
)
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiError
from apiops_orchestrator.domain.ports.orchestrator_auth_port import (
    OrchestratorAuthError,
)
from apiops_orchestrator.infrastructure.exceptions.http_client_exceptions import (
    HttpClient4xxError,
    HttpClientError,
    HttpClientServerError,
)

MOCK_PATH = "apiops_orchestrator.infrastructure.utils.http_client.HttpClient.request"

VAZAMENTOS = (HttpClientError, requests.RequestException)


def _falhas_de_transporte():
    """As falhas que o HttpClient sabe reportar, mais uma crua de rede."""
    return [
        pytest.param(
            HttpClient4xxError(
                status_code=401, title="Unauthorized", detail="Authentication required"
            ),
            id="4xx",
        ),
        pytest.param(
            HttpClient4xxError(
                status_code=404, title="Not Found", detail="No such resource"
            ),
            id="404",
        ),
        pytest.param(
            HttpClientServerError("Failed after 3 retries, with 500 status"),
            id="5xx",
        ),
        pytest.param(requests.ConnectionError("sem rota para o host"), id="conexao"),
    ]


def _manager() -> ManagerApiAdapter:
    settings = Mock(spec=Settings)
    settings.HOST = "http://urltest.com"
    return ManagerApiAdapter(
        token="token", base_path="/base/", max_retries=1, api_id=123, settings=settings
    )


def _auth() -> OrchestratorAuthAdapter:
    settings = Settings.__new__(Settings)
    object.__setattr__(settings, "AUTH_HOST", "https://auth.example.com")
    object.__setattr__(settings, "HOST", "https://plat.example.com")
    object.__setattr__(settings, "AUTH_LOGIN_PATH", "/orq-auth/v1/oauth2/token")
    object.__setattr__(settings, "AUTH_VALIDATE_PATH", None)
    return OrchestratorAuthAdapter(settings=settings, max_retries=1)


# Amostra representativa da superficie do Manager: uma rota por familia de leitura
# (api, revisao, catalogo do tenant, consumo, governanca) mais a unica de escrita
# que o repositorio usa fora da esteira.
ROTAS_DO_MANAGER = [
    ("get_api_by_id", ()),
    ("get_revision", (8948,)),
    ("get_revision_swagger", (8948,)),
    ("get_workflow", (327,)),
    ("list_environments", ()),
    ("list_attributes", ()),
    ("list_apps", ()),
    ("list_plans", ()),
    ("get_environment", (1,)),
    ("update_revision", (8948, {"name": "x"})),
]

ROTAS_DE_AUTH = [
    ("login", ("Y3JlZDpzZWNyZXQ=",)),
    ("validate_access_token", ("token",)),
]


@pytest.mark.parametrize("metodo, args", ROTAS_DO_MANAGER, ids=lambda v: v if isinstance(v, str) else "")
@pytest.mark.parametrize("falha", _falhas_de_transporte())
def test_manager_nunca_deixa_vazar_excecao_de_transporte(metodo, args, falha):
    adapter = _manager()
    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = falha
        try:
            getattr(adapter, metodo)(*args)
        except ManagerApiError:
            pass
        except VAZAMENTOS as exc:
            pytest.fail(f"{metodo} deixou vazar {type(exc).__name__} pelo port")
        except Exception as exc:  # noqa: BLE001 — e exatamente o que se quer proibir
            pytest.fail(
                f"{metodo} levantou {type(exc).__name__}, fora do contrato do port"
            )


@pytest.mark.parametrize("metodo, args", ROTAS_DE_AUTH, ids=lambda v: v if isinstance(v, str) else "")
@pytest.mark.parametrize("falha", _falhas_de_transporte())
def test_auth_nunca_deixa_vazar_excecao_de_transporte(metodo, args, falha):
    adapter = _auth()
    with patch(MOCK_PATH) as mock_request:
        mock_request.side_effect = falha
        try:
            getattr(adapter, metodo)(*args)
        except OrchestratorAuthError:
            pass
        except VAZAMENTOS as exc:
            pytest.fail(f"{metodo} deixou vazar {type(exc).__name__} pelo port")
        except Exception as exc:  # noqa: BLE001
            pytest.fail(
                f"{metodo} levantou {type(exc).__name__}, fora do contrato do port"
            )
