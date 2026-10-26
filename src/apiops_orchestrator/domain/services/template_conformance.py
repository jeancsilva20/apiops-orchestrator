"""Conformidade do fluxo efetivo com a régua (V-11 · D-13).

Lógica pura. A régua é o fluxo de uma **API template** lida por GET; o fluxo
efetivo é o que o repositório produz para cada escopo. O comparador não julga
intenção: emite `INFO`/`WARNING` para o code review e **nunca bloqueia** — o dev
decide subir algo fora do padrão.

Os quatro requisitos da V-11 §4, implementados:

1. **sequência, não conjunto** — um `Log` acrescentado onde a régua já tem um
   `Log` desaparece numa comparação por conjunto. O alinhamento é feito por
   `difflib`, por ponto de execução;
2. **`content` nos tipos nativos** — é onde mora a configuração, e é o caso real
   (`encryptContent: true` × `false`). Em `Custom` o casamento é por
   `customInterceptorId`: mesmo id, mesmo objeto no tenant, então comparar o
   `content` seria redundante e geraria diff textual de script;
3. **classificar o modo** — append, override e supressão se distinguem pela
   forma da lista, não por flag no wire;
4. **ignorar o não governado** — fora de `FIRST`/`SECOND` nada é comparado.

A raiz da revision é comparada **item a item**: ela não herda de nenhum escopo
acima, então tratá-la como append esconderia divergência.
"""

import difflib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from apiops_orchestrator.domain.services.repo_layout import is_governed

SEVERITY_INFO = "INFO"
SEVERITY_WARNING = "WARNING"

POINTS = ("FIRST", "SECOND")


@dataclass(frozen=True)
class Finding:
    severity: str
    scope: str
    message: str
    kind: Optional[str] = None
    custom_interceptor_id: Optional[int] = None


def _normalize_scalar(value: Any) -> Any:
    """Forma canônica para COMPARAÇÃO (não para escrita).

    O wire devolve `"quota": "1000"` como string e o repositório pode trazer o
    inteiro. São o mesmo valor: compará-los cruamente acusaria achado falso num
    campo idêntico. A escrita continua preservando a string — são decisões
    independentes.
    """
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            return float(text)
        except ValueError:
            return value
    return value


def _normalize_content(content: Any) -> Any:
    """Normaliza recursivamente, aceitando `content` como JSON serializado."""
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (TypeError, ValueError):
            return _normalize_scalar(content)
    if isinstance(content, dict):
        return {k: _normalize_content(v) for k, v in sorted(content.items())}
    if isinstance(content, list):
        return [_normalize_content(v) for v in content]
    return _normalize_scalar(content)


# Pública para a conferência pós-publicação comparar `content` pela mesma regra.
normalize_content = _normalize_content


def _custom_id(item: Dict[str, Any]) -> Optional[int]:
    value = item.get("customInterceptorId")
    if value is None and item.get("type") == "Custom":
        value = item.get("id")
    return value


def _key(item: Dict[str, Any]) -> Tuple[str, Optional[int]]:
    """Identidade para alinhamento. O `content` fica de fora de propósito:
    um `Log` alterado ainda É o mesmo `Log`, e a diferença é `WARNING` de
    alteração, não um par remoção+append."""
    return (str(item.get("type") or ""), _custom_id(item))


def _custom_name(item: Dict[str, Any]) -> Optional[str]:
    """Nome legível de um `Custom`, materializado no `content` do wire.

    O wire guarda `{"id": 33, "name": "CyberArk and OAuth Autentication",
    "script": ...}` como string JSON. O id sozinho não diz nada a quem lê o
    relatório; o nome é o que identifica o interceptor para uma pessoa.
    """
    content = item.get("content")
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (TypeError, ValueError):
            return None
    if isinstance(content, dict):
        name = content.get("name")
        return str(name) if name else None
    return None


def _label(item: Dict[str, Any]) -> str:
    """Identificação do interceptor para o relatório (V-11 §5).

    `Custom #33 — CyberArk and OAuth Autentication` quando o nome é conhecido;
    `Custom #33` quando não é. Tipos nativos saem pelo próprio tipo.
    """
    kind = item.get("type") or "?"
    cid = _custom_id(item)
    if not cid:
        return str(kind)
    name = _custom_name(item)
    return f"{kind} #{cid} — {name}" if name else f"{kind} #{cid}"


def _governed(items: Optional[Sequence[Dict[str, Any]]], point: str) -> List[Dict[str, Any]]:
    return [
        i
        for i in (items or [])
        if is_governed(i.get("executionPoint"))
        and (i.get("executionPoint") or "").upper() == point
        and i.get("status") != "REMOVED"
    ]


