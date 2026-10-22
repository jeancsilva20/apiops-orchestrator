"""Materializa o layout canônico a partir do estado do Manager.

Lógica pura: recebe os dicts já lidos por GET e devolve `(caminho, texto)`. Não
toca disco nem rede — quem escreve é a camada de aplicação.

Opera sobre o **wire cru**, sem modelos intermediários.

Decisões que o código implementa:

* **V-18** — o escopo raiz é `all.yaml`;
* **V-25** — a supressão de item herdado é a **lista completa explícita**; o item
  removido é identificado por `parent.id`, confirmado por leitura da revisão 9175;
* **V-22** — o que está fora de `FIRST`/`SECOND` não entra no YAML;
* **V-26** — a herança é sempre declarada (`inherit`);
* **V-28** — itens próprios sem marcações são append (`inherit: true`);
* **fila 23/24** — os dois reparos de serialização.
"""

import json
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from apiops_orchestrator.domain.services import repo_layout as layout
from apiops_orchestrator.domain.services.interceptor_flow import particionar
from apiops_orchestrator.domain.services.yaml_serialization import escalar

LARGURA_DESCRICAO = 92
STATUS_REMOVIDO = "REMOVED"


@dataclass(frozen=True)
class ArquivoMaterializado:
    caminho: str
    texto: str


@dataclass(frozen=True)
class ResultadoMaterializacao:
    arquivos: List[ArquivoMaterializado]
    avisos: List[str]

    @property
    def caminhos(self) -> List[str]:
        return [a.caminho for a in self.arquivos]


# --------------------------------------------------------------------------- YAML


def _bloco(dados: Any, recuo: int) -> List[str]:
    """Serializa dict/list em YAML de bloco, com os reparos de escalar."""
    linhas: List[str] = []
    pad = " " * recuo
    if isinstance(dados, dict):
        for chave, valor in dados.items():
            if isinstance(valor, (dict, list)) and valor:
                linhas.append(f"{pad}{chave}:")
                linhas.extend(_bloco(valor, recuo + 2))
            elif isinstance(valor, dict):
                linhas.append(f"{pad}{chave}: {{}}")
            elif isinstance(valor, list):
                linhas.append(f"{pad}{chave}: []")
            else:
                linhas.append(f"{pad}{chave}: {escalar(valor)}")
    elif isinstance(dados, list):
        for item in dados:
            if isinstance(item, dict) and item:
                sub = _bloco(item, recuo + 2)
                linhas.append(f"{pad}- {sub[0].strip()}")
                linhas.extend(sub[1:])
            else:
                linhas.append(f"{pad}- {escalar(item)}")
    return linhas


def _descricao(valor: Optional[str], recuo: int = 0) -> List[str]:
    """Descrição curta em uma linha; longa vira bloco dobrado `>-`."""
    import re

    bruto = re.sub(r"\s+", " ", str(valor or "").strip())
    pad = " " * recuo
    if not bruto:
        return []
    if len(bruto) <= 90:
        return [f"{pad}description: {escalar(bruto)}"]
    linhas = [f"{pad}description: >-"]
    atual = ""
    for palavra in bruto.split(" "):
        if len(atual) + len(palavra) + 1 > LARGURA_DESCRICAO:
            linhas.append(f"{pad}  {atual}")
            atual = palavra
        else:
            atual = f"{atual} {palavra}".strip()
    if atual:
        linhas.append(f"{pad}  {atual}")
    return linhas


def _bloco_destination(url: Any, timeout: Any) -> List[str]:
    linhas = ["destination:"]
    if url:
        linhas.append(f"  url: {escalar(url)}")
    else:
        linhas.append("  url: ''            # vazio = herda do escopo acima")
    if timeout not in (None, ""):
        linhas.append(f"  timeout: {escalar(str(timeout))}")
    return linhas


def _bloco_interceptors(itens: Sequence[Dict[str, Any]], titulo: str) -> List[str]:
    if not itens:
        return []
    linhas = ["", f"{titulo}:"]
    for item in itens:
        if item.get("type") == "Custom" and item.get("customInterceptorId"):
            linhas.append("  - type: Custom")
            linhas.append(f"    id: {item['customInterceptorId']}")
            continue
        linhas.append(f"  - type: {escalar(item.get('type'))}")
        bruto = item.get("content")
        dados = bruto
        if isinstance(bruto, str):
            try:
                dados = json.loads(bruto)
            except (TypeError, ValueError):
                dados = bruto
        if isinstance(dados, (dict, list)) and dados:
            linhas.append("    content:")
            linhas.extend(_bloco(dados, 6))
        elif dados not in (None, "", {}, []):
            linhas.append(f"    content: {escalar(dados)}")
    return linhas


