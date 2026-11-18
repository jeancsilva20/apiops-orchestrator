#!/usr/bin/env python3
"""Extrai uma API do Sensedia Manager na estrutura de repositório proposta.

PROTÓTIPO DE VALIDAÇÃO — não é código do CLI. Só leitura (GET), nenhuma escrita.
Usa apenas a biblioteca padrão: não precisa de .env, requests ou PyYAML.

Como usar:
    1. preencha TOKEN com o access token de superadmin do Manager;
    2. preencha API_ID (e, se quiser, REVISION_NUMBER);
    3. python extrair_estrutura.py

Regras aplicadas (itens V-01, V-12, V-16 e V-17 do refino):

    slug(txt)   NFKD -> ascii · remove '{' '}' · [^A-Za-z0-9] -> '-' · colapsa '-'
                minúsculas · trim · trunca no último '-' antes de MAX_SLUG

    pasta       resources/<slug(resource.name)>
                colidiu ou truncou? -> tenta sufixo LEGÍVEL (path da 1ª operação)
                ainda colide ou estourou? -> sufixo MARCA sha1(operações)[:6]

    arquivo     <método>_<path completo, '/'->'_' , {param} preservado>.yaml

    destino     objeto { url, timeout } sempre declarado; url '' significa herdar
    interceptors  só executionPoint FIRST/SECOND; o resto é estado não governado
    inherit     true = herda o fluxo do escopo acima (default quando ausente)
                false = herança quebrada; o arquivo declara o fluxo que vale
"""

import hashlib
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request

# ----------------------------------------------------------------------------- configuração
HOST = "https://platform-production.sensedia.com"
TOKEN = "eyJraWQiOiIwSTZ2Kyt6NlJVaFlib2w5ak1sTHZSR0xjNnVVWndpQXJ6VGRQZGptSzBVPSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiIyaXJsZ25iZmE5Z2FjNDEyMm4zaGFvbTM1aCIsInRva2VuX3VzZSI6ImFjY2VzcyIsInNjb3BlIjoiYXBpcy9hbGwiLCJhdXRoX3RpbWUiOjE3OTE5OTA5NzgsImlzcyI6Imh0dHBzOi8vY29nbml0by1pZHAuc2EtZWFzdC0xLmFtYXpvbmF3cy5jb20vc2EtZWFzdC0xXzFRSXM0Y0VHaiIsImV4cCI6MTc5MjA3NzM3OCwiaWF0IjoxNzkxOTkwOTc4LCJ2ZXJzaW9uIjoyLCJqdGkiOiJmNzI5ZWM1ZC1kNTJmLTRjNjItYjMxYS00NmE1NTdhMTQzNDgiLCJjbGllbnRfaWQiOiIyaXJsZ25iZmE5Z2FjNDEyMm4zaGFvbTM1aCJ9.DmqH8uAIMIStTMLRGnde9LnjOoC2VNllRo2YL6QGIDPXrZblIF8q6766OAIdS4_N8Sv2oIMKk_xki9WQAuI3XsE2VuRvd-RZenshP1NRPk8s-PVPhAvB3fZJT-MIQOuNRZsISHBoCNKOQOwHTe1R_YGHuSBeuLBZAFtj_OzpV7g553NrYZM66sS4GT89GjAlhgfPLWRWcmXSsohP5qc89fifMT_AEKWEa0lE0tAX3DZ4_4NahrPShNWtm26P5psAtgxmPfbLFQilwQ7ueVazDmIspUG5cE7qiockQ3FPlVGKIxc0gVg5JvQSS_upjPi6o4Rx4WMIUYz5F19BjWK95w"
API_ID = 417
REVISION_NUMBER = 2      # None = revisão corrente (lastRevision); ou 1, 2, 3, 4
DESTINO = "saida"           # pasta onde a árvore será escrita (relativa a este arquivo)

MAX_SLUG = 60               # orçamento de caminho (Windows: 248 p/ diretório, 260 p/ arquivo)
MAX_ARQUIVO = 90            # teto do nome do arquivo (sem a extensao)
MAX_SUFIXO_PASTA = 40       # teto do sufixo legivel de desambiguacao de pasta
# -----------------------------------------------------------------------------

BASE = f"{HOST.rstrip('/')}/api-manager/api/v3"
GOV = {"FIRST", "SECOND"}
RESERVADOS = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {
    f"lpt{i}" for i in range(1, 10)
}
avisos = []


