# -*- coding: utf-8 -*-
"""Caderno de testes do `sen validate` contra a API 417.

Cada teste: altera o repo -> publica -> GET na plataforma -> VERIFICA o efeito
-> restaura o baseline. O veredito vem da verificacao, nao do HTTP.
"""
import importlib.util, json, pathlib, shutil, sys, traceback

BASE = pathlib.Path(sys.argv[1])
PROVA = pathlib.Path(sys.argv[2])
TRAB = BASE.parent / "trabalho2"
SAIDA = BASE.parent / "caderno"
SAIDA.mkdir(exist_ok=True)

spec = importlib.util.spec_from_file_location("prova", str(PROVA))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.TOKEN = BASE.joinpath("token.txt").read_text(encoding="utf-8").strip()
m.EXECUTION_MODE = "pipeline"
m.TEMPLATE_LOCAL_OVERRIDE = 414
m.PUBLICAR_RECURSOS = True

API_ID, REV = 417, 9161
resultados = []


class Log(m.Log):
    def __call__(self, texto="", nivel="INFO"):
        self.linhas.append(texto if nivel == "RAW" else "%-7s %s" % (nivel, texto))


def cli(log):
    return m.Api(log)


def ler():
    log = Log(SAIDA / "_scratch.txt")
    c = cli(log)
    ok1, api = c.chamar("GET", "/apis/%d" % API_ID)
    ok2, rev = c.chamar("GET", "/revisions/%d" % REV)
    return (api if ok1 else {}), (rev if ok2 else {})


def restaurar():
    log = Log(SAIDA / "_scratch.txt")
    c = cli(log)
    api = json.loads(BASE.joinpath("api_417.json").read_text(encoding="utf-8"))
    rev = json.loads(BASE.joinpath("revision_%d.json" % REV).read_text(encoding="utf-8"))
    c.chamar("PUT", "/apis/%d" % API_ID, api)
    c.chamar("PUT", "/revisions/%d" % REV, rev)


def preparar():
    if TRAB.exists():
        shutil.rmtree(TRAB)
    shutil.copytree(BASE / "repo_original", TRAB)
    return TRAB


# ------------------------------------------------------------------- helpers

def achar_op(rev, metodo, path):
    for r in rev.get("resources") or []:
        for o in r.get("operations") or []:
            if (o.get("method") or "").upper() == metodo and o.get("path") == path:
                return r, o
    return None, None


def achar_res(rev, nome):
    for r in rev.get("resources") or []:
        if r.get("name") == nome:
            return r
    return None


def tipos(lista):
    return [(i.get("type"), i.get("customInterceptorId")) for i in (lista or [])]


# ----------------------------------------------------------------- execucao

def rodar(ident, titulo, esperado, mutacao, verificar):
    print("\n" + "=" * 78)
    print("%s - %s" % (ident, titulo))
    print("   esperado: %s" % esperado)
    print("=" * 78)
    reg = {"id": ident, "titulo": titulo, "esperado": esperado}
    log = Log(SAIDA / ("%s.txt" % ident))
    try:
        repo = preparar()
        mutacao(repo)
        api_antes, rev_antes = ler()

        repo_data = m.carregar_repo(repo, log)
        c = cli(log)
        ok, api_remota = c.chamar("GET", "/apis/%d" % API_ID)
        m.guarda_identidade(repo_data, api_remota, log)
        res = m.publicar(c, repo_data, api_remota, log)
        reg["http_ok"] = res["revision_ok"]
        reg["conferido"] = res.get("conferido")
        if not res["revision_ok"]:
            reg["erro_http"] = json.dumps(res["revision_resposta"], ensure_ascii=False)[:400]

        api_dep, rev_dep = ler()
        veredito, detalhe = verificar(api_antes, rev_antes, api_dep, rev_dep, reg)
        reg["veredito"], reg["detalhe"] = veredito, detalhe
    except m.Abortar as parada:
        reg["abortou"] = str(parada)
        api_dep, rev_dep = ler()
        try:
            veredito, detalhe = verificar(None, None, api_dep, rev_dep, reg)
        except Exception:
            veredito, detalhe = "?", "abortou antes de publicar"
        reg["veredito"], reg["detalhe"] = veredito, detalhe
    except Exception as exc:  # noqa: BLE001
        reg["veredito"] = "ERRO"
        reg["detalhe"] = "%s: %s" % (type(exc).__name__, exc)
        traceback.print_exc()
    finally:
        log.gravar()
        restaurar()
    print("   VEREDITO: %s" % reg.get("veredito"))
    print("   %s" % reg.get("detalhe"))
    resultados.append(reg)


