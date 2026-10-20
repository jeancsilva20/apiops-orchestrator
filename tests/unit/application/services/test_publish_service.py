"""`sen publish` com port fake.

O fake grava a ordem das chamadas: é assim que se prova que as pré-condições
abortam ANTES da escrita, e que a régua e o completeness não são lidos.
"""

import textwrap
from types import SimpleNamespace

import pytest

from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)
from apiops_orchestrator.application.exceptions.validate_exceptions import (
    CustomInexistenteError,
    GovernanceBlockedError,
    IdentidadeDivergenteError,
    LayoutInvalidoError,
    PublicacaoDivergenteError,
    PublicacaoRecusadaError,
    TagInvalidaError,
    ValidateError,
)
from apiops_orchestrator.application.services.publish_service import PublishService
from apiops_orchestrator.domain.models.publish_view import SCHEMA_SEN_PUBLISH_V1
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiGovernanceBlockedError,
    ManagerApiTransportRejectedError,
)

API = {
    "id": 417,
    "name": "Servico de Letras",
    "version": "1.0.0",
    "basePath": "/letras/v2",
    "revisions": [
        {"id": 9161, "revisionNumber": 1},
        {"id": 9175, "revisionNumber": 2},
        {"id": 9180, "revisionNumber": 3},
    ],
    "lastRevision": {},
}


def _revisao(revision_id, numero):
    return {
        "id": revision_id,
        "revisionNumber": numero,
        "workflowId": 500,
        "workflowStageId": 1402,
        "api": {"name": "Servico de Letras", "description": "antes", "apiTags": []},
        "destination": "https://x",
        "interceptors": [],
        "resources": [],
    }


REVISOES = {
    9161: _revisao(9161, 1),
    9175: _revisao(9175, 2),
    9180: _revisao(9180, 3),
}

WORKFLOW = {
    "workflowId": 500,
    "stages": [{"workflowStageId": 1402, "attributesRequisites": []}],
}

BASIC_INFO = """\
apiVersion: api-management.sensedia.com/v1
kind: ApiBasicInfo
spec:
  id: 417
  name: "Servico de Letras"
  version: "1.0.0"
  basePath: "/letras/v2"
  description: "depois"
  template: 414
"""

ALL_YAML = "destination:\n  url: https://backend\n"


class ManagerFake:
    """Port fake que grava a sequência exata de chamadas e os ids tocados."""

    def __init__(self, api=None, workflow=None, customs=None, publicado=None, erro_put=None):
        self.api = api or API
        self.workflow = workflow or WORKFLOW
        self.customs = customs if customs is not None else {}
        self._publicado = publicado
        self._erro_put = erro_put
        self.chamadas = []
        self.ids_lidos = []
        self.id_gravado = None
        self.payload_enviado = None

    # --- leitura
    def get_api_by_id(self, api_id=None):
        self.chamadas.append(f"get_api_by_id:{api_id}")
        return self.api

    def get_revision(self, revision_id):
        self.chamadas.append("get_revision")
        self.ids_lidos.append(revision_id)
        if self.payload_enviado is not None:
            return self._publicado if self._publicado is not None else self.payload_enviado
        return REVISOES[revision_id]

    def get_workflow(self, workflow_id):
        self.chamadas.append("get_workflow")
        return self.workflow

    def list_attributes(self):
        self.chamadas.append("list_attributes")
        return [{"id": 149, "name": "My new", "tags": ["Tag1", "Tag2"]}]

    def get_custom_interceptor_by_id(self, custom_interceptor_id):
        self.chamadas.append("get_custom")
        return self.customs.get(custom_interceptor_id)

    def get_revision_completeness(self, revision_id):  # pragma: no cover - não deve ser chamado
        self.chamadas.append("get_revision_completeness")
        raise AssertionError("o publish não lê completeness (plano §7)")

    # --- escrita
    def update_revision(self, revision_id, payload):
        self.chamadas.append("update_revision")
        if self._erro_put is not None:
            raise self._erro_put
        self.id_gravado = revision_id
        self.payload_enviado = payload
        return {}

    def publish_api_changes(self, data):  # pragma: no cover - não deve ser chamado
        self.chamadas.append("publish_api_changes")
        raise AssertionError("o orquestrador nunca usa POST /revisions (D-005 §9)")


