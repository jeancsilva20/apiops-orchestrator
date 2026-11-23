"""Trace de chamadas e analytics prontos (`GET /calls`, `GET /calls/{id}`).

Lógica pura sobre o wire do Manager (mapeamento APIM 10 + sondagem do tenant):

* a rota aceita uma janela de **no máximo 7 dias**, com datas no formato
  `yyyy-MM-dd'T'HH:mm:ss` em UTC;
* cada chamada carrega `id == traceId == requestID` (UUID), status, durações,
  API/revisão/recurso/operação, ambiente, app, dono do token e tamanhos de
  payload; o detalhe acrescenta `requestHeaders`/`responseHeaders` (texto) e
  `trace` (string JSON: lista de passos `{timeMillis, message, data}`);
* segredos **nunca** saem daqui: `accessToken`, `appSecret`, `appToken` e
  `clientId` são descartados, e headers de credencial saem mascarados.
"""

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

MAX_WINDOW_DAYS = 7
WIRE_DATE = "%Y-%m-%dT%H:%M:%S"
MASK = "•••••"

_SECRET_HEADERS = re.compile(
    r"^(authorization|proxy-authorization|cookie|set-cookie|x-api-key|api[-_]?key|"
    r"client[-_]?secret|client[-_]?id|access[-_]?token|x-auth-token|x-xsrf-token)$",
    re.IGNORECASE,
)
_RELATIVE = re.compile(r"^(\d+)\s*([mhd])$", re.IGNORECASE)


# --------------------------------------------------------------------------- janela


def parse_moment(text: Optional[str], *, now: datetime, default: datetime) -> datetime:
    """`24h`/`7d`/`30m` (relativo a agora), `YYYY-MM-DD` ou ISO; vazio = `default`."""
    if text is None or not str(text).strip():
        return default
    raw = str(text).strip()
    match = _RELATIVE.match(raw)
    if match:
        amount, unit = int(match.group(1)), match.group(2).lower()
        delta = {"m": timedelta(minutes=amount), "h": timedelta(hours=amount), "d": timedelta(days=amount)}[unit]
        return now - delta
    for pattern in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            f"momento inválido: {raw!r}. Use 24h, 7d, 30m, YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS (UTC)."
        ) from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def window(
    since: Optional[str], until: Optional[str], *, now: Optional[datetime] = None
) -> Tuple[str, str, Dict[str, Any]]:
    """`(beginDate, endDate, info)` prontos para o wire, dentro do limite da rota.

    Sem `since`, a janela é de 24 horas. Uma janela maior que 7 dias é
    encolhida para os 7 dias que terminam em `until`, e `info["clamped"]`
    diz isso ao chamador.
    """
    now = (now or datetime.now(timezone.utc)).replace(microsecond=0)
    end = parse_moment(until, now=now, default=now)
    begin = parse_moment(since, now=now, default=end - timedelta(hours=24))
    if begin >= end:
        raise ValueError("a janela está vazia: --since precisa ser anterior a --until")
    clamped = False
    if end - begin > timedelta(days=MAX_WINDOW_DAYS):
        begin = end - timedelta(days=MAX_WINDOW_DAYS)
        clamped = True
    # A plataforma recusa início anterior aos últimos 7 dias contados de agora.
    floor = now - timedelta(days=MAX_WINDOW_DAYS) + timedelta(minutes=1)
    if begin < floor:
        begin = floor
        clamped = True
    begin_text = begin.astimezone(timezone.utc).strftime(WIRE_DATE)
    end_text = end.astimezone(timezone.utc).strftime(WIRE_DATE)
    return begin_text, end_text, {"begin": begin_text, "end": end_text, "clamped": clamped}


def status_filters(
    *,
    errors: bool = False,
    status_from: Optional[int] = None,
    status_to: Optional[int] = None,
) -> Dict[str, str]:
    """`--errors` = 400..599; `--status-from/--status-to` explícitos vencem."""
    low, high = status_from, status_to
    if errors:
        low = low if low is not None else 400
        high = high if high is not None else 599
    filters: Dict[str, str] = {}
    if low is not None:
        filters["httpStatusFrom"] = str(low)
        filters["httpStatusTo"] = str(high if high is not None else 599)
    elif high is not None:
        filters["httpStatusFrom"] = "100"
        filters["httpStatusTo"] = str(high)
    return filters


