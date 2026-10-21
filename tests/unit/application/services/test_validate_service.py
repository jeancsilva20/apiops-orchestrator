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
    ApiInacessivelError,
    CustomInexistenteError,
    GovernanceBlockedError,
    IdentidadeDivergenteError,
    LayoutInvalidoError,
    PublicacaoDivergenteError,
    PublicacaoRecusadaError,
    TagInvalidaError,
    TemplateNaoConfiguradaError,
)
from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    INTERNAL_ERROR_MESSAGE,
)
from apiops_orchestrator.application.services.validate_service import ValidateService
from apiops_orchestrator.domain.models.login_session_model import LoginSession
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


# --- api-visibility ---------------------------------------------------------

GRUPO_ALHEIO = {
    "visibilityType": "GROUP",
    "groupVisibility": {"name": "Lab-tech"},
    "owner": "isaac.machado",
    "users": [],
}


def _sessao(perfil="developer"):
    dados = {
        "accessToken": "x",
        "tokenType": "Bearer",
        "expiresIn": 3600,
        "scope": "validate",
        "profile": perfil,
    }
    if perfil == "developer":
        dados.update(
            userName="isaac.machado",
            userEmail="isaac.machado@sensedia.com",
            userGroups=["APIOps"],
        )
    return LoginSession.model_validate(dados)


def _servico_da_sessao(manager, sessao):
    return ValidateService(
        manager_api=manager,
        importer=LocalFileImporterAdapter(),
        settings=_settings(),
        session=sessao,
    )


def test_api_invisivel_aborta_logo_apos_ler_a_api(tmp_path):
    manager = ManagerFake(api=dict(API, visibility=GRUPO_ALHEIO))

    with pytest.raises(ApiInacessivelError) as capturado:
        _servico_da_sessao(manager, _sessao()).validate(_repo(tmp_path), confirmar=SIM)

    assert manager.chamadas == ["get_api_by_id"]
    assert capturado.value.message.startswith(
        "API 417 não encontrada ou sem permissão de acesso."
    )
    assert "Nada foi publicado." in capturado.value.message
    assert capturado.value.exit_code == 1


class _ManagerSemAApi(ManagerFake):
    def get_api_by_id(self, api_id=None):
        self.chamadas.append("get_api_by_id")
        raise ManagerApiTransportRejectedError(status_code=404, title="Not Found")


@pytest.mark.parametrize("perfil", ["developer", "super-admin"])
def test_api_inexistente_responde_como_a_invisivel(tmp_path, perfil):
    invisivel = ManagerFake(api=dict(API, visibility=GRUPO_ALHEIO))
    with pytest.raises(ApiInacessivelError) as esperado:
        _servico_da_sessao(invisivel, _sessao()).validate(_repo(tmp_path), confirmar=SIM)

    manager = _ManagerSemAApi()
    with pytest.raises(ApiInacessivelError) as capturado:
        _servico_da_sessao(manager, _sessao(perfil)).validate(_repo(tmp_path), confirmar=SIM)

    assert capturado.value.message == esperado.value.message
    assert manager.chamadas == ["get_api_by_id"]


def test_outra_recusa_do_get_da_api_nao_vira_api_inexistente(tmp_path):
    class _ManagerQueNega(ManagerFake):
        def get_api_by_id(self, api_id=None):
            raise ManagerApiTransportRejectedError(status_code=403, title="Forbidden")

    with pytest.raises(ManagerApiTransportRejectedError):
        _servico_da_sessao(_ManagerQueNega(), _sessao()).validate(
            _repo(tmp_path), confirmar=SIM
        )


def test_api_me_compartilhada_com_o_dev_segue_a_cascata(tmp_path):
    compartilhada = {
        "visibilityType": "ME",
        "owner": "paulo.silva",
        "users": [{"id": 7, "username": "isaac.machado"}],
    }
    manager = ManagerFake(api=dict(API, visibility=compartilhada))

    _servico_da_sessao(manager, _sessao()).validate(_repo(tmp_path), confirmar=SIM)

    assert "update_revision" in manager.chamadas


def test_super_admin_valida_api_de_qualquer_grupo(tmp_path):
    manager = ManagerFake(api=dict(API, visibility=GRUPO_ALHEIO))

    _servico_da_sessao(manager, _sessao("super-admin")).validate(
        _repo(tmp_path), confirmar=SIM
    )

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


