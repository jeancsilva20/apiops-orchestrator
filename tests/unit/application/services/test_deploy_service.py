"""`sen deploy` com port fake que grava a ordem das chamadas."""

import copy
import textwrap
from types import SimpleNamespace

import pytest

from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)
from apiops_orchestrator.application.exceptions.deploy_exceptions import (
    DeployError,
    DeployFalhouError,
    DeployGovernanceBlockedError,
)
from apiops_orchestrator.application.services.deploy_service import DeployService
from apiops_orchestrator.domain.models.catalog_revision_model import (
    CatalogRevisionCompleteness,
)
from apiops_orchestrator.domain.models.deploy_model import SCHEMA_SEN_DEPLOY_V1
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiGovernanceBlockedError,
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)


def _deploy(dep_id, rev_id, numero, env, status="DEPLOYED", data=1792434435000):
    return {
        "id": dep_id,
        "revisionId": rev_id,
        "revisionNumber": numero,
        "apiId": 417,
        "environmentId": env,
        "status": status,
        "deployDate": data,
    }


def _api(deploys_rev2=None, deploys_rev3=None, ambientes=None, api_tags=None):
    return {
        "id": 417,
        "name": "Servico de Letras",
        "version": "1.0.0",
        "basePath": "/letras/v2",
        "apiTags": api_tags
        if api_tags is not None
        else [{"attributeName": "My new", "tags": ["Tag1"]}],
        "environments": ambientes
        if ambientes is not None
        else [{"id": 7, "name": "DEV-APIOPS"}],
        "revisions": [
            {"id": 9161, "revisionNumber": 1, "workflowId": 500, "workflowStageId": 1402, "deployments": []},
            {"id": 9175, "revisionNumber": 2, "workflowId": 500, "workflowStageId": 1402,
             "deployments": deploys_rev2 or []},
            {"id": 9327, "revisionNumber": 3, "workflowId": 500, "workflowStageId": 1402,
             "deployments": deploys_rev3 or []},
        ],
    }


def _workflow(deployable=None, completeness=0.0, requisitos=None):
    return {
        "workflowId": 500,
        "stages": [
            {
                "workflowStageId": 1402,
                "completenessRequisite": completeness,
                "attributesRequisites": requisitos or [],
                "deployableEnvironments": deployable if deployable is not None else [7],
            }
        ],
    }


ATRIBUTOS = [
    {"id": 149, "name": "My new", "tags": ["Tag1", "Tag2"]},
    {"id": 231, "name": "teste giroto", "tags": ["teste giroto"]},
]

BASIC_INFO = """\
apiVersion: api-management.sensedia.com/v1
kind: ApiBasicInfo
spec:
  id: 417
  name: "Servico de Letras"
  version: "1.0.0"
  basePath: "/letras/v2"
"""


class ManagerFake:
    """Port fake: grava as chamadas e simula o efeito do `POST /deployments`."""

    def __init__(
        self,
        api=None,
        workflow=None,
        completeness=77.5,
        erro_post=None,
        id_novo=269,
        efeito=True,
        erro_releitura=None,
    ):
        self.api = api or _api(deploys_rev3=[_deploy(267, 9327, 3, 7)])
        self.workflow = workflow or _workflow()
        self.completeness = completeness
        self.erro_post = erro_post
        self.id_novo = id_novo
        self.efeito = efeito
        self.erro_releitura = erro_releitura
        self.chamadas = []
        self.post = None

    def get_api_by_id(self, api_id=None):
        self.chamadas.append("get_api_by_id")
        if self.post is not None and self.erro_releitura is not None:
            raise self.erro_releitura
        return copy.deepcopy(self.api)

    def get_workflow(self, workflow_id):
        self.chamadas.append("get_workflow")
        return self.workflow

    def list_attributes(self):
        self.chamadas.append("list_attributes")
        return ATRIBUTOS

    def get_revision_completeness(self, revision_id):
        self.chamadas.append("get_revision_completeness")
        return CatalogRevisionCompleteness(score=self.completeness, suggestions=[])

    def deploy_revision(self, environment_id, revision_id):
        self.chamadas.append("deploy_revision")
        self.post = (environment_id, revision_id)
        if self.erro_post is not None:
            raise self.erro_post
        if self.efeito:
            # Como a plataforma: o anterior no ambiente vira UNDEPLOYED.
            for revisao in self.api["revisions"]:
                for d in revisao["deployments"]:
                    if d["environmentId"] == environment_id and d["status"] == "DEPLOYED":
                        d["status"] = "UNDEPLOYED"
                alvo = revisao["id"] == revision_id
                if alvo:
                    revisao["deployments"].append(
                        _deploy(self.id_novo, revision_id, revisao["revisionNumber"],
                                environment_id, data=1792434500000)
                    )
        return self.id_novo

    # --- proibidos
    def update_revision(self, *a, **k):  # pragma: no cover
        raise AssertionError("o deploy não grava conteúdo")

    def publish_api_changes(self, *a, **k):  # pragma: no cover
        raise AssertionError("o orquestrador nunca usa POST /revisions")

    def get_revision(self, *a, **k):  # pragma: no cover
        raise AssertionError("GET /revisions/{id} devolve deployments vazio (L-2)")


