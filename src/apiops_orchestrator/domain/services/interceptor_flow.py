"""Identidade, partição e composição dos fluxos de interceptors.

Lógica pura, sem rede: recebe dados já lidos e devolve dados.

    position  ->  do ESCOPO    (ordena só dentro do escopo; os números do escopo
                                seguem a ordem do YAML)
    idTemp    ->  do PAYLOAD   (único em toda a chamada; contador global)
    id        ->  null em item novo; preservado em item existente

Cada escopo guarda os itens próprios e as marcações `REMOVED` do que deixa de
herdar; o Manager executa o que o pai executa, menos o marcado, mais o próprio
(V-28).
"""

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Sequence, Tuple

from apiops_orchestrator.domain.services.repo_layout import (
    GOVERNED_EXECUTION_POINTS,
    is_governed,
)

__all__ = [
    "GOVERNED_EXECUTION_POINTS",
    "is_governed",
    "partition",
    "interceptor_key",
    "largest_identifier",
    "identity",
    "tombstone_target",
    "composed_flow",
    "prepare_idtemp_counter",
    "build_new_item",
    "ScopeFlow",
    "resolve_declared_flow",
    "assemble_scope_flow",
]


def interceptor_key(item: Dict[str, Any]) -> Tuple[str, Optional[int], str]:
    """Identidade declarativa de um interceptor, para casamento entre repo e wire.

    `Custom` é identificado pelo `customInterceptorId`: mesmo id, mesmo objeto no
    tenant. Os tipos nativos não têm id — o que os distingue é o tipo e o ponto
    de execução, e a diferença de configuração mora no `content`, comparado pela
    conformidade.
    """
    kind = str(item.get("type") or "")
    custom_id = item.get("customInterceptorId")
    if custom_id is None and kind == "Custom":
        custom_id = item.get("id")
    point = str(item.get("executionPoint") or "").upper()
    return (kind, custom_id, point)