def _por_ponto(itens: Iterable[Dict[str, Any]], ponto: str) -> List[Dict[str, Any]]:
    return [i for i in itens if (i.get("executionPoint") or "").upper() == ponto]


def _fluxo(itens: Sequence[Dict[str, Any]]) -> List[str]:
    return _bloco_interceptors(_por_ponto(itens, "FIRST"), "interceptors_request") + (
        _bloco_interceptors(_por_ponto(itens, "SECOND"), "interceptors_response")
    )


# --------------------------------------------------------------------------- escopos


def _separar(itens: Optional[Sequence[Dict[str, Any]]]) -> Tuple[list, list, list]:
    """Governados presentes, tombstones e preservados.

    O tombstone (`status: REMOVED`) NÃO é item do fluxo: é a marca de um item
    herdado que foi suprimido. Tratá-lo como presente publicaria de volta o que
    se queria remover.
    """
    governados, preservados = particionar(itens)
    presentes = [i for i in governados if i.get("status") != STATUS_REMOVIDO]
    tombstones = [i for i in governados if i.get("status") == STATUS_REMOVIDO]
    return presentes, tombstones, preservados


def _suprimir(herdado: Sequence[Dict[str, Any]], tombstones: Sequence[Dict[str, Any]]):
    """Fluxo herdado menos os itens apontados por `parent.id` (V-25 §2.1)."""
    alvos = {
        (t.get("parent") or {}).get("id")
        for t in tombstones
        if (t.get("parent") or {}).get("id") is not None
    }
    return [i for i in herdado if i.get("id") not in alvos], alvos


def materializar(api: Dict[str, Any], revision: Dict[str, Any]) -> ResultadoMaterializacao:
    """Produz a árvore canônica inteira a partir do estado remoto."""
    avisos: List[str] = []
    arquivos: List[ArquivoMaterializado] = []

    # --- api-basic-info.yaml -------------------------------------------------
    spec = {
        "id": api.get("id"),
        "name": api.get("name"),
        "version": api.get("version"),
        "basePath": api.get("basePath"),
    }
    linhas = [
        "apiVersion: api-management.sensedia.com/v1",
        "kind: ApiBasicInfo",
        "spec:",
        f"  id: {escalar(spec['id'])}",
        f"  name: {escalar(spec['name'])}",
        f"  version: {escalar(spec['version'])}",
        f"  basePath: {escalar(spec['basePath'])}",
    ]
    linhas.extend(_descricao(api.get("description"), recuo=2))
    # `template` não vem do wire: a plataforma não tem esta chave (D-12).
    linhas.append("  template: ''")
    responsavel = api.get("apiResponsible") or {}
    linhas.append("  apiResponsible:")
    linhas.append(f"    username: {escalar(responsavel.get('username') or '')}")
    linhas.append(f"    groupName: {escalar(responsavel.get('groupName') or '')}")
    tags = api.get("apiTags")
    if tags is not None:
        linhas.append("  apiTags:")
        for t in tags:
            linhas.append(f"    - attributeName: {escalar(t.get('attributeName'))}")
            valores = t.get("tags") or []
            if valores:
                linhas.append("      tags:")
                linhas.extend(_bloco(valores, 8))
            else:
                linhas.append("      tags: []")
    arquivos.append(_arquivo(layout.ARQUIVO_BASIC_INFO, linhas))

    # --- all.yaml (escopo raiz) ---------------------------------------------
    raiz_presentes, raiz_tombstones, raiz_preservados = _separar(
        revision.get("interceptors")
    )
    if raiz_tombstones:
        avisos.append(
            "a raiz da revision tem item com status REMOVED, o que não deveria "
            "acontecer: a raiz não herda de nenhum escopo acima"
        )
    linhas = [
        f"# escopo `all` — raiz da revision {revision.get('id')} "
        f"(revisionNumber {revision.get('revisionNumber')})",
        f"# API {api.get('id')} · {api.get('name')} · {api.get('basePath')}",
    ]
    linhas += _bloco_destination(revision.get("destination"), revision.get("timeout"))
    linhas += _fluxo(raiz_presentes)
    if raiz_preservados:
        linhas += [
            "",
            f"# {len(raiz_preservados)} interceptor(es) fora de FIRST/SECOND — "
            "estado não governado, preservado por GET no publish",
        ]
    arquivos.append(_arquivo(layout.ARQUIVO_RAIZ, linhas))

    # --- recursos e operações ------------------------------------------------
    recursos = revision.get("resources") or []
    for recurso in recursos:
        pasta = layout.nome_pasta(recurso, recursos, avisos)
        base = f"{layout.PASTA_RECURSOS}/{pasta}"

        rec_presentes, rec_tombstones, _ = _separar(recurso.get("interceptors"))
        herdado_do_recurso, _ = _suprimir(raiz_presentes, rec_tombstones)
        efetivo_do_recurso = herdado_do_recurso + rec_presentes

        linhas = [f"name: {escalar(recurso.get('name'))}"]
        linhas.extend(_descricao(recurso.get("description")))
        linhas += _bloco_destination(recurso.get("destination"), recurso.get("timeout"))
        linhas += _declarar_heranca(
            presentes=rec_presentes,
            tombstones=rec_tombstones,
            herdado=raiz_presentes,
        )
        arquivos.append(_arquivo(f"{base}/{layout.ARQUIVO_RECURSO}", linhas))

        for op in recurso.get("operations") or []:
            op_presentes, op_tombstones, _ = _separar(op.get("interceptors"))
            linhas = [f"path: {escalar(op.get('path'))}"]
            linhas += _bloco_destination(op.get("destination"), op.get("timeout"))
            linhas.extend(_descricao(op.get("description")))
            linhas += _declarar_heranca(
                presentes=op_presentes,
                tombstones=op_tombstones,
                herdado=efetivo_do_recurso,
            )
            nome = layout.nome_arquivo(op, avisos)
            arquivos.append(_arquivo(f"{base}/{nome}", linhas))

    return ResultadoMaterializacao(arquivos=arquivos, avisos=avisos)