def _settings(modo="pipeline", revisao=3, ambiente=7):
    return SimpleNamespace(
        EXECUTION_MODE=modo,
        modo_pipeline=(modo == "pipeline"),
        TARGET_REVISION_NUMBER=revisao,
        TARGET_ENVIRONMENT_ID=ambiente,
    )


def _repo(tmp_path, basic_info=BASIC_INFO):
    (tmp_path / "api-basic-info.yaml").write_text(textwrap.dedent(basic_info), encoding="utf-8")
    return tmp_path


def _servico(manager, **cfg):
    return DeployService(
        manager_api=manager, importer=LocalFileImporterAdapter(), settings=_settings(**cfg)
    )


# --- caminho feliz -------------------------------------------------------------


def test_deploya_a_revisao_do_numero_no_ambiente_e_confere(tmp_path):
    manager = ManagerFake()
    view = _servico(manager).deploy(_repo(tmp_path))

    assert manager.post == (7, 9327)
    assert view.schema == SCHEMA_SEN_DEPLOY_V1
    assert view.revision.manager_id == 9327 and view.revision.revision_number == 3
    assert view.environment.manager_id == 7 and view.environment.name == "DEV-APIOPS"
    assert view.deployment.status == "SUCCESS"
    assert view.deployment.verified is True
    assert view.deployment.deployment_id == 269
    assert manager.chamadas[-2:] == ["deploy_revision", "get_api_by_id"]


def test_revisao_ja_no_ar_faz_o_post_mesmo_assim(tmp_path):
    """E-1: com revisões fixas, o novo deploy é o que leva o conteúdo publicado."""
    manager = ManagerFake()  # a 9327 já está DEPLOYED (267) no ambiente 7
    view = _servico(manager).deploy(_repo(tmp_path))

    assert "deploy_revision" in manager.chamadas
    assert view.previous_state.deployment_id == 267
    assert view.new_state.deployment_id == 269


def test_estado_anterior_e_novo_na_troca_de_revisao(tmp_path):
    manager = ManagerFake(api=_api(deploys_rev2=[_deploy(268, 9175, 2, 7)]))
    view = _servico(manager).deploy(_repo(tmp_path))

    assert view.previous_state.revision_number == 2
    assert view.new_state.revision_number == 3
    # deployDate em epoch ms (1792434500000) vira ISO-8601 UTC.
    assert view.new_state.deployed_at == "2026-10-19T18:28:20Z"


def test_primeiro_deploy_no_ambiente_tem_estado_anterior_nulo(tmp_path):
    manager = ManagerFake(api=_api())
    view = _servico(manager).deploy(_repo(tmp_path))
    assert view.previous_state is None


def test_deploy_em_outro_ambiente_nao_conta_como_estado_anterior(tmp_path):
    manager = ManagerFake(
        api=_api(
            deploys_rev3=[_deploy(270, 9327, 3, 9)],
            ambientes=[{"id": 7, "name": "DEV-APIOPS"}, {"id": 9, "name": "HMG-APIOPS"}],
        ),
        workflow=_workflow(deployable=[]),
    )
    view = _servico(manager).deploy(_repo(tmp_path))
    assert view.previous_state is None