# ------------------------------------------------------------------ cenarios

NOVA_DESC = "Descricao EDITADA pelo teste automatizado do APIOps."


def t01_mut(repo):
    f = repo / "api-basic-info.yaml"
    t = f.read_text(encoding="utf-8")
    ini = t.index("  description:")
    fim = t.index("\n  #", ini)
    f.write_text(t[:ini] + '  description: "%s"' % NOVA_DESC + t[fim:], encoding="utf-8")


def t01_ver(aa, ra, ad, rd, reg):
    atual = (ad.get("description") or "")
    if atual == NOVA_DESC:
        return "PASSOU", "description na plataforma = %r" % atual[:50]
    return "FALHOU", "esperava %r, veio %r" % (NOVA_DESC[:30], atual[:50])


def t02_mut(repo):
    f = repo / "api-basic-info.yaml"
    t = f.read_text(encoding="utf-8")
    f.write_text(t.replace('basePath: "/letras/v2"', 'basePath: "/letras/v9"'), encoding="utf-8")


def t02_ver(aa, ra, ad, rd, reg):
    if not reg.get("abortou"):
        return "FALHOU", "deveria ter abortado na guarda, mas seguiu"
    if ad.get("basePath") != "/letras/v2":
        return "FALHOU", "o basePath da plataforma foi alterado: %r" % ad.get("basePath")
    return "PASSOU", "abortou antes de escrever; basePath intacto (%s)" % ad.get("basePath")


def t03_mut(repo):
    f = repo / "api-basic-info.yaml"
    t = f.read_text(encoding="utf-8")
    f.write_text(t.replace('    - attributeName: "My new"\n      tags: ["Tag1"]\n', ""),
                 encoding="utf-8")


def t03_ver(aa, ra, ad, rd, reg):
    tags = sorted(t.get("attributeName") for t in (ad.get("apiTags") or []))
    bloqueou = not reg.get("http_ok")
    if bloqueou and "My new" in tags:
        return "PASSOU", "bloqueado (HTTP 412) e a tag continua na plataforma: %s" % tags
    if bloqueou:
        return "PARCIAL", "bloqueou, mas as tags ficaram %s" % tags
    return "FALHOU", "publicou sem bloquear; tags=%s" % tags


NOVO_DESTINO = "https://dev-backend.ecad.org.br/EDITADO-PELO-TESTE/tarefas"


def t04_mut(repo):
    f = repo / "resources" / "tarefas" / "get_tarefas.yaml"
    t = f.read_text(encoding="utf-8")
    ini = t.index("  url: ")
    fim = t.index("\n", ini)
    f.write_text(t[:ini] + "  url: " + NOVO_DESTINO + t[fim:], encoding="utf-8")


def t04_ver(aa, ra, ad, rd, reg):
    _, op = achar_op(rd, "GET", "/tarefas")
    if op is None:
        return "FALHOU", "a operacao GET /tarefas sumiu"
    if op.get("destination") == NOVO_DESTINO:
        return "PASSOU", "destination replicado: %s" % op.get("destination")
    return "FALHOU", "destination na plataforma = %r" % op.get("destination")