def _settings(modo="pipeline", revisao=2):
    return SimpleNamespace(
        EXECUTION_MODE=modo,
        modo_pipeline=(modo == "pipeline"),
        TEMPLATE_API_ID=414 if modo == "pipeline" else None,
        TARGET_REVISION_NUMBER=revisao,
    )


def _repo(tmp_path, basic_info=BASIC_INFO, extras=None):
    (tmp_path / "api-basic-info.yaml").write_text(
        textwrap.dedent(basic_info), encoding="utf-8"
    )
    (tmp_path / "all.yaml").write_text(ALL_YAML, encoding="utf-8")
    for caminho, conteudo in (extras or {}).items():
        destino = tmp_path / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(textwrap.dedent(conteudo), encoding="utf-8")
    return tmp_path


def _servico(manager, modo="pipeline", revisao=2):
    return PublishService(
        manager_api=manager,
        importer=LocalFileImporterAdapter(),
        settings=_settings(modo, revisao),
    )


SIM = lambda _: True   # noqa: E731
NAO = lambda _: False  # noqa: E731


def _explode(_):
    raise AssertionError("a esteira não pode pedir confirmação (D-17)")


# --- revisão alvo (V-24) ------------------------------------------------------


@pytest.mark.parametrize("numero,revision_id", [(1, 9161), (2, 9175), (3, 9180)])
def test_esteira_grava_na_revisao_de_target_revision_number(tmp_path, numero, revision_id):
    manager = ManagerFake()
    view = _servico(manager, revisao=numero).publish(_repo(tmp_path), confirmar=_explode)

    assert set(manager.ids_lidos) == {revision_id}
    assert manager.id_gravado == revision_id
    assert view.revision.revision_number == numero
    assert view.publicacao.verified is True


def test_esteira_sem_a_variavel_falha_antes_de_qualquer_chamada(tmp_path):
    """P-1: na esteira, ausente não é 1."""
    manager = ManagerFake()
    with pytest.raises(ValidateError) as capturado:
        _servico(manager, revisao=None).publish(_repo(tmp_path), confirmar=_explode)

    assert "TARGET_REVISION_NUMBER" in capturado.value.message
    assert capturado.value.exit_code == 1
    assert manager.chamadas == []


@pytest.mark.parametrize("numero", [2, 3, 4])
def test_local_fora_da_draft_recusa_antes_de_qualquer_chamada(tmp_path, numero):
    """P-2: na máquina local só a Draft."""
    manager = ManagerFake()
    with pytest.raises(ValidateError) as capturado:
        _servico(manager, modo="local", revisao=numero).publish(
            _repo(tmp_path), confirmar=SIM
        )

    assert "revisão 1 (Draft)" in capturado.value.message
    assert manager.chamadas == []


@pytest.mark.parametrize("numero", [None, 1])
def test_local_sem_a_variavel_ou_com_1_grava_na_draft(tmp_path, numero):
    manager = ManagerFake()
    view = _servico(manager, modo="local", revisao=numero).publish(
        _repo(tmp_path), confirmar=SIM
    )

    assert manager.id_gravado == 9161
    assert view.revision.revision_number == 1


def test_revisao_inexistente_nomeia_as_disponiveis_e_nao_escreve(tmp_path):
    """P-3: criar revisão é ato humano."""
    manager = ManagerFake()
    with pytest.raises(ValidateError) as capturado:
        _servico(manager, revisao=4).publish(_repo(tmp_path), confirmar=_explode)

    assert "número 4" in capturado.value.message
    assert "1, 2, 3" in capturado.value.message
    assert "update_revision" not in manager.chamadas


