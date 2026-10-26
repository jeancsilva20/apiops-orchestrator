"""Leitura do estado de deploy em `GET /apis/{id}`.

`revisions[].deployments` é a fonte: `GET /revisions/{id}` não preenche o campo
e `environments[]` não mostra ambiente não ligado à API (sondagem 2026-10-19).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DEPLOYED = "DEPLOYED"


def instant(epoch_ms: Any) -> Optional[str]:
    """Epoch em milissegundos → ISO-8601 UTC."""
    try:
        return datetime.fromtimestamp(int(epoch_ms) / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def records(revision: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Registros de deploy de uma revisão."""
    return [d for d in revision.get("deployments") or [] if isinstance(d, dict)]


def api_records(api: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Registros de deploy de todas as revisões da API."""
    return [d for revision in api.get("revisions") or [] for d in records(revision)]


def active_in_environment(api: Dict[str, Any], environment_id: int) -> Optional[Dict[str, Any]]:
    """Deploy `DEPLOYED` mais recente da API no ambiente."""
    active = [
        d
        for d in api_records(api)
        if d.get("status") == DEPLOYED and d.get("environmentId") == environment_id
    ]
    if not active:
        return None
    return max(active, key=lambda d: d.get("deployDate") or 0)


def active_for_revision(revision: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Deploy `DEPLOYED` mais recente da revisão em cada ambiente, por id do ambiente."""
    by_environment: Dict[Any, Dict[str, Any]] = {}
    for d in records(revision):
        if d.get("status") != DEPLOYED or d.get("environmentId") is None:
            continue
        current = by_environment.get(d["environmentId"])
        if current is None or (d.get("deployDate") or 0) > (current.get("deployDate") or 0):
            by_environment[d["environmentId"]] = d
    return [by_environment[k] for k in sorted(by_environment, key=str)]
