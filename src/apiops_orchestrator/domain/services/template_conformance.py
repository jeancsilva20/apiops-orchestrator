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

from apiops_orchestrator.domain.services.repo_layout import eh_governado

SEVERIDADE_INFO = "INFO"
SEVERIDADE_WARNING = "WARNING"

PONTOS = ("FIRST", "SECOND")


@dataclass(frozen=True)
class Achado:
    severidade: str
    escopo: str
    mensagem: str
    tipo: Optional[str] = None
    custom_interceptor_id: Optional[int] = None


def _normalizar_escalar(valor: Any) -> Any:
    """Forma canônica para COMPARAÇÃO (não para escrita).

    O wire devolve `"quota": "1000"` como string e o repositório pode trazer o
    inteiro. São o mesmo valor: compará-los cruamente acusaria achado falso num
    campo idêntico. A escrita continua preservando a string — são decisões
    independentes.
    """
    if isinstance(valor, bool) or valor is None:
        return valor
    if isinstance(valor, (int, float)):
        return float(valor)
    if isinstance(valor, str):
        texto = valor.strip()
        try:
            return float(texto)
        except ValueError:
            return valor
    return valor


def _normalizar_content(content: Any) -> Any:
    """Normaliza recursivamente, aceitando `content` como JSON serializado."""
    if isinstance(content, str):
        try:
            content = json.loads(content)
        except (TypeError, ValueError):
            return _normalizar_escalar(content)
    if isinstance(content, dict):
        return {k: _normalizar_content(v) for k, v in sorted(content.items())}
    if isinstance(content, list):
        return [_normalizar_content(v) for v in content]
    return _normalizar_escalar(content)


# Pública para a conferência pós-publicação comparar `content` pela mesma regra.
normalizar_content = _normalizar_content


def _custom_id(item: Dict[str, Any]) -> Optional[int]:
    valor = item.get("customInterceptorId")
    if valor is None and item.get("type") == "Custom":
        valor = item.get("id")
    return valor


def _chave(item: Dict[str, Any]) -> Tuple[str, Optional[int]]:
    """Identidade para alinhamento. O `content` fica de fora de propósito:
    um `Log` alterado ainda É o mesmo `Log`, e a diferença é `WARNING` de
    alteração, não um par remoção+append."""
    return (str(item.get("type") or ""), _custom_id(item))


def _nome_do_custom(item: Dict[str, Any]) -> Optional[str]:
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
        nome = content.get("name")
        return str(nome) if nome else None
    return None


def _rotulo(item: Dict[str, Any]) -> str:
    """Identificação do interceptor para o relatório (V-11 §5).

    `Custom #33 — CyberArk and OAuth Autentication` quando o nome é conhecido;
    `Custom #33` quando não é. Tipos nativos saem pelo próprio tipo.
    """
    tipo = item.get("type") or "?"
    cid = _custom_id(item)
    if not cid:
        return str(tipo)
    nome = _nome_do_custom(item)
    return f"{tipo} #{cid} — {nome}" if nome else f"{tipo} #{cid}"


def _governados(itens: Optional[Sequence[Dict[str, Any]]], ponto: str) -> List[Dict[str, Any]]:
    return [
        i
        for i in (itens or [])
        if eh_governado(i.get("executionPoint"))
        and (i.get("executionPoint") or "").upper() == ponto
        and i.get("status") != "REMOVED"
    ]


def comparar(
    fluxo_efetivo: Optional[Sequence[Dict[str, Any]]],
    regua: Optional[Sequence[Dict[str, Any]]],
    escopo: str,
) -> List[Achado]:
    """Compara um escopo com a régua e devolve os achados.

    Nunca levanta exceção e nunca bloqueia: a saída é sempre uma lista.
    """
    achados: List[Achado] = []
    for ponto in PONTOS:
        achados.extend(
            _comparar_ponto(
                _governados(fluxo_efetivo, ponto), _governados(regua, ponto), escopo
            )
        )
    return achados


