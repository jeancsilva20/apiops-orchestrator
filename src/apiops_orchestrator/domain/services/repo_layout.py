"""Nomenclatura e descoberta do layout canônico — lógica pura, sem rede e sem IO.

Transplantado de `docs/feat-api-estructure/decisoes-refino-409/exemplos-gerados/extrair_estrutura.py`,
validado contra 6 APIs reais (155 arquivos). Duas mudanças em relação ao protótipo:

1. a lista de avisos deixa de ser estado global do módulo e passa a ser recebida
   explicitamente, para que a função seja pura e testável em paralelo;
2. entra `method_from_file()`, o caminho inverso — o YAML da operação NÃO declara
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
MAX_FILE = 90
MAX_FOLDER_SUFFIX = 40

# Nomes dos arquivos base. São EXATOS: a ausência aborta a E1 (V-18 §2.3).
BASIC_INFO_FILE = "api-basic-info.yaml"
ROOT_FILE = "all.yaml"
RESOURCE_FILE = "resource.yaml"
RESOURCES_FOLDER = "resources"
# Optional: its absence is not reported in `missing`.
COMPONENTS_FILE = "components.yaml"

METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD")

# Execution points governados pelo repositório. O que estiver fora volta
# intacto na publicação e não entra na conformidade (V-22).
GOVERNED_EXECUTION_POINTS = frozenset({"FIRST", "SECOND"})

# Nomes reservados pelo Windows: uma pasta chamada `con` ou `aux` é
# incriável, independentemente da extensão.
RESERVED = (
    {"con", "prn", "aux", "nul"}
    | {f"com{i}" for i in range(1, 10)}
    | {f"lpt{i}" for i in range(1, 10)}
)


def slug(text: Optional[str], limit: int = MAX_SLUG) -> str:
    """Normaliza para ASCII minúsculo com hífens, truncando em fronteira de palavra."""
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    t = t.replace("{", "").replace("}", "")
    t = re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-").lower()
    t = re.sub(r"-{2,}", "-", t)
    if limit and len(t) > limit:
        cut = t[:limit]
        t = cut.rsplit("-", 1)[0] if "-" in cut else cut
    return t


def common_prefix(paths: Sequence[str]) -> str:
    """Maior prefixo de segmentos compartilhado por todos os paths."""
    if not paths:
        return ""
    segments = [p.strip("/").split("/") for p in paths]
    common: List[str] = []
    for i in range(min(len(s) for s in segments)):
        col = {s[i] for s in segments}
        if len(col) != 1:
            break
        common.append(col.pop())
    return "/".join(common)


def sorted_operations(resource: Dict[str, Any]) -> List[tuple]:
    """Pares (path, método) em ordem estável — base do determinismo da marca."""
    return sorted(
        (o.get("path", ""), (o.get("method") or "").upper())
        for o in resource.get("operations") or []
    )


def fingerprint(resource: Dict[str, Any]) -> str:
    """Marca determinística derivada das operações do recurso."""
    ops = [f"{m} {p}" for p, m in sorted_operations(resource)]
    seed = "|".join(ops) or (resource.get("name") or "")
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:6]


def folder_name(
    resource: Dict[str, Any],
    all_resources: Sequence[Dict[str, Any]],
    warnings: Optional[List[str]] = None,
) -> str:
    """Nome da pasta do recurso, com desambiguação híbrida.

    A ordem importa: tenta o slug puro, depois um sufixo **legível** (o path da
    primeira operação) e só recorre à marca como último caso. A mensagem
    distingue colisão por nome IDÊNTICO de colisão por TRUNCAMENTO — são
    problemas diferentes para quem lê o repositório.
    """
    name = resource.get("name") or ""
    if not name:
        name = "/" + common_prefix([o["path"] for o in resource.get("operations") or []])

    complete = slug(name, limit=0)
    raw_base = slug(name)

    # A desambiguação se mede sobre o slug BRUTO. Medi-la sobre o nome já
    # reescrito faria um nome reservado parecer truncado e impediria o recurso de
    # se encontrar entre os homônimos — defeito herdado do protótipo, onde nunca
    # apareceu porque nenhuma das 6 APIs reais tem recurso chamado `con`/`aux`.
    homonyms = [r for r in all_resources if slug(r.get("name") or "") == raw_base]
    truncated = complete != raw_base

    base = f"{raw_base}-recurso" if raw_base in RESERVED else raw_base
    if len(homonyms) == 1 and not truncated:
        return base

    if warnings is not None and len(homonyms) > 1:
        names = {r.get("name") for r in homonyms}
        if len(names) == 1:
            warnings.append(
                f"{len(homonyms)} recursos com o MESMO nome "
                f"{resource.get('name')!r} — desambiguados no repositório"
            )
        else:
            warnings.append(
                f"{len(homonyms)} recursos cujo nome, truncado em {MAX_SLUG} "
                f"caracteres, colide em {base!r} — desambiguados no repositório"
            )

    # (a) sufixo legível: path da primeira operação
    ops = sorted_operations(resource)
    if ops:
        readable = f"{base}-{slug(ops[0][0], MAX_FOLDER_SUFFIX)}"
        competing = []
        for r in homonyms:
            o = sorted_operations(r)
            if o:
                competing.append(f"{base}-{slug(o[0][0], MAX_FOLDER_SUFFIX)}")
        if competing.count(readable) <= 1 and len(readable) <= MAX_SLUG:
            return readable

    # (b) marca determinística, último recurso
    return f"{base}-{fingerprint(resource)}"


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


def file_name(op: Dict[str, Any], warnings: Optional[List[str]] = None) -> str:
    """`<method>_<path complete>.yaml` — o prefixo do recurso NÃO é cortado.

    Só quando o nome estoura `MAX_FILE` ele é truncado e recebe a marca, para
    não ultrapassar o limite de caminho do sistema de arquivos.
    """
    method = (op.get("method") or "").lower()
    suffix = slug_path(op.get("path"))
    name = f"{method}_{suffix}" if suffix else method
    if len(name) > MAX_FILE:
        cut = name[:MAX_FILE]
        cut = cut.rsplit("_", 1)[0] if "_" in cut else cut
        digest = hashlib.sha1(
            f"{method} {op.get('path')}".encode("utf-8")
        ).hexdigest()[:6]
        name = f"{cut}-{digest}"
        if warnings is not None:
            warnings.append(
                f"nome de arquivo truncado em {MAX_FILE} caracteres: "
                f"{method.upper()} {op.get('path')}"
            )
    return f"{name}.yaml"


def method_from_file(name: str) -> Optional[str]:
    """`<method>_<path>.yaml` → método, ou `None` se o nome não for de operação.

    O YAML da operação NÃO carrega `method` (D-005 §4): o nome do arquivo é a
    única fonte. Vale também para o nome truncado, porque o método é prefixo.
    """
    if not name:
        return None
    base = name[:-5] if name.lower().endswith(".yaml") else name
    if not base or base == RESOURCE_FILE[:-5]:
        return None
    head = base.split("_", 1)[0].upper()
    return head if head in METHODS else None


def is_base_file(name: str) -> bool:
    """Arquivos obrigatórios pelo nome exato (V-18 §2.3)."""
    return name in (BASIC_INFO_FILE, ROOT_FILE, RESOURCE_FILE)


def is_governed(execution_point: Optional[str]) -> bool:
    """Interceptor governado pelo repositório, ou preservado intacto (V-22)."""
    return (execution_point or "").upper() in GOVERNED_EXECUTION_POINTS


# --------------------------------------------------------------------------- E1


@dataclass(frozen=True)
class DiscoveredOperation:
    """Um arquivo de operação. O método vem do NOME, não do conteúdo."""

    file: str
    method: str
    file_path: str


@dataclass(frozen=True)
class DiscoveredResource:
    """Uma pasta sob `resources/`."""

    slug: str
    resource_file_path: str
    operations: List[DiscoveredOperation] = field(default_factory=list)


@dataclass(frozen=True)
class DiscoveredRepository:
    """Resultado da descoberta da E1.

    `missing` lista os arquivos base ausentes **pelo nome exato**. Enquanto ela
    não estiver vazia, o repositório não pode ser publicado: a raiz não herda de
    nenhum escopo, então publicar sem ela não preserva o que está lá — apaga o
    fluxo da revision (V-18 §2.3).

    `ignored` são `.yaml` que não casam com nenhum padrão do layout. NÃO são
    erro: um arquivo de notas ou a configuração de outra ferramenta convivem no
    repositório. A proteção contra erro de digitação vem da obrigatoriedade do
    nome, não da proibição do desconhecido.
    """

    basic_info_path: Optional[str] = None
    root_file_path: Optional[str] = None
    components_path: Optional[str] = None
    resources: List[DiscoveredResource] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    ignored: List[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.missing

    @property
    def total_operations(self) -> int:
        return sum(len(r.operations) for r in self.resources)


def _normalize(file_path: str) -> str:
    return file_path.replace("\\", "/").strip("/")


def discover(relative_paths: Sequence[str]) -> DiscoveredRepository:
    """Descobre a estrutura do repositório a partir de uma LISTAGEM de caminhos.

    Função pura: não toca disco nem rede. Quem lista é a camada de aplicação,
    pela porta de importação — assim a E1 inteira é testável sem fixture em
    disco, e a regra do layout fica num lugar só.

    Caminhos são relativos à raiz do repositório, com `/` como separador.
    """
    files = [_normalize(c) for c in relative_paths]
    files = [c for c in files if c.lower().endswith((".yaml", ".yml"))]

    basic_info = BASIC_INFO_FILE if BASIC_INFO_FILE in files else None
    root = ROOT_FILE if ROOT_FILE in files else None
    components_path = COMPONENTS_FILE if COMPONENTS_FILE in files else None

    missing: List[str] = []
    if basic_info is None:
        missing.append(BASIC_INFO_FILE)
    if root is None:
        missing.append(ROOT_FILE)

    # Agrupa o que está sob `resources/<slug>/`, preservando ordem estável.
    by_resource: Dict[str, List[str]] = {}
    ignored: List[str] = []
    for file_path in files:
        if file_path in (BASIC_INFO_FILE, ROOT_FILE, COMPONENTS_FILE):
            continue
        parts = file_path.split("/")
        if len(parts) == 3 and parts[0] == RESOURCES_FOLDER:
            by_resource.setdefault(parts[1], []).append(parts[2])
        else:
            ignored.append(file_path)

    resources: List[DiscoveredResource] = []
    for resource_slug in sorted(by_resource):
        names = by_resource[resource_slug]
        base = posixpath.join(RESOURCES_FOLDER, resource_slug)

        if RESOURCE_FILE not in names:
            missing.append(posixpath.join(base, RESOURCE_FILE))

        operations: List[DiscoveredOperation] = []
        for name in sorted(names):
            if name == RESOURCE_FILE:
                continue
            method = method_from_file(name)
            if method is None:
                # `.yaml` dentro da pasta do recurso que não nomeia um método:
                # não é operação, e não derruba a descoberta.
                ignored.append(posixpath.join(base, name))
                continue
            operations.append(
                DiscoveredOperation(
                    file=name,
                    method=method,
                    file_path=posixpath.join(base, name),
                )
            )

        resources.append(
            DiscoveredResource(
                slug=resource_slug,
                resource_file_path=posixpath.join(base, RESOURCE_FILE),
                operations=operations,
            )
        )

    return DiscoveredRepository(
        basic_info_path=basic_info,
        root_file_path=root,
        components_path=components_path,
        resources=resources,
        missing=missing,
        ignored=sorted(ignored),
    )
