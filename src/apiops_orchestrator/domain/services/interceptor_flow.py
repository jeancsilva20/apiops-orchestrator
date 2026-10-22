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
    eh_governado,
)

__all__ = [
    "GOVERNED_EXECUTION_POINTS",
    "eh_governado",
    "particionar",
    "chave_interceptor",
    "maior_identificador",
    "identidade",
    "alvo_da_marcacao",
    "fluxo_composto",
    "preparar_contador_idtemp",
    "construir_item_novo",
    "FluxoDoEscopo",
    "resolver_fluxo_declarado",
    "montar_fluxo_do_escopo",
]


def chave_interceptor(item: Dict[str, Any]) -> Tuple[str, Optional[int], str]:
    """Identidade declarativa de um interceptor, para casamento entre repo e wire.

    `Custom` é identificado pelo `customInterceptorId`: mesmo id, mesmo objeto no
    tenant. Os tipos nativos não têm id — o que os distingue é o tipo e o ponto
    de execução, e a diferença de configuração mora no `content`, comparado pela
    conformidade.
    """
    tipo = str(item.get("type") or "")
    custom_id = item.get("customInterceptorId")
    if custom_id is None and tipo == "Custom":
        custom_id = item.get("id")
    ponto = str(item.get("executionPoint") or "").upper()
    return (tipo, custom_id, ponto)


