from apiops_orchestrator.domain.models.completeness_model import (
    COMPLETENESS_SCHEMA_V1,
    SenCompleteness,
)


def probe_payload() -> dict:
    """Espelho do wire real (probe 25/09, api 85.0) + identidade completa."""
    return {
        "generatedAt": "2026-09-25T12:00:00Z",
        "api": {
            "managerId": 375,
            "name": "Manager Training 1.0",
            "version": "1.0",
            "context": {"type": "ORGANIZATION", "groupName": None, "owner": "trainer.sensedia"},
        },
        "revision": {"managerId": 5513},
        "maturity": {"score": 85.0},
        "suggestions": [
            'Response code 200 of operation POST /oauth2/token/validation has a '
            'description "OK" that is too short. Use more than 4 characters to '
            "describe the outcome.",
            'Response code 200 of operation POST /oauth2/token has a description '
            '"OK" that is too short. Use more than 4 characters to describe the '
            "outcome.",
            'Response code 200 of operation GET /users/{username}/groups has a '
            'description "OK" that is too short. Use more than 4 characters to '
            "describe the outcome.",
 'Operation GET /users/{username}/groups description "" is too short.',
        ],
    }


# -------------------------------------------------------------------------
# Contrato de saida — arvore (identidade + completeness, so fields provados)
# -------------------------------------------------------------------------


def test_contract_indexes_wire_plain_suggestions_one_based():
    """Wire manda list[str]; model enumera 1-based preservando ordem de chegada."""
    envelope = SenCompleteness.model_validate(probe_payload())

    assert envelope.maturity.score == 85.0
    assert [s.index for s in envelope.suggestions] == [1, 2, 3, 4]
    assert envelope.suggestions[0].text.startswith(
        "Response code 200 of operation POST /oauth2/token/validation"
    )
    assert envelope.api.managerId == 375
    assert envelope.revision.managerId == 5513


def test_contract_accepts_pre_indexed_suggestions_too():
    """Servico tambem pode entrar com {index, text} pronto (mesmo resultado)."""
    payload = probe_payload()
    payload["suggestions"] = [{"index": 1, "text": "unica dica"}]

    envelope = SenCompleteness.model_validate(payload)
    assert envelope.suggestions[0].index == 1
    assert envelope.suggestions[0].text == "unica dica"


def test_contract_dump_has_only_proven_keys_and_no_ghosts():
    """Dump = contrato exato; campos aposentados sao PROIBIDOS (sem nulls)."""
    dumped = SenCompleteness.model_validate(probe_payload()).model_dump(by_alias=True)

    assert set(dumped.keys()) == {
        "schema",
        "generatedAt",
        "api",
        "revision",
        "maturity",
        "gate",
        "suggestions",
    }
    banned = (
        "violations",
        "rulesLost",
        "issues",
        "severity",
        "classification",
        "ruleId",
        "impactPoints",
        "range",
        "deployedEnvironments",
        "agCatalogId",
        "agId",
        "last",
        "totalLossPoints",
        "satellite",
        "api-finder",
        "hardcoded",
    )
    flat = str(dumped)
    for key in banned:
        assert key not in flat


def test_contract_alias_round_trip_keeps_tree():
    envelope = SenCompleteness.model_validate(probe_payload())

    dumped = envelope.model_dump(by_alias=True)
    assert dumped["schema"] == COMPLETENESS_SCHEMA_V1
    assert "schema_" not in dumped

    restored = SenCompleteness.model_validate(dumped)
    assert restored == envelope


def test_degraded_identity_expresses_absence_without_narrator():
    """Lookup de identidade falhou: so o managerId garante; ausencia fala por si."""
    payload = probe_payload()
    payload["api"] = {"managerId": 375}
    payload.pop("suggestions")

    envelope = SenCompleteness.model_validate(payload)

    assert envelope.api.name is None
    assert envelope.api.version is None
    assert envelope.api.context is None
    assert envelope.suggestions == []
    assert envelope.gate.percent == 70.0


def test_empty_suggestions_render_zeroed_list():
    payload = probe_payload()
    payload["suggestions"] = []

    envelope = SenCompleteness.model_validate(payload)
    assert envelope.suggestions == []


def test_score_clamped_between_zero_and_hundred_one_decimal():
    for raw, expected in ((105.0, 100.0), (-3.0, 0.0), (70.56, 70.6), (85.0, 85.0)):
        payload = probe_payload()
        payload["maturity"]["score"] = raw

        envelope = SenCompleteness.model_validate(payload)
        assert envelope.maturity.score == expected