# --------------------------------------------------------------------------- chamadas


def _int(value: Any) -> Optional[int]:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def describe_call(call: Dict[str, Any]) -> Dict[str, Any]:
    """Resumo de uma chamada, sem credenciais."""
    return {
        "traceId": call.get("traceId") or call.get("id"),
        "when": call.get("receivedOnDate") or call.get("callDate"),
        "api": {"id": call.get("apiId"), "name": call.get("apiName") or None},
        "revisionId": _int(call.get("revisionId")),
        "resource": {"id": _int(call.get("resourceId")) or None, "name": call.get("resourceName") or None},
        "operation": {"id": _int(call.get("operationId")) or None, "name": call.get("operationName") or None},
        "environment": {"id": call.get("environmentId"), "name": call.get("environmentName") or None},
        "method": call.get("method"),
        "uri": call.get("uri") or call.get("completeUrl") or call.get("url"),
        "status": _int(call.get("resultStatus")),
        "targetStatus": _int(call.get("targetResultStatus")) or None,
        "result": call.get("typeStatus"),
        "errorType": call.get("typeError") or None,
        "durationMillis": _int(call.get("durationMillis")) if call.get("durationMillis") is not None else _int(call.get("duration")),
        "gatewayMillis": _int(call.get("gatewayDurationMillis")),
        "targetMillis": _int(call.get("targetDurationMillis")),
        "app": call.get("appName") or None,
        "appDeveloper": call.get("appDeveloper") or None,
        "tokenOwner": call.get("accessTokenOwner") or None,
        "caller": call.get("callerAddress") or call.get("receivedFromAddress") or None,
        "requestBytes": _int(call.get("requestPayload")),
        "responseBytes": _int(call.get("responsePayload")),
        "cache": call.get("cache"),
        "billing": call.get("billing"),
    }


def mask_headers(text: Any) -> List[Dict[str, Any]]:
    """`"nome: valor\\n…"` → lista `{name, value, masked}` com credenciais ocultas."""
    if not isinstance(text, str) or not text.strip():
        return []
    rows = []
    for line in text.splitlines():
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        name, value = name.strip(), value.strip()
        secret = bool(_SECRET_HEADERS.match(name))
        rows.append({"name": name, "value": MASK if secret else value, "masked": secret})
    return rows


_SECRET_KEY = re.compile(
    r"(secret|passw|pwd|token|credential|authorization|cookie|api[-_]?key|client[-_]?id)",
    re.IGNORECASE,
)
_HEADER_LINE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")


def _mask_header_lines(text: str) -> str:
    """Mascara, dentro de um texto multilinha, as linhas `nome: valor` de credencial."""
    if "\n" not in text and ":" not in text:
        return text
    out = []
    for line in text.splitlines():
        match = _HEADER_LINE.match(line.strip())
        if match and _SECRET_HEADERS.match(match.group(1)):
            out.append(f"{match.group(1)}: {MASK}")
        else:
            out.append(line)
    return "\n".join(out)


def sanitize_data(value: Any) -> Any:
    """`data` de um passo do pipeline sem credenciais.

    O gateway grava no trace o log da requisição (headers e corpo). Chaves de
    credencial viram `•••••`, e textos com linhas `header: valor` passam pela
    mesma máscara dos headers.
    """
    if isinstance(value, dict):
        return {
            str(k): (MASK if _SECRET_KEY.search(str(k)) else sanitize_data(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [sanitize_data(v) for v in value]
    if isinstance(value, str):
        return _mask_header_lines(value)
    return value


def parse_trace(raw: Any) -> List[Dict[str, Any]]:
    """`trace` do wire (string JSON ou lista) → passos `{step, timeMillis, message, data}`."""
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except ValueError:
            return [{"step": 1, "timeMillis": None, "message": raw, "data": None}]
    if not isinstance(data, list):
        return []
    steps = []
    for index, item in enumerate(data, start=1):
        if isinstance(item, dict):
            steps.append(
                {
                    "step": index,
                    "timeMillis": _int(item.get("timeMillis")),
                    "message": _mask_header_lines(str(item.get("message"))) if isinstance(item.get("message"), str) else item.get("message"),
                    "data": sanitize_data(item.get("data")),
                }
            )
        else:
            steps.append({"step": index, "timeMillis": None, "message": str(item), "data": None})
    return steps


def describe_call_detail(call: Dict[str, Any], *, include_headers: bool = True) -> Dict[str, Any]:
    document = describe_call(call)
    steps = parse_trace(call.get("trace"))
    document["trace"] = steps
    document["totals"] = {
        "steps": len(steps),
        "traceMillis": sum(s["timeMillis"] or 0 for s in steps),
    }
    if include_headers:
        document["requestHeaders"] = mask_headers(call.get("requestHeaders"))
        document["responseHeaders"] = mask_headers(call.get("responseHeaders"))
    return document


# --------------------------------------------------------------------------- analytics


def _percentile(values: Sequence[int], ratio: float) -> Optional[int]:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(ratio * (len(ordered) - 1))))
    return ordered[index]


def _top(counter: Dict[Any, int], limit: int) -> List[Dict[str, Any]]:
    rows = sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))
    return [{"key": key, "calls": count} for key, count in rows[:limit]]


