"""Fixtures da borda da CLI: um runner e um invocador.

Antes cada arquivo redeclarava `runner = CliRunner()`, o seu proprio `_ctx`/
`_invoke` e a largura (`LARGO = {"COLUMNS": "200"}`). Aqui ficam uma vez.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional, Sequence

import pytest
from typer.testing import CliRunner

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app
from sen_support.cli_fabricas import contexto


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def invoke_sen(runner: CliRunner) -> Callable[..., Any]:
    """Invoca `sen <args>` montando o ctx.obj a partir dos apelidos de FABRICAS.

    `obj=` e a escotilha para os casos em que o ctx.obj precisa ser cru —
    sobretudo `obj={}`, que prova o caminho de "fabrica ausente".
    `colunas` fixa a largura para que a quebra do Rich nao entre na assercao.
    """

    def _invoke(
        args: Sequence[str],
        *,
        entrada: Optional[str] = None,
        colunas: int = 200,
        obj: Optional[Mapping[str, Any]] = None,
        **fabricas: Any,
    ):
        if obj is not None and fabricas:
            raise AssertionError("passe `obj=` OU apelidos de fabrica, nunca os dois")
        return runner.invoke(
            app,
            ["sen", *args],
            obj=dict(obj) if obj is not None else contexto(**fabricas),
            input=entrada,
            env={"COLUMNS": str(colunas)},
        )

    return _invoke


@pytest.fixture
def uma_linha() -> Callable[[Any], str]:
    """Achata a saida do Rich para procurar frase sem tropecar na quebra."""

    def _uma_linha(resultado: Any) -> str:
        return " ".join(resultado.output.split())

    return _uma_linha
