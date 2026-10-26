"""Nomenclatura e descoberta do layout canônico — lógica pura, sem rede e sem IO.

Transplantado de `docs/feat-api-estructure/decisoes-refino-409/exemplos-gerados/extrair_estrutura.py`,
validado contra 6 APIs reais (155 arquivos). Duas mudanças em relação ao protótipo:

1. a lista de avisos deixa de ser estado global do módulo e passa a ser recebida
   explicitamente, para que a função seja pura e testável em paralelo;
2. entra `metodo_do_arquivo()`, o caminho inverso — o YAML da operação NÃO declara
   `method`, então o nome do arquivo é a única fonte (D-005 §4).

Árvore canônica (D-005 §4, com `all.yaml` fechado pela V-18):

    repositorio-da-api/
    ├── api-basic-info.yaml
    ├── all.yaml                       escopo raiz da revision
    ├── components.yaml                optional: OpenAPI contract components
    └── resources/
        └── <slug-do-recurso>/
            ├── resource.yaml
            └── <metodo>_<path>.yaml
"""

import hashlib
import posixpath
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

# Orçamento de caminho. Windows limita 248 para diretório e 260 para arquivo;
# os tetos abaixo deixam folga para a raiz do repositório.
MAX_SLUG = 60
MAX_ARQUIVO = 90
MAX_SUFIXO_PASTA = 40

# Nomes dos arquivos base. São EXATOS: a ausência aborta a E1 (V-18 §2.3).
ARQUIVO_BASIC_INFO = "api-basic-info.yaml"
ARQUIVO_RAIZ = "all.yaml"
ARQUIVO_RECURSO = "resource.yaml"
PASTA_RECURSOS = "resources"
# Optional: its absence is not reported in `faltando`.
COMPONENTS_FILE = "components.yaml"

METODOS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD")

# Execution points governados pelo repositório. O que estiver fora volta
# intacto na publicação e não entra na conformidade (V-22).
GOVERNED_EXECUTION_POINTS = frozenset({"FIRST", "SECOND"})

# Nomes reservados pelo Windows: uma pasta chamada `con` ou `aux` é
# incriável, independentemente da extensão.
RESERVADOS = (
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)


def slug(texto: Optional[str], limite: int = MAX_SLUG) -> str:
    """Normaliza para ASCII minúsculo com hífens, truncando em fronteira de palavra."""
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    t = t.replace("{", "").replace("}", "")
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
    t = re.sub(r"-{2,}", "-", t)
    if limite and len(t) > limite:
        corte = t[:limite]
        t = corte.rsplit("-", 1)[0] if "-" in corte else corte
    return t


def prefixo_comum(paths: Sequence[str]) -> str:
    """Maior prefixo de segmentos compartilhado por todos os paths."""
    if not paths:
        return ""
    segs = [p.strip("/").split("/") for p in paths]
    comum: List[str] = []
    for i in range(min(len(s) for s in segs)):
        col = {s[i] for s in segs}
        if len(col) != 1:
            break
        comum.append(col.pop())
    return "/".join(comum)


def operacoes_ordenadas(recurso: Dict[str, Any]) -> List[tuple]:
    """Pares (path, método) em ordem estável — base do determinismo da marca."""
    return sorted(
        (o.get("path", ""), (o.get("method") or "").upper())
        for o in recurso.get("operations") or []
    )


def marca(recurso: Dict[str, Any]) -> str:
    """Marca determinística derivada das operações do recurso."""
    ops = [f"{m} {p}" for p, m in operacoes_ordenadas(recurso)]
    semente = "|".join(ops) or (recurso.get("name") or "")
    return hashlib.sha1(semente.encode("utf-8")).hexdigest()[:6]


