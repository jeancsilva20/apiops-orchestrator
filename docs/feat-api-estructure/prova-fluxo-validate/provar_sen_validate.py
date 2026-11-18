# -*- coding: utf-8 -*-
r"""
Prova de fluxo do `sen validate` - v2 - instrumento de validacao empirica.

NAO e codigo de producao. Reproduz o cenario da secao 6 de
docs/feat-api-estructure/plano-comandos-sen.md com dado real.

NOVIDADES DA v2 (a partir dos achados de 2026-10-15):
  * a FASE 5b agora PUBLICA RECURSOS E OPERACOES a partir do repositorio -
    rotas novas sobem, rotas removidas do repo deixam de ser enviadas;
  * o metodo da operacao vem do NOME DO ARQUIVO (`<metodo>_<path>.yaml`, D-005 S4),
    porque o YAML da operacao nao carrega o campo `method`;
  * `apiTags` do repositorio entram no objeto `api` aninhado do payload da revision -
    e e dali que o Adaptive Governance valida;
  * WORKFLOW_STAGE_OVERRIDE permite escolher o stage enviado. Isso DECIDE se o AG
    roda: stage sem `attributesRequisites` (ex.: 1401) nao valida nada; stage com
    requisitos (ex.: 1402) dispara a validacao e pode devolver 412.

    FASE 1  carregar repositorio local            (E1)          sem rede
    FASE 2  GET da API + GUARDA 1                 (guarda)      GET
    FASE 3  GET do template + conformidade        (E2)          GET
    FASE 4  GUARDA 2 - confirmacao s/n            (guarda)      ---
    FASE 5   PUT UNICO da revisao 1, DENSO        (E3)          ESCRITA
    FASE 5.1 conferencia pos-publicacao           (E3)          GET
    FASE 6  completeness                          (E4)          GET
    FASE 7  relatorio consolidado (tudo-ou-nada)

AUTOCONTIDO: token e host em constantes, sem importar apiops_orchestrator,
sem PYTHONPATH. Dependencia externa: PyYAML (para ler os YAML do repositorio).

    cd docs\feat-api-estructure\prova-fluxo-validate
    ..\..\..\.venv\Scripts\python.exe provar_sen_validate.py
    ..\..\..\.venv\Scripts\python.exe provar_sen_validate.py --restore logs\<execucao>\backup

COMO OBTER O TOKEN (uma vez por dia; cole na constante TOKEN, ou use a variavel
SEN_ADMIN_TOKEN / um arquivo `.token` nesta pasta):

    cd CLI\apiops-orchestrator
    .venv\Scripts\python.exe -c "import sys; sys.argv=['sen','login']; from apiops_orchestrator.main import main; main()"
    set PYTHONPATH=src
    .venv\Scripts\python.exe -c "from apiops_orchestrator.config.settings import Settings; from apiops_orchestrator.infrastructure.secure_storage.session_store import SessionStore; from apiops_orchestrator.adapters.outbound.http.orchestrator_auth_api.orchestrator_auth_adapter import OrchestratorAuthAdapter as A; s=Settings(); x=SessionStore(directory=s.PACKAGE_ROOT).load(); print(A(settings=s,max_retries=3).validate_access_token(x.accessToken)['extra_info']['admin_access_token'])"

SEGURANCA: backup completo antes de escrever; confirmacao explicita;
`--restore <pasta>`; o token nunca vai para o log (so o tamanho).
"""

import argparse
import datetime
import json
import os
import pathlib
import sys
import traceback
import urllib.error
import urllib.request

try:
    import yaml
except ImportError:  # pragma: no cover
    print("ERRO: PyYAML nao encontrado. Rode com o python do venv do projeto:")
    print(r"      ..\..\..\.venv\Scripts\python.exe provar_sen_validate.py")
    sys.exit(2)

# ----------------------------------------------------------------- CONFIGURACAO

HOST = "https://platform-production.sensedia.com"

# >>> COLE O ADMIN ACCESS TOKEN AQUI <<<   (expira em ~24h; veja o cabecalho)
#
# ATENCAO: a pasta esta no .gitignore do diretorio, mas o segredo fica em disco.
# Rotacione o token depois dos testes.
TOKEN = "eyJraWQiOiIwSTZ2Kyt6NlJVaFlib2w5ak1sTHZSR0xjNnVVWndpQXJ6VGRQZGptSzBVPSIsImFsZyI6IlJTMjU2In0.eyJzdWIiOiIyaXJsZ25iZmE5Z2FjNDEyMm4zaGFvbTM1aCIsInRva2VuX3VzZSI6ImFjY2VzcyIsInNjb3BlIjoiYXBpcy9hbGwiLCJhdXRoX3RpbWUiOjE3OTE5OTA5NzgsImlzcyI6Imh0dHBzOi8vY29nbml0by1pZHAuc2EtZWFzdC0xLmFtYXpvbmF3cy5jb20vc2EtZWFzdC0xXzFRSXM0Y0VHaiIsImV4cCI6MTc5MjA3NzM3OCwiaWF0IjoxNzkxOTkwOTc4LCJ2ZXJzaW9uIjoyLCJqdGkiOiJmNzI5ZWM1ZC1kNTJmLTRjNjItYjMxYS00NmE1NTdhMTQzNDgiLCJjbGllbnRfaWQiOiIyaXJsZ25iZmE5Z2FjNDEyMm4zaGFvbTM1aCJ9.DmqH8uAIMIStTMLRGnde9LnjOoC2VNllRo2YL6QGIDPXrZblIF8q6766OAIdS4_N8Sv2oIMKk_xki9WQAuI3XsE2VuRvd-RZenshP1NRPk8s-PVPhAvB3fZJT-MIQOuNRZsISHBoCNKOQOwHTe1R_YGHuSBeuLBZAFtj_OzpV7g553NrYZM66sS4GT89GjAlhgfPLWRWcmXSsohP5qc89fifMT_AEKWEa0lE0tAX3DZ4_4NahrPShNWtm26P5psAtgxmPfbLFQilwQ7ueVazDmIspUG5cE7qiockQ3FPlVGKIxc0gVg5JvQSS_upjPi6o4Rx4WMIUYz5F19BjWK95w"

