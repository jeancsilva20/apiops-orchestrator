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
from apiops_orchestrator.domain.models.validate_view import (
    DOCUMENTATION_NOT_UPDATED,
    DOCUMENTATION_UNCHANGED,
    DOCUMENTATION_UPDATED,
)
from apiops_orchestrator.domain.ports.manager_api_port import (
    ManagerApiTransportRejectedError,
    ManagerApiTransportUnavailableError,
)
from apiops_orchestrator.domain.services.openapi_contract import RepositoryContract

REVISION_ID = 9554
OK = {"200": {"description": "Consulta realizada"}}
REVISION = {
    "id": REVISION_ID,
    "workflowId": 139,
    "workflowStageId": 420,
    "interceptors": [],
    "resources": [{"name": "T", "interceptors": [], "operations": [{"method": "GET", "path": "/t", "interceptors": []}]}],
}
LOG = {
    "x-interceptor-position": 1,
    "x-interceptor-type": "LOG",
    "x-interceptor-content": "{}",
    "x-interceptor-execution-point": "FIRST",
    "x-interceptor-status": "REFERENCE",
}


def _revision_with(**operation):
    revision = copy.deepcopy(REVISION)
    revision["resources"][0]["operations"][0].update(operation)
    return revision


def _swagger(**operation):
    get = {"summary": "Consulta", "parameters": [], "responses": OK, "x-resource-name": "T", "x-interceptors": {}}
    get.update(operation)
    return {
        "openapi": "3.0.0",
        "info": {"title": "T", "version": "1.0.0"},
        "servers": [{"url": "/t"}],
        "x-resources": {"T": {"x-interceptors": {}}},
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
    prepared = PreparedContract(contract=_contract(), write=False, warnings=[SWAGGER_2_WARNING])

    result = ContractWriter(manager, command="validate").write(REVISION_ID, prepared, REVISION)

    assert (result.status, result.reason) == (DOCUMENTATION_NOT_UPDATED, SWAGGER_2_WARNING)
    assert manager.calls == []


def test_unchanged_contract_is_not_written():
    manager = FakeManager(_swagger())

    result = ContractWriter(manager, command="validate").write(REVISION_ID, _prepared(), REVISION)

    assert (result.status, result.reason) == (DOCUMENTATION_UNCHANGED, None)
    assert manager.calls == ["get_revision_swagger"]


def test_documentation_changed_by_the_revision_write_is_updated_without_a_swagger_write():
    before = _swagger(summary="Antigo", description="Antigo")
    manager = FakeManager(_swagger(description="Consulta"))
    prepared = PreparedContract(contract=_contract(), write=True, before=before)

    result = ContractWriter(manager, command="validate").write(
        REVISION_ID, prepared, _revision_with(description="Consulta")
    )

    assert (result.status, result.reason) == (DOCUMENTATION_UPDATED, None)
    assert manager.calls == ["get_revision_swagger"]


def test_recreated_interceptors_alone_do_not_count_as_documentation():
    before = _swagger(**{"x-interceptors": {"1": LOG}})
    manager = FakeManager(_swagger(**{"x-interceptors": {"7": LOG}}))
    prepared = PreparedContract(contract=_contract(), write=True, before=before)
    flow = _revision_with(
        interceptors=[{"id": 5, "position": 1, "type": "Log", "content": "{}", "executionPoint": "FIRST",
                       "status": "REFERENCE"}]
    )

    result = ContractWriter(manager, command="validate").write(REVISION_ID, prepared, flow)

    assert result.status == DOCUMENTATION_UNCHANGED
    assert manager.calls == ["get_revision_swagger"]


def test_prepare_keeps_the_swagger_read_before_the_writes():
    current = _swagger()
    prepared = ContractWriter(FakeManager(current), command="validate").prepare(REVISION_ID, _contract())

    assert prepared.before == current


def test_changed_contract_is_written_and_verified():
    manager = FakeManager(_swagger())
    steps = []

    result = ContractWriter(manager, command="validate").write(
        REVISION_ID, _prepared(_contract(operationId="consultar")), REVISION, steps.append
    )

    assert (result.status, result.reason) == (DOCUMENTATION_UPDATED, None)
    assert manager.calls == [
        "get_revision_swagger",
        "update_revision_swagger",
        "get_revision_swagger",
        "get_revision",
    ]
    assert manager.sent["paths"]["/t"]["get"]["operationId"] == "consultar"
    assert manager.sent["servers"] == [{"url": "/t"}]
    assert steps == ["Montando o contrato", "Gravando o contrato no Manager", "Conferindo o contrato gravado"]


def test_rejection_with_reasons_is_why_the_documentation_was_not_updated():
    rejection = ManagerApiTransportRejectedError(400, "Invalid Request", messages=["Schema inválido"])
    manager = FakeManager(_swagger(), put_error=rejection)

    result = ContractWriter(manager, command="publish").write(
        REVISION_ID, _prepared(_contract(operationId="consultar")), REVISION
    )

    assert result.status == DOCUMENTATION_NOT_UPDATED
    assert "recusou a gravação do contrato" in result.reason and "Schema inválido" in result.reason
    assert "O fluxo foi gravado normalmente" in result.reason


def test_unavailable_platform_is_why_the_documentation_was_not_updated():
    manager = FakeManager(_swagger(), put_error=ManagerApiTransportUnavailableError("502"))

    result = ContractWriter(manager, command="publish").write(
        REVISION_ID, _prepared(_contract(operationId="consultar")), REVISION
    )

    assert result.status == DOCUMENTATION_NOT_UPDATED
    assert "não respondeu à gravação do contrato" in result.reason


def test_missing_route_stops_the_write():
    manager = FakeManager(_swagger())
    contract = RepositoryContract(operations={("GET", "/t"): {}, ("POST", "/t"): {"responses": OK}})

    result = ContractWriter(manager, command="validate").write(REVISION_ID, _prepared(contract), REVISION)

    assert result.status == DOCUMENTATION_NOT_UPDATED
    assert "POST /t" in result.reason
    assert "update_revision_swagger" not in manager.calls


def test_swagger_written_differently_is_updated_with_the_divergence():
    written = _swagger(operationId="outro")
    manager = FakeManager(_swagger(), written_override=written)

    result = ContractWriter(manager, command="validate").write(
        REVISION_ID, _prepared(_contract(operationId="consultar")), REVISION
    )

    assert result.status == DOCUMENTATION_UPDATED
    assert "não é o que foi enviado" in result.reason and "GET /t · operationId" in result.reason


def test_runtime_changed_by_the_swagger_write_is_updated_with_the_divergence():
    changed = dict(REVISION, workflowStageId=999)
    manager = FakeManager(_swagger(), revision=changed)

    result = ContractWriter(manager, command="validate").write(
        REVISION_ID, _prepared(_contract(operationId="consultar")), REVISION
    )

    assert result.status == DOCUMENTATION_UPDATED
    assert "`workflowStageId` era 420 e ficou 999" in result.reason


def test_written_contract_that_cannot_be_read_back_is_updated_but_not_verified():
    class RereadFails(FakeManager):
        def get_revision(self, revision_id):
            raise ManagerApiTransportUnavailableError("502")

    manager = RereadFails(_swagger())

    result = ContractWriter(manager, command="validate").write(
        REVISION_ID, _prepared(_contract(operationId="consultar")), REVISION
    )

    assert result.status == DOCUMENTATION_UPDATED
    assert "não consegui relê-lo para conferir" in result.reason


# --- swagger aligned to the flow ----------------------------------------------------


def test_swagger_in_sync_with_the_flow_is_not_aligned():
    manager = FakeManager(_swagger())

    result = ContractWriter(manager, command="validate").write(
        REVISION_ID, _prepared(_contract(operationId="consultar")), REVISION
    )

    assert (result.status, result.aligned) == (DOCUMENTATION_UPDATED, [])
    assert "aligned" not in result.to_document()


def test_route_the_manager_left_out_of_the_swagger_is_created():
    swagger = _swagger()
    del swagger["paths"]["/t"]
    manager = FakeManager(swagger)
    flow = _revision_with(description="Consulta T")

    result = ContractWriter(manager, command="publish").write(REVISION_ID, _prepared(), flow)

    assert (result.status, result.reason) == (DOCUMENTATION_UPDATED, None)
    assert result.to_document()["aligned"] == ["GET /t: criada"]
    created = manager.sent["paths"]["/t"]["get"]
    assert created["x-resource-name"] == "T"
    assert (created["description"], created["summary"], created["responses"]) == ("Consulta T", "Consulta", OK)


def test_stale_interceptors_are_replaced_by_the_flow_ones():
    manager = FakeManager(_swagger(**{"x-interceptors": {"3": LOG}}))

    result = ContractWriter(manager, command="validate").write(REVISION_ID, _prepared(), REVISION)

    assert result.aligned == ["GET /t: interceptors"]
    assert manager.sent["paths"]["/t"]["get"]["x-interceptors"] == {}


def test_route_the_flow_no_longer_has_leaves_the_swagger():
    swagger = _swagger()
    swagger["paths"]["/t"]["post"] = {"responses": OK, "x-resource-name": "T", "x-interceptors": {}}
    manager = FakeManager(swagger)

    result = ContractWriter(manager, command="validate").write(REVISION_ID, _prepared(), REVISION)

    assert result.aligned == ["POST /t: tirada"]
    assert "post" not in manager.sent["paths"]["/t"]


def test_flow_the_swagger_cannot_carry_stops_the_alignment():
    swagger = _swagger()
    del swagger["paths"]["/t"]
    manager = FakeManager(swagger)
    flow = _revision_with(certificateId=12)

    result = ContractWriter(manager, command="validate").write(REVISION_ID, _prepared(), flow)

    assert result.status == DOCUMENTATION_NOT_UPDATED
    assert "GET /t: certificateId" in result.reason
    assert "update_revision_swagger" not in manager.calls


def test_rejected_alignment_is_not_reported_as_aligned():
    swagger = _swagger()
    del swagger["paths"]["/t"]
    rejection = ManagerApiTransportRejectedError(400, "Invalid Request", messages=["Invalid interceptors"])
    manager = FakeManager(swagger, put_error=rejection)

    result = ContractWriter(manager, command="validate").write(REVISION_ID, _prepared(), REVISION)

    assert (result.status, result.aligned) == (DOCUMENTATION_NOT_UPDATED, [])