# ----------------------------------------------------------------------------- HTTP
def http_get(caminho):
    req = urllib.request.Request(
        BASE + caminho,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        corpo = exc.read().decode("utf-8", "ignore")[:200]
        if exc.code in (401, 403):
            sys.exit(f"ERRO {exc.code}: token recusado ou expirado.\n{corpo}")
        sys.exit(f"ERRO {exc.code} em GET {caminho}\n{corpo}")
    except urllib.error.URLError as exc:
        sys.exit(f"ERRO de rede em GET {caminho}: {exc.reason}")


# ----------------------------------------------------------------------------- nomes
def slug(texto, limite=MAX_SLUG):
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    t = t.replace("{", "").replace("}", "")
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
    t = re.sub(r"-{2,}", "-", t)
    if limite and len(t) > limite:
        corte = t[:limite]
        t = corte.rsplit("-", 1)[0] if "-" in corte else corte
    return t


def prefixo_comum(paths):
    if not paths:
        return ""
    segs = [p.strip("/").split("/") for p in paths]
    comum = []
    for i in range(min(len(s) for s in segs)):
        col = {s[i] for s in segs}
        if len(col) != 1:
            break
        comum.append(col.pop())
    return "/".join(comum)


def operacoes_ordenadas(recurso):
    return sorted(
        (o.get("path", ""), (o.get("method") or "").upper())
        for o in recurso.get("operations") or []
    )


def marca(recurso):
    ops = [f"{m} {p}" for p, m in operacoes_ordenadas(recurso)]
    semente = "|".join(ops) or (recurso.get("name") or "")
    return hashlib.sha1(semente.encode("utf-8")).hexdigest()[:6]


def nome_pasta(recurso, todos):
    """Slug do name, com desambiguação híbrida: legível primeiro, marca como último recurso."""
    nome = recurso.get("name") or ""
    if not nome:
        nome = "/" + prefixo_comum([o["path"] for o in recurso.get("operations") or []])
    completo = slug(nome, limite=0)
    base = slug(nome)
    if base in RESERVADOS:
        base = f"{base}-recurso"

    homonimos = [r for r in todos if slug(r.get("name") or "") == base]
    truncou = completo != base
    if len(homonimos) == 1 and not truncou:
        return base

    if len(homonimos) > 1:
        nomes = {r.get("name") for r in homonimos}
        if len(nomes) == 1:
            avisos.append(f"{len(homonimos)} recursos com o MESMO nome {recurso.get('name')!r} — desambiguados no repo")
        else:
            avisos.append(f"{len(homonimos)} recursos cujo nome, truncado em {MAX_SLUG} chars, colide em {base!r} — desambiguados no repo")

    # (a) sufixo legível: path da primeira operação
    ops = operacoes_ordenadas(recurso)
    if ops:
        legivel = f"{base}-{slug(ops[0][0], MAX_SUFIXO_PASTA)}"
        concorrentes = []
        for r in homonimos:
            o = operacoes_ordenadas(r)
            if o:
                concorrentes.append(f"{base}-{slug(o[0][0], MAX_SUFIXO_PASTA)}")
        unico = concorrentes.count(legivel) <= 1
        if unico and len(legivel) <= MAX_SLUG:
            return legivel

    # (c) marca determinística
    return f"{base}-{marca(recurso)}"


def slug_path(path):
    """Path completo como sufixo de arquivo: '/' vira '_', `{param}` é preservado.

    Transformação mínima — o nome do arquivo tem de ser lido como a rota:
        /letras/{id}                          -> letras_{id}
        /tarefas/{id}/atribuicao-responsavel  -> tarefas_{id}_atribuicao-responsavel
    """
    t = unicodedata.normalize("NFKD", path or "").encode("ascii", "ignore").decode()
    t = t.strip("/").lower()
    t = re.sub(r"[^A-Za-z0-9{}\-_/]+", "-", t)
    t = t.replace("/", "_")
    return re.sub(r"-{2,}", "-", t).strip("-_")


def nome_arquivo(op, prefixo=None):
    """<método>_<path completo>.yaml — o prefixo do recurso NÃO é cortado.

    Só quando o nome estoura MAX_ARQUIVO ele é truncado e recebe a marca
    determinística, para não ultrapassar o limite de caminho do sistema de arquivos.
    """
    metodo = (op.get("method") or "").lower()
    sufixo = slug_path(op.get("path"))
    nome = f"{metodo}_{sufixo}" if sufixo else metodo
    if len(nome) > MAX_ARQUIVO:
        corte = nome[:MAX_ARQUIVO]
        corte = corte.rsplit("_", 1)[0] if "_" in corte else corte
        digest = hashlib.sha1(f"{metodo} {op.get('path')}".encode("utf-8")).hexdigest()[:6]
        nome = f"{corte}-{digest}"
        avisos.append(f"nome de arquivo truncado em {MAX_ARQUIVO} chars: {metodo.upper()} {op.get('path')}")
    return f"{nome}.yaml"


# ----------------------------------------------------------------------------- YAML
def escalar(valor):
    if valor is None:
        return "null"
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, (int, float)):
        return str(valor)
    texto = str(valor)
    if texto == "" or re.search(r"[:#\n]|^\s|\s$", texto) or texto.lower() in {"true", "false", "null", "yes", "no"}:
        return json.dumps(texto, ensure_ascii=False)
    return texto


