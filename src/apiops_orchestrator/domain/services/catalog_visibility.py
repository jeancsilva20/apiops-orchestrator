from typing import Any, List, Optional

from apiops_orchestrator.domain.models.api_catalog_model import (
    ApiCatalogEntry,
    OwnershipContext,
)
from apiops_orchestrator.infrastructure.utils.text_normalizer import (
    accent_fold,  # type: ignore[import-untyped]
)


def _fold_stripped(value: Any) -> str:
    return accent_fold(value).strip()


def finder_row_visible_to(
    entry: ApiCatalogEntry,
    username: Optional[str],
    groups: Optional[List[str]],
    super_admin: bool = False,
) -> bool:
    if super_admin:
        return True

    folded_username = _fold_stripped(username)
    folded_groups = {_fold_stripped(g) for g in (groups or [])}

    match entry.contextType:
        case OwnershipContext.ORGANIZATION:
            return True
        case OwnershipContext.ME:
            if folded_username and _fold_stripped(entry.owner) == folded_username:
                return True
            return any(
                _fold_stripped(login) == folded_username
                for login in entry.contextUserLogins
            )
        case OwnershipContext.GROUP:
            group_name = _fold_stripped(entry.contextGroupName)
            return bool(group_name) and group_name in folded_groups
        case _:
            return False



def finder_rows_visible_to(
    entries: Optional[List[ApiCatalogEntry]],
    username: Optional[str],
    groups: Optional[List[str]],
    super_admin: bool = False,
) -> List[ApiCatalogEntry]:
    return [
        entry
        for entry in (entries or [])
        if finder_row_visible_to(entry, username, groups, super_admin)
    ]