def compare(
    effective_flow: Optional[Sequence[Dict[str, Any]]],
    ruler: Optional[Sequence[Dict[str, Any]]],
    scope: str,
) -> List[Finding]:
    """Compara um escopo com a régua e devolve os achados.

    Nunca levanta exceção e nunca bloqueia: a saída é sempre uma lista.
    """
    findings: List[Finding] = []
    for point in POINTS:
        findings.extend(
            _compare_point(
                _governed(effective_flow, point),
                _governed(ruler, point),
                scope,
                _POINT_NAME[point],
            )
        )
    return findings


_POINT_NAME = {"FIRST": "request", "SECOND": "response"}


def _compare_point(
    effective: Sequence[Dict[str, Any]],
    ruler: Sequence[Dict[str, Any]],
    scope: str,
    point_name: str,
) -> List[Finding]:
    findings: List[Finding] = []
    effective_keys = [_key(i) for i in effective]
    ruler_keys = [_key(i) for i in ruler]

    missing: List[Tuple[int, Dict[str, Any]]] = []
    additions: List[Tuple[int, Dict[str, Any]]] = []
    matcher = difflib.SequenceMatcher(a=ruler_keys, b=effective_keys, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for ruler_item, effective_item in zip(ruler[i1:i2], effective[j1:j2]):
                findings.extend(_compare_content(ruler_item, effective_item, scope))
            continue
        if tag in ("delete", "replace"):
            missing.extend((i, ruler[i]) for i in range(i1, i2))
        if tag in ("insert", "replace"):
            additions.extend((j, effective[j]) for j in range(j1, j2))

    # Um item que só mudou de lugar sai do alinhamento como "falta aqui" mais
    # "sobra ali" — duas afirmações falsas sobre um item que existe dos dois
    # lados. O par vira um achado só, de posição; a ordem muda o comportamento.
    for ruler_index, ruler_item in list(missing):
        pair = next(
            ((j, e) for j, e in additions if _key(e) == _key(ruler_item)), None
        )
        if pair is None:
            continue
        missing.remove((ruler_index, ruler_item))
        additions.remove(pair)
        findings.append(
            _position_finding(ruler_item, ruler_index, pair[0], scope, point_name)
        )
        findings.extend(_compare_content(ruler_item, pair[1], scope))

    findings.extend(_missing_findings([i for _, i in missing], scope))
    findings.extend(_append_findings([i for _, i in additions], scope))
    return findings


def _position_finding(
    item: Dict[str, Any], in_ruler: int, here: int, scope: str, point_name: str
) -> Finding:
    return Finding(
        severity=SEVERITY_WARNING,
        scope=scope,
        message=(
            f'"{_label(item)}" executa em outra posição: na template é o '
            f"{in_ruler + 1}º do {point_name}, aqui é o {here + 1}º"
        ),
        kind=item.get("type"),
        custom_interceptor_id=_custom_id(item),
    )


def _compare_content(
    ruler_item: Dict[str, Any], effective_item: Dict[str, Any], scope: str
) -> List[Finding]:
    # Custom casa por id: mesmo id, mesmo objeto no tenant.
    if ruler_item.get("type") == "Custom":
        return []
    expected = _normalize_content(ruler_item.get("content"))
    actual = _normalize_content(effective_item.get("content"))
    if expected == actual:
        return []
    return [
        Finding(
            severity=SEVERITY_WARNING,
            scope=scope,
            message=(
                f'"{_label(ruler_item)}" está configurado diferente da template '
                f"({_summarize_difference(expected, actual)})"
            ),
            kind=ruler_item.get("type"),
        )
    ]


def _summarize_difference(expected: Any, actual: Any) -> str:
    """Nomeia os campos divergentes, em vez de despejar os dois `content`."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        field_names = [
            f"{c}: {actual.get(c)!r}, na template {expected.get(c)!r}"
            for c in sorted(set(expected) | set(actual))
            if expected.get(c) != actual.get(c)
        ]
        if field_names:
            return "; ".join(field_names)
    return f"{actual!r}, na template {expected!r}"


def _append_findings(items: Sequence[Dict[str, Any]], scope: str) -> List[Finding]:
    return [
        Finding(
            severity=SEVERITY_INFO,
            scope=scope,
            message=f'"{_label(i)}" não existe na template — é um acréscimo desta API',
            kind=i.get("type"),
            custom_interceptor_id=_custom_id(i),
        )
        for i in items
    ]


def _missing_findings(items: Sequence[Dict[str, Any]], scope: str) -> List[Finding]:
    return [
        Finding(
            severity=SEVERITY_WARNING,
            scope=scope,
            message=(
                f'"{_label(i)}" está na template, mas não é executado aqui'
            ),
            kind=i.get("type"),
            custom_interceptor_id=_custom_id(i),
        )
        for i in items
    ]
