"""Montagem do payload da revisão e conferência pós-publicação.

Lógica pura. O payload nasce como **cópia profunda do estado remoto** e recebe
só o que o repositório declara — assim tudo que o repositório não governa volta
intacto, sem precisar ser enumerado.

O fluxo de interceptors é a exceção deliberada: desde a **V-27** ele é
**resolvido aqui**, descendo `all.yaml` → `resource.yaml` → operação, e vai para
o wire já resolvido. A plataforma deixou de decidir o que cada escopo executa.

É por construção que `workflowId` e `workflowStageId` são preservados (D-020):
eles viajam na cópia, e nada aqui os reescreve.
"""

import copy
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from apiops_orchestrator.domain.services.interceptor_flow import (
    FluxoDoEscopo,
    montar_fluxo_do_escopo,
    particionar,
    preparar_contador_idtemp,
    resolver_fluxo_declarado,
)


@dataclass(frozen=True)
class PayloadMontado:
    corpo: Dict[str, Any]
    avisos: List[str] = field(default_factory=list)


def _declarados(bloco: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Itens declarados no YAML, já com o execution point derivado da chave."""
    saida = []
    for chave, ponto in (
        ("interceptors_request", "FIRST"),
        ("interceptors_response", "SECOND"),
    ):
        for item in bloco.get(chave) or []:
            tipo = item.get("type")
            saida.append(
                {
                    "type": tipo,
                    "executionPoint": ponto,
                    "content": item.get("content"),
                    "customInterceptorId": item.get("id") if tipo == "Custom" else None,
                }
            )
    return saida


def _destino(bloco: Dict[str, Any]) -> Tuple[Optional[str], Optional[Any]]:
    destino = bloco.get("destination") or {}
    if not isinstance(destino, dict):
        return None, None
    return destino.get("url") or None, destino.get("timeout")


def _vivos(remoto: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Itens governados que o escopo tem de fato na plataforma, sem tombstones."""
    proprios = particionar((remoto or {}).get("interceptors"))[0]
    return [i for i in proprios if i.get("status") != "REMOVED"]


def _rotular(itens: Sequence[Dict[str, Any]]) -> str:
    return ", ".join(
        f"{i.get('type')}#{i['customInterceptorId']}"
        if i.get("customInterceptorId")
        else str(i.get("type"))
        for i in itens
    )


def _avisos_do_escopo(
    fluxo: FluxoDoEscopo,
    remoto: Optional[Dict[str, Any]],
    escopo: str,
    *,
    raiz: bool = False,
) -> List[str]:
    """O que o dev precisa saber sobre o efeito da declaração neste escopo.

    Sob a V-27 o repositório resolve o fluxo e a plataforma passa a ser
    sobrescrita. Isso transforma duas situações antes inócuas em **remoções**, e
    nenhuma delas pode acontecer calada.
    """
    avisos: List[str] = []
    proprios = _vivos(remoto)

    if fluxo.contraditorio:
        avisos.append(
            f"{escopo}: o arquivo declara `inherit: false` mas não lista nenhum "
            "interceptor. O Manager não consegue representar \"não executa nada\" — "
            "lista vazia sempre significa herdar. Na prática este ponto vai continuar "
            "herdando o fluxo do nível acima.\n"
            "Para que ele execute outra coisa, liste os interceptors que devem valer "
            "aqui."
        )

    if raiz:
        # A raiz não herda de ninguém: `[]` ali não significa "herda", significa
        # "sem fluxo". É a remoção mais cara que o comando pode provocar — e o
        # rótulo do escopo ("raiz da revision") não ajuda ninguém, então a
        # mensagem fala do `all.yaml` diretamente.
        if not fluxo.efetivo and proprios:
            avisos.append(
                "O `all.yaml` não declara nenhum interceptor, e a API tem "
                f"{len(proprios)} hoje no Manager ({_rotular(proprios)}). O "
                "`all.yaml` é o nível mais alto e não herda de ninguém, então ao "
                "publicar esses interceptors saem — e com eles o fluxo de todos os "
                "recursos e rotas que os herdavam.\n"
                "Se a intenção era mantê-los, declare-os no `all.yaml`."
            )
    elif fluxo.heranca_pura and proprios:
        avisos.append(
            f"{escopo}: hoje tem {len(proprios)} interceptor(es) próprio(s) no "
            f"Manager ({_rotular(proprios)}), mas o repositório declara que este "
            "ponto apenas herda. Ao publicar, esses interceptors saem e o fluxo "
            "passa a ser o do nível acima.\n"
            "Se a intenção era mantê-los, liste-os no arquivo com `inherit: false`."
        )

    return avisos


def _herda(bloco: Dict[str, Any]) -> bool:
    """`inherit` ausente equivale a `true` (V-26: a herança é sempre declarada,
    e a ausência não é quebra)."""
    valor = bloco.get("inherit")
    return True if valor is None else bool(valor)


def montar(
    *,
    draft: Dict[str, Any],
    basic_info: Dict[str, Any],
    raiz: Dict[str, Any],
    recursos: Sequence[Any],
    resolver_custom: Optional[Callable[[int], Optional[Dict[str, Any]]]] = None,
) -> PayloadMontado:
    """Monta o corpo do `PUT` a partir do estado remoto e do repositório.

    `resolver_custom` é injetado pela camada de aplicação: um `Custom` novo
    precisa do `{id, name, script}` do catálogo no `content`, e buscá-lo é rede —
    que não entra aqui. Sem o resolvedor, um `Custom` novo vai sem conteúdo.
    """
    corpo = copy.deepcopy(draft)
    avisos: List[str] = []
    contador: Iterator[int] = preparar_contador_idtemp(draft)

    def _content(declarado: Dict[str, Any]) -> Any:
        """O wire quer `content` como string JSON (ver `construir_item_novo`)."""
        if declarado.get("type") == "Custom":
            custom_id = declarado.get("customInterceptorId")
            vivo = resolver_custom(custom_id) if (resolver_custom and custom_id) else None
            if vivo is None:
                return None
            return json.dumps(
                {
                    "id": vivo.get("id"),
                    "name": vivo.get("name"),
                    "script": vivo.get("script"),
                },
                ensure_ascii=False,
            )
        return declarado.get("content")

    # --- basic info viaja no `api` aninhado; é ali que o AG atua (W-7) -------
    spec = basic_info.get("spec") or {}
    if isinstance(corpo.get("api"), dict):
        for campo in ("name", "description"):
            if spec.get(campo) is not None:
                corpo["api"][campo] = spec[campo]
        if spec.get("apiTags") is not None:
            corpo["api"]["apiTags"] = spec["apiTags"]

    # --- escopo raiz ---------------------------------------------------------
    # A resolução desce daqui: o efetivo da raiz alimenta os recursos, e o de
    # cada recurso alimenta suas operações (V-27 §2). A raiz não herda — seu
    # fluxo é exatamente o que o `all.yaml` declara.
    fluxo_raiz = resolver_fluxo_declarado(_declarados(raiz), raiz=True)
    avisos.extend(_avisos_do_escopo(fluxo_raiz, draft, "raiz da revision", raiz=True))
    url, timeout = _destino(raiz)
    corpo["destination"] = url
    corpo["timeout"] = timeout
    corpo["interceptors"] = montar_fluxo_do_escopo(
        fluxo_raiz,
        draft.get("interceptors"),
        gerar_idtemp=contador,
        resolver_content=_content,
    )

    # --- recursos e operações ------------------------------------------------
    remotos_por_nome = {
        r.get("name"): r for r in (draft.get("resources") or []) if r.get("name")
    }
    saida_recursos: List[Dict[str, Any]] = []

    for recurso in recursos:
        dados = recurso.dados or {}
        nome = dados.get("name")
        remoto = remotos_por_nome.get(nome) or {}
        bloco = copy.deepcopy(remoto) if remoto else {"name": nome}

        fluxo_recurso = resolver_fluxo_declarado(
            _declarados(dados), fluxo_raiz.efetivo, inherit=_herda(dados)
        )
        avisos.extend(_avisos_do_escopo(fluxo_recurso, remoto, f"resource {nome}"))
        if dados.get("description") is not None:
            bloco["description"] = dados.get("description")
        url, timeout = _destino(dados)
        bloco["destination"] = url
        bloco["timeout"] = timeout
        bloco["interceptors"] = montar_fluxo_do_escopo(
            fluxo_recurso,
            remoto.get("interceptors"),
            gerar_idtemp=contador,
            resolver_content=_content,
        )

        remotas_por_chave = {
            (str(o.get("method") or "").upper(), o.get("path")): o
            for o in (remoto.get("operations") or [])
        }
        operacoes: List[Dict[str, Any]] = []
        for op in recurso.operacoes:
            od = op.dados or {}
            chave = (op.metodo, od.get("path"))
            remota = remotas_por_chave.get(chave) or {}
            item = copy.deepcopy(remota) if remota else {}
            fluxo_op = resolver_fluxo_declarado(
                _declarados(od), fluxo_recurso.efetivo, inherit=_herda(od)
            )
            avisos.extend(
                _avisos_do_escopo(fluxo_op, remota, f"{op.metodo} {od.get('path')}")
            )
            item["method"] = op.metodo
            item["path"] = od.get("path")
            if od.get("description") is not None:
                item["description"] = od.get("description")
            url, timeout = _destino(od)
            item["destination"] = url
            item["timeout"] = timeout
            item["interceptors"] = montar_fluxo_do_escopo(
                fluxo_op,
                remota.get("interceptors"),
                gerar_idtemp=contador,
                resolver_content=_content,
            )
            if not remota:
                # W-6: a operação PERTENCE ao recurso. Reaproveitar o `id` de
                # uma operação de outro recurso faz o Manager DESCARTÁ-LA, com
                # HTTP 200 — operação nova vai sem `id`.
                item.pop("id", None)
            operacoes.append(item)

        bloco["operations"] = operacoes
        saida_recursos.append(bloco)

    corpo["resources"] = saida_recursos

    sumidos = set(remotos_por_nome) - {r.get("name") for r in saida_recursos}
    if sumidos:
        avisos.append(
            "Estes recursos existem no Manager e não no repositório, e serão "
            f"removidos ao publicar: {', '.join(sorted(str(s) for s in sumidos))}. "
            "O que não está no repositório não é enviado, e o que não é enviado o "
            "Manager apaga."
        )

    return PayloadMontado(corpo=corpo, avisos=avisos)


# --------------------------------------------------------------------------- E3.1


def _assinatura_operacoes(no: Dict[str, Any]) -> set:
    saida = set()
    for recurso in no.get("resources") or []:
        for op in recurso.get("operations") or []:
            saida.add(
                (
                    recurso.get("name"),
                    str(op.get("method") or "").upper(),
                    op.get("path"),
                )
            )
    return saida


def _por_escopo(no: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Itens governados de cada escopo da árvore, indexados pelo rótulo."""
    saida = {"raiz": particionar(no.get("interceptors"))[0]}
    for recurso in no.get("resources") or []:
        nome = recurso.get("name")
        saida[f"resource {nome}"] = particionar(recurso.get("interceptors"))[0]
        for op in recurso.get("operations") or []:
            rotulo = f"{nome}/{str(op.get('method') or '').upper()} {op.get('path')}"
            saida[rotulo] = particionar(op.get("interceptors"))[0]
    return saida


def _contagem_por_escopo(no: Dict[str, Any]) -> Dict[str, int]:
    """Quantos itens **vivos** cada escopo tem.

    Tombstones ficam de fora porque não são fluxo: contá-los faria um escopo com
    8 itens e 1 supressão parecer ter 9. Eles são conferidos à parte.
    """
    return {
        escopo: len([i for i in itens if i.get("status") != "REMOVED"])
        for escopo, itens in _por_escopo(no).items()
    }


def _destinos_por_escopo(no: Dict[str, Any]) -> Dict[str, Any]:
    """`destination` e `timeout` de cada escopo, para a conferência.

    Entram aqui porque `''` e `null` **não** são equivalentes na escrita: a
    plataforma guarda literalmente o que recebe (medido em 2026-10-15, fechando
    a P-8). Sem conferi-los, uma troca silenciosa de um pelo outro passaria.
    """
    saida: Dict[str, Any] = {
        "raiz": (no.get("destination"), no.get("timeout")),
    }
    for recurso in no.get("resources") or []:
        nome = recurso.get("name")
        saida[f"resource {nome}"] = (recurso.get("destination"), recurso.get("timeout"))
        for op in recurso.get("operations") or []:
            rotulo = f"{nome}/{str(op.get('method') or '').upper()} {op.get('path')}"
            saida[rotulo] = (op.get("destination"), op.get("timeout"))
    return saida


def conferir(enviado: Dict[str, Any], publicado: Dict[str, Any]) -> List[str]:
    """Compara enviado × publicado e devolve as divergências.

    **HTTP 200 não é prova de sucesso** (W-8): foram observadas três perdas
    silenciosas distintas sob 200 — `idTemp` colidido, operação migrada de
    recurso e item descartado por dedupe. A releitura é o veredito.
    """
    divergencias: List[str] = []

    ops_enviadas = _assinatura_operacoes(enviado)
    ops_publicadas = _assinatura_operacoes(publicado)
    for faltando in sorted(ops_enviadas - ops_publicadas):
        divergencias.append(
            f"a operação {faltando[1]} {faltando[2]}, do recurso {faltando[0]}, foi "
            "enviada mas não está no Manager"
        )
    for sobrando in sorted(ops_publicadas - ops_enviadas):
        divergencias.append(
            f"a operação {sobrando[1]} {sobrando[2]}, do recurso {sobrando[0]}, está "
            "no Manager mas não foi enviada"
        )

    enviadas = _contagem_por_escopo(enviado)
    publicadas = _contagem_por_escopo(publicado)
    for escopo, quantidade in sorted(enviadas.items()):
        presente = publicadas.get(escopo)
        if presente is None:
            divergencias.append(f"{escopo} foi enviado mas não está no Manager")
        elif presente != quantidade:
            divergencias.append(
                f"{escopo}: foram enviados {quantidade} interceptor(es) e o Manager "
                f"gravou {presente}"
            )

    nomes_enviados = {r.get("name") for r in (enviado.get("resources") or [])}
    nomes_publicados = {r.get("name") for r in (publicado.get("resources") or [])}
    for faltando in sorted(str(n) for n in nomes_enviados - nomes_publicados):
        divergencias.append(f"o recurso {faltando} foi enviado mas não está no Manager")
    # O T10 provou que o que não está no repositório é removido. Um recurso que
    # sobrevive sem ter sido enviado é divergência na direção oposta — e sem esta
    # conferência ele passaria despercebido.
    for sobrando in sorted(str(n) for n in nomes_publicados - nomes_enviados):
        divergencias.append(
            f"o recurso {sobrando} está no Manager mas não foi enviado"
        )

    # V-27 §8 (E-2): sob a nova semântica o repositório nunca envia tombstone —
    # a supressão se escreve omitindo o item da lista. Um `status: REMOVED` que
    # sobreviva ao PUT continua suprimindo um item herdado, então o fluxo
    # publicado não é o que o repositório declarou. Vale o veredito.
    for escopo, itens in sorted(_por_escopo(publicado).items()):
        remanescentes = [i for i in itens if i.get("status") == "REMOVED"]
        if remanescentes:
            divergencias.append(
                f"{escopo}: o Manager ainda tem {len(remanescentes)} marcação(ões) de "
                f"interceptor removido ({_rotular(remanescentes)}) que não foram "
                "enviadas; elas continuam suprimindo itens do fluxo herdado"
            )

    destinos_enviados = _destinos_por_escopo(enviado)
    destinos_publicados = _destinos_por_escopo(publicado)
    for escopo, enviado_par in sorted(destinos_enviados.items()):
        publicado_par = destinos_publicados.get(escopo)
        if publicado_par is None:
            continue  # a ausência do escopo já foi reportada acima
        if enviado_par != publicado_par:
            divergencias.append(
                f"{escopo}: destination/timeout foi enviado como {enviado_par!r} e "
                f"gravado como {publicado_par!r}"
            )

    return divergencias