def _declarar_heranca(
    *,
    presentes: Sequence[Dict[str, Any]],
    tombstones: Sequence[Dict[str, Any]],
    herdado: Sequence[Dict[str, Any]],
) -> List[str]:
    """Decide entre herança pura, append e supressão — e escreve o bloco.

    A supressão (V-25) é a **lista completa explícita**: o fluxo herdado menos os
    itens apontados por `parent.id`, mais o que o escopo tem de próprio. Sem
    marcações, os itens próprios executam depois do herdado: é append (V-28).
    """
    if tombstones:
        restante, alvos = _suprimir(herdado, tombstones)
        nomes = ", ".join(sorted({str(t.get("type")) for t in tombstones}))
        nao_resolvidos = len(tombstones) - len(
            [a for a in alvos if any(i.get("id") == a for i in herdado)]
        )
        linhas = ["", "inherit: false", f"# este ponto deixa de executar, do herdado: {nomes}"]
        fluxo = list(restante) + list(presentes)
        if fluxo:
            linhas.append("# a lista abaixo é o fluxo completo que vale aqui")
        else:
            linhas.append("# não executa nenhum interceptor")
        if nao_resolvidos:
            linhas.append(
                f"# atenção: {nao_resolvidos} remoção(ões) apontam para um "
                "interceptor que não está no fluxo herdado deste ponto"
            )
        return linhas + _fluxo(fluxo)

    if not presentes:
        # Sem artigo: `escopo` ora é "recurso", ora "operação", e qualquer
        # artigo fixo erra a concordância num dos dois.
        return [
            "",
            "inherit: true",
            "# apenas herda o fluxo do nível acima: nenhum interceptor próprio",
        ]

    return [
        "",
        "inherit: true",
        "# os interceptors abaixo executam depois do fluxo herdado",
    ] + _fluxo(presentes)


def _arquivo(caminho: str, linhas: Sequence[Optional[str]]) -> ArquivoMaterializado:
    texto = "\n".join(l for l in linhas if l is not None).rstrip() + "\n"
    return ArquivoMaterializado(caminho=caminho, texto=texto)