def nome_pasta(
    recurso: Dict[str, Any],
    todos: Sequence[Dict[str, Any]],
    avisos: Optional[List[str]] = None,
) -> str:
    """Nome da pasta do recurso, com desambiguação híbrida.

    A ordem importa: tenta o slug puro, depois um sufixo **legível** (o path da
    primeira operação) e só recorre à marca como último caso. A mensagem
    distingue colisão por nome IDÊNTICO de colisão por TRUNCAMENTO — são
    problemas diferentes para quem lê o repositório.
    """
    nome = recurso.get("name") or ""
    if not nome:
        nome = "/" + prefixo_comum([o["path"] for o in recurso.get("operations") or []])

    completo = slug(nome, limite=0)
    base_bruto = slug(nome)

    # A desambiguação se mede sobre o slug BRUTO. Medi-la sobre o nome já
    # reescrito faria um nome reservado parecer truncado e impediria o recurso de
    # se encontrar entre os homônimos — defeito herdado do protótipo, onde nunca
    # apareceu porque nenhuma das 6 APIs reais tem recurso chamado `con`/`aux`.
    homonimos = [r for r in todos if slug(r.get("name") or "") == base_bruto]
    truncou = completo != base_bruto

    base = f"{base_bruto}-recurso" if base_bruto in RESERVADOS else base_bruto
    if len(homonimos) == 1 and not truncou:
        return base

    if avisos is not None and len(homonimos) > 1:
        nomes = {r.get("name") for r in homonimos}
        if len(nomes) == 1:
            avisos.append(
                f"{len(homonimos)} recursos com o MESMO nome "
                f"{recurso.get('name')!r} — desambiguados no repositório"
            )
        else:
            avisos.append(
                f"{len(homonimos)} recursos cujo nome, truncado em {MAX_SLUG} "
                f"caracteres, colide em {base!r} — desambiguados no repositório"
            )

    # (a) sufixo legível: path da primeira operação
    ops = operacoes_ordenadas(recurso)
    if ops:
        legivel = f"{base}-{slug(ops[0][0], MAX_SUFIXO_PASTA)}"
        concorrentes = []
        for r in homonimos:
            o = operacoes_ordenadas(r)
            if o:
                concorrentes.append(f"{base}-{slug(o[0][0], MAX_SUFIXO_PASTA)}")
        if concorrentes.count(legivel) <= 1 and len(legivel) <= MAX_SLUG:
            return legivel

    # (b) marca determinística, último recurso
    return f"{base}-{marca(recurso)}"


def slug_path(path: Optional[str]) -> str:
    """Path completo como sufixo de arquivo: `/` vira `_` e `{param}` é preservado.

    Transformação mínima — o nome do arquivo tem de ser lido como a rota:

        /letras/{id}                          -> letras_{id}
        /tarefas/{id}/atribuicao-responsavel  -> tarefas_{id}_atribuicao-responsavel
    """
    t = unicodedata.normalize("NFKD", path or "").encode("ascii", "ignore").decode()
    t = t.strip("/").lower()
    t = re.sub(r"[^A-Za-z0-9{}\-_/]+", "-", t)
    t = t.replace("/", "_")
    return re.sub(r"-{2,}", "-", t).strip("-_")


def nome_arquivo(op: Dict[str, Any], avisos: Optional[List[str]] = None) -> str:
    """`<metodo>_<path completo>.yaml` — o prefixo do recurso NÃO é cortado.

    Só quando o nome estoura `MAX_ARQUIVO` ele é truncado e recebe a marca, para
    não ultrapassar o limite de caminho do sistema de arquivos.
    """
    metodo = (op.get("method") or "").lower()
    sufixo = slug_path(op.get("path"))
    nome = f"{metodo}_{sufixo}" if sufixo else metodo
    if len(nome) > MAX_ARQUIVO:
        corte = nome[:MAX_ARQUIVO]
        corte = corte.rsplit("_", 1)[0] if "_" in corte else corte
        digest = hashlib.sha1(
            f"{metodo} {op.get('path')}".encode("utf-8")
        ).hexdigest()[:6]
        nome = f"{corte}-{digest}"
        if avisos is not None:
            avisos.append(
                f"nome de arquivo truncado em {MAX_ARQUIVO} caracteres: "
                f"{metodo.upper()} {op.get('path')}"
            )
    return f"{nome}.yaml"


def metodo_do_arquivo(nome: str) -> Optional[str]:
    """`<metodo>_<path>.yaml` → método, ou `None` se o nome não for de operação.

    O YAML da operação NÃO carrega `method` (D-005 §4): o nome do arquivo é a
    única fonte. Vale também para o nome truncado, porque o método é prefixo.
    """
    if not nome:
        return None
    base = nome[:-5] if nome.lower().endswith(".yaml") else nome
    if not base or base == ARQUIVO_RECURSO[:-5]:
        return None
    cabeca = base.split("_", 1)[0].upper()
    return cabeca if cabeca in METODOS else None


def eh_arquivo_base(nome: str) -> bool:
    """Arquivos obrigatórios pelo nome exato (V-18 §2.3)."""
    return nome in (ARQUIVO_BASIC_INFO, ARQUIVO_RAIZ, ARQUIVO_RECURSO)


def eh_governado(execution_point: Optional[str]) -> bool:
    """Interceptor governado pelo repositório, ou preservado intacto (V-22)."""
    return (execution_point or "").upper() in GOVERNED_EXECUTION_POINTS


# --------------------------------------------------------------------------- E1


@dataclass(frozen=True)
class OperacaoDescoberta:
    """Um arquivo de operação. O método vem do NOME, não do conteúdo."""

    arquivo: str
    metodo: str
    caminho: str


