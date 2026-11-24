"""Invocacao da CLI nos testes escritos a mao.

Existe pelo mesmo motivo do `invoke_sen` do conftest — tirar o `runner` e o
`ctx.obj` duplicados de cada arquivo — mas na forma de FUNCAO, nao de fixture,
para que os testes ja escritos continuem chamando `_invoke(args, servico)` sem
reescrever o corpo de cada um.
"""

from __future__ import annotations

from typing import Any, Sequence

from typer.testing import CliRunner

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from sen_support.cli_fabricas import contexto

runner = CliRunner()

# Largura fixa: o Rich quebra a linha pela largura do console, e sem isto a
# assercao tropeca na quebra em vez de no conteudo.
LARGO = {"COLUMNS": "200"}


def invocar(args: Sequence[str], **fabricas: Any):
    """`sen <args>` com o ctx.obj montado pelos apelidos de `FABRICAS`."""
    return runner.invoke(app, ["sen", *args], obj=contexto(**fabricas), env=LARGO)


def invocar_navegacao(args: Sequence[str], servico: Any):
    """O atalho mais usado: so o servico de navegacao no contexto."""
    return invocar(args, navegacao=servico)


def invocar_cru(args: Sequence[str], obj: Any = None):
    """Para os casos que precisam do ctx.obj cru — `obj={}` sobretudo."""
    return runner.invoke(app, ["sen", *args], obj=obj, env=LARGO)