_API_TRES_REVISOES = {
    **API,
    "revisions": [
        {"id": 9161, "revisionNumber": 1},
        {"id": 9162, "revisionNumber": 2},
        {"id": 9163, "revisionNumber": 3},
    ],
}


class _ManagerQueAnotaIds(ManagerFake):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ids_lidos = []
        self.id_gravado = None

    def get_revision(self, revision_id):
        self.ids_lidos.append(revision_id)
        return super().get_revision(revision_id)

    def update_revision(self, revision_id, payload):
        self.id_gravado = revision_id
        return super().update_revision(revision_id, payload)


@pytest.mark.parametrize("numero", [None, 1, 2, 3])
def test_local_grava_sempre_na_draft_e_ignora_a_variavel(tmp_path, numero):
    """V-24 §6: fora da esteira a revisão alvo não depende da configuração."""
    manager = _ManagerQueAnotaIds(api=_API_TRES_REVISOES)
    view = _servico(manager, modo="local", revisao=numero).validate(
        _repo(tmp_path), confirmar=SIM
    )

    assert manager.id_gravado == 9161
    assert view.revision.revision_number == 1
    assert "executionMode" not in view.to_document()


@pytest.mark.parametrize("numero,revision_id", [(1, 9161), (2, 9162), (3, 9163)])
def test_pipeline_le_e_grava_na_revisao_de_target_revision_number(
    tmp_path, numero, revision_id
):
    """V-24: na esteira o alvo vem da variável, resolvido pelo número."""
    manager = _ManagerQueAnotaIds(api=_API_TRES_REVISOES)
    view = _servico(manager, modo="pipeline", revisao=numero).validate(
        _repo(tmp_path), confirmar=SIM
    )

    assert set(manager.ids_lidos) == {revision_id}
    assert manager.id_gravado == revision_id
    assert view.revision.revision_number == numero


def test_pipeline_com_revisao_inexistente_aborta_antes_de_escrever(tmp_path):
    manager = _ManagerQueAnotaIds(api=_API_TRES_REVISOES)
    with pytest.raises(Exception, match="número 7"):
        _servico(manager, modo="pipeline", revisao=7).validate(
            _repo(tmp_path), confirmar=SIM
        )
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
    # Na esteira não há confirmação: o aviso sai no resultado.
    manager = ManagerFake(draft=draft)
    view = _servico(manager, modo="pipeline").validate(
        _repo(tmp_path, extras=extras), confirmar=SIM
    )

    avisos = [a for a in view.achados if a.scope == "repositório"]
    assert len(avisos) == 1
    assert "esses interceptors saem" in avisos[0].message
    assert "Log" in avisos[0].message
    assert avisos[0].severity == "WARNING"

    # Em local o aviso vai para a confirmação, ANTES da gravação, e não se repete.
    perguntas = []
    (tmp_path / "local").mkdir()
    view = _servico(ManagerFake(draft=draft)).validate(
        _repo(tmp_path / "local", extras=extras),
        confirmar=lambda texto: perguntas.append(texto) or True,
    )
    assert "esses interceptors saem" in perguntas[0]
    assert "Atenção:" in perguntas[0]
    assert [a for a in view.achados if a.scope == "repositório"] == []


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


def test_412_por_completude_nao_manda_ajustar_api_tags(tmp_path):
    """O motivo é texto livre: não presumir que todo bloqueio é atributo faltante."""
    motivo = "Actual Completeness is 50.0 but expected greater than or equal to 70.0"
    erro = ManagerApiGovernanceBlockedError(
        status_code=412, title="PRECONDITION_FAILED", workflow_id=394,
        raw=_ENVELOPE_412, messages=[motivo],
    )

    with pytest.raises(GovernanceBlockedError) as capturado:
        _servico(_ManagerQueRecusa(erro)).validate(_repo(tmp_path), confirmar=SIM)

    mensagem = capturado.value.message
    assert motivo in mensagem
    assert "apiTags" not in mensagem
    assert "Corrija conforme o motivo acima" in mensagem


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