def particionar(
    remotos: Optional[Sequence[Dict[str, Any]]],
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
    governados: List[Dict[str, Any]] = []
    preservados: List[Dict[str, Any]] = []
    for item in remotos or []:
        if eh_governado(item.get("executionPoint")):
            governados.append(item)
        else:
            preservados.append(item)
    return governados, preservados


def maior_identificador(no: Any) -> int:
    """Maior `id`, `idTemp` ou `position` encontrado em toda a árvore do payload.

    É o piso do contador global de `idTemp` (W-9): o `idTemp` é único no
    **payload inteiro**, não no escopo. Dois itens novos em escopos diferentes
    que compartilhem o valor fazem o Manager **descartar um deles**, devolvendo
    HTTP 200 — uma das três perdas silenciosas observadas.

    A varredura é profunda de propósito: `interceptors` aparecem na raiz, em cada
    recurso e em cada operação, e o contador precisa enxergar todos.
    """
    maior = 0
    pilha = [no]
    while pilha:
        atual = pilha.pop()
        if isinstance(atual, dict):
            for campo in ("id", "idTemp", "position"):
                valor = atual.get(campo)
                if isinstance(valor, bool):
                    continue
                if isinstance(valor, int) and valor > maior:
                    maior = valor
                elif isinstance(valor, str) and valor.isdigit():
                    maior = max(maior, int(valor))
            pilha.extend(atual.values())
        elif isinstance(atual, (list, tuple)):
            pilha.extend(atual)
    return maior


def identidade(item: Dict[str, Any]) -> Any:
    """`id` do item ou, no item que ainda não existe no Manager, o `idTemp`."""
    return item["id"] if item.get("id") is not None else item.get("idTemp")


def alvo_da_marcacao(marcacao: Dict[str, Any]) -> Any:
    """Identidade do item herdado que a marcação `REMOVED` aponta."""
    return identidade(marcacao.get("parent") or {})


def fluxo_composto(
    proprios: Optional[Sequence[Dict[str, Any]]],
    herdado: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Fluxo governado que o escopo executa: o herdado, menos os itens marcados
    como removidos no escopo, mais os itens próprios em ordem de `position`."""
    governados, _ = particionar(proprios)
    removidos = {
        alvo_da_marcacao(i) for i in governados if i.get("status") == "REMOVED"
    }
    removidos.discard(None)
    mantidos = [i for i in herdado or [] if identidade(i) not in removidos]
    proprios_vivos = sorted(
        (i for i in governados if i.get("status") != "REMOVED"),
        key=lambda i: i.get("position") or 0,
    )
    return mantidos + proprios_vivos


# --------------------------------------------------------------------------- publish


# Piso dos `idTemp`, acima de qualquer id que o Manager gere. O item novo vai com
# `id` igual ao `idTemp` (ver `construir_item_novo`), então o número temporário
# não pode coincidir com o id de um item existente nem com os ids que o Manager
# gera no mesmo PUT. A UI usa números dessa ordem (o relógio em milissegundos).
PISO_IDTEMP = 1_000_000_000_000


def preparar_contador_idtemp(payload: Any) -> "Iterator[int]":
    """Contador GLOBAL de `idTemp`, acima de tudo que já existe e do piso.

    **W-9**: o `idTemp` é único no **payload inteiro**, não no escopo. Dois itens
    novos em escopos diferentes que compartilhem o valor fazem o Manager
    **descartar um deles**, devolvendo HTTP 200.
    """
    proximo = max(maior_identificador(payload) + 1, PISO_IDTEMP)
    while True:
        yield proximo
        proximo += 1


def construir_item_novo(
    *,
    tipo: str,
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
      `PISO_IDTEMP`, então não coincide com o id de um item existente;
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
        "type": tipo,
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
class FluxoDoEscopo:
    """O que um escopo guarda e o que executa, decidido pelo repositório.

    * `proprios` — itens declarados, que o escopo guarda;
    * `quebra` — o escopo marca como removido todo item que o pai executa;
    * `efetivo` — o que o escopo executa.
    """

    proprios: List[Dict[str, Any]] = field(default_factory=list)
    efetivo: List[Dict[str, Any]] = field(default_factory=list)
    quebra: bool = False

    @property
    def heranca_pura(self) -> bool:
        """Sem itens próprios e sem quebra: a lista vai vazia e o escopo herda."""
        return not self.proprios and not self.quebra


def resolver_fluxo_declarado(
    declarados: Optional[Sequence[Dict[str, Any]]],
    herdado: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    inherit: bool = True,
    raiz: bool = False,
) -> FluxoDoEscopo:
    """Decide o que UM escopo guarda e executa.

    `herdado` é o `efetivo` do escopo acima. A raiz guarda e executa o que o
    `all.yaml` declara.

    | `inherit` | guarda | executa |
    |---|---|---|
    | `true` | os declarados | o herdado + os declarados |
    | `false` | os declarados + marcação de todo o herdado | os declarados |
    """
    declarados = list(declarados or [])
    herdado = list(herdado or [])

    if raiz:
        return FluxoDoEscopo(proprios=declarados, efetivo=declarados)
    if inherit:
        return FluxoDoEscopo(proprios=declarados, efetivo=herdado + declarados)
    return FluxoDoEscopo(proprios=declarados, efetivo=declarados, quebra=True)


def montar_fluxo_do_escopo(
    fluxo: FluxoDoEscopo,
    remotos: Optional[Sequence[Dict[str, Any]]],
    *,
    gerar_idtemp: Optional["Iterator[int]"] = None,
    resolver_content: Optional[Any] = None,
    herdado: Optional[Sequence[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Escreve no formato do PUT de revisão o que o escopo guarda.

    Os itens próprios reaproveitam a identidade técnica do remoto (`id`,
    `idTemp`, `status`, `parentType`) e levam o `content` e a ordem do YAML; só
    o `Custom` mantém o `content` do Manager (V-11 §4). O escopo reusa as
    posições que já ocupa, os novos estendem a faixa e o conjunto segue a ordem
    declarada. Com `quebra`, cada item de `herdado` — o fluxo que o pai executa
    neste payload (`fluxo_composto`) — ganha uma marcação de remoção.
    """
    gerar_idtemp = gerar_idtemp or preparar_contador_idtemp({})
    governados, preservados = particionar(remotos)

    if fluxo.heranca_pura:
        # V-22: o não governado continua voltando intacto.
        return list(preservados)

    # Pool de ocorrências por chave. Um `dict` chave→item perderia repetições, e
    # fluxos reais REPETEM tipo: `/health-check` tem dois `Log` em FIRST, e a
    # própria régua também. Deduplicar aqui descartaria um deles no payload — a
    # mesma classe de perda silenciosa que a conferência existe para pegar.
    #
    # O tombstone fica FORA do pool: ele tem a mesma chave do item que suprime, e
    # reaproveitá-lo publicaria um `status: REMOVED` no lugar do item vivo. As
    # marcações de remoção são remontadas à parte, a partir do herdado.
    disponiveis: Dict[Any, List[Dict[str, Any]]] = {}
    for item in governados:
        if item.get("status") == "REMOVED":
            continue
        disponiveis.setdefault(chave_interceptor(item), []).append(item)

    def consumir(chave: Any) -> Optional[Dict[str, Any]]:
        fila = disponiveis.get(chave)
        return fila.pop(0) if fila else None

    def content_declarado(declarado: Dict[str, Any]) -> Any:
        if resolver_content is not None:
            return resolver_content(declarado)
        return declarado.get("content")

    saida: List[Dict[str, Any]] = []
    posicao = max([i.get("position") or 0 for i in governados] or [0])

    for declarado in fluxo.proprios:
        existente = consumir(chave_interceptor(declarado))
        if existente is not None:
            # Cópia: o remoto pertence a quem chamou e não pode ser alterado.
            item = copy.deepcopy(existente)
            if declarado.get("type") != "Custom":
                item["content"] = _content_do_wire(content_declarado(declarado))
            saida.append(item)
            continue
        posicao += 1
        saida.append(
            construir_item_novo(
                tipo=str(declarado.get("type")),
                execution_point=str(declarado.get("executionPoint") or "FIRST"),
                idtemp=next(gerar_idtemp),
                position=posicao,
                content=content_declarado(declarado),
                custom_interceptor_id=declarado.get("customInterceptorId")
                or (declarado.get("id") if declarado.get("type") == "Custom" else None),
            )
        )

    _ordenar_posicoes_como_declarado(saida)

    if fluxo.quebra:
        saida += _marcar_como_removido(herdado or [], governados, gerar_idtemp)

    # V-22: o não governado volta intacto, sempre.
    return saida + list(preservados)


def _marcar_como_removido(
    herdado: Sequence[Dict[str, Any]],
    remotos: Sequence[Dict[str, Any]],
    gerar_idtemp: "Iterator[int]",
) -> List[Dict[str, Any]]:
    """Uma marcação de remoção para cada item herdado, reaproveitando a que o
    escopo já tiver para o mesmo item. Item que entra no pai neste payload é
    apontado pelo `idTemp`."""
    existentes = {
        alvo_da_marcacao(i): i for i in remotos if i.get("status") == "REMOVED"
    }
    marcacoes: List[Dict[str, Any]] = []
    for item in herdado:
        alvo = identidade(item)
        if alvo is None:
            continue
        existente = existentes.pop(alvo, None)
        if existente is not None:
            marcacao = copy.deepcopy(existente)
        else:
            marcacao = construir_item_novo(
                tipo=str(item.get("type")),
                execution_point=str(item.get("executionPoint") or "FIRST"),
                idtemp=next(gerar_idtemp),
                position=item.get("position") or 0,
                content=item.get("content"),
                custom_interceptor_id=item.get("customInterceptorId"),
                parent_type=item.get("parentType") or "REVISION",
            )
            marcacao["status"] = "REMOVED"
            if item.get("id") is not None:
                marcacao["parent"] = {"id": item["id"], "idTemp": item["id"]}
            else:
                marcacao["parent"] = {"id": None, "idTemp": item.get("idTemp")}
        marcacao["position"] = item.get("position")
        marcacoes.append(marcacao)
    return marcacoes


def _content_do_wire(content: Any) -> Any:
    """O wire carrega `content` como STRING JSON (ver `construir_item_novo`)."""
    if isinstance(content, (dict, list)):
        return json.dumps(content, ensure_ascii=False)
    return content


def _ordenar_posicoes_como_declarado(itens: List[Dict[str, Any]]) -> None:
    """Redistribui, por execution point, as posições do escopo na ordem da lista.

    A plataforma executa pela `position`, não pela ordem da lista (W-3, D-8).
    Manter a posição remota de um item reusado ignoraria uma reordenação feita
    no YAML, e um item inserido no meio iria para o fim. Os números usados são
    os mesmos que o escopo já ocupa — só a atribuição muda.
    """
    for ponto in GOVERNED_EXECUTION_POINTS:
        do_ponto = [i for i in itens if str(i.get("executionPoint") or "").upper() == ponto]
        numeros = sorted(i.get("position") or 0 for i in do_ponto)
        for item, numero in zip(do_ponto, numeros):
            item["position"] = numero