def test_documento_conforme_ao_contrato(tmp_path):
    doc = _servico(ManagerFake()).deploy(_repo(tmp_path)).to_document()

    assert doc["schema"] == "apiops.sen-deploy/v1"
    assert doc["environment"] == {"managerId": 7, "name": "DEV-APIOPS"}
    assert doc["governance"]["deployableEnvironments"] == [7]
    assert doc["governance"]["blocked"] is False
    assert doc["previousState"]["deploymentId"] == 267
    assert doc["newState"]["deploymentId"] == 269
    assert doc["deployment"]["status"] == "SUCCESS"
    assert "token" not in str(doc).lower()


# --- E0: configuração ----------------------------------------------------------


def test_modo_local_recusa_antes_de_qualquer_chamada(tmp_path):
    manager = ManagerFake()
    with pytest.raises(DeployError) as capturado:
        _servico(manager, modo="local").deploy(_repo(tmp_path))

    assert "esteira" in capturado.value.message
    assert capturado.value.exit_code == 1
    assert manager.chamadas == []


@pytest.mark.parametrize(
    "cfg,variavel",
    [({"revisao": None}, "TARGET_REVISION_NUMBER"), ({"ambiente": None}, "TARGET_ENVIRONMENT_ID")],
)
def test_variavel_ausente_falha_antes_de_qualquer_chamada(tmp_path, cfg, variavel):
    manager = ManagerFake()
    with pytest.raises(DeployError) as capturado:
        _servico(manager, **cfg).deploy(_repo(tmp_path))

    assert variavel in capturado.value.message
    assert manager.chamadas == []


@pytest.mark.parametrize("numero", [1, 0, -2])
def test_draft_ou_numero_invalido_recusa_antes_de_qualquer_chamada(tmp_path, numero):
    manager = ManagerFake()
    with pytest.raises(DeployError):
        _servico(manager, revisao=numero).deploy(_repo(tmp_path))
    assert manager.chamadas == []


# --- E1: manifesto -------------------------------------------------------------


def test_manifesto_ausente_falha_sem_rede(tmp_path):
    manager = ManagerFake()
    with pytest.raises(DeployError) as capturado:
        _servico(manager).deploy(tmp_path)

    assert "api-basic-info.yaml" in capturado.value.message
    assert manager.chamadas == []


def test_manifesto_sem_spec_id_falha_sem_rede(tmp_path):
    manager = ManagerFake()
    sem_id = BASIC_INFO.replace("  id: 417\n", "")
    with pytest.raises(DeployError) as capturado:
        _servico(manager).deploy(_repo(tmp_path, sem_id))

    assert "spec.id" in capturado.value.message
    assert manager.chamadas == []


def test_manifesto_ilegivel_aponta_o_arquivo(tmp_path):
    manager = ManagerFake()
    with pytest.raises(DeployError) as capturado:
        _servico(manager).deploy(_repo(tmp_path, "spec: [sem fechar\n"))

    assert "não pôde ser lido" in capturado.value.message
    assert manager.chamadas == []


def test_resto_do_repositorio_nao_e_exigido(tmp_path):
    """O conteúdo já foi gravado pelo publish: sem `all.yaml` o deploy segue."""
    view = _servico(ManagerFake()).deploy(_repo(tmp_path))
    assert view.deployment.verified is True


# --- E2: guardas ---------------------------------------------------------------


def test_identidade_divergente_aborta_sem_escrever(tmp_path):
    manager = ManagerFake()
    outro = BASIC_INFO.replace("/letras/v2", "/pedidos/v1")
    with pytest.raises(DeployError) as capturado:
        _servico(manager).deploy(_repo(tmp_path, outro))

    assert "outra API" in capturado.value.message
    assert "Nenhum deploy foi feito" in capturado.value.message
    assert "deploy_revision" not in manager.chamadas


def test_revisao_inexistente_lista_numero_e_id_e_nao_escreve(tmp_path):
    manager = ManagerFake()
    with pytest.raises(DeployError) as capturado:
        _servico(manager, revisao=4).deploy(_repo(tmp_path))

    mensagem = capturado.value.message
    assert "3 (id 9327)" in mensagem and "2 (id 9175)" in mensagem
    assert "deploy_revision" not in manager.chamadas