def analytics_summary(
    calls: Sequence[Dict[str, Any]], *, total: int, top: int = 5
) -> Dict[str, Any]:
    """Volumetria, erros, latência e top por operação/app/ambiente/caller sobre a amostra."""
    classes = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "other": 0}
    by_status: Dict[Any, int] = {}
    by_operation: Dict[str, int] = {}
    by_app: Dict[str, int] = {}
    by_env: Dict[str, int] = {}
    by_caller: Dict[str, int] = {}
    by_api: Dict[str, int] = {}
    by_hour: Dict[str, int] = {}
    latencies: List[int] = []
    gateway: List[int] = []
    target: List[int] = []
    errors: List[Dict[str, Any]] = []
    for raw in calls:
        call = describe_call(raw)
        status = call["status"]
        bucket = f"{status // 100}xx" if isinstance(status, int) and 100 <= status <= 599 else "other"
        classes[bucket] = classes.get(bucket, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
        op = call["operation"]["name"] or f"{call['method'] or '?'} {call['uri'] or '?'}"
        by_operation[op] = by_operation.get(op, 0) + 1
        by_app[call["app"] or "(sem app)"] = by_app.get(call["app"] or "(sem app)", 0) + 1
        env = call["environment"]["name"] or str(call["environment"]["id"])
        by_env[env] = by_env.get(env, 0) + 1
        by_caller[call["caller"] or "?"] = by_caller.get(call["caller"] or "?", 0) + 1
        api = f"{call['api']['name'] or '?'} ({call['api']['id']})"
        by_api[api] = by_api.get(api, 0) + 1
        when = str(call["when"] or "")
        if len(when) >= 13:
            by_hour[when[:13]] = by_hour.get(when[:13], 0) + 1
        if call["durationMillis"] is not None:
            latencies.append(call["durationMillis"])
        if call["gatewayMillis"] is not None:
            gateway.append(call["gatewayMillis"])
        if call["targetMillis"] is not None:
            target.append(call["targetMillis"])
        if isinstance(status, int) and status >= 400:
            errors.append(call)
    sample = len(calls)
    error_count = classes["4xx"] + classes["5xx"]
    return {
        "sample": sample,
        "total": total,
        "classes": classes,
        "errorRate": round(error_count / sample, 4) if sample else None,
        "latencyMillis": {
            "avg": round(sum(latencies) / len(latencies), 1) if latencies else None,
            "p50": _percentile(latencies, 0.50),
            "p95": _percentile(latencies, 0.95),
            "max": max(latencies) if latencies else None,
            "gatewayAvg": round(sum(gateway) / len(gateway), 1) if gateway else None,
            "targetAvg": round(sum(target) / len(target), 1) if target else None,
        },
        "topStatus": _top(by_status, top),
        "topApis": _top(by_api, top),
        "topOperations": _top(by_operation, top),
        "topApps": _top(by_app, top),
        "topEnvironments": _top(by_env, top),
        "topCallers": _top(by_caller, top),
        "byHour": [{"hour": h, "calls": c} for h, c in sorted(by_hour.items())],
        "recentErrors": [
            {k: e[k] for k in ("traceId", "when", "method", "uri", "status", "errorType", "app")}
            for e in errors[:top]
        ],
    }
