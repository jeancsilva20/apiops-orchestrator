"""`display_output`: os dois ramos que nenhum teste tocava.

O modulo era exercitado so de lado, por `-o json` nos comandos, e os dois ramos
que ele proprio decide — realce quando ha terminal, escrita crua quando nao ha —
nunca foram afirmados. O ramo cru e justamente o que protege o contrato com a
esteira: `rich.Syntax` ajusta a saida a largura do console e cortaria um valor
longo no meio, produzindo JSON invalido (ver o comentario em
`output_display.py:33-40`). Um teste que nao prova isso deixa a regressao passar.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
import yaml

from apiops_orchestrator.adapters.inbound.cli import output_display
from apiops_orchestrator.adapters.inbound.cli.output_format import OutputFormat

DOCUMENTO = {
    "schema": "sen.calls/v1",
    "total": 1,
    # Valor longo de proposito: e o que o renderizador quebraria na largura.
    "url": "https://gateway.example.com/" + "a" * 220,
    "acentos": "revisão · governança",
}


def _sem_terminal(monkeypatch):
    monkeypatch.setattr(
        type(output_display.console), "is_terminal", property(lambda self: False)
    )


def _com_terminal(monkeypatch):
    monkeypatch.setattr(
        type(output_display.console), "is_terminal", property(lambda self: True)
    )


@pytest.mark.parametrize("formato", [OutputFormat.JSON, OutputFormat.YAML])
def test_sem_terminal_a_saida_de_maquina_sai_crua_e_inteira(
    formato, monkeypatch, capsys
):
    """Sem terminal, nada de realce: o valor longo chega inteiro, sem quebra."""
    _sem_terminal(monkeypatch)

    output_display.display_output(DOCUMENTO, output_format=formato)

    saida = capsys.readouterr().out
    carregar = json.loads if formato is OutputFormat.JSON else yaml.safe_load
    assert carregar(saida) == DOCUMENTO
    assert DOCUMENTO["url"] in saida  # nenhuma quebra no meio do valor
    assert saida.endswith("\n")


def test_sem_terminal_acrescenta_a_quebra_de_linha_final(monkeypatch, capsys):
    """YAML ja termina em \\n; JSON nao — e quem le por linha precisa dela."""
    _sem_terminal(monkeypatch)

    output_display.display_output({"a": 1}, output_format=OutputFormat.JSON)

    assert capsys.readouterr().out.endswith("}\n")


def test_com_terminal_usa_realce_de_sintaxe(monkeypatch):
    """So para leitura humana, e com `soft_wrap` para nao cortar o valor."""
    _com_terminal(monkeypatch)

    with patch.object(output_display.console, "print") as imprimir:
        output_display.display_output(DOCUMENTO, output_format=OutputFormat.JSON)

    imprimir.assert_called_once()
    (renderizavel,), kwargs = imprimir.call_args
    assert "json" in renderizavel.lexer.name.lower()
    # O valor longo entra inteiro no renderizavel; `soft_wrap` impede o corte.
    assert DOCUMENTO["url"] in renderizavel.code
    assert kwargs["soft_wrap"] is True


def test_texto_delega_ao_callback():
    chamado = MagicMock()

    output_display.display_output(
        DOCUMENTO, output_format=OutputFormat.TEXT, text_callback=chamado
    )

    chamado.assert_called_once_with()


def test_texto_sem_callback_imprime_o_dado(capsys):
    """Fallback: comando sem renderizador proprio ainda mostra alguma coisa."""
    output_display.display_output({"chave": "valor"}, output_format=OutputFormat.TEXT)

    assert "valor" in capsys.readouterr().out


def test_acentos_sobrevivem_a_serializacao(monkeypatch, capsys):
    """`ensure_ascii=False`/`allow_unicode=True`: nada de `\\u00e7` na saida."""
    _sem_terminal(monkeypatch)

    output_display.display_output(DOCUMENTO, output_format=OutputFormat.JSON)

    saida = capsys.readouterr().out
    assert "governança" in saida
    assert "\\u00e7" not in saida
