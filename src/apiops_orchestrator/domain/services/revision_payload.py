"""Montagem do payload da revisão e conferência pós-publicação.

Lógica pura. O payload nasce como **cópia profunda do estado remoto** e recebe
só o que o repositório declara — assim tudo que o repositório não governa volta
intacto, sem precisar ser enumerado.

O fluxo de interceptors é a exceção deliberada: o que cada escopo guarda é
decidido aqui, descendo `all.yaml` → `resource.yaml` → operação — os itens
próprios e as marcações do que deixa de herdar (V-28).

É por construção que `workflowId` e `workflowStageId` são preservados (D-020):
eles viajam na cópia, e nada aqui os reescreve.
"""

import copy
import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from apiops_orchestrator.domain.services.interceptor_flow import (
    FluxoDoEscopo,
    alvo_da_marcacao,
    fluxo_composto,
    identidade,
    montar_fluxo_do_escopo,
    particionar,
    preparar_contador_idtemp,
    resolver_fluxo_declarado,
)
from apiops_orchestrator.domain.services.template_conformance import normalizar_content


@dataclass(frozen=True)
class PayloadMontado:
    corpo: Dict[str, Any]
    avisos: List[str] = field(default_factory=list)
    # Itens próprios que o REPOSITÓRIO declara para cada escopo que não só herda,
    # na ordem declarada. É o oráculo da conferência: comparar o publicado só com
    # o payload deixaria passar qualquer perda na própria montagem.
    esperado: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)


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
    """Itens próprios que a publicação remove do escopo, que não podem sair calados."""
    avisos: List[str] = []
    proprios = _vivos(remoto)

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
            "Se a intenção era mantê-los, liste-os no arquivo."
        )

    return avisos


def _avisos_de_herdado_cortado(
    fluxo: FluxoDoEscopo,
    remoto: Optional[Dict[str, Any]],
    herdado_remoto: Sequence[Dict[str, Any]],
    herdado: Sequence[Dict[str, Any]],
    escopo: str,
) -> List[str]:
    """Herdado que o escopo executa hoje e deixa de executar porque quebra a
    herança. `herdado_remoto` e `herdado` são o que o pai executa hoje e depois
    desta publicação."""
    if not fluxo.quebra or not remoto:
        return []
    executa_hoje = {
        identidade(i) for i in fluxo_composto(remoto.get("interceptors"), herdado_remoto)
    }
    continua_no_pai = {i.get("id") for i in herdado if i.get("id") is not None}
    cortados = [
        i for i in herdado_remoto
        if i.get("id") in executa_hoje and i.get("id") in continua_no_pai
    ]
    if not cortados:
        return []
    return [
        f"{escopo}: o arquivo declara `inherit: false`, e ao publicar este ponto deixa "
        f"de executar {len(cortados)} interceptor(es) herdado(s) que executa hoje "
        f"({_rotular(cortados)}).\n"
        "Se a intenção era mantê-los, use `inherit: true` para seguir herdando, ou "
        "liste-os no arquivo."
    ]


def _herda(bloco: Dict[str, Any]) -> bool:
    """`inherit` ausente equivale a `true` (V-26: a herança é sempre declarada,
    e a ausência não é quebra)."""
    valor = bloco.get("inherit")
    return True if valor is None else bool(valor)


# --- identidade do recurso: as rotas, não o nome (V-12a) ---------------------
#
# O Manager aceita dois recursos com o mesmo nome (a 409 rev1 tem dois `Letras`)
# e o repositório não versiona `id` (D-005 §2). O único elo estável entre uma
# pasta e o recurso remoto é o conjunto de rotas — e cada rota pertence a um só
# recurso, lá (W-6) e aqui (I-6).

Rota = Tuple[str, Optional[str]]


def _rota(metodo: Any, path: Any) -> Rota:
    return (str(metodo or "").upper(), path)


def _rotulo_rota(rota: Rota) -> str:
    return f"{rota[0]} {rota[1]}"