def test_api_sem_revisoes_falha_sem_escrever(tmp_path):
    """P-10."""
    manager = ManagerFake(api=dict(API, revisions=[]))
    with pytest.raises(ValidateError) as capturado:
        _servico(manager).publish(_repo(tmp_path), confirmar=_explode)

    assert "nenhuma revisão" in capturado.value.message
    assert "update_revision" not in manager.chamadas


# --- pré-condições (P-4, P-8, W-2, pré-check) --------------------------------


def test_layout_invalido_aborta_sem_tocar_a_rede(tmp_path):
    """P-8."""
    (tmp_path / "api-basic-info.yaml").write_text(BASIC_INFO, encoding="utf-8")
    manager = ManagerFake()
    with pytest.raises(LayoutInvalidoError):
        _servico(manager).publish(tmp_path, confirmar=_explode)

    assert manager.chamadas == []


def test_identidade_divergente_aborta_antes_de_escrever(tmp_path):
    """P-4 / D-11."""
    divergente = BASIC_INFO.replace('basePath: "/letras/v2"', 'basePath: "/letras/v9"')
    manager = ManagerFake()
    with pytest.raises(IdentidadeDivergenteError):
        _servico(manager).publish(_repo(tmp_path, divergente), confirmar=_explode)

    assert "update_revision" not in manager.chamadas


def test_custom_inexistente_aborta_antes_de_escrever(tmp_path):
    extras = {
        "resources/x/resource.yaml": 'name: "X"\n',
        "resources/x/get_x.yaml": (
            "path: /x\ninterceptors_request:\n  - type: Custom\n    id: 178\n"
        ),
    }
    manager = ManagerFake(customs={})
    with pytest.raises(CustomInexistenteError) as capturado:
        _servico(manager).publish(_repo(tmp_path, extras=extras), confirmar=_explode)

    assert "178" in capturado.value.message
    assert "update_revision" not in manager.chamadas


BASIC_INFO_COM_TAGS = BASIC_INFO + """\
  apiTags:
    - attributeName: My new
      tags:
        - {tag}
"""


def test_tag_fora_do_atributo_aborta_antes_de_escrever(tmp_path):
    manager = ManagerFake()
    repo = _repo(tmp_path, basic_info=BASIC_INFO_COM_TAGS.format(tag="TagInexistente"))
    with pytest.raises(TagInvalidaError):
        _servico(manager).publish(repo, confirmar=_explode)

    assert "update_revision" not in manager.chamadas


def test_atributo_exigido_faltando_bloqueia_com_exit_3_antes_de_escrever(tmp_path):
    """P-5: o faltante é calculado, nunca extraído de texto."""
    workflow = {
        "stages": [
            {
                "workflowStageId": 1402,
                "attributesRequisites": [{"attributeId": 149, "mustHave": True}],
            }
        ]
    }
    manager = ManagerFake(workflow=workflow)
    with pytest.raises(GovernanceBlockedError) as capturado:
        _servico(manager).publish(_repo(tmp_path), confirmar=_explode)

    assert capturado.value.exit_code == 3
    assert "My new" in capturado.value.message
    assert "update_revision" not in manager.chamadas


# --- o publish não faz o diagnóstico do validate (plano §6 / §7) -------------


def test_nao_le_a_api_template_nem_o_completeness(tmp_path):
    manager = ManagerFake()
    _servico(manager).publish(_repo(tmp_path), confirmar=_explode)

    assert "get_api_by_id:414" not in manager.chamadas
    assert "get_revision_completeness" not in manager.chamadas
    assert manager.chamadas.count("get_api_by_id:417") == 1


# --- confirmação (D-9 / D-17) ------------------------------------------------


def test_local_pede_confirmacao_e_recusa_nao_escreve(tmp_path):
    perguntas = []

    def _recusa(texto):
        perguntas.append(texto)
        return False

    manager = ManagerFake()
    view = _servico(manager, modo="local", revisao=1).publish(
        _repo(tmp_path), confirmar=_recusa
    )

    assert view.publicacao.attempted is False
    assert "update_revision" not in manager.chamadas
    assert "revisão 1 (id 9161)" in perguntas[0]