def partition(
    remote_resources: Optional[Sequence[Dict[str, Any]]],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Separa os interceptors remotos em **governados** e **preservados** (V-22).

    Governado é o que está em `FIRST` ou `SECOND`: é o que o repositório declara
    e o que entra na conformidade com a régua.

    Preservado é todo o resto. Ele **não** aparece no YAML, **não** é comparado
    com a régua e tem de voltar **intacto** na publicação — o repositório não é
    autoridade sobre ele. Omiti-lo do payload o apagaria.

    A ordem relativa é mantida nas duas listas, e os itens não são copiados nem
    normalizados: o preservado volta como veio.
    """
    governed: List[Dict[str, Any]] = []
    preserved: List[Dict[str, Any]] = []
    for item in remote_resources or []:
        if is_governed(item.get("executionPoint")):
            governed.append(item)
        else:
            preserved.append(item)
    return governed, preserved


def largest_identifier(no: Any) -> int:
    """Maior `id`, `idTemp` ou `position` encontrado em toda a árvore do payload.

    É o piso do contador global de `idTemp` (W-9): o `idTemp` é único no
    **payload inteiro**, não no escopo. Dois itens novos em escopos diferentes
    que compartilhem o valor fazem o Manager **descartar um deles**, devolvendo
    HTTP 200 — uma das três perdas silenciosas observadas.

    A varredura é profunda de propósito: `interceptors` aparecem na raiz, em cada
    recurso e em cada operação, e o contador precisa enxergar todos.
    """
    largest = 0
    stack = [no]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for field_name in ("id", "idTemp", "position"):
                value = current.get(field_name)
                if isinstance(value, bool):
                    continue
                if isinstance(value, int) and value > largest:
                    largest = value
                elif isinstance(value, str) and value.isdigit():
                    largest = max(largest, int(value))
            stack.extend(current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
    return largest


def identity(item: Dict[str, Any]) -> Any:
    """`id` do item ou, no item que ainda não existe no Manager, o `idTemp`."""
    return item["id"] if item.get("id") is not None else item.get("idTemp")


def tombstone_target(tombstone: Dict[str, Any]) -> Any:
    """Identidade do item herdado que a marcação `REMOVED` aponta."""
    return identity(tombstone.get("parent") or {})


def composed_flow(
    own: Optional[Sequence[Dict[str, Any]]],
    inherited: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Fluxo governado que o escopo executa: o herdado, menos os itens marcados
    como removidos no escopo, mais os itens próprios em ordem de `position`."""
    governed, _ = partition(own)
    removed = {
        tombstone_target(i) for i in governed if i.get("status") == "REMOVED"
    }
    removed.discard(None)
    kept = [i for i in inherited or [] if identity(i) not in removed]
    live_own = sorted(
        (i for i in governed if i.get("status") != "REMOVED"),
        key=lambda i: i.get("position") or 0,
    )
    return kept + live_own


# --------------------------------------------------------------------------- publish


# Piso dos `idTemp`, acima de qualquer id que o Manager gere. O item novo vai com
# `id` igual ao `idTemp` (ver `build_new_item`), então o número temporário
# não pode coincidir com o id de um item existente nem com os ids que o Manager
# gera no mesmo PUT. A UI usa números dessa ordem (o relógio em milissegundos).
IDTEMP_FLOOR = 1_000_000_000_000


def prepare_idtemp_counter(payload: Any) -> "Iterator[int]":
    """Contador GLOBAL de `idTemp`, acima de tudo que já existe e do piso.

    **W-9**: o `idTemp` é único no **payload inteiro**, não no escopo. Dois itens
    novos em escopos diferentes que compartilhem o valor fazem o Manager
    **descartar um deles**, devolvendo HTTP 200.
    """
    next_id = max(largest_identifier(payload) + 1, IDTEMP_FLOOR)
    while True:
        yield next_id
        next_id += 1


def build_new_item(
    *,
    kind: str,
    execution_point: str,
    idtemp: int,
    position: int,
    content: Any = None,
    custom_interceptor_id: Optional[int] = None,
    parent_type: str = "REVISION",
) -> Dict[str, Any]:
    """Monta um interceptor que o repositório declara e o remoto não tem.

    Três regras do wire, todas observadas:

    * **W-1** — `idTemp` é **obrigatório**. Sem ele, ou com `None`, o Manager
      devolve **500** com `errors: []`;
    * `id` vai igual ao `idTemp`, como a UI faz. Com `id` nulo, a marcação de
      uma rota para item novo do recurso some quando o recurso também marca um
      item novo da raiz no mesmo PUT (bateria da 425). O `idTemp` vem acima de
      `IDTEMP_FLOOR`, então não coincide com o id de um item existente;
    * `customInterceptorId` é **preservado** — é a referência ao script no tenant.
    """
    if idtemp is None:
        raise ValueError(
            "idTemp é obrigatório em item novo (W-1): sem ele o Manager devolve "
            "500 com a lista de erros vazia"
        )
    # O wire carrega `content` como STRING JSON, não como objeto: um `Log` real
    # chega como '{"acceptedTerms": true, ...}'. Enviar o dict do YAML cru faz o
    # Manager recusar com HTTP 400 — observado nos cenários T07, T08 e T11.
    if isinstance(content, (dict, list)):
        content = json.dumps(content, ensure_ascii=False)
    return {
        "id": idtemp,
        "idTemp": idtemp,
        "position": position,
        "type": kind,
        "content": content,
        "executionPoint": execution_point,
        "status": "REFERENCE",
        "parent": None,
        "parentType": parent_type,
        "resource": None,
        "operation": None,
        "planId": None,
        "customInterceptorId": custom_interceptor_id,
    }


@dataclass(frozen=True)
class ScopeFlow:
    """O que um escopo guarda e o que executa, decidido pelo repositório.

    * `own` — itens declarados, que o escopo guarda;
    * `breaks_inheritance` — o escopo marca como removido todo item que o pai executa;
    * `effective` — o que o escopo executa.
    """

    own: List[Dict[str, Any]] = field(default_factory=list)
    effective: List[Dict[str, Any]] = field(default_factory=list)
    breaks_inheritance: bool = False

    @property
    def pure_inheritance(self) -> bool:
        """Sem itens próprios e sem quebra: a lista vai vazia e o escopo herda."""
        return not self.own and not self.breaks_inheritance


def resolve_declared_flow(
    declared: Optional[Sequence[Dict[str, Any]]],
    inherited: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    inherit: bool = True,
    root: bool = False,
) -> ScopeFlow:
    """Decide o que UM escopo guarda e executa.

    `inherited` é o `effective` do escopo acima. A raiz guarda e executa o que o
    `all.yaml` declara.

    | `inherit` | guarda | executa |
    |---|---|---|
    | `true` | os declarados | o herdado + os declarados |
    | `false` | os declarados + marcação de todo o herdado | os declarados |
    """
    declared = list(declared or [])
    inherited = list(inherited or [])

    if root:
        return ScopeFlow(own=declared, effective=declared)
    if inherit:
        return ScopeFlow(own=declared, effective=inherited + declared)
    return ScopeFlow(own=declared, effective=declared, breaks_inheritance=True)


def assemble_scope_flow(
    flow: ScopeFlow,
    remote_resources: Optional[Sequence[Dict[str, Any]]],
    *,
    generate_idtemp: Optional["Iterator[int]"] = None,
    resolver_content: Optional[Any] = None,
    inherited: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Escreve no formato do PUT de revisão o que o escopo guarda.

    Os itens próprios reaproveitam a identidade técnica do remoto (`id`,
    `idTemp`, `status`, `parentType`) e levam o `content` e a ordem do YAML; só
    o `Custom` mantém o `content` do Manager (V-11 §4). O escopo reusa as
    posições que já ocupa, os novos estendem a faixa e o conjunto segue a ordem
    declarada. Com `breaks_inheritance`, cada item de `inherited` — o fluxo que o pai executa
    neste payload (`composed_flow`) — ganha uma marcação de remoção.
    """
    generate_idtemp = generate_idtemp or prepare_idtemp_counter({})
    governed, preserved = partition(remote_resources)

    if flow.pure_inheritance:
        # V-22: o não governado continua voltando intacto.
        return list(preserved)

    # Pool de ocorrências por chave. Um `dict` chave→item perderia repetições, e
    # fluxos reais REPETEM tipo: `/health-check` tem dois `Log` em FIRST, e a
    # própria régua também. Deduplicar aqui descartaria um deles no payload — a
    # mesma classe de perda silenciosa que a conferência existe para pegar.
    #
    # O tombstone fica FORA do pool: ele tem a mesma chave do item que suprime, e
    # reaproveitá-lo publicaria um `status: REMOVED` no lugar do item vivo. As
    # marcações de remoção são remontadas à parte, a partir do herdado.
    available: Dict[Any, List[Dict[str, Any]]] = {}
    for item in governed:
        if item.get("status") == "REMOVED":
            continue
        available.setdefault(interceptor_key(item), []).append(item)

    def consume(key: Any) -> Optional[Dict[str, Any]]:
        queue = available.get(key)
        return queue.pop(0) if queue else None

    def declared_content(declared: Dict[str, Any]) -> Any:
        if resolver_content is not None:
            return resolver_content(declared)
        return declared.get("content")

    output: List[Dict[str, Any]] = []
    position = max([i.get("position") or 0 for i in governed] or [0])

    for declared in flow.own:
        existing_item = consume(interceptor_key(declared))
        if existing_item is not None:
            # Cópia: o remoto pertence a quem chamou e não pode ser alterado.
            item = copy.deepcopy(existing_item)
            if declared.get("type") != "Custom":
                item["content"] = _wire_content(declared_content(declared))
            output.append(item)
            continue
        position += 1
        output.append(
            build_new_item(
                kind=str(declared.get("type")),
                execution_point=str(declared.get("executionPoint") or "FIRST"),
                idtemp=next(generate_idtemp),
                position=position,
                content=declared_content(declared),
                custom_interceptor_id=declared.get("customInterceptorId")
                or (declared.get("id") if declared.get("type") == "Custom" else None),
            )
        )

    _sort_positions_as_declared(output)

    if flow.breaks_inheritance:
        output += _mark_as_removed(inherited or [], governed, generate_idtemp)

    # V-22: o não governado volta intacto, sempre.
    return output + list(preserved)


def _mark_as_removed(
    inherited: Sequence[Dict[str, Any]],
    remote_resources: Sequence[Dict[str, Any]],
    generate_idtemp: "Iterator[int]",
) -> List[Dict[str, Any]]:
    """Uma marcação de remoção para cada item herdado, reaproveitando a que o
    escopo já tiver para o mesmo item. Item que entra no pai neste payload é
    apontado pelo `idTemp`."""
    existing = {
        tombstone_target(i): i for i in remote_resources if i.get("status") == "REMOVED"
    }
    tombstones: List[Dict[str, Any]] = []
    for item in inherited:
        target = identity(item)
        if target is None:
            continue
        existing_item = existing.pop(target, None)
        if existing_item is not None:
            tombstone = copy.deepcopy(existing_item)
        else:
            tombstone = build_new_item(
                kind=str(item.get("type")),
                execution_point=str(item.get("executionPoint") or "FIRST"),
                idtemp=next(generate_idtemp),
                position=item.get("position") or 0,
                content=item.get("content"),
                custom_interceptor_id=item.get("customInterceptorId"),
                parent_type=item.get("parentType") or "REVISION",
            )
            tombstone["status"] = "REMOVED"
            if item.get("id") is not None:
                tombstone["parent"] = {"id": item["id"], "idTemp": item["id"]}
            else:
                tombstone["parent"] = {"id": None, "idTemp": item.get("idTemp")}
        tombstone["position"] = item.get("position")
        tombstones.append(tombstone)
    return tombstones


def _wire_content(content: Any) -> Any:
    """O wire carrega `content` como STRING JSON (ver `build_new_item`)."""
    if isinstance(content, (dict, list)):
        return json.dumps(content, ensure_ascii=False)
    return content


def _sort_positions_as_declared(items: List[Dict[str, Any]]) -> None:
    """Redistribui, por execution point, as posições do escopo na ordem da lista.

    A plataforma executa pela `position`, não pela ordem da lista (W-3, D-8).
    Manter a posição remota de um item reusado ignoraria uma reordenação feita
    no YAML, e um item inserido no meio iria para o fim. Os números usados são
    os mesmos que o escopo já ocupa — só a atribuição muda.
    """
    for point in GOVERNED_EXECUTION_POINTS:
        at_point = [i for i in items if str(i.get("executionPoint") or "").upper() == point]
        numbers = sorted(i.get("position") or 0 for i in at_point)
        for item, number in zip(at_point, numbers):
            item["position"] = number