def _rotas_do_no(recurso: Dict[str, Any]) -> List[Rota]:
    return [_rota(o.get("method"), o.get("path")) for o in recurso.get("operations") or []]


def parear_por_rotas(
    lado: Sequence[Tuple[Optional[str], Sequence[Rota]]],
    remotos: Sequence[Tuple[Optional[str], Sequence[Rota]]],
) -> Dict[int, int]:
    """Liga cada recurso de `lado` a no máximo um de `remotos`, 1:1, pelas rotas.

    Ganha o par com mais rotas em comum; empatado, o de mesmo nome; ainda
    empatado, o que vem primeiro em `lado` — as pastas, que a descoberta já
    entrega em ordem alfabética. Recurso com rotas, mas nenhuma em comum, fica
    sem par: pela V-12a é outro recurso, mesmo com nome igual.
    """
    dono: Dict[Rota, int] = {}
    for j, (_, rotas) in enumerate(remotos):
        for rota in rotas:
            dono.setdefault(rota, j)

    candidatos = []
    for i, (nome, rotas) in enumerate(lado):
        em_comum = Counter(dono[r] for r in rotas if r in dono)
        for j, quantidade in em_comum.items():
            candidatos.append((-quantidade, remotos[j][0] != nome, i, j))

    pares: Dict[int, int] = {}
    tomados = set()
    for _, _, i, j in sorted(candidatos):
        if i in pares or j in tomados:
            continue
        pares[i] = j
        tomados.add(j)

    # Recurso SEM rota nenhuma, dos dois lados, não tem identidade por rotas —
    # recriá-lo perderia o que o Manager preserva nele (V-22). Só aqui o nome
    # decide, e só quando é único entre os que sobraram sem rota.
    sem_rota_a = [i for i, (_, rotas) in enumerate(lado) if not rotas and i not in pares]
    sem_rota_b = [j for j, (_, rotas) in enumerate(remotos) if not rotas and j not in tomados]
    for i in sem_rota_a:
        nome = lado[i][0]
        iguais_a = [k for k in sem_rota_a if lado[k][0] == nome]
        iguais_b = [k for k in sem_rota_b if remotos[k][0] == nome]
        if len(iguais_a) == 1 and len(iguais_b) == 1:
            pares[i] = iguais_b[0]
    return pares


def _rotulos_de_recursos(
    recursos: Sequence[Tuple[Optional[str], Sequence[Rota]]],
) -> List[str]:
    """Como cada recurso é nomeado nas mensagens e nos escopos.

    Nome repetido ganha a primeira rota como qualificador — `Letras (rota GET
    /letras/{id})`. A rota identifica o recurso nos dois lados, repositório e
    Manager (V-12a); sem ela, dois `Letras` virariam o mesmo escopo e as
    contagens se misturariam.
    """
    repeticoes = Counter(nome for nome, _ in recursos)
    rotulos = []
    for nome, rotas in recursos:
        if repeticoes[nome] > 1 and rotas:
            primeira = min(rotas, key=lambda r: (r[1] or "", r[0]))
            rotulos.append(f"{nome} (rota {_rotulo_rota(primeira)})")
        else:
            rotulos.append(str(nome))
    return rotulos