def t05_mut(repo):
    d = repo / "resources" / "musicas"
    d.mkdir(parents=True, exist_ok=True)
    (d / "resource.yaml").write_text(
        'name: "Musicas"\ndescription: "Catalogo de musicas"\n'
        "destination:\n  url: ''\n\ninherit: true\n", encoding="utf-8")
    (d / "get_musicas.yaml").write_text(
        "path: /musicas\ndestination:\n  url: https://dev-backend.ecad.org.br/musicas\n"
        'description: "Lista musicas"\n\ninherit: true\n', encoding="utf-8")


def t05_ver(aa, ra, ad, rd, reg):
    res = achar_res(rd, "Musicas")
    if res is None:
        return "FALHOU", "o recurso Musicas nao foi criado"
    _, op = achar_op(rd, "GET", "/musicas")
    if op is None:
        return "FALHOU", "o recurso existe mas a operacao GET /musicas nao"
    raiz = len([i for i in (rd.get("interceptors") or [])
                if i.get("executionPoint") in ("FIRST", "SECOND")])
    propios = len(op.get("interceptors") or [])
    return "PASSOU", ("recurso e rota criados; a rota tem %d interceptor(es) proprio(s) e "
                      "a raiz tem %d - heranca por lista vazia" % (propios, raiz))


def t06_mut(repo):
    for alvo in (repo / "resources" / "letras" / "resource.yaml",
                 repo / "resources" / "letras" / "post_tarefas_{id}_letras.yaml"):
        t = alvo.read_text(encoding="utf-8")
        alvo.write_text(t.replace("inherit: true", "inherit: false"), encoding="utf-8")


def t06_ver(aa, ra, ad, rd, reg):
    res = achar_res(rd, "Letras")
    _, op = achar_op(rd, "POST", "/tarefas/{id}/letras")
    if res is None or op is None:
        return "FALHOU", "recurso ou rota sumiram"
    n_res = len(res.get("interceptors") or [])
    n_op = len(op.get("interceptors") or [])
    if n_res == 0 and n_op == 0:
        return "ATENCAO", ("recurso e rota ficaram com lista VAZIA (%d/%d). No Manager "
                           "lista vazia = HERDA: a rota continua executando o fluxo da "
                           "revision. Nao existe 'rota sem interceptors'." % (n_res, n_op))
    return "PASSOU", "recurso=%d rota=%d interceptor(es)" % (n_res, n_op)


def t07_mut(repo):
    f = repo / "resources" / "tarefas" / "resource.yaml"
    t = f.read_text(encoding="utf-8").replace("inherit: true", "inherit: false")
    t += ("\ninterceptors_request:\n"
          "  - type: Custom\n    id: 32\n"
          "  - type: Payload size\n    content:\n      maxSize: 1024\n")
    f.write_text(t, encoding="utf-8")


def t07_ver(aa, ra, ad, rd, reg):
    res = achar_res(rd, "Tarefas")
    if res is None:
        return "FALHOU", "recurso Tarefas sumiu"
    seus = tipos(res.get("interceptors"))
    linhas = []
    for metodo, path in (("GET", "/tarefas"), ("GET", "/tarefas/{id}")):
        _, op = achar_op(rd, metodo, path)
        linhas.append("%s %s -> %d proprio(s)" % (metodo, path, len(op.get("interceptors") or []) if op else -1))
    return "PASSOU", ("resource com %d item(ns) %s | rotas: %s | as rotas herdam por lista "
                      "vazia, nao por copia" % (len(seus), seus, "; ".join(linhas)))


def t08_mut(repo):
    f = repo / "resources" / "tarefas" / "get_tarefas_{id}.yaml"
    t = f.read_text(encoding="utf-8").replace("inherit: true", "inherit: false")
    t += ("\ninterceptors_request:\n"
          "  - type: Custom\n    id: 33\n"
          "  - type: Log\n    content:\n      acceptedTerms: true\n"
          "      encryptContent: false\n      encryptPathAndParameters: false\n")
    f.write_text(t, encoding="utf-8")


