"""Aritmética de identidade e partição dos fluxos de interceptors.

Lógica pura, sem rede: recebe dados já lidos e devolve dados. É aqui que moram
as nove regras de wire (W-1 a W-9) observadas contra a plataforma, porque todas
são determinísticas.

A regra de identidade, condensada:

    position  ->  do ESCOPO    (por escopo e execution point; contínua entre
                                escopos no wire; nunca renumerada 1..N — os
                                números do escopo seguem a ordem do YAML)
    idTemp    ->  do PAYLOAD   (único em toda a chamada; contador global)
    id        ->  null em item novo; preservado em item existente

A **resolução da herança** mora aqui desde a V-27: o fluxo efetivo de um escopo é
computado a partir do repositório (`all.yaml` → `resource.yaml` → operação) e
publicado resolvido. A plataforma guarda; não decide.
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
    "fluxo_efetivo",
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


def fluxo_efetivo(
    proprios: Optional[Sequence[Dict[str, Any]]],
    herdado: Optional[Sequence[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Fluxo que um escopo realmente executa.

    Combina duas regras observadas que, juntas, dão uma conta simples:

    * **W-4** — o Manager guarda o fluxo **resolvido**, não o delta. A lista de um
      escopo já é o que ele executa por inteiro.
    * **W-5** — lista **vazia** significa HERDAR. "Escopo sem fluxo" não existe na
      plataforma.

    Logo: lista própria não vazia **é** o efetivo; vazia, o efetivo é o do pai.
    Somar as duas conta em dobro — erro fácil, porque a intuição de "override
    soma ao herdado" é exatamente o contrário do que a plataforma faz.

    O **tombstone** é o terceiro caso, e o mais fácil de perder: um escopo que
    só carrega itens `status: REMOVED` tem lista de presentes vazia, mas NÃO
    herda o fluxo do pai inteiro — herda o fluxo do pai **menos** os itens que
    o tombstone aponta por `parent.id` (V-25 §2.1). Ignorar isso faria a
    supressão desaparecer da conformidade: o comparador veria o item como
    executado quando ele não é.
    """
    governados, _ = particionar(proprios)
    presentes = [i for i in governados if i.get("status") != "REMOVED"]
    if presentes:
        return presentes

    herdados_governados, _ = particionar(herdado)
    efetivo_do_pai = [
        i for i in herdados_governados if i.get("status") != "REMOVED"
    ]

    suprimidos = {
        (t.get("parent") or {}).get("id")
        for t in governados
        if t.get("status") == "REMOVED" and (t.get("parent") or {}).get("id") is not None
    }
    if not suprimidos:
        return efetivo_do_pai
    return [i for i in efetivo_do_pai if i.get("id") not in suprimidos]


# --------------------------------------------------------------------------- publish


def preparar_contador_idtemp(payload: Any) -> "Iterator[int]":
    """Contador GLOBAL de `idTemp`, começando acima de tudo que já existe.

    **W-9**: o `idTemp` é único no **payload inteiro**, não no escopo. Dois itens
    novos em escopos diferentes que compartilhem o valor fazem o Manager
    **descartar um deles**, devolvendo HTTP 200 — foi assim que um `Custom` da
    raiz sumiu sem erro.

    O contador é um só, compartilhado por todos os escopos. Calcular "a próxima
    posição livre" por escopo é exatamente o bug.
    """
    proximo = maior_identificador(payload) + 1
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
    * `id` vai **nulo**: o item ainda não existe, e inventar um id o faria
      colidir com outro;
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
        "id": None,
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
    """Fluxo que um escopo deve executar, computado a partir do REPOSITÓRIO.

    A V-27 tirou a resolução da herança da plataforma e a trouxe para cá: o
    efetivo de um escopo é o do seu pai **no repositório** combinado com o que
    ele declara, e não o que a plataforma guardava no escopo.

    * `efetivo` — a lista resolvida, que é o que a conformidade compara;
    * `heranca_pura` — o efetivo é **exatamente** o do pai. A lista vai VAZIA no
      wire: é a codificação compacta da mesma resposta (V-27 §2), e mantém a
      propagação viva quando o `all.yaml` muda;
    * `contraditorio` — `inherit: false` sem itens. A plataforma não sabe
      representar "escopo que não executa nada" (T06), então isso vira aviso.
    """

    efetivo: List[Dict[str, Any]] = field(default_factory=list)
    heranca_pura: bool = False
    contraditorio: bool = False


