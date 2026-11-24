"""Documentos de exemplo que os fakes devolvem.

Vinham duplicados por arquivo de teste (cada um redeclarava `API`, `REVISION`,
`COUNTS`, `_item`, `_scope`). Reunidos aqui sem mudanca de semantica: os valores
sao os mesmos que `test_navigation_commands.py` usava.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

API: Dict[str, Any] = {
    "id": 400,
    "name": "Orchestrator Auth API",
    "version": "1.0.1",
    "basePath": "/orq-auth/v1",
}

REVISION: Dict[str, Any] = {
    "id": 8948,
    "number": 4,
    "lifeCycle": "DRAFT",
    "workflowId": 139,
    "workflowStageId": 420,
    "deployedIn": ["Default"],
}

COUNTS: Dict[str, int] = {
    "own": 1,
    "removes": 0,
    "inherited": 0,
    "effective": 1,
    "preserved": 0,
}


def item(id_: int = 19195, kind: str = "Log", content: Any = None) -> Dict[str, Any]:
    return {
        "id": id_,
        "position": 0,
        "executionPoint": "FIRST",
        "type": kind,
        "status": "REFERENCE",
        "customInterceptorId": None,
        "customName": None,
        "summary": "acceptedTerms=True",
        **({"content": content} if content is not None else {}),
    }


def scope(
    kind: str = "root",
    key: str = "all",
    label: str = "all",
    own: Optional[Dict[str, Any]] = None,
    effective: Any = None,
    removes: Any = None,
) -> Dict[str, Any]:
    documento = {
        "scope": key,
        "kind": kind,
        "label": label,
        "id": 8948,
        "destination": {"url": None, "timeout": None},
        "inherits": None if kind == "root" else not removes,
        "counts": COUNTS,
        "removes": removes or [],
        "own": own or {"request": [item()], "response": []},
    }
    if effective is not None:
        documento["effective"] = effective
    return documento


def cabecalho(**extra: Any) -> Dict[str, Any]:
    """O envelope `{api, revision}` que os comandos de revisao devolvem."""
    return {"api": API, "revision": REVISION, **extra}
