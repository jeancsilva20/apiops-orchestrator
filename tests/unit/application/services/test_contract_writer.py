"""Contract step: validates, reads, writes and verifies the revision swagger through a fake port."""

import copy
from types import SimpleNamespace

import pytest

from apiops_orchestrator.application.exceptions.validate_exceptions import (
    InvalidContractError,
)
from apiops_orchestrator.application.services.contract_writer import (
    SWAGGER_2_WARNING,
    ContractWriter,
    PreparedContract,
)
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)
from apiops_orchestrator.domain.services.openapi_contract import RepositoryContract

REVISION_ID = 9554
OK = {"200": {"description": "Consulta realizada"}}
REVISION = {"id": REVISION_ID, "workflowId": 139, "workflowStageId": 420, "interceptors": [], "resources": []}


def _swagger(**operation):
    get = {"summary": "Consulta", "parameters": [], "responses": OK, "x-resource-name": "T", "x-interceptors": {}}
    get.update(operation)
    return {
        "openapi": "3.0.0",
        "info": {"title": "T", "version": "1.0.0"},
        "servers": [{"url": "/t"}],
        "paths": {"/t": {"get": get}},
    }


def _contract(**fields):
    operation = {"summary": "Consulta", "parameters": [], "responses": OK}
    operation.update(fields)
    return RepositoryContract(operations={("GET", "/t"): operation})


class FakeManager:
    """Fake port: serves one swagger, records the calls and stores what is written."""

    def __init__(self, swagger, revision=None, put_error=None, get_error=None, written_override=None):
        self.swagger = swagger
        self.revision = revision or REVISION
        self.put_error = put_error
        self.get_error = get_error
        self.written_override = written_override
        self.calls = []
        self.sent = None

    def get_revision_swagger(self, revision_id):
        self.calls.append("get_revision_swagger")
        if self.get_error is not None:
            raise self.get_error
        if self.sent is not None:
            return copy.deepcopy(self.written_override or self.sent)
        return copy.deepcopy(self.swagger)

    def update_revision_swagger(self, revision_id, document):
        self.calls.append("update_revision_swagger")
        if self.put_error is not None:
            raise self.put_error
        self.sent = copy.deepcopy(document)
        return {"result": "success"}

    def get_revision(self, revision_id):
        self.calls.append("get_revision")
        return copy.deepcopy(self.revision)


def _prepared(contract=None, write=True):
    return PreparedContract(contract=contract or _contract(), write=write)


# --- validate ------------------------------------------------------------------


def _loaded(operation_data, components=None, ignored=()):
    operation = SimpleNamespace(method="GET", data=operation_data, file_path="resources/t/get_t.yaml")
    resource = SimpleNamespace(data={"name": "T"}, operations=[operation], file_path="resources/t/resource.yaml")
    return SimpleNamespace(
        basic_info={"spec": {"id": 1}}, components=components or {}, resources=[resource], ignored=list(ignored)
    )


def test_validate_returns_the_contract_and_the_warnings():
    writer = ContractWriter(FakeManager(_swagger()), command="validate")

    contract, warnings = writer.validate(
        _loaded({"path": "/t", "summary": "Consulta", "responses": {"200": {"description": "OK"}}})
    )

    assert ("GET", "/t") in contract.operations
    [warning] = warnings
    assert "responses.200" in warning


def test_validate_raises_on_an_invalid_contract_without_calling_the_manager():
    manager = FakeManager(_swagger())

    with pytest.raises(InvalidContractError) as raised:
        ContractWriter(manager, command="validate").validate(_loaded({"path": "/t"}))

    assert raised.value.exit_code == 1
    assert "não declara `responses`" in raised.value.message
    assert "parou antes de acessar o Manager" in raised.value.message
    assert manager.calls == []


# --- prepare -------------------------------------------------------------------


def test_prepare_lists_what_leaves_the_documentation():
    current = _swagger(responses={"200": {"description": "Ok"}, "404": {"description": "Sem tarefa"}})
    prepared = ContractWriter(FakeManager(current), command="validate").prepare(REVISION_ID, _contract())

    assert prepared.write is True
    [warning] = prepared.warnings
    assert "GET /t · resposta 404" in warning


