"""Bateria de aceitação do `sen deploy` contra a API 417 (ESCREVE no ambiente 7).

**Não roda por padrão.** Exige `APIOPS_BATERIA_417=1` e sessão válida de
superadmin (`sen login --service`).

Só refaz o deploy da revisão que já está no ar no ambiente, então o conteúdo
servido não muda. O estado final é conferido contra o inicial.
"""

import os
import textwrap
from types import SimpleNamespace

import pytest

from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)
from apiops_orchestrator.application.exceptions.deploy_exceptions import DeployError
from apiops_orchestrator.application.services.deploy_service import DeployService

API_ID = 417
AMBIENTE = 7
AMBIENTE_NAO_LIGADO = 9

pytestmark = pytest.mark.skipif(
    os.environ.get("APIOPS_BATERIA_417") != "1",
    reason="bateria que ESCREVE na API 417; exige APIOPS_BATERIA_417=1",
)


@pytest.fixture(scope="module")
def manager():
    from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
        ManagerApiAdapter,
    )
    from apiops_orchestrator.main import _build_admin_token, _load_settings

    settings = _load_settings()
    return ManagerApiAdapter(
        token=_build_admin_token(settings),
        base_path="/api-manager/api/v3/",
        max_retries=3,
        settings=settings,
    )


def _ativo(api, environment):
    active = [
        d
        for r in api["revisions"]
        for d in r.get("deployments") or []
        if d["status"] == "DEPLOYED" and d["environmentId"] == environment
    ]
    return max(active, key=lambda d: d["deployDate"]) if active else None


def _registros(api):
    return sum(len(r.get("deployments") or []) for r in api["revisions"])


@pytest.fixture(scope="module")
def inicial(manager):
    api = manager.get_api_by_id(API_ID)
    ativo = _ativo(api, AMBIENTE)
    assert ativo is not None, "a bateria precisa de uma revisão da 417 no ar no ambiente 7"
    return {"api": api, "ativo": ativo}


@pytest.fixture(scope="module")
def repo(tmp_path_factory, inicial):
    api = inicial["api"]
    folder = tmp_path_factory.mktemp("repo-417")
    (folder / "api-basic-info.yaml").write_text(
        textwrap.dedent(
            f"""\
            apiVersion: api-management.sensedia.com/v1
            kind: ApiBasicInfo
            spec:
              id: {API_ID}
              version: "{api['version']}"
              basePath: "{api['basePath']}"
            """
        ),
        encoding="utf-8",
    )
    return folder


def _servico(manager, revision, environment):
    return DeployService(
        manager_api=manager,
        importer=LocalFileImporterAdapter(),
        settings=SimpleNamespace(
            EXECUTION_MODE="pipeline",
            pipeline_mode=True,
            TARGET_REVISION_NUMBER=revision,
            TARGET_ENVIRONMENT_ID=environment,
        ),
    )


def test_D01_redeploy_da_revisao_no_ar_e_conferido(manager, repo, inicial):
    number = inicial["ativo"]["revisionNumber"]
    view = _servico(manager, number, AMBIENTE).deploy(repo)

    assert view.deployment.verified is True
    assert view.previous_state.deployment_id == inicial["ativo"]["id"]
    assert view.new_state.deployment_id != inicial["ativo"]["id"]
    assert view.new_state.revision_number == number

    after = manager.get_api_by_id(API_ID)
    assert _ativo(after, AMBIENTE)["id"] == view.new_state.deployment_id


@pytest.mark.sem_escrita
def test_D02_ambiente_nao_ligado_recusa_sem_criar_registro(manager, repo, inicial):
    antes = _registros(manager.get_api_by_id(API_ID))
    with pytest.raises(DeployError) as capturado:
        _servico(manager, inicial["ativo"]["revisionNumber"], AMBIENTE_NAO_LIGADO).deploy(repo)

    assert f"ambiente {AMBIENTE_NAO_LIGADO}" in capturado.value.message
    assert _registros(manager.get_api_by_id(API_ID)) == antes


@pytest.mark.sem_escrita
def test_D03_revisao_inexistente_recusa_sem_criar_registro(manager, repo):
    antes = _registros(manager.get_api_by_id(API_ID))
    with pytest.raises(DeployError) as capturado:
        _servico(manager, 99, AMBIENTE).deploy(repo)

    assert "número 99" in capturado.value.message
    assert _registros(manager.get_api_by_id(API_ID)) == antes


@pytest.mark.sem_escrita
def test_ZZ_ambiente_termina_com_a_mesma_revisao(manager, inicial):
    ativo = _ativo(manager.get_api_by_id(API_ID), AMBIENTE)
    assert ativo["revisionId"] == inicial["ativo"]["revisionId"]