def _avisos_de_homonimos(recursos: Sequence[Any]) -> List[str]:
    """Pastas diferentes com o mesmo `name`: aceito, mas quase sempre engano."""
    pastas_por_nome: Dict[str, List[str]] = {}
    for recurso in recursos:
        nome = (recurso.dados or {}).get("name")
        if nome:
            pastas_por_nome.setdefault(nome, []).append(recurso.slug)

    avisos = []
    for nome, pastas in pastas_por_nome.items():
        if len(pastas) < 2:
            continue
        lista = ", ".join(f"`{p}`" for p in pastas[:-1]) + f" e `{pastas[-1]}`"
        avisos.append(
            f"As pastas {lista} declaram recursos com o mesmo nome, \"{nome}\". O "
            "Manager aceita, mas quem olha a API vê recursos iguais e não sabe qual é "
            "qual.\n"
            "Se são o mesmo recurso, junte as rotas em uma pasta só. Se não são, dê a "
            "cada um um nome diferente no `resource.yaml`."
        )
    return avisos


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
    esperado: Dict[str, List[Dict[str, Any]]] = {}
    contador: Iterator[int] = preparar_contador_idtemp(draft)

    def _esperar(escopo: str, fluxo: FluxoDoEscopo) -> None:
        # Herança pura vai como `[]`: a contagem por escopo já cobre esse caso.
        if not fluxo.heranca_pura:
            esperado[escopo] = list(fluxo.proprios)

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
    # A decisão desce daqui: o efetivo da raiz alimenta os recursos, e o de cada
    # recurso alimenta suas operações. A raiz não herda — seu fluxo é exatamente
    # o que o `all.yaml` declara.
    fluxo_raiz = resolver_fluxo_declarado(_declarados(raiz), raiz=True)
    avisos.extend(_avisos_do_escopo(fluxo_raiz, draft, "raiz da revision", raiz=True))
    _esperar("raiz", fluxo_raiz)
    url, timeout = _destino(raiz)
    corpo["destination"] = url
    corpo["timeout"] = timeout
    corpo["interceptors"] = montar_fluxo_do_escopo(
        fluxo_raiz,
        draft.get("interceptors"),
        gerar_idtemp=contador,
        resolver_content=_content,
    )
    composto_raiz = fluxo_composto(corpo["interceptors"])
    composto_raiz_remoto = fluxo_composto(draft.get("interceptors"))

    # --- recursos e operações ------------------------------------------------
    # Cada pasta é ligada ao recurso remoto pelas rotas, não pelo nome (V-12a):
    # pelo nome, dois homônimos caíam no mesmo remoto e um deles sumia calado.
    remotos: List[Dict[str, Any]] = list(draft.get("resources") or [])
    rotas_remotas = [_rotas_do_no(r) for r in remotos]
    lado_remoto = [(r.get("name"), rotas) for r, rotas in zip(remotos, rotas_remotas)]
    lado_repo = [
        (
            (recurso.dados or {}).get("name"),
            [_rota(op.metodo, (op.dados or {}).get("path")) for op in recurso.operacoes],
        )
        for recurso in recursos
    ]
    pares = parear_por_rotas(lado_repo, lado_remoto)
    rotulos_repo = _rotulos_de_recursos(lado_repo)
    rotulos_remotos = _rotulos_de_recursos(lado_remoto)
    dono_remoto: Dict[Rota, int] = {}
    for j, rotas in enumerate(rotas_remotas):
        for rota in rotas:
            dono_remoto.setdefault(rota, j)
    no_repositorio = {rota for _, rotas in lado_repo for rota in rotas}

    avisos.extend(_avisos_de_homonimos(recursos))
    saida_recursos: List[Dict[str, Any]] = []
    rotas_movidas: List[str] = []

    for i, recurso in enumerate(recursos):
        dados = recurso.dados or {}
        nome = dados.get("name")
        rotulo = rotulos_repo[i]
        indice_remoto = pares.get(i)
        remoto = remotos[indice_remoto] if indice_remoto is not None else {}
        bloco = copy.deepcopy(remoto) if remoto else {}
        # Ligado pelas rotas, o recurso pode ter trocado de nome: o repositório
        # prevalece, e o `id` fica — trocar o nome não recria o recurso.
        bloco["name"] = nome if nome is not None else bloco.get("name")

        fluxo_recurso = resolver_fluxo_declarado(
            _declarados(dados), fluxo_raiz.efetivo, inherit=_herda(dados)
        )
        avisos.extend(_avisos_do_escopo(fluxo_recurso, remoto, f"resource {rotulo}"))
        avisos.extend(
            _avisos_de_herdado_cortado(
                fluxo_recurso, remoto, composto_raiz_remoto, composto_raiz,
                f"resource {rotulo}",
            )
        )
        _esperar(f"resource {rotulo}", fluxo_recurso)
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
            herdado=composto_raiz,
        )
        composto_recurso = fluxo_composto(bloco["interceptors"], composto_raiz)
        composto_recurso_remoto = fluxo_composto(
            remoto.get("interceptors"), composto_raiz_remoto
        )

        remotas_por_chave = {
            _rota(o.get("method"), o.get("path")): o
            for o in (remoto.get("operations") or [])
        }
        operacoes: List[Dict[str, Any]] = []
        for op in recurso.operacoes:
            od = op.dados or {}
            chave = _rota(op.metodo, od.get("path"))
            # Só reaproveita o remoto se a rota estiver no recurso ligado ao seu
            # dono: `remotas_por_chave` é do recurso pareado, e só dele (W-6).
            remota = remotas_por_chave.get(chave) or {}
            origem = dono_remoto.get(chave)
            if origem is not None and origem != indice_remoto:
                rotas_movidas.append(
                    f"{_rotulo_rota(chave)}: sai do recurso {rotulos_remotos[origem]} e "
                    f"vai para o recurso {nome} (pasta `{recurso.slug}`)"
                    + (", que será criado" if indice_remoto is None else "")
                )
            item = copy.deepcopy(remota) if remota else {}
            fluxo_op = resolver_fluxo_declarado(
                _declarados(od), fluxo_recurso.efetivo, inherit=_herda(od)
            )
            avisos.extend(
                _avisos_do_escopo(fluxo_op, remota, f"{op.metodo} {od.get('path')}")
            )
            avisos.extend(
                _avisos_de_herdado_cortado(
                    fluxo_op, remota, composto_recurso_remoto, composto_recurso,
                    f"{op.metodo} {od.get('path')}",
                )
            )
            _esperar(_rotulo_rota(chave), fluxo_op)
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
                herdado=composto_recurso,
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

    # O PUT grava a revisão inteira: o que está no Manager e não no repositório
    # é apagado. Não bloqueia — remover pode ser a intenção —, mas é avisado.
    # A comparação é por recurso e por rota, nunca por nome: um homônimo que
    # some precisa aparecer aqui mesmo com o nome ainda presente.
    pareados = set(pares.values())
    sumidos = [rotulos_remotos[j] for j in range(len(remotos)) if j not in pareados]
    # Só para recurso que continua: o que some junto com o recurso inteiro já é
    # nomeado no aviso de recursos. Rota que está em outra pasta não sumiu —
    # mudou de recurso, e é avisada à parte.
    rotas_sumidas = [
        f"{_rotulo_rota(rota)} (recurso {rotulos_remotos[j]})"
        for j in sorted(pareados)
        for rota in sorted(rotas_remotas[j], key=str)
        if rota not in no_repositorio
    ]
    if sumidos:
        avisos.append(
            "Os recursos abaixo existem no Manager mas não estão no repositório. Ao "
            "publicar, eles serão apagados do Manager:\n"
            + "\n".join(f"  - {s}" for s in sorted(sumidos))
            + "\n\nSe não era essa a intenção, adicione-os ao repositório antes de "
            "publicar."
        )
    if rotas_movidas:
        avisos.append(
            "As rotas abaixo estão no repositório em um recurso diferente do que têm "
            "hoje no Manager. Ao publicar, elas saem do recurso de origem e passam "
            "para o de destino:\n"
            + "\n".join(f"  - {r}" for r in rotas_movidas)
            + "\n\nSe não era essa a intenção, devolva-as à pasta do recurso de origem."
        )
    if rotas_sumidas:
        avisos.append(
            "As rotas abaixo existem no Manager mas não estão no repositório. Ao "
            "publicar, elas serão apagadas do Manager:\n"
            + "\n".join(f"  - {r}" for r in rotas_sumidas)
            + "\n\nSe não era essa a intenção, adicione-as ao repositório antes de "
            "publicar."
        )

    return PayloadMontado(corpo=corpo, avisos=avisos, esperado=esperado)