def test_esteira_nao_pergunta(tmp_path):
    manager = ManagerFake()
    _servico(manager).publish(_repo(tmp_path), confirmar=_explode)
    assert "update_revision" in manager.chamadas


# --- escrita (W-7, W-8, D-020) -----------------------------------------------


def test_um_unico_put_depois_de_todas_as_leituras_e_nenhum_post(tmp_path):
    manager = ManagerFake()
    _servico(manager).publish(_repo(tmp_path), confirmar=_explode)

    assert manager.chamadas.count("update_revision") == 1
    assert "publish_api_changes" not in manager.chamadas
    escrita = manager.chamadas.index("update_revision")
    for leitura in ("get_api_by_id:417", "get_workflow"):
        assert manager.chamadas.index(leitura) < escrita
    # a releitura de conferência vem depois da escrita
    assert manager.chamadas[-1] == "get_revision"


def test_workflow_e_stage_da_revisao_alvo_viajam_intactos(tmp_path):
    """D-020: lidos em runtime, nunca configurados nem avançados."""
    manager = ManagerFake()
    _servico(manager, revisao=3).publish(_repo(tmp_path), confirmar=_explode)

    assert manager.payload_enviado["workflowId"] == 500
    assert manager.payload_enviado["workflowStageId"] == 1402
    assert manager.payload_enviado["revisionNumber"] == 3


def test_200_com_perda_e_falha(tmp_path):
    """W-8: HTTP 200 não é prova de sucesso."""
    publicado = dict(REVISOES[9175], resources=[{"name": "sumiu", "operations": []}])
    manager = ManagerFake(publicado=publicado)

    with pytest.raises(PublicacaoDivergenteError) as capturado:
        _servico(manager).publish(_repo(tmp_path), confirmar=_explode)

    assert capturado.value.exit_code == 1


def test_412_no_put_e_exit_3_com_o_motivo_literal(tmp_path):
    motivo = "Actual Completeness is 50.0 but expected greater than or equal to 70.0"
    erro = ManagerApiGovernanceBlockedError(
        status_code=412, title="PRECONDITION_FAILED", workflow_id=500,
        raw={"status": 412}, messages=[motivo],
    )
    manager = ManagerFake(erro_put=erro)

    with pytest.raises(GovernanceBlockedError) as capturado:
        _servico(manager).publish(_repo(tmp_path), confirmar=_explode)

    assert capturado.value.exit_code == 3
    assert motivo in capturado.value.message
    assert "apiTags" not in capturado.value.message


def test_recusa_do_put_nomeia_a_revisao_alvo(tmp_path):
    erro = ManagerApiTransportRejectedError(
        status_code=400, title="Bad Request", messages=["basePath must start with /"]
    )
    manager = ManagerFake(erro_put=erro)

    with pytest.raises(PublicacaoRecusadaError) as capturado:
        _servico(manager).publish(_repo(tmp_path), confirmar=_explode)

    mensagem = capturado.value.message
    assert "gravação da revisão 2" in mensagem
    assert "basePath must start with /" in mensagem
    assert "rascunho" not in mensagem
    assert capturado.value.exit_code == 1


@pytest.mark.parametrize("status", [401, 403])
def test_sessao_ou_acesso_negado_no_put_orienta_sen_login(tmp_path, status):
    """P-6."""
    erro = ManagerApiTransportRejectedError(status_code=status, title="x", messages=[])
    manager = ManagerFake(erro_put=erro)

    with pytest.raises(PublicacaoRecusadaError) as capturado:
        _servico(manager).publish(_repo(tmp_path), confirmar=_explode)

    assert "sen login" in capturado.value.message


# --- contrato de saída -------------------------------------------------------


def test_documento_segue_o_contrato_v1(tmp_path):
    manager = ManagerFake()
    view = _servico(manager).publish(_repo(tmp_path), confirmar=_explode)
    doc = view.to_document()

    assert doc["schema"] == SCHEMA_SEN_PUBLISH_V1
    assert list(doc) == [
        "schema", "generatedAt", "executionMode", "api", "revision",
        "governance", "publication", "warnings",
    ]
    assert doc["executionMode"] == "pipeline"
    assert doc["revision"] == {"managerId": 9175, "revisionNumber": 2, "deployments": []}
    assert doc["publication"]["verified"] is True
    assert doc["governance"]["workflowId"] == 500
    assert doc["governance"]["stageId"] == 1402


