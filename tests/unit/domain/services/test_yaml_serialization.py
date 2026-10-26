"""Reparos de serialização do YAML do repositório (fila, itens 23 e 24)."""

import pytest
import yaml

from apiops_orchestrator.domain.services.yaml_serialization import (
    scalar,
    looks_like_number,
    needs_quotes,
)


def _round_trip(value):
    """Serializa e relê, como o importador e o publisher fazem."""
    return yaml.safe_load(f"chave: {scalar(value)}")["chave"]


@pytest.mark.parametrize(
    "indicador",
    ["*****", "&ancora", "!tag", "|bloco", ">dobra", "%diretiva", "@dominio",
     "`cmd`", "[a,b]", "{a: b}", "? pergunta", "- item", "#comentario"],
)
def test_escalar_iniciado_por_indicador_sobrevive(indicador):
    """O caso real: `replaceChar: *****` sem aspas torna o arquivo IMPARSEÁVEL.

    Dois arquivos de `api-400-rev4` estão nesse estado — o `safe_load` tenta ler
    um alias e levanta `ScannerError`.
    """
    assert needs_quotes(indicador)
    assert _round_trip(indicador) == indicador


@pytest.mark.parametrize("text", ["1000", "30", "0.5", "-5", "+7", "1e3", ".5"])
def test_string_numerica_continua_string(text):
    """O wire devolve `quota` e `timeout` como STRING.

    Emitidos sem aspas, voltam como inteiro: o round-trip quebra e a comparação
    com a régua acusa achado falso num campo idêntico.
    """
    assert looks_like_number(text)
    loaded = _round_trip(text)
    assert loaded == text
    assert isinstance(loaded, str)


@pytest.mark.parametrize("word", ["true", "false", "null", "yes", "no", "on", "off"])
def test_palavra_reservada_continua_string(word):
    loaded = _round_trip(word)
    assert loaded == word
    assert isinstance(loaded, str)


def test_string_vazia_sobrevive():
    """V-03: string vazia significa herdar — não pode virar `None` na releitura."""
    loaded = _round_trip("")
    assert loaded == ""
    assert isinstance(loaded, str)


@pytest.mark.parametrize(
    "value,kind",
    [(1000, int), (2.5, float), (True, bool), (False, bool), (None, type(None))],
)
def test_tipos_nativos_preservam_o_tipo(value, kind):
    """Número nativo sai cru: aqui o tipo YAML É o tipo pretendido."""
    loaded = _round_trip(value)
    assert isinstance(loaded, kind)
    assert loaded == value if value is not None else loaded is None


def test_texto_comum_nao_recebe_aspas_desnecessarias():
    assert scalar("texto normal") == "texto normal"
    assert not needs_quotes("texto normal")


def test_url_com_dois_pontos_e_citada():
    url = "https://dev-backend.ecad.org.br/app-demo/tarefas"
    assert _round_trip(url) == url
