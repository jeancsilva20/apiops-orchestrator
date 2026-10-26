"""Resolução e leitura da régua — E2 (V-11 binding · D-12 · P-2 · D-4 · W-2)."""

import json
import pathlib
from types import SimpleNamespace

import pytest

from apiops_orchestrator.application.exceptions.validate_exceptions import (
    CustomNotFoundError,
    RulerUnreachableError,
    MissingTemplateError,
    TemplateNotConfiguredError,
)
from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    INTERNAL_ERROR_MESSAGE,
    UNAVAILABLE_MESSAGE,
)
from apiops_orchestrator.application.services.ruler_service import (
    RulerService,
    compute_flow_hash,
)
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)

FIXTURES = pathlib.Path(__file__).parents[3] / "fixtures" / "manager"


class ManagerFake:
    def __init__(self, api=None, erro=None, customs=None):
        self._api = api or {}
        self._erro = erro
        self._customs = customs if customs is not None else {}
        self.chamadas = []

    def get_api_by_id(self, api_id=None):
        self.chamadas.append(("get_api_by_id", api_id))
        if self._erro:
            raise self._erro
        return self._api

    def get_custom_interceptor_by_id(self, custom_interceptor_id):
        self.chamadas.append(("get_custom", custom_interceptor_id))
        return self._customs.get(custom_interceptor_id)


def _settings(mode="local", template_id=None):
    return SimpleNamespace(
        EXECUTION_MODE=mode,
        pipeline_mode=(mode == "pipeline"),
        TEMPLATE_API_ID=template_id,
    )


def _basic_info(template=""):
    return {"spec": {"id": 417, "template": template}}


def _api_regua(interceptors, revision_number=1, api_id=414):
    return {
        "id": api_id,
        "lastRevision": {"revisionNumber": revision_number, "interceptors": interceptors},
    }


ITENS = [
    {"type": "Custom", "customInterceptorId": 125, "executionPoint": "FIRST"},
    {"type": "Log", "executionPoint": "FIRST", "content": '{"acceptedTerms": true}'},
    {"type": "Custom", "customInterceptorId": 178, "executionPoint": "THIRD"},
]


# --- resolução do id (V-11 binding) ----------------------------------------


def test_local_le_o_id_do_manifesto():
    servico = RulerService(ManagerFake(), _settings("local"))
    assert servico.resolver_id(_basic_info(template=414)) == 414


def test_local_com_template_vazio_e_erro():
    """D-12 revogou o 'vazio permitido' da V-11 §1: sem régua não há validação."""
    servico = RulerService(ManagerFake(), _settings("local"))
    with pytest.raises(MissingTemplateError):
        servico.resolver_id(_basic_info(template=""))


def test_pipeline_ignora_o_manifesto_e_usa_o_cofre():
    """A régua não pode ser trocada por um commit."""
    servico = RulerService(ManagerFake(), _settings("pipeline", template_id=414))
    assert servico.resolver_id(_basic_info(template=999)) == 414


def test_pipeline_avisa_a_divergencia_de_binding():
    servico = RulerService(ManagerFake(), _settings("pipeline", template_id=414))
    warning = servico.binding_divergence(_basic_info(template=999))
    assert warning and "999" in warning and "414" in warning
    assert "definida pela plataforma" in warning
    assert "variável" not in warning and "EXECUTION_MODE" not in warning


def test_pipeline_sem_id_configurado_aborta():
    """Validar contra nada numa esteira é pior do que parar (V-11 §4)."""
    servico = RulerService(ManagerFake(), _settings("pipeline", template_id=None))
    with pytest.raises(TemplateNotConfiguredError) as capturado:
        servico.resolver_id(_basic_info(template=414))
    # É configuração, não rede: a mensagem não pode mandar verificar a conexão.
    assert "TEMPLATE_API_ID não está definida" in capturado.value.message
    assert "rede" not in capturado.value.message


# --- leitura e aborto (P-2) -------------------------------------------------


def test_le_a_regua_em_um_unico_get():
    """V-11 §6: `lastRevision` já traz o fluxo completo."""
    manager = ManagerFake(api=_api_regua(ITENS, revision_number=1))
    ruler = RulerService(manager, _settings("local")).load(_basic_info(414))

    assert [c[0] for c in manager.chamadas] == ["get_api_by_id"]
    assert ruler.template_id == 414
    assert ruler.revision_number == 1


def test_apenas_o_governado_entra_na_regua():
    """V-22: fora de FIRST/SECOND não é comparado."""
    ruler = RulerService(
        ManagerFake(api=_api_regua(ITENS)), _settings("local")
    ).load(_basic_info(414))
    assert ruler.total == 2
    assert all(i["executionPoint"] in ("FIRST", "SECOND") for i in ruler.interceptors)


@pytest.mark.parametrize(
    "erro,status",
    [
        (ManagerApiTransportRejectedError(404, "Not Found"), 404),
        (ManagerApiTransportRejectedError(403, "Forbidden"), 403),
        (ManagerApiTransportUnavailableError("timeout"), None),
    ],
)
def test_regua_inalcancavel_aborta(erro, status):
    servico = RulerService(ManagerFake(erro=erro), _settings("local"))
    with pytest.raises(RulerUnreachableError) as capturado:
        servico.load(_basic_info(414))
    assert capturado.value.exit_code == 1


