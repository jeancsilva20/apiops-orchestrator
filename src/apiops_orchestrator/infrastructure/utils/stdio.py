"""Endurece stdout/stderr: nenhum glifo decorativo derruba a CLI.

Contexto do defeito que isto corrige. A ajuda do grupo `get` trazia `→`
(U+2192); num stdout cp1252 — o padrao do Windows em pipe, redirecionamento,
log de CI e subprocess — o Rich levantava `UnicodeEncodeError` no meio da
renderizacao, o `except Exception` de `main.py` o traduzia em "erro interno na
consulta" e `sen --help` saia com codigo 1. Uma ajuda que nao se consegue ler
nao e ajuda.

Corrigir glifo a glifo ja havia sido tentado no repositorio (ha cinco
degradacoes ad hoc em `cli_adapter.py` e ate um comentario dizendo que `≥`
quebra em cp1252) e mesmo assim o defeito chegou a producao: a saida de dados
usa `→`, `←`, `↳`, `−` e `█` em dezenas de pontos. A correcao estrutural e no
stream, uma vez, no entrypoint.

Duas camadas, nesta ordem:

1. `errors="replace"` em todo stream — um caractere fora do encoding vira `?`
   em vez de abortar a execucao no meio da escrita.
2. `encoding="utf-8"` **somente quando o destino nao e terminal**. Em pipe,
   arquivo, CI ou subprocess quem le e um programa, e utf-8 e o certo. Terminal
   de verdade fica intocado de proposito: e isso que mantem
   `cli_adapter._supports_text()` respondendo `False` num console cp1252
   legitimo, preservando a arte ASCII em vez de produzir mojibake.
"""

from __future__ import annotations

import os
import sys
from typing import Any


def _endurecer(stream: Any) -> None:
    """Aplica as duas camadas a um stream, sem nunca levantar.

    `reconfigure(encoding=...)` **reseta `errors` para `strict`** — por isso os
    dois argumentos andam sempre juntos; passar so o encoding pioraria o quadro
    num pipe, onde o default era `surrogateescape`.
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    try:
        # Escolha explicita do usuario manda: so se acrescenta a tolerancia.
        if os.getenv("PYTHONIOENCODING"):
            reconfigure(errors="replace")
            return
        try:
            terminal = bool(stream.isatty())
        except Exception:
            terminal = False
        if terminal:
            reconfigure(errors="replace")
        else:
            reconfigure(encoding="utf-8", errors="replace")
    except (ValueError, OSError, AttributeError, LookupError):
        # Uma CLI nao morre por nao conseguir ajustar um stream: no executavel
        # frozen sem console `sys.stdout` pode ser None, e sob captura de teste
        # o objeto pode nao aceitar reconfiguracao.
        pass


def harden_stdio() -> None:
    """Ponto unico, chamado como primeira instrucao de `main()`."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None:
            _endurecer(stream)


__all__ = ["harden_stdio"]