def test_revision_id_vem_so_das_revisoes_da_propria_api(tmp_path):
    """E-5: o POST aceita revisão de outra API; o id nunca vem de fora da API."""
    manager = ManagerFake()
    _servico(manager, revisao=2).deploy(_repo(tmp_path))
    assert manager.post == (7, 9175)


def test_ambiente_nao_ligado_lista_os_ligados_e_nao_escreve(tmp_path):
    manager = ManagerFake()
    with pytest.raises(DeployError) as capturado:
        _servico(manager, ambiente=9).deploy(_repo(tmp_path))

    mensagem = capturado.value.message
    assert "ambiente 9" in mensagem and "7 (DEV-APIOPS)" in mensagem
    assert capturado.value.exit_code == 1
    assert "deploy_revision" not in manager.chamadas


def test_api_sem_nenhum_ambiente_ligado(tmp_path):
    manager = ManagerFake(api=_api(ambientes=[]))
    with pytest.raises(DeployError) as capturado:
        _servico(manager).deploy(_repo(tmp_path))
    assert "nenhum ambiente" in capturado.value.message


# --- E3: governança ------------------------------------------------------------


def test_ambiente_fora_do_permitido_pelo_stage_bloqueia_com_3(tmp_path):
    manager = ManagerFake(
        api=_api(ambientes=[{"id": 7, "name": "DEV-APIOPS"}, {"id": 9, "name": "HMG-APIOPS"}]),
        workflow=_workflow(deployable=[7]),
    )
    with pytest.raises(DeployGovernanceBlockedError) as capturado:
        _servico(manager, ambiente=9).deploy(_repo(tmp_path))

    assert capturado.value.exit_code == 3
    assert "ambiente 9" in capturado.value.message
    assert "deploy_revision" not in manager.chamadas


def test_lista_de_ambientes_vazia_e_sem_restricao(tmp_path):
    manager = ManagerFake(workflow=_workflow(deployable=[]))
    view = _servico(manager).deploy(_repo(tmp_path))
    assert view.deployment.verified is True


def test_completeness_abaixo_do_exigido_bloqueia(tmp_path):
    manager = ManagerFake(workflow=_workflow(completeness=70.0), completeness=65.0)
    with pytest.raises(DeployGovernanceBlockedError) as capturado:
        _servico(manager).deploy(_repo(tmp_path))

    assert "65.0" in capturado.value.message and "70.0" in capturado.value.message
    assert "deploy_revision" not in manager.chamadas


def test_completeness_igual_ao_exigido_libera(tmp_path):
    manager = ManagerFake(workflow=_workflow(completeness=70.0), completeness=70.0)
    view = _servico(manager).deploy(_repo(tmp_path))
    assert view.governanca.completeness_actual == 70.0


def test_requisito_zero_nao_le_o_completeness(tmp_path):
    manager = ManagerFake(workflow=_workflow(completeness=0.0))
    _servico(manager).deploy(_repo(tmp_path))
    assert "get_revision_completeness" not in manager.chamadas


def test_atributo_exigido_ausente_no_manager_bloqueia(tmp_path):
    manager = ManagerFake(
        workflow=_workflow(requisitos=[{"attributeId": 231, "mustHave": True}])
    )
    with pytest.raises(DeployGovernanceBlockedError) as capturado:
        _servico(manager).deploy(_repo(tmp_path))

    assert "teste giroto" in capturado.value.message
    assert "deploy_revision" not in manager.chamadas


def test_atributos_vem_do_manager_e_nao_do_repositorio(tmp_path):
    """O manifesto não declara apiTags; os do Manager satisfazem o requisito."""
    manager = ManagerFake(
        workflow=_workflow(requisitos=[{"attributeId": 149, "mustHave": True}])
    )
    view = _servico(manager).deploy(_repo(tmp_path))
    assert [a.name for a in view.governanca.required] == ["My new"]