def test_etapas_narradas_na_ordem(tmp_path):
    etapas = []
    _servico(ManagerFake()).publish(
        _repo(tmp_path), confirmar=_explode, progresso=etapas.append
    )

    assert etapas == [
        "Lendo o repositório",
        "Consultando a API no Manager",
        "Verificando os interceptors Custom",
        "Verificando a governança",
        "Gravando a revisão 2 no Manager",
        "Conferindo o que foi gravado",
    ]


# --- o repositório prevalece no content (regressão do S10 contra a 417) -------


def test_alterar_content_de_interceptor_existente_chega_ao_put(tmp_path, monkeypatch):
    revisao = dict(
        REVISOES[9175],
        interceptors=[
            {"id": 11, "idTemp": 11, "type": "Rate limit", "executionPoint": "FIRST",
             "position": 4, "status": "REFERENCE", "content": '{"quota": "1000"}'},
        ],
    )
    monkeypatch.setitem(REVISOES, 9175, revisao)
    all_yaml = (
        "destination:\n  url: https://backend\n\n"
        "interceptors_request:\n  - type: Rate limit\n    content:\n      quota: \"500\"\n"
    )
    repo = _repo(tmp_path)
    (repo / "all.yaml").write_text(all_yaml, encoding="utf-8")

    manager = ManagerFake()
    view = _servico(manager).publish(repo, confirmar=_explode)

    enviado = manager.payload_enviado["interceptors"][0]
    assert enviado["id"] == 11
    assert '"quota": "500"' in enviado["content"]
    assert view.publicacao.verified is True


def test_content_perdido_pela_plataforma_falha_a_conferencia(tmp_path):
    """200 com o content antigo: a releitura contra o DECLARADO pega."""
    all_yaml = (
        "destination:\n  url: https://backend\n\n"
        "interceptors_request:\n  - type: Rate limit\n    content:\n      quota: \"500\"\n"
    )
    publicado = dict(
        REVISOES[9175],
        destination="https://backend",
        interceptors=[
            {"id": 11, "type": "Rate limit", "executionPoint": "FIRST", "position": 1,
             "content": '{"quota": "1000"}'},
        ],
    )
    repo = _repo(tmp_path)
    (repo / "all.yaml").write_text(all_yaml, encoding="utf-8")

    with pytest.raises(PublicacaoDivergenteError) as capturado:
        _servico(ManagerFake(publicado=publicado)).publish(repo, confirmar=_explode)

    assert "`quota` declarado" in capturado.value.message


# --- avisos de remoção: na confirmação em local, no resultado na esteira -----

def _revisao_com_recurso_extra(monkeypatch, numero_id):
    revisao = dict(
        REVISOES[numero_id],
        resources=[{"name": "Saude", "operations": [{"id": 3, "method": "GET", "path": "/health"}]}],
    )
    monkeypatch.setitem(REVISOES, numero_id, revisao)


def test_local_mostra_a_remocao_na_confirmacao_e_nao_no_resultado(tmp_path, monkeypatch):
    _revisao_com_recurso_extra(monkeypatch, 9161)
    perguntas = []
    view = _servico(ManagerFake(), modo="local", revisao=1).publish(
        _repo(tmp_path), confirmar=lambda texto: perguntas.append(texto) or True
    )

    assert "Atenção:" in perguntas[0]
    assert "serão apagados do Manager" in perguntas[0] and "  - Saude" in perguntas[0]
    assert not any("apagados do Manager" in a for a in view.avisos)


def test_local_recusa_depois_de_ver_a_remocao_nao_grava(tmp_path, monkeypatch):
    _revisao_com_recurso_extra(monkeypatch, 9161)
    manager = ManagerFake()
    view = _servico(manager, modo="local", revisao=1).publish(_repo(tmp_path), confirmar=NAO)

    assert view.publicacao.attempted is False
    assert "update_revision" not in manager.chamadas