def texto(valor):
    """String de texto livre sempre entre aspas (molde da D-003)."""
    return json.dumps(str(valor or ""), ensure_ascii=False)


def descricao(valor, recuo=0):
    """Descricao curta em uma linha; longa vira bloco dobrado `>-` quebrado em ~92 colunas."""
    bruto = re.sub(r"\s+", " ", str(valor or "").strip())
    pad = " " * recuo
    if len(bruto) <= 90:
        return [f"{pad}description: {texto(bruto)}"]
    linhas, atual = [f"{pad}description: >-"], ""
    for palavra in bruto.split(" "):
        if len(atual) + len(palavra) + 1 > 92:
            linhas.append(f"{pad}  {atual}")
            atual = palavra
        else:
            atual = f"{atual} {palavra}".strip()
    if atual:
        linhas.append(f"{pad}  {atual}")
    return linhas


def yaml_bloco(dados, recuo):
    linhas = []
    pad = " " * recuo
    if isinstance(dados, dict):
        for chave, valor in dados.items():
            if isinstance(valor, (dict, list)) and valor:
                linhas.append(f"{pad}{chave}:")
                linhas.extend(yaml_bloco(valor, recuo + 2))
            else:
                linhas.append(f"{pad}{chave}: {escalar(valor) if not isinstance(valor, (dict, list)) else ('{}' if isinstance(valor, dict) else '[]')}")
    elif isinstance(dados, list):
        for item in dados:
            if isinstance(item, dict) and item:
                sub = yaml_bloco(item, recuo + 2)
                linhas.append(f"{pad}- {sub[0].strip()}")
                linhas.extend(sub[1:])
            else:
                linhas.append(f"{pad}- {escalar(item)}")
    return linhas


def bloco_destination(destino, timeout):
    linhas = ["destination:"]
    if destino:
        linhas.append(f"  url: {destino}")
    else:
        linhas.append("  url: ''            # vazio = herda do escopo acima")
    if timeout:
        linhas.append(f"  timeout: '{timeout}'")
    return linhas


def bloco_interceptors(itens, titulo):
    if not itens:
        return []
    linhas = ["", f"{titulo}:"]
    for item in itens:
        if item.get("type") == "Custom" and item.get("customInterceptorId"):
            linhas.append("  - type: Custom")
            linhas.append(f"    id: {item['customInterceptorId']}")
            continue
        linhas.append(f"  - type: {item.get('type')}")
        bruto = item.get("content")
        try:
            dados = json.loads(bruto) if bruto else None
        except (TypeError, ValueError):
            dados = None
        if isinstance(dados, (dict, list)) and dados:
            linhas.append("    content:")
            linhas.extend(yaml_bloco(dados, 6))
    return linhas