def t08_ver(aa, ra, ad, rd, reg):
    _, op = achar_op(rd, "GET", "/tarefas/{id}")
    if op is None:
        return "FALHOU", "a rota sumiu"
    seus = tipos(op.get("interceptors"))
    tem_33 = any(c == 33 for _, c in seus)
    if tem_33 and len(seus) == 2:
        return "PASSOU", "a rota subiu com os 2 interceptors declarados: %s" % seus
    return "ATENCAO", "a rota ficou com %d item(ns): %s" % (len(seus), seus)


def t10_mut(repo):
    (repo / "resources" / "letras" / "delete_letras_{id}.yaml").unlink()


def t10_ver(aa, ra, ad, rd, reg):
    _, op = achar_op(rd, "DELETE", "/letras/{id}")
    if op is None:
        res = achar_res(rd, "Letras")
        n = len(res.get("operations") or []) if res else -1
        return "PASSOU", "a rota foi removida da plataforma; Letras ficou com %d operacao(oes)" % n
    return "FALHOU", "a rota continua na plataforma"


def t11_mut(repo):
    f = repo / "resources" / "letras" / "post_tarefas_{id}_letras.yaml"
    t = f.read_text(encoding="utf-8")
    t += ("\ninterceptors_request:\n"
          "  - type: Payload size\n    content:\n      maxSize: 512\n")
    f.write_text(t, encoding="utf-8")


def t11_ver(aa, ra, ad, rd, reg):
    _, op = achar_op(rd, "POST", "/tarefas/{id}/letras")
    if op is None:
        return "FALHOU", "a rota sumiu"
    seus = tipos(op.get("interceptors"))
    antes = 0
    if ra:
        _, op_antes = achar_op(ra, "POST", "/tarefas/{id}/letras")
        antes = len(op_antes.get("interceptors") or []) if op_antes else 0
    if any(t == "Payload size" for t, _ in seus):
        return "PASSOU", "append: a rota foi de %d para %d item(ns) -> %s" % (antes, len(seus), seus)
    return "ATENCAO", "o item nao aparece na rota (antes=%d, agora=%d): %s" % (antes, len(seus), seus)


TESTES = [
    ("T01", "Editar a description da API", "a nova description aparece no GET", t01_mut, t01_ver),
    ("T02", "Editar o basePath", "a guarda recusa antes de qualquer escrita", t02_mut, t02_ver),
    ("T03", "Remover a tag 'My new'", "o AG bloqueia e a tag permanece", t03_mut, t03_ver),
    ("T04", "Editar o destination de GET /tarefas", "o novo destino aparece no GET", t04_mut, t04_ver),
    ("T05", "Adicionar a rota GET /musicas", "a rota existe e herda o fluxo", t05_mut, t05_ver),
    ("T06", "inherit:false vazio em recurso e rota", "a rota sobe sem interceptors", t06_mut, t06_ver),
    ("T07", "inherit:false + interceptors no RESOURCE", "as rotas do recurso herdam", t07_mut, t07_ver),
    ("T08", "inherit:false + interceptors numa ROTA", "os interceptors sobem na rota", t08_mut, t08_ver),
    ("T10", "Remover a rota DELETE /letras/{id}", "a rota some da plataforma", t10_mut, t10_ver),
    ("T11", "Acrescentar interceptor com inherit:true", "append ao fim do fluxo", t11_mut, t11_ver),
]

if __name__ == "__main__":
    so = sys.argv[3] if len(sys.argv) > 3 else None
    for ident, titulo, esperado, mut, ver in TESTES:
        if so and so != ident:
            continue
        rodar(ident, titulo, esperado, mut, ver)
    SAIDA.joinpath("resultados.json").write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n\n" + "=" * 78)
    print("%-6s %-12s %s" % ("TESTE", "VEREDITO", "DETALHE"))
    print("=" * 78)
    for r in resultados:
        print("%-6s %-12s %s" % (r["id"], r.get("veredito"), (r.get("detalhe") or "")[:60]))