def test_prepare_without_removals_has_no_warning():
    prepared = ContractWriter(FakeManager(_swagger()), command="validate").prepare(REVISION_ID, _contract())

    assert prepared.write is True
    assert prepared.warnings == []


def test_prepare_stops_the_contract_on_swagger_2():
    manager = FakeManager({"swagger": "2.0", "paths": {}})
    prepared = ContractWriter(manager, command="publish").prepare(REVISION_ID, _contract())

    assert prepared.write is False
    assert prepared.warnings == [SWAGGER_2_WARNING]


def test_prepare_stops_the_contract_when_the_swagger_cannot_be_read():
    manager = FakeManager(_swagger(), get_error=ManagerApiTransportUnavailableError("down"))
    prepared = ContractWriter(manager, command="publish").prepare(REVISION_ID, _contract())

    assert prepared.write is False
    [warning] = prepared.warnings
    assert "não será gravado" in warning and "Manager indisponível" in warning


# --- write ---------------------------------------------------------------------


def test_nothing_is_written_when_prepare_stopped_the_contract():
    manager = FakeManager(_swagger())

    assert ContractWriter(manager, command="validate").write(REVISION_ID, _prepared(write=False), REVISION) == []
    assert manager.calls == []


def test_unchanged_contract_is_not_written():
    manager = FakeManager(_swagger())

    warnings = ContractWriter(manager, command="validate").write(REVISION_ID, _prepared(), REVISION)

    assert warnings == []
    assert manager.calls == ["get_revision_swagger"]


def test_changed_contract_is_written_and_verified():
    manager = FakeManager(_swagger())
    steps = []

    warnings = ContractWriter(manager, command="validate").write(
        REVISION_ID, _prepared(_contract(operationId="consultar")), REVISION, steps.append
    )

    assert warnings == []
    assert manager.calls == [
        "get_revision_swagger",
        "update_revision_swagger",
        "get_revision_swagger",
        "get_revision",
    ]
    assert manager.sent["paths"]["/t"]["get"]["operationId"] == "consultar"
    assert manager.sent["servers"] == [{"url": "/t"}]
    assert steps == ["Montando o contrato", "Gravando o contrato no Manager", "Conferindo o contrato gravado"]


def test_rejection_with_reasons_becomes_a_warning():
    rejection = ManagerApiTransportRejectedError(400, "Invalid Request", messages=["Schema inválido"])
    manager = FakeManager(_swagger(), put_error=rejection)

    [warning] = ContractWriter(manager, command="publish").write(
        REVISION_ID, _prepared(_contract(operationId="consultar")), REVISION
    )

    assert "recusou a gravação do contrato" in warning and "Schema inválido" in warning
    assert "O fluxo foi gravado normalmente" in warning


def test_unavailable_platform_becomes_a_warning():
    manager = FakeManager(_swagger(), put_error=ManagerApiTransportUnavailableError("502"))

    [warning] = ContractWriter(manager, command="publish").write(
        REVISION_ID, _prepared(_contract(operationId="consultar")), REVISION
    )

    assert "não respondeu à gravação do contrato" in warning


def test_missing_route_stops_the_write():
    manager = FakeManager(_swagger())
    contract = RepositoryContract(operations={("GET", "/t"): {}, ("POST", "/t"): {"responses": OK}})

    [warning] = ContractWriter(manager, command="validate").write(REVISION_ID, _prepared(contract), REVISION)

    assert "POST /t" in warning
    assert "update_revision_swagger" not in manager.calls


def test_swagger_written_differently_becomes_a_warning():
    written = _swagger(operationId="outro")
    manager = FakeManager(_swagger(), written_override=written)

    [warning] = ContractWriter(manager, command="validate").write(
        REVISION_ID, _prepared(_contract(operationId="consultar")), REVISION
    )

    assert "não é o que foi enviado" in warning and "GET /t · operationId" in warning


def test_runtime_changed_by_the_swagger_write_becomes_a_warning():
    changed = dict(REVISION, workflowStageId=999)
    manager = FakeManager(_swagger(), revision=changed)

    [warning] = ContractWriter(manager, command="validate").write(
        REVISION_ID, _prepared(_contract(operationId="consultar")), REVISION
    )

    assert "`workflowStageId` era 420 e ficou 999" in warning
