"""Cascata E1→E4 do `sen validate`, com port fake.

O fake **grava a ordem das chamadas**: é assim que se prova que as guardas
abortam ANTES da escrita, e não só que abortam.
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
)
from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    INTERNAL_ERROR_MESSAGE,
)
from apiops_orchestrator.application.services.validate_service import ValidateService
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiGovernanceBlockedError,
    ManagerApiTransportRejectedError,
)

API = {
    "id": 417,
    "name": "Servico de Letras",
    "version": "1.0.0",
    "basePath": "/letras/v2",
    "revisions": [{"id": 9161, "revisionNumber": 1}],
    "lastRevision": {},
}

DRAFT = {
    "id": 9161,
    "revisionNumber": 1,
    "workflowId": 500,
    "workflowStageId": 1402,
    "api": {"name": "Servico de Letras", "description": "antes", "apiTags": []},
    "destination": "https://x",
    "interceptors": [],
    "resources": [],
}

REGUA = {
    "id": 414,
    "lastRevision": {"revisionNumber": 1, "interceptors": []},
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
    """Port fake que grava a sequência exata de chamadas."""

    def __init__(self, api=None, draft=None, workflow=None, customs=None, publicado=None):
        self.api = api or API
        self.draft = draft or DRAFT
        self.workflow = workflow or WORKFLOW
        self.customs = customs if customs is not None else {}
        self._publicado = publicado
        self.chamadas = []
        self.payload_enviado = None

    # --- leitura
    def get_api_by_id(self, api_id=None):
        self.chamadas.append("get_api_by_id")
        return REGUA if api_id == 414 else self.api

    def get_revision(self, revision_id):
        self.chamadas.append("get_revision")
        if self.payload_enviado is not None:
            return self._publicado if self._publicado is not None else self.payload_enviado
        return self.draft

    def get_workflow(self, workflow_id):
        self.chamadas.append("get_workflow")
        return self.workflow

    def list_attributes(self):
        self.chamadas.append("list_attributes")
        return [{"id": 149, "name": "My new"}, {"id": 231, "name": "teste giroto"}]

    def get_custom_interceptor_by_id(self, custom_interceptor_id):
        self.chamadas.append("get_custom")
        return self.customs.get(custom_interceptor_id)

    def get_revision_completeness(self, revision_id):
        self.chamadas.append("get_revision_completeness")
        return SimpleNamespace(score=42.0, suggestions=["Adicione exemplos"])

    # --- escrita
    def update_revision(self, revision_id, payload):
        self.chamadas.append("update_revision")
        self.payload_enviado = payload
        return {}

    def publish_api_changes(self, data):  # pragma: no cover - não deve ser chamado
        self.chamadas.append("publish_api_changes")
        raise AssertionError("o orquestrador nunca usa POST /revisions (D-005 §9)")


def _settings(modo="local", revisao=1):
    return SimpleNamespace(
        EXECUTION_MODE=modo,
        modo_pipeline=(modo == "pipeline"),
        # Na esteira a régua vem do cofre; em local, do manifesto (V-11 binding).
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


def _servico(manager, modo="local", revisao=1):
    return ValidateService(
        manager_api=manager,
        importer=LocalFileImporterAdapter(),
        settings=_settings(modo, revisao),
    )


SIM = lambda _: True   # noqa: E731
NAO = lambda _: False  # noqa: E731


# --- caminho feliz ----------------------------------------------------------


def test_cascata_completa_publica_e_confere(tmp_path):
    manager = ManagerFake()
    view = _servico(manager).validate(_repo(tmp_path), confirmar=SIM)

    assert view.publicacao.attempted and view.publicacao.verified
    assert view.api.manager_id == 417
    assert view.revision.revision_number == 1
    assert view.regua.template_id == 414
    assert view.completeness.score == 42.0


def test_a_escrita_vem_depois_de_todas_as_leituras(tmp_path):
    manager = ManagerFake()
    _servico(manager).validate(_repo(tmp_path), confirmar=SIM)

    escrita = manager.chamadas.index("update_revision")
    for leitura in ("get_api_by_id", "get_revision", "get_workflow"):
        assert manager.chamadas.index(leitura) < escrita


def test_e3_faz_um_unico_put_e_nenhum_post(tmp_path):
    """W-7: escrever também em `PUT /apis` furaria o gate do AG."""
    manager = ManagerFake()
    _servico(manager).validate(_repo(tmp_path), confirmar=SIM)

    assert manager.chamadas.count("update_revision") == 1
    assert "publish_api_changes" not in manager.chamadas


def test_conferencia_relê_a_revisao_depois_de_publicar(tmp_path):
    manager = ManagerFake()
    _servico(manager).validate(_repo(tmp_path), confirmar=SIM)

    depois = manager.chamadas[manager.chamadas.index("update_revision") :]
    assert "get_revision" in depois


# --- D-020: o stage é preservado -------------------------------------------


def test_workflow_e_stage_viajam_intactos_no_payload(tmp_path):
    manager = ManagerFake()
    _servico(manager).validate(_repo(tmp_path), confirmar=SIM)

    assert manager.payload_enviado["workflowId"] == 500
    assert manager.payload_enviado["workflowStageId"] == 1402


def test_basic_info_viaja_no_api_aninhado(tmp_path):
    """W-7: é no `api` aninhado do payload da revision que o AG atua."""
    manager = ManagerFake()
    _servico(manager).validate(_repo(tmp_path), confirmar=SIM)

    assert manager.payload_enviado["api"]["description"] == "depois"


# --- guardas ----------------------------------------------------------------


def test_e1_aborta_sem_tocar_a_rede(tmp_path):
    (tmp_path / "api-basic-info.yaml").write_text(BASIC_INFO, encoding="utf-8")
    manager = ManagerFake()
    with pytest.raises(LayoutInvalidoError) as capturado:
        _servico(manager).validate(tmp_path, confirmar=SIM)

    assert manager.chamadas == []
    assert "all.yaml" in capturado.value.message


def test_guarda_de_identidade_aborta_antes_de_escrever(tmp_path):
    """D-11: `version` e `basePath` definem a identidade funcional."""
    divergente = BASIC_INFO.replace('basePath: "/letras/v2"', 'basePath: "/letras/v9"')
    manager = ManagerFake()
    with pytest.raises(IdentidadeDivergenteError):
        _servico(manager).validate(_repo(tmp_path, divergente), confirmar=SIM)

    assert "update_revision" not in manager.chamadas


def test_spec_id_divergente_nao_aborta(tmp_path):
    """D-11: `spec.id` é o endereço do GET, não a identidade."""
    manager = ManagerFake(api=dict(API, id=999))
    _servico(manager).validate(_repo(tmp_path), confirmar=SIM)
    assert "update_revision" in manager.chamadas


def test_governanca_bloqueia_antes_de_escrever(tmp_path):
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
        _servico(manager).validate(_repo(tmp_path), confirmar=SIM)

    assert capturado.value.exit_code == 3
    assert "My new" in capturado.value.message
    assert "update_revision" not in manager.chamadas


def test_confirmacao_negada_nao_escreve(tmp_path):
    manager = ManagerFake()
    view = _servico(manager).validate(_repo(tmp_path), confirmar=NAO)

    assert view.publicacao.attempted is False
    assert "update_revision" not in manager.chamadas


def test_pipeline_nao_pergunta(tmp_path):
    def _explode(_):
        raise AssertionError("a esteira não pode pedir confirmação (D-17)")

    manager = ManagerFake()
    _servico(manager, modo="pipeline").validate(_repo(tmp_path), confirmar=_explode)
    assert "update_revision" in manager.chamadas


def test_local_so_publica_na_revisao_1(tmp_path):
    """V-24: a Draft não é ambiente e não tem deploy."""
    manager = ManagerFake()
    with pytest.raises(Exception, match="Draft"):
        _servico(manager, revisao=2).validate(_repo(tmp_path), confirmar=SIM)
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
        _servico(manager).validate(_repo(tmp_path, extras=extras), confirmar=SIM)

    assert "178" in capturado.value.message
    assert "update_revision" not in manager.chamadas


# --- W-8: 200 não é prova ---------------------------------------------------


def test_divergencia_pos_publicacao_e_falha(tmp_path):
    """Três perdas silenciosas sob HTTP 200 foram observadas."""
    publicado = dict(DRAFT, resources=[{"name": "sumiu", "operations": []}])
    manager = ManagerFake(publicado=publicado)

    with pytest.raises(PublicacaoDivergenteError) as capturado:
        _servico(manager).validate(_repo(tmp_path), confirmar=SIM)

    assert capturado.value.exit_code == 1
    assert "não foi enviado" in capturado.value.message


def test_completeness_nao_bloqueia(tmp_path):
    """Decisão 2: informativa no validate; o gate trava em DEV+."""
    manager = ManagerFake()
    view = _servico(manager).validate(_repo(tmp_path), confirmar=SIM)
    assert view.completeness.score == 42.0
    assert view.completeness.gate_percent == 70.0
    assert view.publicacao.verified is True


# --- a conformidade avalia o PAYLOAD, não o estado remoto -------------------


def test_conformidade_avalia_o_que_sera_publicado_nao_o_remoto(tmp_path):
    """Defeito encontrado ao usar o comando: a E2 comparava o estado ANTERIOR.

    O dev editava o repositório, rodava `sen validate`, e os achados descreviam
    o estado de antes da edição — só uma segunda execução mostraria o efeito da
    própria mudança.
    """
    extras = {
        "resources/x/resource.yaml": 'name: "X"\n',
        "resources/x/get_x.yaml": (
            "path: /x\ninherit: false\n\ninterceptors_request:\n"
            "  - type: Log\n    content:\n      acceptedTerms: true\n"
        ),
    }
    # O remoto NÃO tem o `Log`; o repositório passa a declará-lo.
    draft = dict(
        DRAFT,
        resources=[
            {
                "name": "X",
                "interceptors": [],
                "operations": [
                    {"method": "GET", "path": "/x", "interceptors": []}
                ],
            }
        ],
    )
    regua = {
        "id": 414,
        "lastRevision": {
            "revisionNumber": 1,
            "interceptors": [
                {"type": "Log", "executionPoint": "FIRST",
                 "content": '{"acceptedTerms": true}'}
            ],
        },
    }

    class _Manager(ManagerFake):
        def get_api_by_id(self, api_id=None):
            self.chamadas.append("get_api_by_id")
            return regua if api_id == 414 else self.api

    manager = _Manager(draft=draft)
    view = _servico(manager).validate(_repo(tmp_path, extras=extras), confirmar=SIM)

    # Avaliando o payload, `GET /x` passa a conformar com a régua.
    de_x = [a for a in view.achados if a.scope == "GET /x"]
    assert de_x == [], f"deveria conformar, mas veio: {[a.message for a in de_x]}"


def test_heranca_pura_sobre_lista_propria_vira_warning(tmp_path):
    """O repositório declara herança pura sobre um escopo que tem lista própria.

    Sob a V-27 isso deixou de ser um no-op e passou a ser uma **remoção**: a
    lista própria sai e o escopo volta a herdar. É o que o dev pediu, mas apaga
    estado — e não pode acontecer calado.
    """
    extras = {
        "resources/x/resource.yaml": 'name: "X"\ninherit: true\n',
        "resources/x/get_x.yaml": "path: /x\ninherit: true\n",
    }
    draft = dict(
        DRAFT,
        resources=[
            {
                "name": "X",
                "interceptors": [],
                "operations": [
                    {
                        "method": "GET",
                        "path": "/x",
                        "interceptors": [
                            {"id": 1, "type": "Log", "executionPoint": "FIRST",
                             "position": 1}
                        ],
                    }
                ],
            }
        ],
    )
    manager = ManagerFake(draft=draft)
    view = _servico(manager).validate(_repo(tmp_path, extras=extras), confirmar=SIM)

    avisos = [a for a in view.achados if a.scope == "repositório"]
    assert len(avisos) == 1
    assert "esses interceptors saem" in avisos[0].message
    assert "Log" in avisos[0].message
    assert avisos[0].severity == "WARNING"


def test_o_texto_da_confirmacao_nao_promete_deploy(tmp_path):
    """D-9 · guarda 2: o dev precisa entender o que vai acontecer.

    A gravação do rascunho é o meio pelo qual a governança dá o veredito —
    nenhum ambiente recebe deploy. O texto diz isso, e a pergunta de sim/não
    fica na borda, que é quem sabe que a confirmação é interativa.
    """
    vistas = []

    def _registrar(mensagem):
        vistas.append(mensagem)
        return True

    _servico(ManagerFake()).validate(_repo(tmp_path), confirmar=_registrar)

    assert len(vistas) == 1
    assert "rascunho" in vistas[0]
    assert "Nenhum ambiente recebe deploy" in vistas[0]
    assert "?" not in vistas[0], "a pergunta é da borda, não do serviço"


def test_as_etapas_sao_narradas_na_ordem_da_cascata(tmp_path):
    """`progresso` existe para a barra saber o que está demorando."""
    etapas = []
    _servico(ManagerFake()).validate(
        _repo(tmp_path), confirmar=SIM, progresso=etapas.append
    )

    assert etapas[0] == "Lendo o repositório"
    assert "Lendo a API-template" in etapas
    assert etapas.index("Lendo a API-template") < etapas.index(
        "Gravando o rascunho no Manager"
    )
    assert etapas[-1] == "Calculando o quality score"


def test_sem_progresso_a_cascata_roda_igual(tmp_path):
    """O narrador é opcional: a esteira não passa nenhum."""
    view = _servico(ManagerFake()).validate(_repo(tmp_path), confirmar=SIM)
    assert view.publicacao.attempted is True


# --- Recusa do PUT do rascunho (V-23 §5 · spec sen-validate exit codes) ------


class _ManagerQueRecusa(ManagerFake):
    def __init__(self, erro, **kwargs):
        super().__init__(**kwargs)
        self._erro = erro

    def update_revision(self, revision_id, payload):
        self.chamadas.append("update_revision")
        raise self._erro


_ENVELOPE_412 = {
    "result": "failure",
    "errors": [{"type": "INVALID", "message": "{...}"}],
    "status": 412,
}


def test_412_da_governanca_no_put_e_bloqueio_com_exit_3_e_motivo_literal(tmp_path):
    erro = ManagerApiGovernanceBlockedError(
        status_code=412, title="PRECONDITION_FAILED", workflow_id=500,
        raw=_ENVELOPE_412, messages=["API must contain attribute My new"],
    )
    manager = _ManagerQueRecusa(erro)

    with pytest.raises(GovernanceBlockedError) as capturado:
        _servico(manager).validate(_repo(tmp_path), confirmar=SIM)

    bloqueio = capturado.value
    assert bloqueio.exit_code == 3
    assert "API must contain attribute My new" in bloqueio.message
    assert "workflow 500" in bloqueio.message
    assert "Nada foi publicado." in bloqueio.message
    assert bloqueio.raw == _ENVELOPE_412
    assert bloqueio.missing == []  # nunca extraído do texto livre
    # a releitura pós-publicação não acontece depois de uma recusa
    assert manager.chamadas[-1] == "update_revision"


@pytest.mark.parametrize("status", [400, 409, 422])
def test_recusa_de_validacao_no_put_mostra_o_motivo_da_plataforma(tmp_path, status):
    erro = ManagerApiTransportRejectedError(
        status_code=status, title="Bad Request", messages=["basePath must start with /"]
    )

    with pytest.raises(PublicacaoRecusadaError) as capturado:
        _servico(_ManagerQueRecusa(erro)).validate(_repo(tmp_path), confirmar=SIM)

    mensagem = capturado.value.message
    assert capturado.value.exit_code == 1
    assert "basePath must start with /" in mensagem
    assert "Nada foi publicado." in mensagem


@pytest.mark.parametrize(
    ("status", "trecho"),
    [(401, "sen login"), (403, "sen login"), (413, "erro interno"), (429, "erro interno")],
)
def test_recusa_sem_motivo_util_usa_a_mensagem_da_familia(tmp_path, status, trecho):
    erro = ManagerApiTransportRejectedError(
        status_code=status, title="x", messages=["Backend response was too large"]
    )

    with pytest.raises(PublicacaoRecusadaError) as capturado:
        _servico(_ManagerQueRecusa(erro)).validate(_repo(tmp_path), confirmar=SIM)

    mensagem = capturado.value.message
    assert trecho in mensagem
    assert "Backend response was too large" not in mensagem
    assert str(status) not in mensagem
    assert capturado.value.exit_code == 1


def test_recusa_de_validacao_sem_motivo_cai_no_erro_interno(tmp_path):
    erro = ManagerApiTransportRejectedError(status_code=422, title="x", messages=[])

    with pytest.raises(PublicacaoRecusadaError) as capturado:
        _servico(_ManagerQueRecusa(erro)).validate(_repo(tmp_path), confirmar=SIM)

    assert INTERNAL_ERROR_MESSAGE in capturado.value.message


# --- apiTags: tag fora do atributo e perda silenciosa -------------------------

BASIC_INFO_COM_TAGS = BASIC_INFO + """\
  apiTags:
    - attributeName: My new
      tags:
        - {tag}