def test_alterar_content_de_interceptor_existente_chega_ao_put(tmp_path):
    """Regressão do S10: o validate grava o content do repositório, não o do Manager."""
    draft = dict(
        DRAFT,
        interceptors=[
            {"id": 11, "idTemp": 11, "type": "Rate limit", "executionPoint": "FIRST",
             "position": 4, "status": "REFERENCE", "content": '{"quota": "1000"}'},
        ],
    )
    repo = _repo(tmp_path)
    (repo / "all.yaml").write_text(
        "destination:\n  url: https://backend\n\n"
        "interceptors_request:\n  - type: Rate limit\n    content:\n      quota: \"500\"\n",
        encoding="utf-8",
    )
    manager = ManagerFake(draft=draft)
    view = _servico(manager).validate(repo, confirmar=SIM)

    enviado = manager.payload_enviado["interceptors"][0]
    assert enviado["id"] == 11 and '"quota": "500"' in enviado["content"]
    assert view.publicacao.verified is True


# --- achado de escopo herdado sai uma vez, no dono do fluxo -------------------


class _ManagerComRegua(ManagerFake):
    def __init__(self, regua_interceptors, **kwargs):
        super().__init__(**kwargs)
        self._regua = {"id": 414, "lastRevision": {"revisionNumber": 1,
                                                   "interceptors": regua_interceptors}}

    def get_api_by_id(self, api_id=None):
        self.chamadas.append("get_api_by_id")
        return self._regua if api_id == 414 else self.api


def _repo_com_recursos(tmp_path, recurso_a_proprio=False):
    extras = {
        "resources/a/resource.yaml": 'name: "A"\n',
        "resources/a/get_a.yaml": "path: /a\n",
        "resources/a/post_a.yaml": "path: /a\n",
        "resources/b/resource.yaml": 'name: "B"\n',
        "resources/b/get_b.yaml": "path: /b\n",
    }
    if recurso_a_proprio:
        extras["resources/a/resource.yaml"] = (
            'name: "A"\ninherit: false\ninterceptors_request:\n  - type: Payload size\n'
            "    content:\n      maxSize: \"1\"\n"
        )
    repo = _repo(tmp_path, extras=extras)
    (repo / "all.yaml").write_text(
        "destination:\n  url: https://backend\n\n"
        "interceptors_request:\n  - type: Log\n    content:\n      encryptContent: false\n",
        encoding="utf-8",
    )
    return repo


REGUA_SO_RATE_LIMIT = [
    {"id": 1, "type": "Rate limit", "executionPoint": "FIRST", "position": 0, "content": "{}"},
]


def test_divergencia_da_raiz_sai_uma_vez_com_os_herdeiros(tmp_path):
    """Recursos e rotas que só herdam não repetem o achado da raiz."""
    manager = _ManagerComRegua(REGUA_SO_RATE_LIMIT)
    view = _servico(manager, modo="pipeline").validate(
        _repo_com_recursos(tmp_path), confirmar=SIM
    )
    da_template = [a for a in view.achados if a.scope != "repositório"]

    assert {a.scope for a in da_template} == {"raiz da revision"}
    assert all(
        a.message.endswith("vale também para 2 recursos e 3 rotas que herdam este fluxo")
        for a in da_template
    )


def test_escopo_com_fluxo_proprio_tem_os_proprios_achados_e_herdeiros(tmp_path):
    manager = _ManagerComRegua(REGUA_SO_RATE_LIMIT)
    view = _servico(manager, modo="pipeline").validate(
        _repo_com_recursos(tmp_path, recurso_a_proprio=True), confirmar=SIM
    )
    por_escopo = {}
    for a in view.achados:
        if a.scope != "repositório":
            por_escopo.setdefault(a.scope, []).append(a.message)

    assert set(por_escopo) == {"raiz da revision", "resource A"}
    assert all(m.endswith("1 recurso e 1 rota que herdam este fluxo")
               for m in por_escopo["raiz da revision"])
    assert all(m.endswith("2 rotas que herdam este fluxo") for m in por_escopo["resource A"])



def test_esteira_sem_template_api_id_falha_antes_do_manager(tmp_path):
    """Configuração da esteira é conferida antes de qualquer chamada."""
    manager = ManagerFake()
    settings = SimpleNamespace(
        EXECUTION_MODE="pipeline", modo_pipeline=True,
        TEMPLATE_API_ID=None, TARGET_REVISION_NUMBER=2,
    )
    servico = ValidateService(
        manager_api=manager, importer=LocalFileImporterAdapter(), settings=settings
    )

    with pytest.raises(TemplateNaoConfiguradaError) as capturado:
        servico.validate(_repo(tmp_path), confirmar=SIM)

    assert capturado.value.exit_code == 1
    assert "TEMPLATE_API_ID não está definida" in capturado.value.message
    assert manager.chamadas == []
