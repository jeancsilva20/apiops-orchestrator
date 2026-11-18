"""Resolução da revisão pelo número, compartilhada por validate, publish, deploy e sync."""

from apiops_orchestrator.domain.services.revisions import (
    revision_by_number,
    revision_numbers,
    revisions,
)

API = {
    "id": 425,
    "revisions": [
        {"id": 9161, "revisionNumber": 1},
        {"id": 9175, "revisionNumber": 2, "workflowId": 500},
        "lixo",
        {"revisionNumber": 3},
    ],
}


def test_revisoes_so_os_dicionarios():
    assert [r.get("revisionNumber") for r in revisions(API)] == [1, 2, 3]
    assert revisions({}) == [] and revisions({"revisions": None}) == []


def test_pelo_numero_devolve_o_sumario_inteiro():
    assert revision_by_number(API, 2) == {"id": 9175, "revisionNumber": 2, "workflowId": 500}


def test_sem_id_ou_inexistente_e_none():
    assert revision_by_number(API, 3) is None
    assert revision_by_number(API, 4) is None


def test_numeros_para_as_mensagens():
    assert revision_numbers(API) == [1, 2, 3]