def escrever(caminho, linhas):
    """Escreve o arquivo. Caminho longo demais vira AVISO e não interrompe a extração."""
    conteudo = "\n".join(l for l in linhas if l is not None).rstrip() + "\n"
    try:
        os.makedirs(os.path.dirname(caminho), exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as fh:
            fh.write(conteudo)
        return True
    except OSError as exc:
        avisos.append(
            f"NAO ESCRITO — caminho absoluto de {len(caminho)} chars excede o limite do sistema "
            f"de arquivos: ...{caminho[-70:]} [{type(exc).__name__}]"
        )
        return False


# ----------------------------------------------------------------------------- geração
def chave_interceptor(item):
    return (item.get("executionPoint"), item.get("type"), item.get("customInterceptorId"), item.get("content"))


def gerar_basic_info(api, raiz):
    """api-basic-info.yaml conforme a D-003 §3: shape direto em `spec.<campo>`.

    Campos de fundo (visibility, apiType, creationDate, revisions, lastRevision,
    flags e contadores) NAO entram no YAML — sao hidratados por GET no publish.
    """
    responsavel = api.get("apiResponsible") or {}
    linhas = [
        "apiVersion: api-management.sensedia.com/v1",
        "kind: ApiBasicInfo",
        "spec:",
        "  # id fisico da API no Manager; readOnly, gravado no import",
        f"  id: {api.get('id')}",
        f"  name: {texto(api.get('name'))}",
        f"  version: {texto(api.get('version'))}",
        "  # basePath: readOnly, imutavel",
        f"  basePath: {texto(api.get('basePath'))}",
        *descricao(api.get("description"), 2),
        "  # id da API-regua de interceptors (Golden Path). Declarado SEMPRE;",
        "  # vazio = esta API nao tem regua e a validacao nao roda. Nao vem do wire:",
        "  # a plataforma nao tem a chave `template` (8 confirmacoes de ausencia).",
        "  template: ''",
        "  # apiResponsible: read-only no MVP; declarado sempre, mesmo vazio",
        "  apiResponsible:",
        f"    username: {texto(responsavel.get('username'))}",
        f"    groupName: {texto(responsavel.get('groupName'))}",
    ]
    tags = api.get("apiTags")
    if tags is None:
        linhas.append("  # apiTags ausente = preserva o remoto; [] = remocao explicita")
    elif not tags:
        linhas.append("  apiTags: []")
    else:
        linhas.append("  # lista declarativa completa de pares (attributeName, tags[])")
        linhas.append("  apiTags:")
        for par in tags:
            linhas.append(f"    - attributeName: {texto(par.get('attributeName'))}")
            valores = ", ".join(texto(v) for v in (par.get("tags") or []))
            linhas.append(f"      tags: [{valores}]")
    escrever(os.path.join(raiz, "api-basic-info.yaml"), linhas)
    return "api-basic-info.yaml"


def gerar(api, revisao, raiz):
    governados = [i for i in (revisao.get("interceptors") or []) if i.get("executionPoint") in GOV]
    fora = [i for i in (revisao.get("interceptors") or []) if i.get("executionPoint") not in GOV]
    gerados = [gerar_basic_info(api, raiz)]

    linhas = [
        f"# escopo `all` — raiz da revision {revisao.get('id')} (revisionNumber {revisao.get('revisionNumber')})",
        f"# API {api.get('id')} · {api.get('name')} · {api.get('basePath')}",
    ]
    linhas += bloco_destination(revisao.get("destination"), revisao.get("timeout"))
    linhas += bloco_interceptors([i for i in governados if i["executionPoint"] == "FIRST"], "interceptors_request")
    linhas += bloco_interceptors([i for i in governados if i["executionPoint"] == "SECOND"], "interceptors_response")
    if fora:
        linhas += ["", f"# {len(fora)} interceptor(es) fora de FIRST/SECOND — estado nao governado,"
                       " preservado por GET no publish"]
    escrever(os.path.join(raiz, "all-all.yaml"), linhas)
    gerados.append("all-all.yaml")

    recursos = revisao.get("resources") or []
    for recurso in recursos:
        pasta = nome_pasta(recurso, recursos)
        ops = recurso.get("operations") or []
        prefixo = prefixo_comum([o.get("path", "") for o in ops])
        removidos_res = [i for i in (recurso.get("interceptors") or [])
                         if i.get("status") == "REMOVED"]
        proprios = [i for i in (recurso.get("interceptors") or [])
                    if i.get("executionPoint") in GOV
                    and i.get("status") != "REMOVED"
                    and chave_interceptor(i) not in {chave_interceptor(j) for j in governados}]

        linhas = [
            f"name: {texto(recurso.get('name'))}",
            *descricao(recurso.get("description")),
        ]
        linhas += bloco_destination(recurso.get("destination"), recurso.get("timeout"))
        linhas += ["", "inherit: true",
                   "# heranca preservada" + (" ; o que vem abaixo SOMA ao fluxo da revision" if proprios else
                                             " ; nenhum interceptor proprio neste recurso")]
        if removidos_res:
            nomes_res = ", ".join(i.get("type") for i in removidos_res)
            linhas += [f"# TOMBSTONE: o fluxo herdado vale, MENOS -> {nomes_res}",
                       "# a remocao ainda nao tem representacao no YAML (item V-25 do refino)"]
        linhas += bloco_interceptors([i for i in proprios if i["executionPoint"] == "FIRST"], "interceptors_request")
        linhas += bloco_interceptors([i for i in proprios if i["executionPoint"] == "SECOND"], "interceptors_response")
        rel = os.path.join("resources", pasta, "resource.yaml")
        escrever(os.path.join(raiz, rel), linhas)
        gerados.append(rel.replace("\\", "/"))

        herdados = governados + proprios
        chaves_herdadas = {chave_interceptor(i) for i in herdados}
        tipos_herdados = {(i["executionPoint"], i["type"], i.get("customInterceptorId")) for i in herdados}

        for op in ops:
            itens = op.get("interceptors") or []
            removidos = [i for i in itens if i.get("status") == "REMOVED"]
            presentes = [i for i in itens if i.get("executionPoint") in GOV and i.get("status") != "REMOVED"]
            reproduz = [i for i in presentes if chave_interceptor(i) in chaves_herdadas]
            novos = [i for i in presentes if chave_interceptor(i) not in chaves_herdadas]

            linhas = [f"path: {op.get('path')}"]
            linhas += bloco_destination(op.get("destination"), op.get("timeout"))
            linhas.extend(descricao(op.get("description")))

            # TOMBSTONE (`status: REMOVED`) = heranca PRESERVADA com um item retirado.
            # NAO e quebra de heranca: emitir `inherit: false` aqui publicaria a rota
            # sem interceptor nenhum. A remocao em si ainda nao tem gramatica no YAML
            # (item V-25); fica registrada em comentario. O `inherit` e decidido pelos
            # itens PRESENTES, nao pelos removidos.
            nota_tombstone = []
            if removidos:
                nomes = ", ".join(i.get("type") for i in removidos)
                nota_tombstone = [
                    f"# TOMBSTONE: o fluxo herdado vale, MENOS -> {nomes}",
                    "# a remocao ainda nao tem representacao no YAML (item V-25 do refino)",
                ]

            if reproduz:
                faltando = sorted(
                    f"{t}#{cid}" for (_, t, cid) in
                    tipos_herdados - {(i["executionPoint"], i["type"], i.get("customInterceptorId")) for i in presentes}
                )
                linhas += ["", "inherit: false",
                           f"# heranca quebrada: o fluxo abaixo substitui o herdado (ausentes: {', '.join(faltando) or 'nenhum'})"]
                linhas += nota_tombstone
                linhas += bloco_interceptors([i for i in presentes if i["executionPoint"] == "FIRST"], "interceptors_request")
                linhas += bloco_interceptors([i for i in presentes if i["executionPoint"] == "SECOND"], "interceptors_response")
            elif novos:
                linhas += ["", "inherit: true", "# heranca preservada; o que vem abaixo SOMA ao fluxo herdado"]
                linhas += nota_tombstone
                linhas += bloco_interceptors([i for i in novos if i["executionPoint"] == "FIRST"], "interceptors_request")
                linhas += bloco_interceptors([i for i in novos if i["executionPoint"] == "SECOND"], "interceptors_response")
            elif removidos:
                linhas += ["", "inherit: true"]
                linhas += nota_tombstone
            else:
                linhas += ["", "inherit: true", "# heranca pura: nenhum item proprio nesta operacao"]

            rel = os.path.join("resources", pasta, nome_arquivo(op, prefixo))
            escrever(os.path.join(raiz, rel), linhas)
            gerados.append(rel.replace("\\", "/"))

    return gerados


def main():
    if TOKEN.startswith("COLE_AQUI"):
        sys.exit("Preencha TOKEN com o access token de superadmin do Manager.")

    api = http_get(f"/apis/{API_ID}")
    revisoes = api.get("revisions") or []
    if REVISION_NUMBER is None:
        revisao = api.get("lastRevision") or {}
    else:
        alvo = [r for r in revisoes if r.get("revisionNumber") == REVISION_NUMBER]
        if not alvo:
            disponiveis = ", ".join(str(r.get("revisionNumber")) for r in revisoes) or "nenhuma"
            sys.exit(f"revisionNumber {REVISION_NUMBER} nao existe na API {API_ID}. Disponiveis: {disponiveis}")
        revisao = http_get(f"/revisions/{alvo[0]['id']}")

    if not revisao.get("resources"):
        sys.exit(f"A revision {revisao.get('id')} nao tem recursos.")

    raiz = os.path.join(os.path.dirname(os.path.abspath(__file__)), DESTINO,
                        f"api-{API_ID}-rev{revisao.get('revisionNumber')}")
    gerados = gerar(api, revisao, raiz)

    print(f"API {api.get('id')} · {api.get('name')} · revision {revisao.get('id')} "
          f"(revisionNumber {revisao.get('revisionNumber')})")
    print(f"destino: {raiz}\n")
    for caminho in sorted(gerados):
        print(f"  {caminho}")
    maior = max(gerados, key=len)
    print(f"\n{len(gerados)} arquivos · {len(revisao.get('resources') or [])} recursos · "
          f"{sum(len(r.get('operations') or []) for r in revisao.get('resources') or [])} operacoes")
    print(f"maior caminho relativo: {len(maior)} chars -> {maior}")
    for aviso in sorted(set(avisos)):
        print(f"AVISO: {aviso}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
