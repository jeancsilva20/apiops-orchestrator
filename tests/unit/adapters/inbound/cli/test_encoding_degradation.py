"""`_supports_text` e `_adapt_encoding`: a degradacao visual da CLI.

Estes dois sao a politica de "ou tudo, ou nada" do visual: quando o stdout nao
da conta dos glifos, logo, molduras e barras caem juntos para ASCII em vez de
meio-virar mojibake. Nunca tiveram teste proprio, embora sejam a razao de
`harden_stdio()` NAO mexer no encoding de um terminal de verdade — se mexesse,
`_supports_text` passaria a dizer True num console cp1252 e a arte sairia
quebrada.
"""

from __future__ import annotations

import sys

import pytest

from apiops_orchestrator.adapters.inbound.cli import cli_adapter

ARTE = "┌─┐│└┘█"


class _StdoutFalso:
    def __init__(self, encoding):
        self.encoding = encoding

    def isatty(self):
        return True


@pytest.fixture
def stdout_com(monkeypatch):
    def _trocar(encoding):
        monkeypatch.setattr(sys, "stdout", _StdoutFalso(encoding))

    return _trocar


@pytest.mark.parametrize("encoding", ["utf-8", "UTF-8", "utf8", "latin-1", "latin1"])
def test_encoding_capaz_e_aceito_sem_sondagem(encoding, stdout_com):
    """utf*/latin* passam por prefixo: sondar cada glifo seria custo a toa."""
    stdout_com(encoding)

    assert cli_adapter._supports_text(ARTE) is True


@pytest.mark.parametrize("encoding", ["cp1252", "ascii"])
def test_encoding_incapaz_e_recusado(encoding, stdout_com):
    stdout_com(encoding)

    assert cli_adapter._supports_text(ARTE) is False


def test_encoding_desconhecido_e_tratado_como_incapaz(stdout_com):
    """Conservador de proposito: sem saber o encoding, degrada."""
    stdout_com("")

    assert cli_adapter._supports_text(ARTE) is False


def test_texto_ascii_passa_em_qualquer_encoding_conhecido(stdout_com):
    stdout_com("cp1252")

    assert cli_adapter._supports_text("so ascii aqui") is True


def test_adapt_encoding_preserva_a_arte_quando_cabe(stdout_com):
    stdout_com("utf-8")

    assert cli_adapter._adapt_encoding(ARTE) == ARTE


def test_adapt_encoding_degrada_box_drawing_e_bloco(stdout_com):
    """Num console cp1252 a moldura vira ASCII e o bloco vira `#`."""
    stdout_com("cp1252")

    adaptado = cli_adapter._adapt_encoding(ARTE)

    assert adaptado.isascii(), adaptado
    assert "#" in adaptado
    for glifo in ARTE:
        assert glifo not in adaptado


def test_toda_substituicao_declarada_e_ascii():
    """Substituto fora do ASCII reintroduziria o problema que isto resolve."""
    for original, substituto in cli_adapter._BOX_ASCII_REPLACEMENTS.items():
        assert not original.isascii(), original
        assert substituto.isascii(), (original, substituto)


def test_logo_de_boas_vindas_degrada_inteiro(stdout_com):
    """O logo e o maior consumidor de `\\u2588` (cli_adapter.py:128-132)."""
    stdout_com("cp1252")

    moldura = cli_adapter._framed_logo()

    assert moldura.isascii(), moldura