def resolver_fluxo_declarado(
    declarados: Optional[Sequence[Dict[str, Any]]],
    herdado: Optional[Sequence[Dict[str, Any]]] = None,
    *,
    inherit: bool = True,
    raiz: bool = False,
) -> FluxoDoEscopo:
    """Resolve o fluxo de UM escopo a partir do repositório (V-27 §2).

    `herdado` é o `efetivo` do escopo acima — também computado daqui, de modo
    que a resolução desce `all.yaml` → `resource.yaml` → arquivo de operação.

    | declarado | `inherit` | efetivo | no wire |
    |---|---|---|---|
    | vazio | `true` | o do pai | `[]` |
    | com itens | `true` | o do pai **+** os declarados | lista completa |
    | com itens | `false` | exatamente os declarados | lista completa |
    | vazio | `false` | o do pai (contraditório) | `[]` + aviso |

    A raiz não herda de ninguém: seu efetivo é o que o `all.yaml` declara, e
    `inherit` ali é informativo.
    """
    declarados = list(declarados or [])
    herdado = list(herdado or [])

    if raiz:
        return FluxoDoEscopo(efetivo=declarados)

    if not declarados:
        # Nos dois casos a plataforma recebe `[]` e volta a herdar; o que muda é
        # se o repositório pediu isso (`inherit: true`) ou se escreveu algo que
        # ela não sabe representar (`inherit: false`).
        return FluxoDoEscopo(
            efetivo=herdado, heranca_pura=True, contraditorio=not inherit
        )

    if inherit:
        return FluxoDoEscopo(efetivo=herdado + declarados)
    return FluxoDoEscopo(efetivo=declarados)


def montar_fluxo_do_escopo(
    fluxo: FluxoDoEscopo,
    remotos: Optional[Sequence[Dict[str, Any]]],
    *,
    gerar_idtemp: Optional["Iterator[int]"] = None,
    resolver_content: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """Traduz um `FluxoDoEscopo` já resolvido para a lista do wire.

    Aqui não se decide mais **o que** o escopo executa — isso saiu para
    `resolver_fluxo_declarado` (V-27). O que resta é casar o resolvido com o que
    a plataforma já tem, para reaproveitar **identidade técnica**: `id`,
    `idTemp`, `status`, `parentType`. Configuração e ordem vêm do repositório,
    que prevalece em tudo o que declara (V-22 §3, D14):

    * `content` de tipo nativo vem do YAML — nele, o `content` **é** a
      configuração (V-11 §4). Só o `Custom` mantém o do Manager: mesmo id é o
      mesmo objeto no tenant;
    * a ordem de cada execution point é a do YAML. Os números de `position` não
      são renumerados 1..N (W-3) — o escopo reusa os que já ocupa, e os itens
      novos estendem a faixa com `max + 1`; o conjunto é redistribuído na ordem
      declarada. O que não existe nasce com `idTemp`.
    """
    gerar_idtemp = gerar_idtemp or preparar_contador_idtemp({})
    governados, preservados = particionar(remotos)

    if fluxo.heranca_pura:
        # Lista governada vazia: a plataforma resolve para o pai, que neste
        # mesmo PUT já recebeu o fluxo que o repositório computou (V-27 §2).
        # V-22: o não governado continua voltando intacto.
        return list(preservados)

    # Pool de ocorrências por chave. Um `dict` chave→item perderia repetições, e
    # fluxos reais REPETEM tipo: `/health-check` tem dois `Log` em FIRST, e a
    # própria régua também. Deduplicar aqui descartaria um deles no payload — a
    # mesma classe de perda silenciosa que a conferência existe para pegar.
    #
    # O tombstone fica FORA do pool: ele tem a mesma chave do item que suprime, e
    # reaproveitá-lo publicaria um `status: REMOVED` no lugar do item vivo. Sob a
    # V-27 a supressão se escreve por omissão da lista, não por tombstone.
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

    for declarado in fluxo.efetivo:
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

    # V-22: o não governado volta intacto, sempre.
    return saida + list(preservados)


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
