"""Reparos de serialização do YAML do repositório (fila, itens 23 e 24)."""

import pytest
import yaml

from apiops_orchestrator.domain.services.yaml_serialization import (
    escalar,
    parece_numero,
    precisa_aspas,
)


def _round_trip(valor):
    """Serializa e relê, como o importador e o publisher fazem."""
    return yaml.safe_load(f"chave: {escalar(valor)}")["chave"]


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
    assert precisa_aspas(indicador)
    assert _round_trip(indicador) == indicador


@pytest.mark.parametrize("texto", ["1000", "30", "0.5", "-5", "+7", "1e3", ".5"])
def test_string_numerica_continua_string(texto):
    """O wire devolve `quota` e `timeout` como STRING.

    Emitidos sem aspas, voltam como inteiro: o round-trip quebra e a comparação
    com a régua acusa achado falso num campo idêntico.
    """
    assert parece_numero(texto)
    lido = _round_trip(texto)
    assert lido == texto
    assert isinstance(lido, str)


@pytest.mark.parametrize("palavra", ["true", "false", "null", "yes", "no", "on", "off"])
def test_palavra_reservada_continua_string(palavra):
    lido = _round_trip(palavra)
    assert lido == palavra
    assert isinstance(lido, str)


def test_string_vazia_sobrevive():
    """V-03: string vazia significa herdar — não pode virar `None` na releitura."""
    lido = _round_trip("")
    assert lido == ""
    assert isinstance(lido, str)


@pytest.mark.parametrize(
    "valor,tipo",
    [(1000, int), (2.5, float), (True, bool), (False, bool), (None, type(None))],
)
def test_tipos_nativos_preservam_o_tipo(valor, tipo):
    """Número nativo sai cru: aqui o tipo YAML É o tipo pretendido."""
    lido = _round_trip(valor)
    assert isinstance(lido, tipo)
    assert lido == valor if valor is not None else lido is None


def test_texto_comum_nao_recebe_aspas_desnecessarias():
    assert escalar("texto normal") == "texto normal"
    assert not precisa_aspas("texto normal")


def test_url_com_dois_pontos_e_citada():
    url = "https://dev-backend.ecad.org.br/app-demo/tarefas"
    assert _round_trip(url) == url