@dataclass(frozen=True)
class RecursoDescoberto:
    """Uma pasta sob `resources/`."""

    slug: str
    caminho_recurso: str
    operacoes: List[OperacaoDescoberta] = field(default_factory=list)


@dataclass(frozen=True)
class RepositorioDescoberto:
    """Resultado da descoberta da E1.

    `faltando` lista os arquivos base ausentes **pelo nome exato**. Enquanto ela
    não estiver vazia, o repositório não pode ser publicado: a raiz não herda de
    nenhum escopo, então publicar sem ela não preserva o que está lá — apaga o
    fluxo da revision (V-18 §2.3).

    `ignorados` são `.yaml` que não casam com nenhum padrão do layout. NÃO são
    erro: um arquivo de notas ou a configuração de outra ferramenta convivem no
    repositório. A proteção contra erro de digitação vem da obrigatoriedade do
    nome, não da proibição do desconhecido.
    """

    caminho_basic_info: Optional[str] = None
    caminho_raiz: Optional[str] = None
    components_path: Optional[str] = None
    recursos: List[RecursoDescoberto] = field(default_factory=list)
    faltando: List[str] = field(default_factory=list)
    ignorados: List[str] = field(default_factory=list)

    @property
    def completo(self) -> bool:
        return not self.faltando

    @property
    def total_operacoes(self) -> int:
        return sum(len(r.operacoes) for r in self.recursos)


def _normalizar(caminho: str) -> str:
    return caminho.replace("\\", "/").strip("/")


def descobrir(caminhos_relativos: Sequence[str]) -> RepositorioDescoberto:
    """Descobre a estrutura do repositório a partir de uma LISTAGEM de caminhos.

    Função pura: não toca disco nem rede. Quem lista é a camada de aplicação,
    pela porta de importação — assim a E1 inteira é testável sem fixture em
    disco, e a regra do layout fica num lugar só.

    Caminhos são relativos à raiz do repositório, com `/` como separador.
    """
    arquivos = [_normalizar(c) for c in caminhos_relativos]
    arquivos = [c for c in arquivos if c.lower().endswith((".yaml", ".yml"))]

    basic_info = ARQUIVO_BASIC_INFO if ARQUIVO_BASIC_INFO in arquivos else None
    raiz = ARQUIVO_RAIZ if ARQUIVO_RAIZ in arquivos else None
    components_path = COMPONENTS_FILE if COMPONENTS_FILE in arquivos else None

    faltando: List[str] = []
    if basic_info is None:
        faltando.append(ARQUIVO_BASIC_INFO)
    if raiz is None:
        faltando.append(ARQUIVO_RAIZ)

    # Agrupa o que está sob `resources/<slug>/`, preservando ordem estável.
    por_recurso: Dict[str, List[str]] = {}
    ignorados: List[str] = []
    for caminho in arquivos:
        if caminho in (ARQUIVO_BASIC_INFO, ARQUIVO_RAIZ, COMPONENTS_FILE):
            continue
        partes = caminho.split("/")
        if len(partes) == 3 and partes[0] == PASTA_RECURSOS:
            por_recurso.setdefault(partes[1], []).append(partes[2])
        else:
            ignorados.append(caminho)

    recursos: List[RecursoDescoberto] = []
    for slug_recurso in sorted(por_recurso):
        nomes = por_recurso[slug_recurso]
        base = posixpath.join(PASTA_RECURSOS, slug_recurso)

        if ARQUIVO_RECURSO not in nomes:
            faltando.append(posixpath.join(base, ARQUIVO_RECURSO))

        operacoes: List[OperacaoDescoberta] = []
        for nome in sorted(nomes):
            if nome == ARQUIVO_RECURSO:
                continue
            metodo = metodo_do_arquivo(nome)
            if metodo is None:
                # `.yaml` dentro da pasta do recurso que não nomeia um método:
                # não é operação, e não derruba a descoberta.
                ignorados.append(posixpath.join(base, nome))
                continue
            operacoes.append(
                OperacaoDescoberta(
                    arquivo=nome,
                    metodo=metodo,
                    caminho=posixpath.join(base, nome),
                )
            )

        recursos.append(
            RecursoDescoberto(
                slug=slug_recurso,
                caminho_recurso=posixpath.join(base, ARQUIVO_RECURSO),
                operacoes=operacoes,
            )
        )

    return RepositorioDescoberto(
        caminho_basic_info=basic_info,
        caminho_raiz=raiz,
        components_path=components_path,
        recursos=recursos,
        faltando=faltando,
        ignorados=sorted(ignorados),
    )
