import pytest

from apiops_orchestrator.infrastructure.utils.text_normalizer import accent_fold


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Autenticação do Consumidor", "autenticacao do consumidor"),
        ("ORQUESTRAÇÃO", "orquestracao"),
        ("api-interface-públicas", "api-interface-publicas"),
        # Casefold além do .lower(): ß, İ, ligaduras
        ("Straße", "strasse"),
        ("İstanbul", "istanbul"),
        # ASCII puro passa inalterado (além de lowercase)
        ("Orchestrator Auth API", "orchestrator auth api"),
        # Espaçamento interno é preservado (matching por substring depende disso)
        ("Entregas  Express", "entregas  express"),
        ("", ""),
    ],
)
def test_accent_fold_normalizes_known_shapes(raw, expected):
    assert accent_fold(raw) == expected


def test_accent_fold_accepts_none_and_empty():
    assert accent_fold(None) == ""
    assert accent_fold("") == ""

def test_accent_fold_accepts_non_string_scalars():
    assert accent_fold(123) == "123"


def test_accent_fold_makes_query_symmetric_between_payload_and_input():
    payload_name = "Autenticação do Consumidor"
    typed_query = "AUTENTICACAO"

    assert accent_fold(typed_query) in accent_fold(payload_name)
