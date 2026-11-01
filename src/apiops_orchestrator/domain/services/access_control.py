"""Leituras do Access Control (`/user-management/v1`): usuários, times e roles.

Vocabulário (mapeamento APIM 14): **Team** na UI é `groups` na API; **Role** na
UI é `policies`. Lógica pura sobre o wire; nada de credencial passa por aqui.
"""

from typing import Any, Dict, List, Optional, Sequence

from apiops_orchestrator.domain.services.tenant_catalog import describe_group, describe_user


def describe_role(policy: Dict[str, Any]) -> Dict[str, Any]:
    products = [
        {
            "id": p.get("id"),
            "name": p.get("name"),
            "inlinePermission": p.get("inlinePermission"),
        }
        for p in policy.get("products") or []
        if isinstance(p, dict)
    ]
    return {
        "id": policy.get("id"),
        "name": policy.get("name"),
        "description": policy.get("description") or None,
        "managedBySensedia": bool(policy.get("sensediaManaged")),
        "usersChangeable": policy.get("usersChangeable"),
        "products": products,
    }


def describe_role_permissions(blocks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """`[{productName, permissions:[{code,name,description}]}]` → por produto, ordenado."""
    out = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        permissions = []
        for perm in block.get("permissions") or []:
            if isinstance(perm, dict):
                permissions.append(
                    {
                        "code": perm.get("code"),
                        "name": perm.get("name"),
                        "description": perm.get("description") or None,
                    }
                )
            else:
                permissions.append({"code": str(perm), "name": None, "description": None})
        permissions.sort(key=lambda p: str(p["code"] or ""))
        out.append(
            {
                "product": block.get("productName"),
                "productId": block.get("productId"),
                "permissions": permissions,
            }
        )
    out.sort(key=lambda b: str(b["product"] or "").lower())
    return out


def role_document(
    policy: Dict[str, Any],
    permissions: Sequence[Dict[str, Any]],
    users: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    by_product = describe_role_permissions(permissions)
    members = sorted(
        (describe_user(u) for u in users if isinstance(u, dict)),
        key=lambda u: str(u["username"] or "").lower(),
    )
    return {
        **describe_role(policy),
        "permissions": by_product,
        "users": members,
        "totals": {
            "permissions": sum(len(b["permissions"]) for b in by_product),
            "products": len(by_product),
            "users": len(members),
        },
    }


def user_document(
    user: Dict[str, Any],
    groups: Sequence[Dict[str, Any]],
    policies: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    teams = sorted(
        (describe_group(g) for g in groups if isinstance(g, dict)),
        key=lambda g: str(g["name"] or "").lower(),
    )
    roles = sorted(
        (
            {
                "id": p.get("id"),
                "name": p.get("name"),
                "description": p.get("description") or None,
                "managedBySensedia": bool(p.get("sensediaManaged")),
            }
            for p in policies
            if isinstance(p, dict)
        ),
        key=lambda r: str(r["name"] or "").lower(),
    )
    return {
        **describe_user(user),
        "enabled": user.get("enabled"),
        "mfaEnabled": user.get("mfaEnabled"),
        "tags": [str(t) for t in (user.get("tags") or [])],
        "teams": teams,
        "roles": roles,
        "isSuperAdmin": any(str(r["name"] or "").lower() == "super admin" for r in roles),
    }


def team_document(group: Dict[str, Any], users: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    members = sorted(
        (describe_user(u) for u in users if isinstance(u, dict)),
        key=lambda u: str(u["username"] or "").lower(),
    )
    return {**describe_group(group), "members": members, "totals": {"members": len(members)}}


def permissions_document(product: str, codes: Sequence[str]) -> Dict[str, Any]:
    """Catálogo de códigos agrupado pelo domínio (`produto.domínio.ação`)."""
    domains: Dict[str, List[str]] = {}
    for code in sorted({str(c) for c in codes}):
        parts = code.split(".")
        domain = parts[1] if len(parts) > 2 else (parts[0] if parts else "")
        domains.setdefault(domain, []).append(code)
    return {
        "product": product,
        "domains": [{"domain": d, "codes": c} for d, c in sorted(domains.items())],
        "totals": {"codes": sum(len(c) for c in domains.values()), "domains": len(domains)},
    }


def role_matches(policy: Dict[str, Any], query: Optional[str]) -> bool:
    if not query:
        return True
    wanted = query.lower()
    return wanted in str(policy.get("name") or "").lower() or wanted in str(
        policy.get("description") or ""
    ).lower()