# Alternativas, se preferir nao deixar o segredo no arquivo: basta nao mexer na
# constante acima e usar a variavel SEN_ADMIN_TOKEN ou um arquivo `.token` nesta
# pasta (os dois ja cobertos pelo .gitignore).
if not TOKEN or TOKEN.startswith("<cole"):
    TOKEN = (os.environ.get("SEN_ADMIN_TOKEN") or "").strip()
if not TOKEN:
    _arquivo_token = pathlib.Path(__file__).resolve().parent / ".token"
    if _arquivo_token.exists():
        # utf-8-sig: o `>` do PowerShell grava com BOM, que invalidaria o token
        TOKEN = _arquivo_token.read_text(encoding="utf-8-sig").strip()
REPO_DIR = pathlib.Path(
    r"C:\Users\jean.silva_sensedia\Documents\Projetos\APIOps\CLI\apiops-orchestrator"
    r"\docs\feat-api-estructure\decisoes-refino-409\exemplos-gerados\saida\api-417-rev2"
)

EXECUTION_MODE = "local"      # local | pipeline  (pipeline nao pergunta s/n)
TEMPLATE_API_ID = 414         # regua, quando EXECUTION_MODE == "pipeline"
REVISION_NUMBER_DRAFT = 1     # Draft por convencao

# Sobrepoe `spec.template` sem editar a fixture (que tem `template: ''`).
#   414  -> fluxo completo contra a regua
#   None -> usa o YAML, provando o cenario "template ausente" (D-12)
TEMPLATE_LOCAL_OVERRIDE = 414

# >>> O INTERRUPTOR DO ADAPTIVE GOVERNANCE <<<
# O stage enviado no payload decide se o AG valida os apiTags:
#   None  -> reenvia o stage atual da revision ("manter o estado do Manager").
#            Se o stage nao tiver attributesRequisites, o AG NAO roda.
#   1402  -> forca o stage com requisitos -> dispara a validacao (pode dar 412)
WORKFLOW_STAGE_OVERRIDE = None

# Publicar a arvore de recursos/operacoes do repositorio (v2).
# False reproduz o comportamento da v1 (so o escopo `all`).
PUBLICAR_RECURSOS = True

BASE_PATH = "/api-manager/api/v3"
AQUI = pathlib.Path(__file__).resolve().parent
LOG_DIR = AQUI / "logs"
GOVERNED = frozenset({"FIRST", "SECOND"})
TIMEOUT = 60
METODOS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD")

# ----------------------------------------------------------------------- LOG


class Log:
    def __init__(self, destino: pathlib.Path):
        self.destino = destino
        self.linhas = []
        self.achados = []

    def __call__(self, texto="", nivel="INFO"):
        carimbo = datetime.datetime.now().strftime("%H:%M:%S")
        linha = texto if nivel == "RAW" else "[%s] %-7s %s" % (carimbo, nivel, texto)
        try:
            print(linha)
        except UnicodeEncodeError:
            print(linha.encode("ascii", "replace").decode("ascii"))
        self.linhas.append(linha)

    def titulo(self, texto):
        self("", "RAW")
        self("=" * 78, "RAW")
        self(texto, "RAW")
        self("=" * 78, "RAW")

    def achado(self, severidade, texto):
        self.achados.append((severidade, texto))
        self("%-8s %s" % (severidade, texto), "RAW")

    def gravar(self):
        self.destino.parent.mkdir(parents=True, exist_ok=True)
        self.destino.write_text("\n".join(self.linhas) + "\n", encoding="utf-8")
        print("\n>>> log salvo em: %s" % self.destino)


# ------------------------------------------------------------------ TRANSPORTE


