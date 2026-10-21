"""Regra de visibilidade de uma API para a sessão (capability `api-visibility`).

A plataforma entrega a visibilidade em dois formatos — campos de contexto no
catálogo e o objeto `visibility` do `GET /apis/{id}` — e os dois viram
`ApiVisibility` antes de passar pela regra.
"""

from typing import Any, Dict, List, Optional

from apiops_orchestrator.domain.models.api_visibility_model import (
    ApiVisibility,
    OwnershipContext,
)
from apiops_orchestrator.infrastructure.utils.text_normalizer import (
    accent_fold,  # type: ignore[import-untyped]
)


def _fold_stripped(value: Any) -> str:
    return accent_fold(value).strip()


def visible_to(
    visibility: ApiVisibility,
    username: Optional[str],
    groups: Optional[List[str]],
    super_admin: bool = False,
) -> bool:
    """Diz se a sessão enxerga a API; tipo ausente ou desconhecido nega."""
    if super_admin:
        return True

    folded_username = _fold_stripped(username)
    folded_groups = {_fold_stripped(g) for g in (groups or [])}

    match visibility.context:
        case OwnershipContext.ORGANIZATION:
            return True
        case OwnershipContext.ME:
            if folded_username and _fold_stripped(visibility.owner) == folded_username:
                return True
            return any(
                _fold_stripped(login) == folded_username
                for login in visibility.userLogins
            )
        case OwnershipContext.GROUP:
            group_name = _fold_stripped(visibility.groupName)
            return bool(group_name) and group_name in folded_groups
        case _:
            return False


def from_api_payload(api: Dict[str, Any]) -> ApiVisibility:
    """Visibilidade a partir do objeto `visibility` do `GET /apis/{id}`."""
    raw = api.get("visibility") if isinstance(api, dict) else None
    if not isinstance(raw, dict):
        return ApiVisibility()

    try:
        context: Optional[OwnershipContext] = OwnershipContext(
            str(raw.get("visibilityType") or "").strip().lower()
        )
    except ValueError:
        context = None

    group = raw.get("groupVisibility")
    users = raw.get("users")
    return ApiVisibility(
        context=context,
        owner=_text(raw.get("owner")),
        groupName=_text(group.get("name")) if isinstance(group, dict) else None,
        userLogins=[
            str(user["username"])
            for user in (users if isinstance(users, list) else [])
            if isinstance(user, dict) and user.get("username")
        ],
    )


def _text(value: Any) -> Optional[str]:
    return str(value) if value is not None else None
