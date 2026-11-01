"""Leituras dos elementos ligados às APIs: ambientes, variáveis, apps, planos e tokens.

Lógica pura sobre o wire cru do Manager (`GET /environments/{id}`, `/apps`,
`/plans`, `/access-tokens`, `/inbounds`, `/gateway-pools`, `/user-management`).
Devolve dicts estáveis para a saída da CLI.

Segredos **nunca** saem daqui em claro:

* a plataforma já mascara `clientId`, `secret`, `code` e `refreshToken`
  (`*****`); mesmo assim esses campos são descartados;
* variável de ambiente `SECURED` sai sempre mascarada;
* variável `DEFAULT` cujo nome ou valor parece credencial (`Basic …`,
  `Bearer …`, chave com `secret`/`password`/`token`/`auth`…) sai mascarada
  por padrão — o chamador pode pedir os valores (`show_values`), e mesmo
  assim a `SECURED` não aparece.
"""

import re
from typing import Any, Dict, List, Optional, Sequence

from apiops_orchestrator.domain.services import api_navigation as nav

MASK = "•••••"

_SENSITIVE_KEY = re.compile(
    r"(secret|passw|pwd|token|credential|auth|basic|bearer|api[-_]?key|private|"
    r"cert|senha|chave|client[-_]?id)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE = re.compile(r"^\s*(basic|bearer)\s+\S", re.IGNORECASE)


def looks_sensitive(key: Any, value: Any) -> bool:
    """Nome de credencial, ou valor com esquema de autorização embutido."""
    if _SENSITIVE_KEY.search(str(key or "")):
        return True
    return bool(_SENSITIVE_VALUE.match(str(value or "")))


def _is_secured(variable: Dict[str, Any]) -> bool:
    return str(variable.get("variableType") or "").upper() == "SECURED"


def describe_variable(
    variable: Dict[str, Any],
    map_: Dict[str, Any],
    environment: Dict[str, Any],
    *,
    show_values: bool = False,
) -> Dict[str, Any]:
    secured = _is_secured(variable)
    sensitive = secured or looks_sensitive(variable.get("key"), variable.get("value"))
    reveal = show_values and not secured
    return {
        "environmentId": environment.get("id"),
        "environmentName": environment.get("name"),
        "map": map_.get("name"),
        "mapId": map_.get("id"),
        "key": variable.get("key"),
        "value": variable.get("value") if (reveal or not sensitive) else MASK,
        "variableType": (variable.get("variableType") or "DEFAULT").upper(),
        "masked": bool(sensitive and not reveal),
    }


def environment_variables(
    environment: Dict[str, Any],
    *,
    show_values: bool = False,
    key: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Variáveis de um ambiente, achatadas por mapa; `key` filtra por substring."""
    wanted = (key or "").lower()
    rows: List[Dict[str, Any]] = []
    for map_ in environment.get("mapVars") or []:
        if not isinstance(map_, dict):
            continue
        for variable in map_.get("vars") or []:
            if not isinstance(variable, dict):
                continue
            if wanted and wanted not in str(variable.get("key") or "").lower():
                continue
            rows.append(describe_variable(variable, map_, environment, show_values=show_values))
    rows.sort(key=lambda r: (str(r["map"] or ""), str(r["key"] or "")))
    return rows


def describe_environment(
    environment: Dict[str, Any], *, show_values: bool = False
) -> Dict[str, Any]:
    label = environment.get("label") if isinstance(environment.get("label"), dict) else {}
    inbound = (
        environment.get("inboundAddress")
        if isinstance(environment.get("inboundAddress"), dict)
        else {}
    )
    visibility = (
        environment.get("visibility") if isinstance(environment.get("visibility"), dict) else {}
    )
    deployed = [
        {
            "apiId": d.get("apiId"),
            "apiName": d.get("apiName"),
            "apiVersion": d.get("apiVersion"),
            "revisionId": d.get("revisionId"),
            "revisionNumber": d.get("revisionNumber"),
        }
        for d in environment.get("revisionsDeployed") or []
        if isinstance(d, dict)
    ]
    deployed.sort(key=lambda d: (str(d["apiName"] or "").lower(), d["apiId"] or 0))
    return {
        "id": environment.get("id"),
        "name": environment.get("name"),
        "description": environment.get("description") or None,
        "inboundUrl": environment.get("inboundUrl"),
        "visibility": visibility.get("visibilityType"),
        "gateway": {
            "pool": label.get("name"),
            "type": label.get("labelType"),
            "host": inbound.get("host"),
            "protocol": inbound.get("protocolType"),
            "tls": inbound.get("tlsType"),
        },
        "variableMaps": [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "description": m.get("description") or None,
                "variables": len(m.get("vars") or []),
            }
            for m in environment.get("mapVars") or []
            if isinstance(m, dict)
        ],
        "variables": environment_variables(environment, show_values=show_values),
        "deployed": deployed,
        "totals": {"deployed": len(deployed)},
    }


# --------------------------------------------------------------------------- consumo


def _api_ref(api: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": api.get("id"), "name": api.get("name"), "version": api.get("version")}


def describe_app(app: Dict[str, Any], *, detail: bool = False) -> Dict[str, Any]:
    """App sem credenciais: identidade, status e as assinaturas (API → planos)."""
    subscriptions = []
    for api in app.get("apis") or []:
        if not isinstance(api, dict):
            continue
        subscriptions.append(
            {
                **_api_ref(api),
                "plans": [
                    {"id": p.get("id"), "name": p.get("name"), "defaultPlan": p.get("defaultPlan")}
                    for p in api.get("plans") or []
                    if isinstance(p, dict)
                ],
            }
        )
    subscriptions.sort(key=lambda s: str(s["name"] or "").lower())
    document = {
        "id": app.get("id"),
        "name": app.get("name"),
        "status": app.get("status"),
        "developer": app.get("developer"),
        "description": app.get("description") or None,
        "creationDate": app.get("creationDate"),
        "apis": subscriptions,
        "accessTokens": len(app.get("accessTokens") or []),
    }
    if detail:
        document["extraInfo"] = app.get("extraInfo") or {}
        document["inboundAddresses"] = [
            (i.get("name") if isinstance(i, dict) else i) for i in app.get("inboundAddresses") or []
        ]
    return document


def app_subscribes(app: Dict[str, Any], api_id: int) -> bool:
    return any(
        isinstance(api, dict) and api.get("id") == api_id for api in app.get("apis") or []
    )


def describe_plan(plan: Dict[str, Any], *, detail: bool = False) -> Dict[str, Any]:
    api = plan.get("api") if isinstance(plan.get("api"), dict) else {}
    items = [i for i in plan.get("interceptors") or [] if isinstance(i, dict)]
    document = {
        "id": plan.get("id"),
        "name": plan.get("name"),
        "description": plan.get("description") or None,
        "defaultPlan": bool(plan.get("defaultPlan")),
        "api": _api_ref(api) if api else None,
        "interceptors": len(items),
    }
    if detail:
        live = sorted(
            (i for i in items if i.get("status") != "REMOVED"),
            key=lambda i: i.get("position") or 0,
        )
        document["flow"] = {
            "request": [nav.describe_item(i, include_content=True) for i in live if (i.get("executionPoint") or "").upper() == "FIRST"],
            "response": [nav.describe_item(i, include_content=True) for i in live if (i.get("executionPoint") or "").upper() == "SECOND"],
        }
    return document


def describe_token(token: Dict[str, Any]) -> Dict[str, Any]:
    """Token sem o código nem o refresh: identidade, dono, app, validade e APIs."""
    app = token.get("app") if isinstance(token.get("app"), dict) else {}
    return {
        "id": token.get("_id") or token.get("id"),
        "owner": token.get("owner"),
        "app": {"id": app.get("id"), "name": app.get("name")},
        "status": token.get("status"),
        "refreshStatus": token.get("refreshStatus"),
        "expiresIn": token.get("expiresIn"),
        "creationDate": token.get("creationDate"),
        "expiredDate": token.get("expiredDate"),
        "apis": [_api_ref(a) for a in token.get("apis") or [] if isinstance(a, dict)],
        "planIds": list(token.get("planIds") or []),
        "generatedBy": (token.get("extraInfo") or {}).get("sensediaGeneratedBy")
        if isinstance(token.get("extraInfo"), dict)
        else None,
    }


def token_touches(token: Dict[str, Any], *, app_id: Optional[int], api_id: Optional[int]) -> bool:
    app = token.get("app") if isinstance(token.get("app"), dict) else {}
    if app_id is not None and app.get("id") != app_id:
        return False
    if api_id is not None and not any(
        isinstance(a, dict) and a.get("id") == api_id for a in token.get("apis") or []
    ):
        return False
    return True


# --------------------------------------------------------------------------- pessoas e infra


def describe_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "username": user.get("username"),
        "name": user.get("name"),
        "email": user.get("email"),
        "status": user.get("status"),
        "providerType": user.get("providerType"),
        "isFederated": user.get("isFederated"),
        "createdAt": user.get("createdAt"),
    }


def describe_group(group: Dict[str, Any]) -> Dict[str, Any]:
    return {"name": group.get("name"), "description": group.get("description") or None}


def describe_inbound(inbound: Dict[str, Any]) -> Dict[str, Any]:
    tls = inbound.get("tlsSecurity") if isinstance(inbound.get("tlsSecurity"), dict) else {}
    return {
        "id": inbound.get("id"),
        "name": inbound.get("name"),
        "host": inbound.get("host"),
        "protocol": inbound.get("protocolType"),
        "tls": inbound.get("tlsType"),
        "minTlsVersion": tls.get("minTlsVersion"),
        "maxTlsVersion": tls.get("maxTlsVersion"),
        "gatewayType": inbound.get("gatewayType"),
        "dataPlane": inbound.get("dataPlane"),
        "hasApps": inbound.get("hasApps"),
        "hasEnvironments": inbound.get("hasEnvironments"),
    }


def describe_gateway_pool(pool: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": pool.get("id"),
        "name": pool.get("name"),
        "description": pool.get("description") or None,
        "type": pool.get("labelType"),
        "routes": pool.get("routes"),
    }


def matches_query(text_fields: Sequence[Any], query: Optional[str]) -> bool:
    if not query:
        return True
    wanted = query.lower()
    return any(wanted in str(field or "").lower() for field in text_fields)
