"""Leitura do estado de deploy em `GET /apis/{id}`.

`revisions[].deployments` é a fonte: `GET /revisions/{id}` não preenche o campo
e `environments[]` não mostra ambiente não ligado à API (sondagem 2026-10-19).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

DEPLOYED = "DEPLOYED"


def instante(epoch_ms: Any) -> Optional[str]:
    """Epoch em milissegundos → ISO-8601 UTC."""
    try:
        return datetime.fromtimestamp(int(epoch_ms) / 1000, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def registros(revisao: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Registros de deploy de uma revisão."""
    return [d for d in revisao.get("deployments") or [] if isinstance(d, dict)]


def registros_da_api(api: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Registros de deploy de todas as revisões da API."""
    return [d for revisao in api.get("revisions") or [] for d in registros(revisao)]


def ativo_no_ambiente(api: Dict[str, Any], ambiente_id: int) -> Optional[Dict[str, Any]]:
    """Deploy `DEPLOYED` mais recente da API no ambiente."""
    ativos = [
        d
        for d in registros_da_api(api)
        if d.get("status") == DEPLOYED and d.get("environmentId") == ambiente_id
    ]
    if not ativos:
        return None
    return max(ativos, key=lambda d: d.get("deployDate") or 0)


def ativos_da_revisao(revisao: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Deploy `DEPLOYED` mais recente da revisão em cada ambiente, por id do ambiente."""
    por_ambiente: Dict[Any, Dict[str, Any]] = {}
    for d in registros(revisao):
        if d.get("status") != DEPLOYED or d.get("environmentId") is None:
            continue
        atual = por_ambiente.get(d["environmentId"])
        if atual is None or (d.get("deployDate") or 0) > (atual.get("deployDate") or 0):
            por_ambiente[d["environmentId"]] = d
    return [por_ambiente[k] for k in sorted(por_ambiente, key=str)]