"""


class _ManagerComCatalogoDeTags(ManagerFake):
    def list_attributes(self):
        self.chamadas.append("list_attributes")
        return [{"id": 149, "name": "My new", "tags": ["Tag1", "Tag2"]}]


def test_tag_fora_do_atributo_aborta_antes_de_escrever(tmp_path):
    manager = _ManagerComCatalogoDeTags()
    repo = _repo(tmp_path, basic_info=BASIC_INFO_COM_TAGS.format(tag="TagInexistente"))

    with pytest.raises(TagInvalidaError) as capturado:
        _servico(manager).validate(repo, confirmar=SIM)

    mensagem = capturado.value.message
    assert capturado.value.exit_code == 1
    assert "`TagInexistente` em `My new`" in mensagem and "Tag1, Tag2" in mensagem
    assert "Nada foi publicado." in mensagem
    assert "update_revision" not in manager.chamadas


def test_tag_valida_segue_para_a_publicacao(tmp_path):
    manager = _ManagerComCatalogoDeTags()
    repo = _repo(tmp_path, basic_info=BASIC_INFO_COM_TAGS.format(tag="Tag2"))

    view = _servico(manager).validate(repo, confirmar=SIM)

    assert view.publicacao.attempted and view.publicacao.verified


def test_apitags_apagadas_pela_plataforma_viram_divergencia(tmp_path):
    """O PUT voltou 200, mas o Manager zerou as apiTags: não é sucesso."""
    publicado = dict(DRAFT, api=dict(DRAFT["api"], apiTags=[]))
    manager = _ManagerComCatalogoDeTags(publicado=publicado)
    repo = _repo(tmp_path, basic_info=BASIC_INFO_COM_TAGS.format(tag="Tag1"))

    with pytest.raises(PublicacaoDivergenteError) as capturado:
        _servico(manager).validate(repo, confirmar=SIM)

    assert "`My new` foi enviado em `apiTags`" in capturado.value.message