def test_esteira_mostra_a_remocao_no_resultado(tmp_path, monkeypatch):
    _revisao_com_recurso_extra(monkeypatch, 9175)
    view = _servico(ManagerFake()).publish(_repo(tmp_path), confirmar=_explode)

    assert any("serão apagados do Manager" in a and "Saude" in a for a in view.avisos)


def test_sem_remocao_a_confirmacao_nao_tem_atencao(tmp_path):
    perguntas = []
    _servico(ManagerFake(), modo="local", revisao=1).publish(
        _repo(tmp_path), confirmar=lambda texto: perguntas.append(texto) or True
    )
    assert "Atenção:" not in perguntas[0]


# --- ambientes com a revisão alvo no ar (só informativo) ---------------------

# 01/10/2026 e 19/10/2026, em epoch ms.
_DIA_1 = 1790812800000
_DIA_19 = 1792368000000


def _api_com_deploys(deployments_da_rev_2, environments=None):
    revisoes = [dict(r) for r in API["revisions"]]
    revisoes[1]["deployments"] = deployments_da_rev_2
    return dict(
        API,
        revisions=revisoes,
        environments=environments
        if environments is not None
        else [{"id": 7, "name": "DEV-APIOPS"}, {"id": 8, "name": "HML-APIOPS"}],
    )


def _deploy(deployment_id, ambiente, status="DEPLOYED", data=_DIA_19):
    return {
        "id": deployment_id,
        "revisionId": 9175,
        "revisionNumber": 2,
        "environmentId": ambiente,
        "status": status,
        "deployDate": data,
    }


def test_revisao_no_ar_traz_ambiente_deploy_e_data(tmp_path):
    manager = ManagerFake(api=_api_com_deploys([_deploy(269, 7)]))
    view = _servico(manager).publish(_repo(tmp_path), confirmar=_explode)

    assert view.to_document()["revision"]["deployments"] == [
        {
            "deploymentId": 269,
            "environment": {"managerId": 7, "name": "DEV-APIOPS"},
            "deployedAt": "2026-10-19T00:00:00Z",
        }
    ]


def test_undeployed_e_ignorado_e_cada_ambiente_aparece_uma_vez(tmp_path):
    manager = ManagerFake(
        api=_api_com_deploys(
            [
                _deploy(266, 7, status="UNDEPLOYED", data=_DIA_1),
                _deploy(268, 8, data=_DIA_1),
                _deploy(269, 7),
            ]
        )
    )
    view = _servico(manager).publish(_repo(tmp_path), confirmar=_explode)

    assert [(d.environment.manager_id, d.deployment_id) for d in view.deployments] == [
        (7, 269),
        (8, 268),
    ]


def test_ambiente_nao_ligado_a_api_vem_sem_nome(tmp_path):
    """A plataforma aceita deploy em ambiente fora de `environments[]` (E-3)."""
    manager = ManagerFake(api=_api_com_deploys([_deploy(271, 9)]))
    view = _servico(manager).publish(_repo(tmp_path), confirmar=_explode)

    assert view.deployments[0].environment.manager_id == 9
    assert view.deployments[0].environment.name is None


def test_revisao_fora_do_ar_vem_como_lista_vazia(tmp_path):
    manager = ManagerFake(api=_api_com_deploys([_deploy(266, 7, status="UNDEPLOYED")]))
    view = _servico(manager).publish(_repo(tmp_path), confirmar=_explode)

    assert view.to_document()["revision"]["deployments"] == []


def test_deploy_de_outra_revisao_nao_conta(tmp_path):
    revisoes = [dict(r) for r in API["revisions"]]
    revisoes[2]["deployments"] = [dict(_deploy(270, 7), revisionId=9180, revisionNumber=3)]
    manager = ManagerFake(api=dict(API, revisions=revisoes))
    view = _servico(manager).publish(_repo(tmp_path), confirmar=_explode)

    assert view.deployments == []
