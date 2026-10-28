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
    ScopeFlow,
    tombstone_target,
    composed_flow,
    identity,
    assemble_scope_flow,
    partition,
    prepare_idtemp_counter,
    resolve_declared_flow,
)
from apiops_orchestrator.domain.services.template_conformance import normalize_content


@dataclass(frozen=True)
class AssembledPayload:
    body: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    # Itens próprios que o REPOSITÓRIO declara para cada escopo que não só herda,
    # na ordem declarada. É o oráculo da conferência: comparar o publicado só com
    # o payload deixaria passar qualquer perda na própria montagem.
    expected: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)


def _declared(block: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Itens declarados no YAML, já com o execution point derivado da chave."""
    output = []
    for key, point in (
        ("interceptors_request", "FIRST"),
        ("interceptors_response", "SECOND"),
    ):
        for item in block.get(key) or []:
            kind = item.get("type")
            output.append(
                {
                    "type": kind,
                    "executionPoint": point,
                    "content": item.get("content"),
                    "customInterceptorId": item.get("id") if kind == "Custom" else None,
                }
            )
    return output


def _destination(block: Dict[str, Any]) -> Tuple[Optional[str], Optional[Any]]:
    destination = block.get("destination") or {}
    if not isinstance(destination, dict):
        return None, None
    return destination.get("url") or None, _timeout(destination.get("timeout"))


def _timeout(value: Any) -> Any:
    """The timeout as the Manager keeps it: a number declared in the YAML goes as text."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return value


def _mock_content(content: Any) -> Any:
    """The Mock content as the Manager keeps it: an object `body` and a numeric `status` go as text."""
    if not isinstance(content, dict):
        return content
    mock = dict(content)
    if isinstance(mock.get("body"), (dict, list)):
        mock["body"] = json.dumps(mock["body"], ensure_ascii=False)
    status = mock.get("status")
    if isinstance(status, int) and not isinstance(status, bool):
        mock["status"] = str(status)
    return mock


def _live(remote: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Itens governados que o escopo tem de fato na plataforma, sem tombstones."""
    own = partition((remote or {}).get("interceptors"))[0]
    return [i for i in own if i.get("status") != "REMOVED"]


def _label(items: Sequence[Dict[str, Any]]) -> str:
    return ", ".join(
        f"{i.get('type')}#{i['customInterceptorId']}"
        if i.get("customInterceptorId")
        else str(i.get("type"))
        for i in items
    )


def _scope_warnings(
    flow: ScopeFlow,
    remote: Optional[Dict[str, Any]],
    scope: str,
    *,
    root: bool = False,
) -> List[str]:
    """Itens próprios que a publicação remove do escopo, que não podem sair calados."""
    warnings: List[str] = []
    own = _live(remote)

    if root:
        # A raiz não herda de ninguém: `[]` ali não significa "herda", significa
        # "sem fluxo". É a remoção mais cara que o comando pode provocar — e o
        # rótulo do escopo ("raiz da revision") não ajuda ninguém, então a
        # mensagem fala do `all.yaml` diretamente.
        if not flow.effective and own:
            warnings.append(
                "O `all.yaml` não declara nenhum interceptor, e a API tem "
                f"{len(own)} hoje no Manager ({_label(own)}). O "
                "`all.yaml` é o nível mais alto e não herda de ninguém, então ao "
                "publicar esses interceptors saem — e com eles o fluxo de todos os "
                "recursos e rotas que os herdavam.\n"
                "Se a intenção era mantê-los, declare-os no `all.yaml`."
            )
    elif flow.pure_inheritance and own:
        warnings.append(
            f"{scope}: hoje tem {len(own)} interceptor(es) próprio(s) no "
            f"Manager ({_label(own)}), mas o repositório declara que este "
            "ponto apenas herda. Ao publicar, esses interceptors saem e o fluxo "
            "passa a ser o do nível acima.\n"
            "Se a intenção era mantê-los, liste-os no arquivo."
        )

    return warnings


def _cut_inherited_warnings(
    flow: ScopeFlow,
    remote: Optional[Dict[str, Any]],
    remote_inherited: Sequence[Dict[str, Any]],
    inherited: Sequence[Dict[str, Any]],
    scope: str,
) -> List[str]:
    """Herdado que o escopo executa hoje e deixa de executar porque quebra a
    herança. `remote_inherited` e `inherited` são o que o pai executa hoje e depois
    desta publicação."""
    if not flow.breaks_inheritance or not remote:
        return []
    currently_runs = {
        identity(i) for i in composed_flow(remote.get("interceptors"), remote_inherited)
    }
    continues_in_parent = {i.get("id") for i in inherited if i.get("id") is not None}
    cut = [
        i for i in remote_inherited
        if i.get("id") in currently_runs and i.get("id") in continues_in_parent
    ]
    if not cut:
        return []
    return [
        f"{scope}: o arquivo declara `inherit: false`, e ao publicar este ponto deixa "
        f"de executar {len(cut)} interceptor(es) herdado(s) que executa hoje "
        f"({_label(cut)}).\n"
        "Se a intenção era mantê-los, use `inherit: true` para seguir herdando, ou "
        "liste-os no arquivo."
    ]


def _inherits(block: Dict[str, Any]) -> bool:
    """`inherit` ausente equivale a `true` (V-26: a herança é sempre declarada,
    e a ausência não é quebra)."""
    value = block.get("inherit")
    return True if value is None else bool(value)


# --- identidade do recurso: as rotas, não o nome (V-12a) ---------------------
#
# O Manager aceita dois recursos com o mesmo nome (a 409 rev1 tem dois `Letras`)
# e o repositório não versiona `id` (D-005 §2). O único elo estável entre uma
# pasta e o recurso remoto é o conjunto de rotas — e cada rota pertence a um só
# recurso, lá (W-6) e aqui (I-6).

Route = Tuple[str, Optional[str]]


def _route(method: Any, path: Any) -> Route:
    return (str(method or "").upper(), path)


def _route_label(route: Route) -> str:
    return f"{route[0]} {route[1]}"


def _node_routes(resource: Dict[str, Any]) -> List[Route]:
    return [_route(o.get("method"), o.get("path")) for o in resource.get("operations") or []]


def pair_by_routes(
    side: Sequence[Tuple[Optional[str], Sequence[Route]]],
    remote_resources: Sequence[Tuple[Optional[str], Sequence[Route]]],
) -> Dict[int, int]:
    """Liga cada recurso de `side` a no máximo um de `remote_resources`, 1:1, pelas rotas.

    Ganha o par com mais rotas em comum; empatado, o de mesmo nome; ainda
    empatado, o que vem primeiro em `side` — as pastas, que a descoberta já
    entrega em ordem alfabética. Recurso com rotas, mas nenhuma em comum, fica
    sem par: pela V-12a é outro recurso, mesmo com nome igual.
    """
    owner: Dict[Route, int] = {}
    for j, (_, routes) in enumerate(remote_resources):
        for route in routes:
            owner.setdefault(route, j)

    candidates = []
    for i, (name, routes) in enumerate(side):
        in_common = Counter(owner[r] for r in routes if r in owner)
        for j, count in in_common.items():
            candidates.append((-count, remote_resources[j][0] != name, i, j))

    pairs: Dict[int, int] = {}
    taken = set()
    for _, _, i, j in sorted(candidates):
        if i in pairs or j in taken:
            continue
        pairs[i] = j
        taken.add(j)

    # Recurso SEM rota nenhuma, dos dois lados, não tem identidade por rotas —
    # recriá-lo perderia o que o Manager preserva nele (V-22). Só aqui o nome
    # decide, e só quando é único entre os que sobraram sem rota.
    routeless_a = [i for i, (_, routes) in enumerate(side) if not routes and i not in pairs]
    routeless_b = [j for j, (_, routes) in enumerate(remote_resources) if not routes and j not in taken]
    for i in routeless_a:
        name = side[i][0]
        equal_a = [k for k in routeless_a if side[k][0] == name]
        equal_b = [k for k in routeless_b if remote_resources[k][0] == name]
        if len(equal_a) == 1 and len(equal_b) == 1:
            pairs[i] = equal_b[0]
    return pairs


def _resource_labels(
    resources: Sequence[Tuple[Optional[str], Sequence[Route]]],
) -> List[str]:
    """Como cada recurso é nomeado nas mensagens e nos escopos.

    Nome repetido ganha a primeira rota como qualificador — `Letras (rota GET
    /letras/{id})`. A rota identifica o recurso nos dois lados, repositório e
    Manager (V-12a); sem ela, dois `Letras` virariam o mesmo escopo e as
    contagens se misturariam.
    """
    repetitions = Counter(name for name, _ in resources)
    labels = []
    for name, routes in resources:
        if repetitions[name] > 1 and routes:
            first = min(routes, key=lambda r: (r[1] or "", r[0]))
            labels.append(f"{name} (rota {_route_label(first)})")
        else:
            labels.append(str(name))
    return labels


def _homonym_warnings(resources: Sequence[Any]) -> List[str]:
    """Pastas diferentes com o mesmo `name`: aceito, mas quase sempre engano."""
    folders_by_name: Dict[str, List[str]] = {}
    for resource in resources:
        name = (resource.data or {}).get("name")
        if name:
            folders_by_name.setdefault(name, []).append(resource.slug)

    warnings = []
    for name, folders in folders_by_name.items():
        if len(folders) < 2:
            continue
        listing = ", ".join(f"`{p}`" for p in folders[:-1]) + f" e `{folders[-1]}`"
        warnings.append(
            f"As pastas {listing} declaram recursos com o mesmo nome, \"{name}\". O "
            "Manager aceita, mas quem olha a API vê recursos iguais e não sabe qual é "
            "qual.\n"
            "Se são o mesmo recurso, junte as rotas em uma pasta só. Se não são, dê a "
            "cada um um nome diferente no `resource.yaml`."
        )
    return warnings


def assemble(
    *,
    draft: Dict[str, Any],
    basic_info: Dict[str, Any],
    root: Dict[str, Any],
    resources: Sequence[Any],
    resolver_custom: Optional[Callable[[int], Optional[Dict[str, Any]]]] = None,
) -> AssembledPayload:
    """Monta o corpo do `PUT` a partir do estado remoto e do repositório.

    `resolver_custom` é injetado pela camada de aplicação: um `Custom` novo
    precisa do `{id, name, script}` do catálogo no `content`, e buscá-lo é rede —
    que não entra aqui. Sem o resolvedor, um `Custom` novo vai sem conteúdo.
    """
    body = copy.deepcopy(draft)
    warnings: List[str] = []
    expected: Dict[str, List[Dict[str, Any]]] = {}
    counter: Iterator[int] = prepare_idtemp_counter(draft)

    def _expect(scope: str, flow: ScopeFlow) -> None:
        # Herança pura vai como `[]`: a contagem por escopo já cobre esse caso.
        if not flow.pure_inheritance:
            expected[scope] = list(flow.own)

    def _content(declared: Dict[str, Any]) -> Any:
        """O wire quer `content` como string JSON (ver `build_new_item`)."""
        if declared.get("type") == "Mock":
            return _mock_content(declared.get("content"))
        if declared.get("type") == "Custom":
            custom_id = declared.get("customInterceptorId")
            live = resolver_custom(custom_id) if (resolver_custom and custom_id) else None
            if live is None:
                return None
            return json.dumps(
                {
                    "id": live.get("id"),
                    "name": live.get("name"),
                    "script": live.get("script"),
                },
                ensure_ascii=False,
            )
        return declared.get("content")

    # --- basic info viaja no `api` aninhado; é ali que o AG atua (W-7) -------
    spec = basic_info.get("spec") or {}
    if isinstance(body.get("api"), dict):
        for field_name in ("name", "description"):
            if spec.get(field_name) is not None:
                body["api"][field_name] = spec[field_name]
        if spec.get("apiTags") is not None:
            body["api"]["apiTags"] = spec["apiTags"]

    # --- escopo raiz ---------------------------------------------------------
    # A decisão desce daqui: o efetivo da raiz alimenta os recursos, e o de cada
    # recurso alimenta suas operações. A raiz não herda — seu fluxo é exatamente
    # o que o `all.yaml` declara.
    root_flow = resolve_declared_flow(_declared(root), root=True)
    warnings.extend(_scope_warnings(root_flow, draft, "raiz da revision", root=True))
    _expect("raiz", root_flow)
    url, timeout = _destination(root)
    body["destination"] = url
    body["timeout"] = timeout
    body["interceptors"] = assemble_scope_flow(
        root_flow,
        draft.get("interceptors"),
        generate_idtemp=counter,
        resolver_content=_content,
    )
    composed_root = composed_flow(body["interceptors"])
    remote_composed_root = composed_flow(draft.get("interceptors"))

    # --- recursos e operações ------------------------------------------------
    # Cada pasta é ligada ao recurso remoto pelas rotas, não pelo nome (V-12a):
    # pelo nome, dois homônimos caíam no mesmo remoto e um deles sumia calado.
    remote_resources: List[Dict[str, Any]] = list(draft.get("resources") or [])
    remote_routes = [_node_routes(r) for r in remote_resources]
    remote_side = [(r.get("name"), routes) for r, routes in zip(remote_resources, remote_routes)]
    repo_side = [
        (
            (resource.data or {}).get("name"),
            [_route(op.method, (op.data or {}).get("path")) for op in resource.operations],
        )
        for resource in resources
    ]
    pairs = pair_by_routes(repo_side, remote_side)
    repo_labels = _resource_labels(repo_side)
    remote_labels = _resource_labels(remote_side)
    remote_owner: Dict[Route, int] = {}
    for j, routes in enumerate(remote_routes):
        for route in routes:
            remote_owner.setdefault(route, j)
    in_repository = {route for _, routes in repo_side for route in routes}

    warnings.extend(_homonym_warnings(resources))
    output_resources: List[Dict[str, Any]] = []
    moved_routes: List[str] = []

    for i, resource in enumerate(resources):
        data = resource.data or {}
        name = data.get("name")
        label = repo_labels[i]
        remote_index = pairs.get(i)
        remote = remote_resources[remote_index] if remote_index is not None else {}
        block = copy.deepcopy(remote) if remote else {}
        # Ligado pelas rotas, o recurso pode ter trocado de nome: o repositório
        # prevalece, e o `id` fica — trocar o nome não recria o recurso.
        block["name"] = name if name is not None else block.get("name")

        resource_flow = resolve_declared_flow(
            _declared(data), root_flow.effective, inherit=_inherits(data)
        )
        warnings.extend(_scope_warnings(resource_flow, remote, f"resource {label}"))
        warnings.extend(
            _cut_inherited_warnings(
                resource_flow, remote, remote_composed_root, composed_root,
                f"resource {label}",
            )
        )
        _expect(f"resource {label}", resource_flow)
        if data.get("description") is not None:
            block["description"] = data.get("description")
        url, timeout = _destination(data)
        block["destination"] = url
        block["timeout"] = timeout
        block["interceptors"] = assemble_scope_flow(
            resource_flow,
            remote.get("interceptors"),
            generate_idtemp=counter,
            resolver_content=_content,
            inherited=composed_root,
        )
        composed_resource = composed_flow(block["interceptors"], composed_root)
        remote_composed_resource = composed_flow(
            remote.get("interceptors"), remote_composed_root
        )

        remote_by_key = {
            _route(o.get("method"), o.get("path")): o
            for o in (remote.get("operations") or [])
        }
        operations: List[Dict[str, Any]] = []
        for op in resource.operations:
            od = op.data or {}
            key = _route(op.method, od.get("path"))
            # Só reaproveita o remoto se a rota estiver no recurso ligado ao seu
            # dono: `remote_by_key` é do recurso pareado, e só dele (W-6).
            remote_op = remote_by_key.get(key) or {}
            origin = remote_owner.get(key)
            if origin is not None and origin != remote_index:
                moved_routes.append(
                    f"{_route_label(key)}: sai do recurso {remote_labels[origin]} e "
                    f"vai para o recurso {name} (pasta `{resource.slug}`)"
                    + (", que será criado" if remote_index is None else "")
                )
            item = copy.deepcopy(remote_op) if remote_op else {}
            op_flow = resolve_declared_flow(
                _declared(od), resource_flow.effective, inherit=_inherits(od)
            )
            warnings.extend(
                _scope_warnings(op_flow, remote_op, f"{op.method} {od.get('path')}")
            )
            warnings.extend(
                _cut_inherited_warnings(
                    op_flow, remote_op, remote_composed_resource, composed_resource,
                    f"{op.method} {od.get('path')}",
                )
            )
            _expect(_route_label(key), op_flow)
            item["method"] = op.method
            item["path"] = od.get("path")
            if od.get("description") is not None:
                item["description"] = od.get("description")
            url, timeout = _destination(od)
            item["destination"] = url
            item["timeout"] = timeout
            item["interceptors"] = assemble_scope_flow(
                op_flow,
                remote_op.get("interceptors"),
                generate_idtemp=counter,
                resolver_content=_content,
                inherited=composed_resource,
            )
            if not remote_op:
                # W-6: a operação PERTENCE ao recurso. Reaproveitar o `id` de
                # uma operação de outro recurso faz o Manager DESCARTÁ-LA, com
                # HTTP 200 — operação nova vai sem `id`.
                item.pop("id", None)
            operations.append(item)

        block["operations"] = operations
        output_resources.append(block)

    body["resources"] = output_resources

    # O PUT grava a revisão inteira: o que está no Manager e não no repositório
    # é apagado. Não bloqueia — remover pode ser a intenção —, mas é avisado.
    # A comparação é por recurso e por rota, nunca por nome: um homônimo que
    # some precisa aparecer aqui mesmo com o nome ainda presente.
    paired = set(pairs.values())
    vanished = [remote_labels[j] for j in range(len(remote_resources)) if j not in paired]
    # Só para recurso que continua: o que some junto com o recurso inteiro já é
    # nomeado no aviso de recursos. Rota que está em outra pasta não sumiu —
    # mudou de recurso, e é avisada à parte.
    vanished_routes = [
        f"{_route_label(route)} (recurso {remote_labels[j]})"
        for j in sorted(paired)
        for route in sorted(remote_routes[j], key=str)
        if route not in in_repository
    ]
    if vanished:
        warnings.append(
            "Os recursos abaixo existem no Manager mas não estão no repositório. Ao "
            "publicar, eles serão apagados do Manager:\n"
            + "\n".join(f"  - {s}" for s in sorted(vanished))
            + "\n\nSe não era essa a intenção, adicione-os ao repositório antes de "
            "publicar."
        )
    if moved_routes:
        warnings.append(
            "As rotas abaixo estão no repositório em um recurso diferente do que têm "
            "hoje no Manager. Ao publicar, elas saem do recurso de origem e passam "
            "para o de destino:\n"
            + "\n".join(f"  - {r}" for r in moved_routes)
            + "\n\nSe não era essa a intenção, devolva-as à pasta do recurso de origem."
        )
    if vanished_routes:
        warnings.append(
            "As rotas abaixo existem no Manager mas não estão no repositório. Ao "
            "publicar, elas serão apagadas do Manager:\n"
            + "\n".join(f"  - {r}" for r in vanished_routes)
            + "\n\nSe não era essa a intenção, adicione-as ao repositório antes de "
            "publicar."
        )

    return AssembledPayload(body=body, warnings=warnings, expected=expected)


# --------------------------------------------------------------------------- E3.1


def _side(no: Dict[str, Any]) -> List[Tuple[Optional[str], List[Route]]]:
    return [(r.get("name"), _node_routes(r)) for r in no.get("resources") or []]


def _verification_labels(
    sent: Dict[str, Any], published: Dict[str, Any]
) -> Tuple[List[str], List[str], Dict[int, int]]:
    """Rótulos dos recursos dos dois lados, ligados pelas rotas.

    O recurso publicado herda o rótulo do enviado com quem foi ligado — é a
    mesma regra do `assemble`, então os escopos do `expected` batem. O que fica
    sem par é divergência.
    """
    sent_side, published_side = _side(sent), _side(published)
    pairs = pair_by_routes(sent_side, published_side)

    sent_labels = _resource_labels(sent_side)
    own = _resource_labels(published_side)
    by_published = {j: i for i, j in pairs.items()}
    published_labels = []
    for j, own_label in enumerate(own):
        if j in by_published:
            published_labels.append(sent_labels[by_published[j]])
        elif own_label in sent_labels:
            # Não pode colidir com um escopo enviado: os itens se misturariam.
            published_labels.append(f"{own_label} (só no Manager)")
        else:
            published_labels.append(own_label)
    return sent_labels, published_labels, pairs


def _scopes(
    no: Dict[str, Any], labels: Sequence[str]
) -> Iterator[Tuple[str, Dict[str, Any]]]:
    """Cada escopo da árvore com o seu rótulo.

    A rota basta como rótulo da operação: é única na revisão (W-6 e I-6).
    """
    yield "raiz", no
    for resource, label in zip(no.get("resources") or [], labels):
        yield f"resource {label}", resource
        for op in resource.get("operations") or []:
            yield _route_label(_route(op.get("method"), op.get("path"))), op


def _operations_signature(no: Dict[str, Any], labels: Sequence[str]) -> set:
    return {
        (label, *_route(op.get("method"), op.get("path")))
        for resource, label in zip(no.get("resources") or [], labels)
        for op in resource.get("operations") or []
    }


def _by_scope(
    no: Dict[str, Any], labels: Sequence[str]
) -> Dict[str, List[Dict[str, Any]]]:
    """Itens governados de cada escopo da árvore, indexados pelo rótulo."""
    return {
        scope: partition(node.get("interceptors"))[0]
        for scope, node in _scopes(no, labels)
    }


def _target_signature(item: Dict[str, Any]) -> Tuple[Any, ...]:
    """Tipo, Custom, ponto de execução e `content` normalizado de um item."""
    content = (
        None
        if item.get("type") == "Custom"
        else json.dumps(normalize_content(item.get("content")), sort_keys=True, default=str)
    )
    point = str(item.get("executionPoint") or "").upper()
    return (item.get("type"), _custom_id(item), point, content)


def _tombstones_by_scope(
    no: Dict[str, Any], labels: Sequence[str]
) -> Dict[str, Dict[Tuple[Any, ...], List[Dict[str, Any]]]]:
    """Marcações de remoção de cada escopo, agrupadas pelo item herdado que
    removem, resolvido no fluxo que o pai executa do mesmo lado."""
    output: Dict[str, Dict[Tuple[Any, ...], List[Dict[str, Any]]]] = {}

    def group(scope: str, items: Any, inherited: Sequence[Dict[str, Any]]) -> None:
        by_identity = {identity(i): i for i in inherited if identity(i) is not None}
        groups: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = {}
        for tombstone in partition(items)[0]:
            if tombstone.get("status") != "REMOVED":
                continue
            target = by_identity.get(tombstone_target(tombstone), tombstone)
            groups.setdefault(_target_signature(target), []).append(tombstone)
        output[scope] = groups

    root = composed_flow(no.get("interceptors"))
    group("raiz", no.get("interceptors"), [])
    for resource, label in zip(no.get("resources") or [], labels):
        group(f"resource {label}", resource.get("interceptors"), root)
        composed = composed_flow(resource.get("interceptors"), root)
        for op in resource.get("operations") or []:
            group(
                _route_label(_route(op.get("method"), op.get("path"))),
                op.get("interceptors"),
                composed,
            )
    return output


def _count_by_scope(no: Dict[str, Any], labels: Sequence[str]) -> Dict[str, int]:
    """Quantos itens **vivos** cada escopo tem.

    Tombstones ficam de fora porque não são fluxo: contá-los faria um escopo com
    8 itens e 1 supressão parecer ter 9. Eles são conferidos à parte.
    """
    return {
        scope: len([i for i in items if i.get("status") != "REMOVED"])
        for scope, items in _by_scope(no, labels).items()
    }


def _destinations_by_scope(no: Dict[str, Any], labels: Sequence[str]) -> Dict[str, Any]:
    """`destination` e `timeout` de cada escopo, para a conferência.

    Entram aqui porque `''` e `null` **não** são equivalentes na escrita: a
    plataforma guarda literalmente o que recebe (medido em 2026-10-15, fechando
    a P-8). Sem conferi-los, uma troca silenciosa de um pelo outro passaria.
    """
    return {
        scope: (node.get("destination"), node.get("timeout"))
        for scope, node in _scopes(no, labels)
    }


def verify(
    sent: Dict[str, Any],
    published: Dict[str, Any],
    expected: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> List[str]:
    """Compara enviado × publicado e devolve as divergências.

    **HTTP 200 não é prova de sucesso** (W-8): foram observadas três perdas
    silenciosas distintas sob 200 — `idTemp` colidido, operação migrada de
    recurso e item descartado por dedupe. A releitura é o veredito.

    `expected` é o fluxo que o repositório declara (`AssembledPayload.expected`).
    Com ele, o fluxo publicado é comparado também com o **declarado** — tipo,
    ordem e `content` —, e não só com o payload: uma perda na própria montagem
    passaria intacta por uma comparação com o enviado.
    """
    divergences: List[str] = []
    # Os recursos dos dois lados são ligados pelas rotas, como no `assemble`:
    # pelo nome, dois homônimos virariam um só escopo e a contagem mentiria.
    sent_labels, published_labels, pairs = _verification_labels(sent, published)
    if expected:
        divergences.extend(
            _declared_flow_divergences(expected, published, published_labels)
        )

    sent_ops = _operations_signature(sent, sent_labels)
    published_ops = _operations_signature(published, published_labels)
    for missing in sorted(sent_ops - published_ops):
        divergences.append(
            f"a operação {missing[1]} {missing[2]}, do recurso {missing[0]}, foi "
            "enviada mas não está no Manager"
        )
    for leftover in sorted(published_ops - sent_ops):
        divergences.append(
            f"a operação {leftover[1]} {leftover[2]}, do recurso {leftover[0]}, está "
            "no Manager mas não foi enviada"
        )

    sent_items = _count_by_scope(sent, sent_labels)
    published_items = _count_by_scope(published, published_labels)
    for scope, count in sorted(sent_items.items()):
        present = published_items.get(scope)
        if present is None:
            divergences.append(f"{scope} foi enviado mas não está no Manager")
        elif present != count:
            divergences.append(
                f"{scope}: foram enviados {count} interceptor(es) e o Manager "
                f"gravou {present}"
            )

    for missing in sorted(r for i, r in enumerate(sent_labels) if i not in pairs):
        divergences.append(f"o recurso {missing} foi enviado mas não está no Manager")
    # O T10 provou que o que não está no repositório é removido. Um recurso que
    # sobrevive sem ter sido enviado é divergência na direção oposta — e sem esta
    # conferência ele passaria despercebido.
    linked = set(pairs.values())
    for leftover in sorted(r for j, r in enumerate(published_labels) if j not in linked):
        divergences.append(
            f"o recurso {leftover} está no Manager mas não foi enviado"
        )

    # Pelo item que removem, e não pelo `parent.id`: a marcação enviada por
    # `idTemp` volta gravada com o id que o Manager gerou.
    sent_tombstones = _tombstones_by_scope(sent, sent_labels)
    written_tombstones = _tombstones_by_scope(published, published_labels)
    for scope in sorted(set(sent_tombstones) | set(written_tombstones)):
        sent_items = sent_tombstones.get(scope, {})
        written = written_tombstones.get(scope, {})
        leftover: List[Dict[str, Any]] = []
        missing: List[Dict[str, Any]] = []
        for target in sorted(set(sent_items) | set(written), key=str):
            difference = len(written.get(target, [])) - len(sent_items.get(target, []))
            if difference > 0:
                leftover += written[target][:difference]
            elif difference < 0:
                missing += sent_items[target][:-difference]
        if leftover:
            divergences.append(
                f"{scope}: o Manager ainda tem {len(leftover)} marcação(ões) de "
                f"interceptor removido ({_label(leftover)}) que não foram "
                "enviadas; elas continuam suprimindo itens do fluxo herdado"
            )
        if missing:
            divergences.append(
                f"{scope}: foram enviadas {len(missing)} marcação(ões) de interceptor "
                f"removido ({_label(missing)}) que o Manager não gravou; esses itens "
                "herdados continuam executando aqui"
            )

    sent_destinations = _destinations_by_scope(sent, sent_labels)
    published_destinations = _destinations_by_scope(published, published_labels)
    for scope, sent_pair in sorted(sent_destinations.items()):
        published_pair = published_destinations.get(scope)
        if published_pair is None:
            continue  # a ausência do escopo já foi reportada acima
        if sent_pair != published_pair:
            divergences.append(
                f"{scope}: destination/timeout foi enviado como {sent_pair!r} e "
                f"gravado como {published_pair!r}"
            )

    divergences.extend(_basic_info_divergences(sent, published))
    return divergences


_POINT_NAME = {"FIRST": "request", "SECOND": "response"}


def _custom_id(item: Dict[str, Any]) -> Optional[int]:
    value = item.get("customInterceptorId")
    if value is None and item.get("type") == "Custom":
        value = item.get("id")
    return value


def _item_label(item: Dict[str, Any]) -> str:
    custom_id = _custom_id(item)
    return f"Custom#{custom_id}" if item.get("type") == "Custom" else str(item.get("type"))


def _different_keys(declared: Any, written: Any) -> str:
    """Quais campos do `content` mudaram — o valor inteiro seria ilegível."""
    if isinstance(declared, dict) and isinstance(written, dict):
        keys = sorted(
            k for k in set(declared) | set(written) if declared.get(k) != written.get(k)
        )
        if keys:
            return ", ".join(
                f"`{k}` declarado {declared.get(k)!r}, gravado {written.get(k)!r}"
                for k in keys
            )
    return f"declarado {declared!r}, gravado {written!r}"


def _declared_flow_divergences(
    expected: Dict[str, List[Dict[str, Any]]],
    published: Dict[str, Any],
    labels: Sequence[str],
) -> List[str]:
    """Fluxo publicado × fluxo declarado, por escopo e execution point.

    A plataforma executa pela `position`, então é por ela que o publicado é
    lido. O `content` só é comparado nos tipos nativos — no `Custom` o id
    identifica o objeto (V-11 §4) —, e pela mesma normalização da conformidade.
    """
    divergences: List[str] = []
    published_by_scope = _by_scope(published, labels)
    for scope, declared in sorted(expected.items()):
        written_in_scope = published_by_scope.get(scope)
        if written_in_scope is None:
            continue  # a ausência do escopo é reportada pela contagem
        for point, point_name in _POINT_NAME.items():
            wanted = [
                d for d in declared
                if str(d.get("executionPoint") or "").upper() == point
            ]
            actual = sorted(
                (
                    i for i in written_in_scope
                    if str(i.get("executionPoint") or "").upper() == point
                    and i.get("status") != "REMOVED"
                ),
                key=lambda i: i.get("position") or 0,
            )
            wanted_signature = [(d.get("type"), _custom_id(d)) for d in wanted]
            actual_signature = [(i.get("type"), _custom_id(i)) for i in actual]
            if wanted_signature != actual_signature:
                divergences.append(
                    f"{scope}: o {point_name} foi declarado como "
                    f"[{', '.join(_item_label(d) for d in wanted)}] e gravado como "
                    f"[{', '.join(_item_label(i) for i in actual)}]"
                )
                continue
            for position, (d, i) in enumerate(zip(wanted, actual), start=1):
                if d.get("type") == "Custom":
                    continue
                wanted_content = normalize_content(d.get("content"))
                actual_content = normalize_content(i.get("content"))
                if wanted_content != actual_content:
                    divergences.append(
                        f"{scope}: o {d.get('type')} (item {position} do "
                        f"{point_name}) não foi gravado como declarado — "
                        f"{_different_keys(wanted_content, actual_content)}"
                    )
    return divergences


def _api_tags_signature(api: Dict[str, Any]) -> Dict[str, frozenset]:
    """`attributeName` → conjunto de tags; a ordem não é contrato da plataforma."""
    return {
        str(item.get("attributeName")): frozenset(str(t) for t in (item.get("tags") or []))
        for item in (api.get("apiTags") or [])
        if isinstance(item, dict)
    }


def _basic_info_divergences(
    sent: Dict[str, Any], published: Dict[str, Any]
) -> List[str]:
    """Confere o `api` aninhado — onde o basic info viaja (W-7).

    Uma tag inexistente no atributo é aceita com 200 e o Manager apaga
    **todas** as `apiTags`. Sem esta conferência, o comando reportava sucesso.
    """
    sent_api = sent.get("api") if isinstance(sent.get("api"), dict) else {}
    published_api = published.get("api") if isinstance(published.get("api"), dict) else {}
    divergences: List[str] = []

    for field_name in ("name", "description"):
        if field_name in sent_api and sent_api.get(field_name) != published_api.get(field_name):
            divergences.append(
                f"o campo `{field_name}` foi enviado como {sent_api.get(field_name)!r} e "
                f"gravado como {published_api.get(field_name)!r}"
            )

    if "apiTags" not in sent_api:
        return divergences
    sent_items = _api_tags_signature(sent_api)
    published_items = _api_tags_signature(published_api)
    for name in sorted(sent_items.keys() - published_items.keys()):
        divergences.append(
            f"o atributo `{name}` foi enviado em `apiTags` mas não está no Manager"
        )
    for name in sorted(published_items.keys() - sent_items.keys()):
        divergences.append(
            f"o atributo `{name}` está nas `apiTags` do Manager mas não foi enviado"
        )
    for name in sorted(sent_items.keys() & published_items.keys()):
        if sent_items[name] != published_items[name]:
            divergences.append(
                f"o atributo `{name}` foi enviado com as tags {sorted(sent_items[name])} "
                f"e gravado com {sorted(published_items[name])}"
            )
    return divergences