# --------------------------------------------------------------------------- E3.1


def _lado(no: Dict[str, Any]) -> List[Tuple[Optional[str], List[Rota]]]:
    return [(r.get("name"), _rotas_do_no(r)) for r in no.get("resources") or []]


def _rotulos_da_conferencia(
    enviado: Dict[str, Any], publicado: Dict[str, Any]
) -> Tuple[List[str], List[str], Dict[int, int]]:
    """Rótulos dos recursos dos dois lados, ligados pelas rotas.

    O recurso publicado herda o rótulo do enviado com quem foi ligado — é a
    mesma regra do `montar`, então os escopos do `esperado` batem. O que fica
    sem par é divergência.
    """
    lado_enviado, lado_publicado = _lado(enviado), _lado(publicado)
    pares = parear_por_rotas(lado_enviado, lado_publicado)

    rotulos_enviados = _rotulos_de_recursos(lado_enviado)
    proprios = _rotulos_de_recursos(lado_publicado)
    por_publicado = {j: i for i, j in pares.items()}
    rotulos_publicados = []
    for j, proprio in enumerate(proprios):
        if j in por_publicado:
            rotulos_publicados.append(rotulos_enviados[por_publicado[j]])
        elif proprio in rotulos_enviados:
            # Não pode colidir com um escopo enviado: os itens se misturariam.
            rotulos_publicados.append(f"{proprio} (só no Manager)")
        else:
            rotulos_publicados.append(proprio)
    return rotulos_enviados, rotulos_publicados, pares