def _comparar_ponto(
    efetivo: Sequence[Dict[str, Any]], regua: Sequence[Dict[str, Any]], escopo: str
) -> List[Achado]:
    achados: List[Achado] = []
    chaves_efetivo = [_chave(i) for i in efetivo]
    chaves_regua = [_chave(i) for i in regua]

    matcher = difflib.SequenceMatcher(a=chaves_regua, b=chaves_efetivo, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for item_regua, item_efetivo in zip(regua[i1:i2], efetivo[j1:j2]):
                achados.extend(_comparar_content(item_regua, item_efetivo, escopo))
        elif tag == "insert":
            achados.extend(_achados_append(efetivo[j1:j2], escopo))
        elif tag == "delete":
            achados.extend(_achados_ausente(regua[i1:i2], escopo))
        elif tag == "replace":
            achados.extend(_achados_ausente(regua[i1:i2], escopo))
            achados.extend(_achados_append(efetivo[j1:j2], escopo))
    return achados


def _comparar_content(
    item_regua: Dict[str, Any], item_efetivo: Dict[str, Any], escopo: str
) -> List[Achado]:
    # Custom casa por id: mesmo id, mesmo objeto no tenant.
    if item_regua.get("type") == "Custom":
        return []
    esperado = _normalizar_content(item_regua.get("content"))
    obtido = _normalizar_content(item_efetivo.get("content"))
    if esperado == obtido:
        return []
    return [
        Achado(
            severidade=SEVERIDADE_WARNING,
            escopo=escopo,
            mensagem=(
                f'"{_rotulo(item_regua)}" está configurado diferente da template '
                f"({_resumir_diferenca(esperado, obtido)})"
            ),
            tipo=item_regua.get("type"),
        )
    ]


def _resumir_diferenca(esperado: Any, obtido: Any) -> str:
    """Nomeia os campos divergentes, em vez de despejar os dois `content`."""
    if isinstance(esperado, dict) and isinstance(obtido, dict):
        campos = [
            f"{c}: {obtido.get(c)!r}, na template {esperado.get(c)!r}"
            for c in sorted(set(esperado) | set(obtido))
            if esperado.get(c) != obtido.get(c)
        ]
        if campos:
            return "; ".join(campos)
    return f"{obtido!r}, na template {esperado!r}"


def _achados_append(itens: Sequence[Dict[str, Any]], escopo: str) -> List[Achado]:
    return [
        Achado(
            severidade=SEVERIDADE_INFO,
            escopo=escopo,
            mensagem=f'"{_rotulo(i)}" não existe na template — é um acréscimo desta API',
            tipo=i.get("type"),
            custom_interceptor_id=_custom_id(i),
        )
        for i in itens
    ]


def _achados_ausente(itens: Sequence[Dict[str, Any]], escopo: str) -> List[Achado]:
    return [
        Achado(
            severidade=SEVERIDADE_WARNING,
            escopo=escopo,
            mensagem=(
                f'"{_rotulo(i)}" está na template, mas não é executado aqui'
            ),
            tipo=i.get("type"),
            custom_interceptor_id=_custom_id(i),
        )
        for i in itens
    ]


def comparar_deriva_de_override(
    fluxo_efetivo: Optional[Sequence[Dict[str, Any]]],
    fluxo_do_pai: Optional[Sequence[Dict[str, Any]]],
    suprimidos_declarados: int,
    escopo: str,
) -> List[Achado]:
    """Avisa quando um override omite mais do que a supressão declarada (V-25 §4.2).

    A lista completa explícita **congela** o fluxo do pai no momento do import.
    Se o pai ganha um interceptor depois, o escopo que fez override não recebe —
    e o override, que existia para remover um item, vira um escopo que ficou para
    trás em tudo. Não há como evitar a cópia; há como avisar.
    """
    efetivo = [i for pt in PONTOS for i in _governados(fluxo_efetivo, pt)]
    pai = [i for pt in PONTOS for i in _governados(fluxo_do_pai, pt)]
    presentes = {_chave(i) for i in efetivo}
    omitidos = [i for i in pai if _chave(i) not in presentes]

    if len(omitidos) <= suprimidos_declarados:
        return []
    return [
        Achado(
            severidade=SEVERIDADE_WARNING,
            escopo=escopo,
            mensagem=(
                f"este ponto substitui o fluxo herdado e deixa {len(omitidos)} "
                "interceptor(es) de fora, mas a remoção pretendida era de apenas "
                f"{suprimidos_declarados}. O nível acima provavelmente ganhou itens "
                "depois que esta lista foi escrita. Fora: "
                + ", ".join(f'"{_rotulo(i)}"' for i in omitidos)
            ),
        )
    ]