def test_mensagem_do_403_nomeia_as_duas_causas():
    """O status não distingue sessão expirada de id de outro ambiente.

    A mensagem nomeia as duas, com a sessão expirada primeiro: é a causa mais
    comum e a única que o dev resolve sozinho.
    """
    servico = RulerService(
        ManagerFake(erro=ManagerApiTransportRejectedError(403, "Forbidden")),
        _settings("local"),
    )
    with pytest.raises(RulerUnreachableError) as capturado:
        servico.load(_basic_info(414))
    message = capturado.value.message
    assert "sen login" in message and "outro ambiente" in message
    assert message.index("sen login") < message.index("outro ambiente")


@pytest.mark.parametrize("status", [400, 413, 429])
def test_recusa_fora_de_403_404_vira_erro_interno_sem_detalhe_http(status):
    servico = RulerService(
        ManagerFake(erro=ManagerApiTransportRejectedError(status, "BACKEND_RESPONSE_TOO_LARGE")),
        _settings("local"),
    )
    with pytest.raises(RulerUnreachableError) as capturado:
        servico.load(_basic_info(414))
    message = capturado.value.message
    assert INTERNAL_ERROR_MESSAGE in message
    assert str(status) not in message and "BACKEND_RESPONSE_TOO_LARGE" not in message
    assert "sen login" not in message
    assert capturado.value.exit_code == 1


def test_manager_indisponivel_usa_a_mensagem_padrao_da_familia():
    servico = RulerService(
        ManagerFake(erro=ManagerApiTransportUnavailableError("timeout")), _settings("local")
    )
    with pytest.raises(RulerUnreachableError) as capturado:
        servico.load(_basic_info(414))
    assert UNAVAILABLE_MESSAGE in capturado.value.message


def test_regua_sem_item_governado_avisa_em_vez_de_falhar():
    ruler = RulerService(
        ManagerFake(api=_api_regua([])), _settings("local")
    ).load(_basic_info(414))
    assert ruler.total == 0
    assert any("não tem nenhum interceptor configurado" in a for a in ruler.warnings)


# --- snapshot (D-4 / P-3) ---------------------------------------------------


def test_hash_e_estavel_para_o_mesmo_fluxo():
    assert compute_flow_hash(ITENS) == compute_flow_hash(list(ITENS))


def test_hash_muda_quando_o_content_muda():
    outro = [dict(ITENS[1], content='{"acceptedTerms": false}')]
    assert compute_flow_hash([ITENS[1]]) != compute_flow_hash(outro)


def test_hash_ignora_id_e_position():
    """Eles mudam entre revisões sem que a régua tenha mudado."""
    a = [{"type": "Log", "executionPoint": "FIRST", "id": 1, "position": 1}]
    b = [{"type": "Log", "executionPoint": "FIRST", "id": 99, "position": 7}]
    assert compute_flow_hash(a) == compute_flow_hash(b)


def test_hash_sensivel_a_ordem():
    """A comparação é por sequência; o snapshot tem de acompanhar."""
    a = [ITENS[0], ITENS[1]]
    assert compute_flow_hash(a) != compute_flow_hash(list(reversed(a)))


@pytest.mark.skipif(not FIXTURES.is_dir(), reason="fixtures do Manager ausentes")
def test_snapshot_da_regua_real():
    data = json.loads((FIXTURES / "regua-414.json").read_text(encoding="utf-8"))
    ruler = RulerService(
        ManagerFake(
            api={
                "id": data["templateId"],
                "lastRevision": {
                    "revisionNumber": data["revisionNumber"],
                    "interceptors": data["interceptors"],
                },
            }
        ),
        _settings("local"),
    ).load(_basic_info(data["templateId"]))

    assert ruler.total == 8
    assert ruler.revision_number == data["revisionNumber"]
    assert len(ruler.flow_hash) == 12


# --- existência dos Custom (W-2) -------------------------------------------


def test_custom_existente_passa():
    servico = RulerService(
        ManagerFake(customs={32: {"id": 32, "name": "Release Notes"}}), _settings("local")
    )
    servico.check_customs([(32, "all.yaml")])


def test_custom_inexistente_aborta_nomeando_id_e_escopo():
    servico = RulerService(ManagerFake(customs={}), _settings("local"))
    with pytest.raises(CustomNotFoundError) as capturado:
        servico.check_customs([(178, "resources/health-check/get_health-check.yaml")])
    assert "178" in capturado.value.message
    assert "get_health-check.yaml" in capturado.value.message


def test_cada_custom_e_consultado_uma_vez_so():
    manager = ManagerFake(customs={32: {"id": 32}})
    servico = RulerService(manager, _settings("local"))
    servico.check_customs([(32, "a"), (32, "b"), (32, "c")])
    assert [c for c in manager.chamadas if c[0] == "get_custom"] == [("get_custom", 32)]


def test_referencia_nula_e_ignorada():
    servico = RulerService(ManagerFake(customs={}), _settings("local"))
    servico.check_customs([(None, "all.yaml")])