class Api:
    def __init__(self, log: Log):
        self.log = log
        if not TOKEN:
            raise RuntimeError(
                "Token nao preenchido. Cole o admin access token na constante TOKEN "
                "(topo do script), ou use a variavel SEN_ADMIN_TOKEN / o arquivo "
                "`.token` nesta pasta. Veja o cabecalho para obter o valor.")
        self.log("token configurado (len=%d)" % len(TOKEN))

    def chamar(self, metodo, caminho, payload=None):
        url = HOST + BASE_PATH + caminho
        corpo = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(
            url, data=corpo, method=metodo,
            headers={
                "Authorization": "Bearer %s" % TOKEN,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        self.log("%s %s%s" % (metodo, BASE_PATH, caminho), "HTTP")
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resposta:
                texto = resposta.read().decode("utf-8", "replace")
                self.log("   -> %s" % resposta.status, "HTTP")
                return True, (json.loads(texto) if texto.strip() else {})
        except urllib.error.HTTPError as erro:
            texto = erro.read().decode("utf-8", "replace")
            try:
                detalhe = json.loads(texto)
            except ValueError:
                detalhe = {"corpo": texto[:4000]}
            self.log("   -> %s %s" % (erro.code, erro.reason), "HTTP")
            self.log("   corpo: %s" % json.dumps(detalhe, ensure_ascii=False)[:3000], "HTTP")
            return False, {"status": erro.code, "reason": erro.reason, "resposta": detalhe}
        except Exception as exc:  # noqa: BLE001
            self.log("   -> falha de transporte: %s" % exc, "HTTP")
            return False, {"status": None, "excecao": type(exc).__name__, "texto": str(exc)[:1000]}


class Abortar(Exception):
    """Interrompe a cascata sem traceback - desfecho previsto."""


# ------------------------------------------------------- FASE 1 - REPOSITORIO


def ler_yaml(caminho: pathlib.Path):
    return yaml.safe_load(caminho.read_text(encoding="utf-8")) or {}


def metodo_do_arquivo(nome):
    """D-005 S4: `<metodo>_<path completo>.yaml`. O YAML nao carrega `method`."""
    base = nome.rsplit(".", 1)[0]
    cabeca = base.split("_", 1)[0].upper()
    return cabeca if cabeca in METODOS else None


def carregar_repo(repo: pathlib.Path, log: Log):
    log.titulo("FASE 1 - carregar o repositorio local (E1)")
    log("pasta: %s" % repo)
    if not repo.is_dir():
        raise RuntimeError("Pasta do repositorio nao encontrada: %s" % repo)

    basic_path = repo / "api-basic-info.yaml"
    if not basic_path.exists():
        raise RuntimeError("api-basic-info.yaml ausente na raiz do repositorio")
    basic = ler_yaml(basic_path)
    spec = basic.get("spec") or {}
    log("spec.id=%s  name=%r  version=%r  basePath=%r  template=%r"
        % (spec.get("id"), spec.get("name"), spec.get("version"),
           spec.get("basePath"), spec.get("template")))
    log("apiTags no repo: %s" % json.dumps(spec.get("apiTags"), ensure_ascii=False))

    all_path = repo / "all-all.yaml"
    escopo_all = ler_yaml(all_path) if all_path.exists() else {}
    if not all_path.exists():
        log("all-all.yaml ausente - escopo da revision vazio", "AVISO")

    recursos = []
    pasta_recursos = repo / "resources"
    if pasta_recursos.is_dir():
        for pasta in sorted(p for p in pasta_recursos.iterdir() if p.is_dir()):
            arq_recurso = pasta / "resource.yaml"
            if not arq_recurso.exists():
                raise RuntimeError("pasta sem resource.yaml: %s" % pasta.name)
            recurso = ler_yaml(arq_recurso)
            operacoes = []
            for arq in sorted(pasta.glob("*.yaml")):
                if arq.name == "resource.yaml":
                    continue
                op = ler_yaml(arq)
                metodo = metodo_do_arquivo(arq.name)
                if metodo is None:
                    raise RuntimeError(
                        "nome de arquivo sem metodo reconhecivel: %s/%s" % (pasta.name, arq.name))
                op["__arquivo__"] = arq.name
                op["__metodo__"] = metodo
                operacoes.append(op)
            if not operacoes:
                raise RuntimeError("recurso sem operacao: %s" % pasta.name)
            recurso["__operacoes__"] = operacoes
            recurso["__pasta__"] = pasta.name
            recursos.append(recurso)
            log("   %-26s %s" % (pasta.name,
                                 [(o["__metodo__"], o.get("path")) for o in operacoes]))

    log("carregado: %d recurso(s), %d operacao(oes)"
        % (len(recursos), sum(len(r["__operacoes__"]) for r in recursos)))
    return {"basic": basic, "spec": spec, "all": escopo_all, "recursos": recursos}


# ---------------------------------------------------------- FASE 2 - GUARDA 1


def guarda_identidade(repo_data, api_remota, log: Log):
    log.titulo("FASE 2 - GUARDA 1: identidade (version e basePath)")
    spec = repo_data["spec"]
    divergiu = False
    for campo, local, remoto in [
        ("version", spec.get("version"), api_remota.get("version")),
        ("basePath", spec.get("basePath"), api_remota.get("basePath")),
    ]:
        igual = str(local) == str(remoto)
        log("%-9s repo=%-28r manager=%-28r %s"
            % (campo, local, remoto, "OK" if igual else "DIVERGE"),
            "INFO" if igual else "ERRO")
        divergiu = divergiu or not igual
    log("spec.id=%s -> API %r (id usado apenas como endereco do GET)"
        % (spec.get("id"), api_remota.get("name")))
    if divergiu:
        raise Abortar(
            "version ou basePath divergem do Manager. O repositorio pode estar "
            "apontado para outra API. Procure o administrador do sistema.")
    log("guarda 1 passou", "OK")


# ------------------------------------------------- FASE 3 - TEMPLATE (REGUA)


def normalizar_wire(item):
    bruto = item.get("content")
    if isinstance(bruto, str):
        try:
            bruto = json.loads(bruto)
        except (ValueError, TypeError):
            pass
    return (item.get("type"), item.get("customInterceptorId"),
            json.dumps(bruto, sort_keys=True, ensure_ascii=False))


def normalizar_yaml(item):
    tipo = item.get("type")
    if tipo == "Custom":
        return (tipo, item.get("id"), json.dumps(None))
    return (tipo, None, json.dumps(item.get("content"), sort_keys=True, ensure_ascii=False))


def fluxo_da_regua(revisao):
    gov = [i for i in (revisao.get("interceptors") or [])
           if i.get("executionPoint") in GOVERNED]
    gov.sort(key=lambda i: (i.get("executionPoint"), i.get("position") or 0))
    return [normalizar_wire(i) for i in gov]


def fluxo_do_repo(bloco):
    saida = []
    for chave in ("interceptors_request", "interceptors_response"):
        for item in (bloco.get(chave) or []):
            saida.append(normalizar_yaml(item))
    return saida


def conformidade(repo_data, regua, log: Log):
    log.titulo("FASE 3 - conformidade com o template (E2)")
    alvo = fluxo_da_regua(regua)
    log("regua: %d item(ns) governado(s)" % len(alvo))
    for t, cid, _ in alvo:
        log("   regua: %s%s" % (t, (" #%s" % cid) if cid else ""), "RAW")

    tipos_alvo = [(t, c) for t, c, _ in alvo]

    def comparar(rotulo, bloco, e_raiz=False):
        if not bloco:
            return
        meu = fluxo_do_repo(bloco)
        tipos_meu = [(t, c) for t, c, _ in meu]
        if e_raiz:
            # A raiz da revision NAO herda de ninguem: ela E o fluxo base.
            faltando = [x for x in tipos_alvo if x not in tipos_meu]
            sobrando = [x for x in tipos_meu if x not in tipos_alvo]
            if faltando:
                log.achado("WARNING", "%s: nao executa %s" % (
                    rotulo, ", ".join("%s%s" % (t, " #%s" % c if c else "") for t, c in faltando)))
            if sobrando:
                log.achado("INFO", "%s: %d item(ns) alem da regua" % (rotulo, len(sobrando)))
            if not faltando and not sobrando:
                log.achado("INFO", "%s: conforme a regua" % rotulo)
            return
        herda = bloco.get("inherit", True)
        if herda:
            if meu:
                log.achado("INFO", "%s: %d item(ns) alem do herdado (append)" % (rotulo, len(meu)))
        elif not meu:
            # `inherit: false` sem lista propria e AMBIGUO - item V-25 em aberto.
            log.achado("WARNING", "%s: inherit:false sem fluxo declarado - "
                                  "remocao nao representavel (V-25 em aberto)" % rotulo)
        else:
            faltando = [x for x in tipos_alvo if x not in tipos_meu]
            if faltando:
                log.achado("WARNING", "%s: quebra a heranca e nao executa %s" % (
                    rotulo, ", ".join("%s%s" % (t, " #%s" % c if c else "") for t, c in faltando)))
            else:
                log.achado("WARNING", "%s: declara o proprio fluxo (inherit: false)" % rotulo)

    comparar("escopo all (raiz da revision)", repo_data["all"], e_raiz=True)
    for recurso in repo_data["recursos"]:
        comparar("resource %r" % recurso.get("name"), recurso)
        for op in recurso["__operacoes__"]:
            comparar("%s %s" % (op["__metodo__"], op.get("path", op["__arquivo__"])), op)


# ---------------------------------------------------------- FASE 4 - GUARDA 2


def guarda_consentimento(api_remota, log: Log):
    log.titulo("FASE 4 - GUARDA 2: consentimento")
    if EXECUTION_MODE == "pipeline":
        log("EXECUTION_MODE=pipeline -> confirmacao dispensada (D-17)", "OK")
        return
    pergunta = ("\nPara validar a estrutura completa da API, ela sera publicada no ambiente "
                "Sensedia na API [%s] [%s]. Deseja prosseguir? (s/n) "
                % (api_remota.get("name"), api_remota.get("version")))
    log(pergunta.strip(), "RAW")
    resposta = input(pergunta).strip().lower()
    log("resposta do usuario: %r" % resposta)
    if resposta not in ("s", "sim", "y", "yes"):
        raise Abortar("Publicacao cancelada pelo usuario.")
    log("consentimento concedido", "OK")


# ---------------------------------------------------- FASE 5 - PUBLICACAO


def backup(api_client, api_id, api_remota, pasta: pathlib.Path, log: Log):
    pasta.mkdir(parents=True, exist_ok=True)
    pasta.joinpath("api_%s.json" % api_id).write_text(
        json.dumps(api_remota, indent=2, ensure_ascii=False), encoding="utf-8")
    salvos = ["api_%s.json" % api_id]
    for rev in api_remota.get("revisions") or []:
        ok, bruto = api_client.chamar("GET", "/revisions/%s" % rev.get("id"))
        if ok:
            nome = "revision_%s.json" % rev.get("id")
            pasta.joinpath(nome).write_text(
                json.dumps(bruto, indent=2, ensure_ascii=False), encoding="utf-8")
            salvos.append(nome)
    log("backup salvo em %s (%s)" % (pasta, ", ".join(salvos)), "OK")


CACHE_CUSTOM = {}
CONTENT_POR_CUSTOM = {}
PROXIMO_IDTEMP = [1]        # contador global de idTemp para itens novos


def preparar_idtemp(draft):
    """`idTemp` e unico no PAYLOAD, nao no escopo. Comeca acima de tudo que ja existe."""
    vistos = [0]
    pilha = [draft]
    while pilha:
        no = pilha.pop()
        for item in (no.get("interceptors") or []):
            for campo in ("id", "idTemp", "position"):
                valor = item.get(campo)
                if isinstance(valor, int):
                    vistos.append(valor)
        for r in (no.get("resources") or []):
            pilha.append(r)
        for o in (no.get("operations") or []):
            pilha.append(o)
    PROXIMO_IDTEMP[0] = max(vistos) + 1
    return PROXIMO_IDTEMP[0]


def novo_idtemp():
    valor = PROXIMO_IDTEMP[0]
    PROXIMO_IDTEMP[0] += 1
    return valor


def indexar_customs_da_api(api_client, api_id, log: Log):
    """Varre TODAS as revisions da API e guarda o `content` de cada Custom.

    O catalogo /custom-interceptors NAO resolve esses ids (404 para 125 e 178,
    e a listagem traz apenas ids 1..31), mas o content esta materializado nas
    revisions. Essa e a unica fonte disponivel para repor um Custom.
    """
    ok, api = api_client.chamar("GET", "/apis/%s" % api_id)
    if not ok:
        return
    for rev in api.get("revisions") or []:
        ok_r, corpo = api_client.chamar("GET", "/revisions/%s" % rev.get("id"))
        if not ok_r:
            continue
        pilha = [corpo]
        while pilha:
            no = pilha.pop()
            for item in (no.get("interceptors") or []):
                cid = item.get("customInterceptorId")
                if cid is not None and cid not in CONTENT_POR_CUSTOM:
                    CONTENT_POR_CUSTOM[cid] = item.get("content")
            for r in (no.get("resources") or []):
                pilha.append(r)
            for o in (no.get("operations") or []):
                pilha.append(o)
    if CONTENT_POR_CUSTOM:
        log("catalogo local de Custom montado a partir das revisions: %s"
            % sorted(CONTENT_POR_CUSTOM))


def buscar_custom(api_client, custom_id, log: Log):
    """Content do Custom. Tenta o catalogo e, se falhar, as revisions da API."""
    if custom_id in CACHE_CUSTOM:
        return CACHE_CUSTOM[custom_id]
    ok, dados = api_client.chamar("GET", "/custom-interceptors/%s" % custom_id)
    if ok:
        conteudo = json.dumps({"id": dados.get("id"), "name": dados.get("name"),
                               "script": dados.get("script")})
    elif custom_id in CONTENT_POR_CUSTOM:
        conteudo = CONTENT_POR_CUSTOM[custom_id]
        log("custom %s nao esta no catalogo; content recuperado de outra revision "
            "da propria API" % custom_id, "AVISO")
    else:
        log("custom %s: ausente no catalogo E em todas as revisions - "
            "impossivel repor" % custom_id, "ERRO")
        CACHE_CUSTOM[custom_id] = None
        return None
    CACHE_CUSTOM[custom_id] = conteudo
    return conteudo


def construir_interceptor(tipo, custom_id, content_yaml, ponto, api_client, log: Log,
                          proxima_posicao=1):
    """Monta um interceptor que o repositorio declara e o remoto nao tem.

    `customInterceptorId` e PRESERVADO (referencia ao script).

    `idTemp` e OBRIGATORIO: sem ele - ou com None - o Manager devolve 500 com
    `errors: []`. Provado por bissecao em 2026-10-15. E a mesma convencao de
    `interceptors_model.set_ids_from_position` no orquestrador. O `id` pode ir
    nulo, que e o correto para um item que ainda nao existe.
    """
    if tipo == "Custom":
        corpo = buscar_custom(api_client, custom_id, log)
        if corpo is None:
            return None
    else:
        corpo = json.dumps(content_yaml)
    return {
        "type": tipo,
        "content": corpo,
        "executionPoint": ponto,
        "status": "REFERENCE",
        "parent": None,
        "resource": None,
        "operation": None,
        "planId": None,
        "customInterceptorId": custom_id,
        "parentType": "REVISION",
        "position": proxima_posicao,
        "id": None,
        # idTemp GLOBAL: dois itens novos em escopos diferentes nao podem
        # compartilhar o valor, ou o Manager descarta um deles (HTTP 200).
        "idTemp": novo_idtemp(),
    }


def fluxo_do_repo_detalhado(bloco):
    """Como fluxo_do_repo, mas devolve tambem o executionPoint e o content cru."""
    saida = []
    for chave, ponto in (("interceptors_request", "FIRST"),
                         ("interceptors_response", "SECOND")):
        for item in (bloco.get(chave) or []):
            tipo = item.get("type")
            cid = item.get("id") if tipo == "Custom" else None
            saida.append((tipo, cid, item.get("content"), ponto))
    return saida


def casar_interceptores(bloco_repo, lista_remota, log: Log, rotulo, e_raiz=False,
                        api_client=None):
    """Monta o fluxo a publicar para UM escopo.

    ACHADO DE 2026-10-15: o Manager guarda em cada escopo o fluxo JA RESOLVIDO -
    a heranca aparece materializada no wire (o resource 9164 tem 9 itens, a
    operacao 9172 tem 7). O repositorio, ao contrario, declara so o delta
    (`inherit: true` + itens proprios). Publicar o delta cru APAGARIA o herdado.

    Por isso:
      raiz da revision -> publica exatamente o que o repo declara (e o fluxo base);
      inherit: true    -> PRESERVA a lista remota (herdado materializado) intacta;
      inherit: false   -> publica SOMENTE os itens declarados.

    `position`/`idTemp` NAO sao reescritos: o wire usa numeracao continua entre
    escopos (resource 2..8, operation 9..15) e renumerar 1..N por escopo
    corromperia a ordem - item P-1/D-8, ainda em aberto.
    """
    remota = list(lista_remota or [])
    preservados = [i for i in remota if i.get("executionPoint") not in GOVERNED]
    governados = [i for i in remota if i.get("executionPoint") in GOVERNED]
    desejado = fluxo_do_repo_detalhado(bloco_repo)
    herda = bloco_repo.get("inherit", True)

    indice = {}
    for item in governados:
        indice.setdefault(normalizar_wire(item)[:2], []).append(item)

    casados, nao_casados, construidos = [], [], []
    for tipo, cid, conteudo, ponto in desejado:
        candidatos = indice.get((tipo, cid))
        if candidatos:
            casados.append(candidatos.pop(0))
            continue
        ocupadas = [i.get("position") or 0 for i in (governados + casados)]
        proxima = max(ocupadas + [0]) + 1
        novo_item = (construir_interceptor(tipo, cid, conteudo, ponto, api_client, log,
                                           proxima_posicao=proxima)
                     if api_client is not None else None)
        if novo_item is not None:
            casados.append(novo_item)
            construidos.append((tipo, cid))
        else:
            nao_casados.append((tipo, cid))

    if construidos:
        log("%s: %d item(ns) CONSTRUIDO(S) do zero (declarado no repo, ausente no "
            "remoto): %s" % (rotulo, len(construidos), construidos), "OK")
    if nao_casados:
        log("%s: %d item(ns) do repo que NAO foi possivel montar -> NAO enviados: %s"
            % (rotulo, len(nao_casados), nao_casados), "ERRO")

    if e_raiz:
        resultado = casados + preservados
        descartados = len(governados) - len(casados)
        if descartados > 0:
            log("%s: %d item(ns) do remoto nao estao no repo -> serao REMOVIDOS"
                % (rotulo, descartados), "AVISO")
    elif herda:
        novos = [i for i in casados if i.get("id") is None]
        resultado = governados + novos + preservados
        log("%s: inherit:true -> fluxo herdado preservado (%d item(ns))"
            % (rotulo, len(governados)))
    else:
        resultado = casados + preservados
        descartados = len(governados) - len(casados)
        if descartados > 0:
            log("%s: inherit:false -> %d item(ns) do remoto NAO serao enviados"
                % (rotulo, descartados), "AVISO")

    return resultado


def montar_resources(repo_data, draft, log: Log, api_client=None):
    """v2 - monta resources/operations a partir do REPOSITORIO."""
    log("montando a arvore a partir do repositorio (PUBLICAR_RECURSOS=True)")

    op_remota, res_remoto_da_op, res_remoto_por_id = {}, {}, {}
    for r in draft.get("resources") or []:
        res_remoto_por_id[r.get("id")] = r
        for o in r.get("operations") or []:
            chave = ((o.get("method") or "").upper(), o.get("path"))
            op_remota[chave] = o
            res_remoto_da_op[chave] = r

    usadas, resources, criadas, mantidas = set(), [], [], []

    for rec in repo_data["recursos"]:
        ops_payload, ids_origem, chaves_ops = [], [], []
        for op in rec["__operacoes__"]:
            chave = (op["__metodo__"], op.get("path"))
            chaves_ops.append(chave)
            destino = op.get("destination") or {}
            remota = op_remota.get(chave)
            if remota is not None:
                usadas.add(chave)
                ids_origem.append(res_remoto_da_op[chave].get("id"))
                corpo_op = json.loads(json.dumps(remota))
                mantidas.append(chave)
            else:
                corpo_op = {
                    "destination": None, "interceptors": [], "apiBroken": False,
                    "timeout": None, "certificateId": None, "description": "",
                    "method": chave[0], "path": chave[1],
                    "async": False, "urls": [], "instruction": None,
                }
                criadas.append(chave)
            if op.get("description") is not None:
                corpo_op["description"] = op["description"]
            if destino.get("url"):
                corpo_op["destination"] = destino["url"]
            if destino.get("timeout"):
                corpo_op["timeout"] = destino["timeout"]
            corpo_op["interceptors"] = casar_interceptores(
                op, (remota or {}).get("interceptors"), log, "%s %s" % chave,
                api_client=api_client)
            ops_payload.append(corpo_op)

        ids_unicos = {i for i in ids_origem if i is not None}
        base = res_remoto_por_id.get(next(iter(ids_unicos))) if len(ids_unicos) == 1 else None
        corpo_res = json.loads(json.dumps(base)) if base else {
            "destination": None, "interceptors": [], "apiBroken": False,
            "timeout": None, "certificateId": None, "connector": None,
        }
        corpo_res["name"] = rec.get("name") or rec["__pasta__"]
        corpo_res["description"] = rec.get("description") or ""
        destino_res = rec.get("destination") or {}
        corpo_res["destination"] = destino_res.get("url") or None
        corpo_res["timeout"] = destino_res.get("timeout") or None
        corpo_res["interceptors"] = casar_interceptores(
            rec, (base or {}).get("interceptors"), log, "resource %s" % corpo_res["name"],
            api_client=api_client)
        corpo_res["operations"] = ops_payload
        # No Manager a operacao PERTENCE ao recurso: um `id` de operacao so vale
        # dentro do recurso de origem. Reaproveita-lo em outro recurso faz o
        # Manager descartar a operacao (recurso novo nasce vazio). Logo, operacao
        # que muda de recurso vai SEM id - e uma operacao nova no destino.
        base_id = base.get("id") if base else None
        movidas = []
        for corpo_op, chave in zip(ops_payload, chaves_ops):
            origem = res_remoto_da_op.get(chave)
            origem_id = origem.get("id") if origem else None
            if origem_id != base_id:
                if corpo_op.pop("id", None) is not None:
                    movidas.append(chave)
        if movidas:
            log("   %d operacao(oes) mudando de recurso -> enviadas SEM id: %s"
                % (len(movidas), movidas), "AVISO")

        if base is None:
            corpo_res.pop("id", None)
            log("   recurso NOVO: %r (sem id - o Manager gera; operacoes idem)"
                % corpo_res["name"])
        resources.append(corpo_res)

    removidas = [c for c in op_remota if c not in usadas]
    log("operacoes: %d mantida(s), %d criada(s), %d removida(s)"
        % (len(mantidas), len(criadas), len(removidas)))
    for c in criadas:
        log("   CRIADA   %s %s" % c, "OK")
    for c in removidas:
        log("   REMOVIDA %s %s  (nao esta no repositorio)" % c, "AVISO")
    log("resources no payload: %d (remoto tinha %d)"
        % (len(resources), len(draft.get("resources") or [])))
    return resources


def publicar(api_client, repo_data, api_remota, log: Log):
    api_id = repo_data["spec"].get("id")

    spec = repo_data["spec"]

    # A FASE 5a (PUT /apis/{id}) FOI REMOVIDA em 2026-10-15.
    # Teste 2: o PUT da API passou (200) removendo um atributo obrigatorio, e o
    # PUT da revision foi barrado (412) pelo mesmo motivo - a API ficou alterada
    # e a revision nao. Duas escritas em sequencia nao sao atomicas, e o gate do
    # Adaptive Governance esta no PUT da REVISION, nao no da API.
    # O payload da revision carrega `api` aninhado (com apiTags), entao uma
    # escrita so basta e passa pelo gate.

    log.titulo("FASE 5 - PUT UNICO da revisao %d (Draft), DENSO" % REVISION_NUMBER_DRAFT)
    indexar_customs_da_api(api_client, api_id, log)
    alvo = None
    for rev in api_remota.get("revisions") or []:
        if rev.get("revisionNumber") == REVISION_NUMBER_DRAFT:
            alvo = rev
    if alvo is None:
        raise Abortar("A API nao possui revisao de numero %d." % REVISION_NUMBER_DRAFT)

    ok, draft = api_client.chamar("GET", "/revisions/%s" % alvo.get("id"))
    if not ok:
        raise Abortar("Nao foi possivel ler a revisao Draft.")

    corpo = json.loads(json.dumps(draft))
    base_idtemp = preparar_idtemp(draft)
    log("idTemp de itens novos comeca em %d (unico no payload inteiro)" % base_idtemp)

    # O basic info do repositorio entra no `api` aninhado - e dali que o AG valida.
    if isinstance(corpo.get("api"), dict):
        for campo in ("name", "description"):
            if spec.get(campo) is not None:
                corpo["api"][campo] = spec[campo]
        if spec.get("apiTags") is not None:
            antes = corpo["api"].get("apiTags")
            corpo["api"]["apiTags"] = spec["apiTags"]
            log("api.apiTags: %s -> %s"
                % (json.dumps(antes, ensure_ascii=False),
                   json.dumps(spec["apiTags"], ensure_ascii=False)))

    stage_atual = draft.get("workflowStageId")
    if WORKFLOW_STAGE_OVERRIDE is not None:
        corpo["workflowStageId"] = WORKFLOW_STAGE_OVERRIDE
        log("workflowStageId: %s -> %s (FORCADO - deve disparar o AG)"
            % (stage_atual, WORKFLOW_STAGE_OVERRIDE), "AVISO")
    else:
        log("workflowId=%s workflowStageId=%s (reenviados como estao; se o stage nao tiver "
            "attributesRequisites, o AG nao valida)" % (draft.get("workflowId"), stage_atual))

    corpo["interceptors"] = casar_interceptores(
        repo_data["all"], draft.get("interceptors"), log, "escopo all", e_raiz=True,
        api_client=api_client)
    destino = (repo_data["all"] or {}).get("destination") or {}
    corpo["destination"] = destino.get("url") or None
    corpo["timeout"] = destino.get("timeout") or None

    if PUBLICAR_RECURSOS:
        corpo["resources"] = montar_resources(repo_data, draft, log, api_client)
    else:
        log("PUBLICAR_RECURSOS=False - resources reenviados como estao", "AVISO")

    ok_b, resposta_b = api_client.chamar("PUT", "/revisions/%s" % alvo.get("id"), corpo)
    log("PUT: %s" % ("ACEITO" if ok_b else "RECUSADO"), "OK" if ok_b else "ERRO")

    conferido = True
    if ok_b:
        conferido = verificar_publicacao(api_client, alvo.get("id"), corpo, log)

    return {"revision_ok": ok_b, "revision_resposta": resposta_b,
            "revision_id": alvo.get("id"), "conferido": conferido}


def verificar_publicacao(api_client, revision_id, enviado, log: Log):
    """FASE 5.1 - compara o que foi enviado com o que o GET devolve.

    Dois casos de PERDA SILENCIOSA sob HTTP 200 (operacoes descartadas ao mudar
    de recurso; interceptor declarado que nao subiu) mostraram que o status code
    nao basta. A salvaguarda da V-22 S4 - falhar alto na perda - vale aqui.
    """
    log.titulo("FASE 5.1 - conferencia pos-publicacao")
    ok, depois = api_client.chamar("GET", "/revisions/%s" % revision_id)
    if not ok:
        log("nao foi possivel reler a revision para conferir", "ERRO")
        return False

    def ops(rev):
        return {((o.get("method") or "").upper(), o.get("path"))
                for r in (rev.get("resources") or [])
                for o in (r.get("operations") or [])}

    def itcs(lista):
        return sorted((i.get("executionPoint"), i.get("type"), i.get("customInterceptorId"))
                      for i in (lista or []))

    problemas = []

    env_ops, dep_ops = ops(enviado), ops(depois)
    sumiram = env_ops - dep_ops
    se_a_mais = dep_ops - env_ops
    log("operacoes: enviadas=%d  presentes=%d" % (len(env_ops), len(dep_ops)))
    if sumiram:
        problemas.append("operacoes enviadas que NAO estao na plataforma: %s" % sorted(sumiram))
    if se_a_mais:
        problemas.append("operacoes na plataforma que NAO foram enviadas: %s" % sorted(se_a_mais))

    env_raiz, dep_raiz = itcs(enviado.get("interceptors")), itcs(depois.get("interceptors"))
    log("interceptors da raiz: enviados=%d  presentes=%d" % (len(env_raiz), len(dep_raiz)))
    if env_raiz != dep_raiz:
        faltam = [i for i in env_raiz if i not in dep_raiz]
        se_a_mais_i = [i for i in dep_raiz if i not in env_raiz]
        if faltam:
            problemas.append("interceptors da raiz enviados e AUSENTES: %s" % faltam)
        if se_a_mais_i:
            problemas.append("interceptors da raiz presentes e NAO enviados: %s" % se_a_mais_i)

    env_res = len(enviado.get("resources") or [])
    dep_res = len(depois.get("resources") or [])
    log("recursos: enviados=%d  presentes=%d" % (env_res, dep_res))

    vazios = [r.get("name") for r in (depois.get("resources") or [])
              if not (r.get("operations") or [])]
    if vazios:
        problemas.append("recursos sem nenhuma operacao apos publicar: %s" % vazios)

    if problemas:
        log("DIVERGENCIAS ENCONTRADAS - a plataforma aceitou (200) mas o estado "
            "nao corresponde ao enviado:", "ERRO")
        for p in problemas:
            log("   %s" % p, "ERRO")
        return False
    log("conferencia OK - o estado publicado corresponde ao enviado", "OK")
    return True


# ------------------------------------------------------- FASE 6 - GOVERNANCA


def governanca(api_client, revision_id, log: Log):
    log.titulo("FASE 6 - Adaptive Governance (E4)")
    ok, dados = api_client.chamar("GET", "/revisions/%s/completeness" % revision_id)
    if not ok:
        log("completeness indisponivel", "AVISO")
        return None
    score = dados.get("completenessScore")
    sugestoes = dados.get("suggestions") or []
    log("completeness: %s%%  (gate de referencia: 70%%)" % score, "OK")
    for s in sugestoes:
        log.achado("AJUSTE", str(s))
    return {"score": score, "suggestions": sugestoes}


# -------------------------------------------------------------- FASE 7 - SAIDA


def relatorio(log: Log, conforme, gov, resultado):
    log.titulo("FASE 7 - RELATORIO CONSOLIDADO")
    log("Conformidade com o template:", "RAW")
    if not conforme:
        log("   nenhum desvio", "RAW")
    for sev, texto in conforme:
        log("   %-8s %s" % (sev, texto), "RAW")
    log("", "RAW")
    log("Adaptive Governance:", "RAW")
    if gov is None:
        log("   indisponivel", "RAW")
    else:
        log("   completeness: %s%%" % gov["score"], "RAW")
        for s in gov["suggestions"]:
            log("   ajuste: %s" % s, "RAW")
    log("", "RAW")
    log("Publicacao: revision=%s | conferencia=%s"
        % ("OK" if resultado["revision_ok"] else "RECUSADO",
           "OK" if resultado.get("conferido") else "DIVERGENTE"), "RAW")


# ------------------------------------------------------------------- RESTORE


def restaurar(api_client, pasta: pathlib.Path, log: Log):
    log.titulo("RESTORE - devolvendo o estado salvo no backup")
    if not pasta.is_dir():
        raise RuntimeError("pasta de backup inexistente: %s" % pasta)
    arquivos = sorted(pasta.glob("*.json"))
    log("%d arquivo(s) no backup" % len(arquivos))
    for arq in arquivos:
        dados = json.loads(arq.read_text(encoding="utf-8"))
        if arq.name.startswith("api_"):
            ok, _ = api_client.chamar("PUT", "/apis/%s" % dados.get("id"), dados)
        else:
            ok, _ = api_client.chamar("PUT", "/revisions/%s" % dados.get("id"), dados)
        log("%s -> %s" % (arq.name, "OK" if ok else "FALHOU"), "OK" if ok else "ERRO")


# ----------------------------------------------------------------------- MAIN


def main():
    parser = argparse.ArgumentParser(description="Prova de fluxo do sen validate (v2)")
    parser.add_argument("--restore", metavar="PASTA", help="restaura um backup e sai")
    parser.add_argument("--repo", metavar="PASTA", help="repositorio da API (sobrepoe REPO_DIR)")
    parser.add_argument("--stage", metavar="ID", type=int,
                        help="forca o workflowStageId enviado (sobrepoe a constante)")
    args = parser.parse_args()

    global WORKFLOW_STAGE_OVERRIDE
    if args.stage is not None:
        WORKFLOW_STAGE_OVERRIDE = args.stage

    carimbo = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    execucao = LOG_DIR / carimbo
    log = Log(execucao / "execucao.txt")

    log.titulo("PROVA DE FLUXO - sen validate v2   (%s)" % carimbo)
    log("HOST=%s" % HOST)
    log("EXECUTION_MODE=%s  PUBLICAR_RECURSOS=%s  WORKFLOW_STAGE_OVERRIDE=%s"
        % (EXECUTION_MODE, PUBLICAR_RECURSOS, WORKFLOW_STAGE_OVERRIDE))

    try:
        api_client = Api(log)

        if args.restore:
            restaurar(api_client, pathlib.Path(args.restore), log)
            log("RESULTADO: RESTORE CONCLUIDO", "OK")
            return 0

        repo = pathlib.Path(args.repo) if args.repo else REPO_DIR
        repo_data = carregar_repo(repo, log)
        api_id = repo_data["spec"].get("id")
        if not api_id:
            raise Abortar("spec.id ausente no api-basic-info.yaml")

        ok, api_remota = api_client.chamar("GET", "/apis/%s" % api_id)
        if not ok:
            raise Abortar("Nao foi possivel ler a API %s no Manager." % api_id)

        guarda_identidade(repo_data, api_remota, log)

        if EXECUTION_MODE == "pipeline":
            template_id, origem = TEMPLATE_API_ID, "variavel de ambiente (pipeline)"
        elif TEMPLATE_LOCAL_OVERRIDE is not None:
            template_id, origem = TEMPLATE_LOCAL_OVERRIDE, "override do instrumento"
        else:
            template_id, origem = repo_data["spec"].get("template"), "YAML (spec.template)"
        log("template resolvido: %r  (origem: %s)" % (template_id, origem))

        if template_id in (None, "", 0):
            raise Abortar("Para executar a validacao e necessario informar um template de api. "
                          "Procure o administrador do sistema.")
        ok, template = api_client.chamar("GET", "/apis/%s" % template_id)
        if not ok:
            raise Abortar("Template %s inalcancavel. (ponto em aberto: P-2)" % template_id)

        conformidade(repo_data, template.get("lastRevision") or {}, log)
        conforme = list(log.achados)
        log.achados.clear()

        guarda_consentimento(api_remota, log)
        backup(api_client, api_id, api_remota, execucao / "backup", log)

        resultado = publicar(api_client, repo_data, api_remota, log)

        if not resultado["revision_ok"]:
            log.titulo("DESFECHO - falha na publicacao (D-18: so o erro do Manager)")
            log(json.dumps(resultado["revision_resposta"], ensure_ascii=False, indent=2), "RAW")
            log("RESULTADO: FALHA NA PUBLICACAO", "ERRO")
            log("restaure com:  --restore %s" % (execucao / "backup"), "RAW")
            return 1

        gov = governanca(api_client, resultado["revision_id"], log)
        relatorio(log, conforme, gov, resultado)
        if not resultado.get("conferido"):
            log("RESULTADO: PUBLICADO COM DIVERGENCIA", "ERRO")
            log("restaure com:  --restore %s" % (execucao / "backup"), "RAW")
            return 1
        log("RESULTADO: SUCESSO", "OK")
        log("restaure o estado anterior com:  --restore %s" % (execucao / "backup"), "RAW")
        return 0

    except Abortar as parada:
        log.titulo("DESFECHO - cascata interrompida")
        log(str(parada), "ERRO")
        log("RESULTADO: ABORTADO", "ERRO")
        return 1
    except Exception as exc:  # noqa: BLE001
        log.titulo("DESFECHO - erro inesperado")
        log("%s: %s" % (type(exc).__name__, exc), "ERRO")
        log(traceback.format_exc(), "RAW")
        log("RESULTADO: ERRO TECNICO", "ERRO")
        return 1
    finally:
        log.gravar()


if __name__ == "__main__":
    sys.exit(main())