def _escopos(
    no: Dict[str, Any], rotulos: Sequence[str]
) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """Cada escopo da árvore com o seu rótulo.

    A rota basta como rótulo da operação: é única na revisão (W-6 e I-6).
    """
    yield "raiz", no
    for recurso, rotulo in zip(no.get("resources") or [], rotulos):
        yield f"resource {rotulo}", recurso
        for op in recurso.get("operations") or []:
            yield _rotulo_rota(_rota(op.get("method"), op.get("path"))), op


def _assinatura_operacoes(no: Dict[str, Any], rotulos: Sequence[str]) -> set:
    return {
        (rotulo, *_rota(op.get("method"), op.get("path")))
        for recurso, rotulo in zip(no.get("resources") or [], rotulos)
        for op in recurso.get("operations") or []
    }


def _por_escopo(
    no: Dict[str, Any], rotulos: Sequence[str]
) -> Dict[str, List[Dict[str, Any]]]:
    """Itens governados de cada escopo da árvore, indexados pelo rótulo."""
    return {
        escopo: particionar(nodo.get("interceptors"))[0]
        for escopo, nodo in _escopos(no, rotulos)
    }


def _assinatura_do_alvo(item: Dict[str, Any]) -> Tuple[Any, ...]:
    """Tipo, Custom, ponto de execução e `content` normalizado de um item."""
    content = (
        None
        if item.get("type") == "Custom"
        else json.dumps(normalizar_content(item.get("content")), sort_keys=True, default=str)
    )
    ponto = str(item.get("executionPoint") or "").upper()
    return (item.get("type"), _custom_id(item), ponto, content)


def _marcacoes_por_escopo(
    no: Dict[str, Any], rotulos: Sequence[str]
) -> Dict[str, Dict[Tuple[Any, ...], List[Dict[str, Any]]]]:
    """Marcações de remoção de cada escopo, agrupadas pelo item herdado que
    removem, resolvido no fluxo que o pai executa do mesmo lado."""
    saida: Dict[str, Dict[Tuple[Any, ...], List[Dict[str, Any]]]] = {}

    def agrupar(escopo: str, itens: Any, herdado: Sequence[Dict[str, Any]]) -> None:
        por_identidade = {identidade(i): i for i in herdado if identidade(i) is not None}
        grupos: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
        for marcacao in particionar(itens)[0]:
            if marcacao.get("status") != "REMOVED":
                continue
            alvo = por_identidade.get(alvo_da_marcacao(marcacao), marcacao)
            grupos.setdefault(_assinatura_do_alvo(alvo), []).append(marcacao)
        saida[escopo] = grupos

    raiz = fluxo_composto(no.get("interceptors"))
    agrupar("raiz", no.get("interceptors"), [])
    for recurso, rotulo in zip(no.get("resources") or [], rotulos):
        agrupar(f"resource {rotulo}", recurso.get("interceptors"), raiz)
        composto = fluxo_composto(recurso.get("interceptors"), raiz)
        for op in recurso.get("operations") or []:
            agrupar(
                _rotulo_rota(_rota(op.get("method"), op.get("path"))),
                op.get("interceptors"),
                composto,
            )
    return saida