def test_todas_as_violacoes_saem_juntas(tmp_path):
    manager = ManagerFake(
        api=_api(ambientes=[{"id": 7, "name": "DEV-APIOPS"}, {"id": 9, "name": "HMG-APIOPS"}]),
        workflow=_workflow(
            deployable=[7],
            completeness=70.0,
            requisitos=[{"attributeId": 231, "mustHave": True}],
        ),
        completeness=65.0,
    )
    with pytest.raises(DeployGovernanceBlockedError) as capturado:
        _servico(manager, ambiente=9).deploy(_repo(tmp_path))
    assert len(capturado.value.violacoes) == 3


def test_revisao_sem_stage_avisa_e_nao_bloqueia(tmp_path):
    api = _api()
    for revisao in api["revisions"]:
        revisao.pop("workflowId")
    view = _servico(ManagerFake(api=api)).deploy(_repo(tmp_path))

    assert view.deployment.verified is True
    assert any("Governança" in a for a in view.avisos)


# --- E4: escrita ---------------------------------------------------------------


def test_variavel_ausente_no_ambiente_repassa_a_mensagem_e_gera_documento(tmp_path):
    erro = ManagerApiTransportRejectedError(
        400, "Bad Request",
        messages=["Environment Variable '$backend' have not found"],
    )
    manager = ManagerFake(erro_post=erro)
    with pytest.raises(DeployFalhouError) as capturado:
        _servico(manager).deploy(_repo(tmp_path))

    assert "$backend" in capturado.value.message
    assert capturado.value.exit_code == 1
    doc = capturado.value.view.to_document()
    assert doc["deployment"]["status"] == "FAILED"
    assert doc["deployment"]["attempted"] is True
    assert doc["deployment"]["accepted"] is False
    assert "$backend" in doc["deployment"]["reason"]


def test_ambiente_inexistente_404_repassa_a_mensagem(tmp_path):
    erro = ManagerApiTransportRejectedError(404, "Not Found", messages=["Environment not found."])
    with pytest.raises(DeployFalhouError) as capturado:
        _servico(ManagerFake(erro_post=erro)).deploy(_repo(tmp_path))
    assert "Environment not found." in capturado.value.message


def test_falha_de_transporte_no_post_gera_documento_e_avisa_que_nao_ha_certeza(tmp_path):
    erro = ManagerApiTransportUnavailableError("down")
    with pytest.raises(DeployFalhouError) as capturado:
        _servico(ManagerFake(erro_post=erro)).deploy(_repo(tmp_path))

    assert "Não foi possível confirmar" in capturado.value.message
    assert capturado.value.view.deployment.status == "FAILED"


def test_412_no_post_vira_bloqueio_de_governanca(tmp_path):
    erro = ManagerApiGovernanceBlockedError(
        412, "Precondition Failed", workflow_id=500,
        messages=["Actual Completeness is 50.0 but expected greater than or equal to 70.0"],
    )
    with pytest.raises(DeployGovernanceBlockedError) as capturado:
        _servico(ManagerFake(erro_post=erro)).deploy(_repo(tmp_path))
    assert capturado.value.exit_code == 3
    assert "50.0" in capturado.value.message


# --- E5: conferência -----------------------------------------------------------


def test_201_sem_efeito_na_releitura_falha_com_o_id(tmp_path):
    manager = ManagerFake(efeito=False)
    with pytest.raises(DeployFalhouError) as capturado:
        _servico(manager).deploy(_repo(tmp_path))

    assert "269" in capturado.value.message
    view = capturado.value.view
    assert view.deployment.accepted is True and view.deployment.verified is False
    assert view.deployment.status == "FAILED"


def test_releitura_indisponivel_falha_sem_afirmar_sucesso(tmp_path):
    manager = ManagerFake(erro_releitura=ManagerApiTransportUnavailableError("down"))
    with pytest.raises(DeployFalhouError) as capturado:
        _servico(manager).deploy(_repo(tmp_path))
    assert capturado.value.view.deployment.verified is False


def test_um_unico_post_e_nada_mais_e_escrito(tmp_path):
    manager = ManagerFake()
    _servico(manager).deploy(_repo(tmp_path))
    assert manager.chamadas.count("deploy_revision") == 1