def _contagem_por_escopo(no: Dict[str, Any], rotulos: Sequence[str]) -> Dict[str, int]:
    """Quantos itens **vivos** cada escopo tem.

    Tombstones ficam de fora porque não são fluxo: contá-los faria um escopo com
    8 itens e 1 supressão parecer ter 9. Eles são conferidos à parte.
    """
    return {
        escopo: len([i for i in itens if i.get("status") != "REMOVED"])
        for escopo, itens in _por_escopo(no, rotulos).items()
    }


def _destinos_por_escopo(no: Dict[str, Any], rotulos: Sequence[str]) -> Dict[str, Any]:
    """`destination` e `timeout` de cada escopo, para a conferência.

    Entram aqui porque `''` e `null` **não** são equivalentes na escrita: a
    plataforma guarda literalmente o que recebe (medido em 2026-10-15, fechando
    a P-8). Sem conferi-los, uma troca silenciosa de um pelo outro passaria.
    """
    return {
        escopo: (nodo.get("destination"), nodo.get("timeout"))
        for escopo, nodo in _escopos(no, rotulos)
    }


def conferir(
    enviado: Dict[str, Any],
    publicado: Dict[str, Any],
    esperado: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> List[str]:
    """Compara enviado × publicado e devolve as divergências.

    **HTTP 200 não é prova de sucesso** (W-8): foram observadas três perdas
    silenciosas distintas sob 200 — `idTemp` colidido, operação migrada de
    recurso e item descartado por dedupe. A releitura é o veredito.

    `esperado` é o fluxo que o repositório declara (`PayloadMontado.esperado`).
    Com ele, o fluxo publicado é comparado também com o **declarado** — tipo,
    ordem e `content` —, e não só com o payload: uma perda na própria montagem
    passaria intacta por uma comparação com o enviado.
    """
    divergencias: List[str] = []
    # Os recursos dos dois lados são ligados pelas rotas, como no `montar`:
    # pelo nome, dois homônimos virariam um só escopo e a contagem mentiria.
    rotulos_e, rotulos_p, pares = _rotulos_da_conferencia(enviado, publicado)
    if esperado:
        divergencias.extend(
            _divergencias_do_fluxo_declarado(esperado, publicado, rotulos_p)
        )

    ops_enviadas = _assinatura_operacoes(enviado, rotulos_e)
    ops_publicadas = _assinatura_operacoes(publicado, rotulos_p)
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

    enviadas = _contagem_por_escopo(enviado, rotulos_e)
    publicadas = _contagem_por_escopo(publicado, rotulos_p)
    for escopo, quantidade in sorted(enviadas.items()):
        presente = publicadas.get(escopo)
        if presente is None:
            divergencias.append(f"{escopo} foi enviado mas não está no Manager")
        elif presente != quantidade:
            divergencias.append(
                f"{escopo}: foram enviados {quantidade} interceptor(es) e o Manager "
                f"gravou {presente}"
            )

    for faltando in sorted(r for i, r in enumerate(rotulos_e) if i not in pares):
        divergencias.append(f"o recurso {faltando} foi enviado mas não está no Manager")
    # O T10 provou que o que não está no repositório é removido. Um recurso que
    # sobrevive sem ter sido enviado é divergência na direção oposta — e sem esta
    # conferência ele passaria despercebido.
    ligados = set(pares.values())
    for sobrando in sorted(r for j, r in enumerate(rotulos_p) if j not in ligados):
        divergencias.append(
            f"o recurso {sobrando} está no Manager mas não foi enviado"
        )

    # Pelo item que removem, e não pelo `parent.id`: a marcação enviada por
    # `idTemp` volta gravada com o id que o Manager gerou.
    marcacoes_enviadas = _marcacoes_por_escopo(enviado, rotulos_e)
    marcacoes_gravadas = _marcacoes_por_escopo(publicado, rotulos_p)
    for escopo in sorted(set(marcacoes_enviadas) | set(marcacoes_gravadas)):
        enviadas = marcacoes_enviadas.get(escopo, {})
        gravadas = marcacoes_gravadas.get(escopo, {})
        sobrando: List[Dict[str, Any]] = []
        faltando: List[Dict[str, Any]] = []
        for alvo in sorted(set(enviadas) | set(gravadas), key=str):
            diferenca = len(gravadas.get(alvo, [])) - len(enviadas.get(alvo, []))
            if diferenca > 0:
                sobrando += gravadas[alvo][:diferenca]
            elif diferenca < 0:
                faltando += enviadas[alvo][:-diferenca]
        if sobrando:
            divergencias.append(
                f"{escopo}: o Manager ainda tem {len(sobrando)} marcação(ões) de "
                f"interceptor removido ({_rotular(sobrando)}) que não foram "
                "enviadas; elas continuam suprimindo itens do fluxo herdado"
            )
        if faltando:
            divergencias.append(
                f"{escopo}: foram enviadas {len(faltando)} marcação(ões) de interceptor "
                f"removido ({_rotular(faltando)}) que o Manager não gravou; esses itens "
                "herdados continuam executando aqui"
            )

    destinos_enviados = _destinos_por_escopo(enviado, rotulos_e)
    destinos_publicados = _destinos_por_escopo(publicado, rotulos_p)
    for escopo, enviado_par in sorted(destinos_enviados.items()):
        publicado_par = destinos_publicados.get(escopo)
        if publicado_par is None:
            continue  # a ausência do escopo já foi reportada acima
        if enviado_par != publicado_par:
            divergencias.append(
                f"{escopo}: destination/timeout foi enviado como {enviado_par!r} e "
                f"gravado como {publicado_par!r}"
            )

    divergencias.extend(_divergencias_do_basic_info(enviado, publicado))
    return divergencias


_NOME_DO_PONTO = {"FIRST": "request", "SECOND": "response"}


def _custom_id(item: Dict[str, Any]) -> Optional[int]:
    valor = item.get("customInterceptorId")
    if valor is None and item.get("type") == "Custom":
        valor = item.get("id")
    return valor


def _rotulo_item(item: Dict[str, Any]) -> str:
    custom_id = _custom_id(item)
    return f"Custom#{custom_id}" if item.get("type") == "Custom" else str(item.get("type"))


def _chaves_diferentes(declarado: Any, gravado: Any) -> str:
    """Quais campos do `content` mudaram — o valor inteiro seria ilegível."""
    if isinstance(declarado, dict) and isinstance(gravado, dict):
        chaves = sorted(
            k for k in set(declarado) | set(gravado) if declarado.get(k) != gravado.get(k)
        )
        if chaves:
            return ", ".join(
                f"`{k}` declarado {declarado.get(k)!r}, gravado {gravado.get(k)!r}"
                for k in chaves
            )
    return f"declarado {declarado!r}, gravado {gravado!r}"


def _divergencias_do_fluxo_declarado(
    esperado: Dict[str, List[Dict[str, Any]]],
    publicado: Dict[str, Any],
    rotulos: Sequence[str],
) -> List[str]:
    """Fluxo publicado × fluxo declarado, por escopo e execution point.

    A plataforma executa pela `position`, então é por ela que o publicado é
    lido. O `content` só é comparado nos tipos nativos — no `Custom` o id
    identifica o objeto (V-11 §4) —, e pela mesma normalização da conformidade.
    """
    divergencias: List[str] = []
    publicados = _por_escopo(publicado, rotulos)
    for escopo, declarados in sorted(esperado.items()):
        gravados_do_escopo = publicados.get(escopo)
        if gravados_do_escopo is None:
            continue  # a ausência do escopo é reportada pela contagem
        for ponto, nome_do_ponto in _NOME_DO_PONTO.items():
            quer = [
                d for d in declarados
                if str(d.get("executionPoint") or "").upper() == ponto
            ]
            tem = sorted(
                (
                    i for i in gravados_do_escopo
                    if str(i.get("executionPoint") or "").upper() == ponto
                    and i.get("status") != "REMOVED"
                ),
                key=lambda i: i.get("position") or 0,
            )
            assinatura_quer = [(d.get("type"), _custom_id(d)) for d in quer]
            assinatura_tem = [(i.get("type"), _custom_id(i)) for i in tem]
            if assinatura_quer != assinatura_tem:
                divergencias.append(
                    f"{escopo}: o {nome_do_ponto} foi declarado como "
                    f"[{', '.join(_rotulo_item(d) for d in quer)}] e gravado como "
                    f"[{', '.join(_rotulo_item(i) for i in tem)}]"
                )
                continue
            for posicao, (d, i) in enumerate(zip(quer, tem), start=1):
                if d.get("type") == "Custom":
                    continue
                quer_content = normalizar_content(d.get("content"))
                tem_content = normalizar_content(i.get("content"))
                if quer_content != tem_content:
                    divergencias.append(
                        f"{escopo}: o {d.get('type')} (item {posicao} do "
                        f"{nome_do_ponto}) não foi gravado como declarado — "
                        f"{_chaves_diferentes(quer_content, tem_content)}"
                    )
    return divergencias


def _assinatura_api_tags(api: Dict[str, Any]) -> Dict[str, frozenset]:
    """`attributeName` → conjunto de tags; a ordem não é contrato da plataforma."""
    return {
        str(item.get("attributeName")): frozenset(str(t) for t in (item.get("tags") or []))
        for item in (api.get("apiTags") or [])
        if isinstance(item, dict)
    }


def _divergencias_do_basic_info(
    enviado: Dict[str, Any], publicado: Dict[str, Any]
) -> List[str]:
    """Confere o `api` aninhado — onde o basic info viaja (W-7).

    Uma tag inexistente no atributo é aceita com 200 e o Manager apaga
    **todas** as `apiTags`. Sem esta conferência, o comando reportava sucesso.
    """
    api_enviada = enviado.get("api") if isinstance(enviado.get("api"), dict) else {}
    api_publicada = publicado.get("api") if isinstance(publicado.get("api"), dict) else {}
    divergencias: List[str] = []

    for campo in ("name", "description"):
        if campo in api_enviada and api_enviada.get(campo) != api_publicada.get(campo):
            divergencias.append(
                f"o campo `{campo}` foi enviado como {api_enviada.get(campo)!r} e "
                f"gravado como {api_publicada.get(campo)!r}"
            )

    if "apiTags" not in api_enviada:
        return divergencias
    enviadas = _assinatura_api_tags(api_enviada)
    publicadas = _assinatura_api_tags(api_publicada)
    for nome in sorted(enviadas.keys() - publicadas.keys()):
        divergencias.append(
            f"o atributo `{nome}` foi enviado em `apiTags` mas não está no Manager"
        )
    for nome in sorted(publicadas.keys() - enviadas.keys()):
        divergencias.append(
            f"o atributo `{nome}` está nas `apiTags` do Manager mas não foi enviado"
        )
    for nome in sorted(enviadas.keys() & publicadas.keys()):
        if enviadas[nome] != publicadas[nome]:
            divergencias.append(
                f"o atributo `{nome}` foi enviado com as tags {sorted(enviadas[nome])} "
                f"e gravado com {sorted(publicadas[nome])}"
            )
    return divergencias
