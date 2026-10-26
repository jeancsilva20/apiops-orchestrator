"""Leitor do layout canônico (D-005 §4 · V-18) — a E1 do `sen validate`."""

import logging
import posixpath
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from apiops_orchestrator.domain.ports.local_file_importer_port import (
    LocalFileImporterPort,
)
from apiops_orchestrator.domain.services import repo_layout as _layout


@dataclass(frozen=True)
class LoadedOperation:
    """Uma operação lida do disco. O método vem do NOME do arquivo."""

    method: str
    path: Optional[str]
    file: str
    file_path: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LoadedResource:
    slug: str
    file_path: str
    data: Dict[str, Any] = field(default_factory=dict)
    operations: List[LoadedOperation] = field(default_factory=list)

    @property
    def name(self) -> Optional[str]:
        return self.data.get("name")


@dataclass(frozen=True)
class LoadedRepository:
    """Resultado da E1: o repositório inteiro em memória, sem rede.

    `missing` e `unreadable` não são exceção aqui de propósito — a camada de
    aplicação é que decide o desfecho e o exit code. O domínio e o leitor apenas
    relatam.
    """

    root_path: str
    basic_info: Dict[str, Any] = field(default_factory=dict)
    root: Dict[str, Any] = field(default_factory=dict)
    components: Dict[str, Any] = field(default_factory=dict)
    resources: List[LoadedResource] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    ignored: List[str] = field(default_factory=list)
    unreadable: List[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.missing and not self.unreadable

    @property
    def total_operations(self) -> int:
        return sum(len(r.operations) for r in self.resources)


def _read_error_reason(exc: Exception) -> str:
    """Por que o arquivo não pôde ser lido, em termos de quem vai corrigi-lo.

    O adapter embrulha o erro do parser numa mensagem com o caminho absoluto da
    máquina e o rastro inteiro do PyYAML. O que interessa ao dev é a linha, a
    coluna e o problema — o erro original vem encadeado e tem as três coisas.
    """
    origin = exc.__cause__ or exc.__context__
    mark = getattr(origin, "problem_mark", None)
    if mark is not None:
        problem = getattr(origin, "problem", None)
        local = f"linha {mark.line + 1}, coluna {mark.column + 1}"
        return f"erro de sintaxe YAML na {local}" + (f" ({problem})" if problem else "")
    if isinstance(exc, PermissionError) or isinstance(origin, PermissionError):
        return "sem permissão de leitura"
    if isinstance(origin, UnicodeDecodeError):
        return "o arquivo não está em UTF-8"
    return "conteúdo inválido"


class RepoCanonicalReader:
    """Lê um repositório no layout canônico. Sem rede — esta é a E1 inteira."""

    def __init__(self, importer: LocalFileImporterPort):
        self.importer = importer
        self.logger = logging.getLogger(__name__)

    def load(self, repo_path: str) -> LoadedRepository:
        root = Path(repo_path)
        relative_paths = self._list(root)
        discovery = _layout.discover(relative_paths)

        unreadable: List[str] = []

        def read(relative_path: Optional[str]) -> Dict[str, Any]:
            if not relative_path:
                return {}
            absolute = str(root / Path(relative_path))
            try:
                return self.importer.read(absolute) or {}
            except Exception as exc:  # YAML malformado, permissão, encoding
                # Não engolir: um arquivo ilegível é falha do repositório, e o
                # caso real existe — `replaceChar: *****` sem aspas torna o
                # arquivo imparseável.
                unreadable.append(f"{relative_path}: {_read_error_reason(exc)}")
                self.logger.info("repo.arquivo_ilegivel caminho=%s", relative_path)
                return {}

        basic_info = read(discovery.basic_info_path)
        root_content = read(discovery.root_file_path)
        components = read(discovery.components_path)

        resources: List[LoadedResource] = []
        for resource in discovery.resources:
            operations = [
                LoadedOperation(
                    method=op.method,
                    path=(data := read(op.file_path)).get("path"),
                    file=op.file,
                    file_path=op.file_path,
                    data=data,
                )
                for op in resource.operations
            ]
            resources.append(
                LoadedResource(
                    slug=resource.slug,
                    file_path=resource.resource_file_path,
                    data=read(resource.resource_file_path)
                    if resource.resource_file_path not in discovery.missing
                    else {},
                    operations=operations,
                )
            )

        return LoadedRepository(
            root_path=str(root),
            basic_info=basic_info,
            root=root_content,
            components=components,
            resources=resources,
            missing=list(discovery.missing),
            ignored=list(discovery.ignored),
            unreadable=unreadable,
        )

    def _list(self, root: Path) -> List[str]:
        """Caminhos relativos, com `/`, de todo `.yaml`/`.yml` sob a raiz."""
        findings = self.importer.glob_files(str(root), "**/*.yaml")
        findings += self.importer.glob_files(str(root), "**/*.yml")
        relative_paths = []
        for raw in findings:
            try:
                rel = Path(raw).resolve().relative_to(root.resolve())
            except ValueError:
                continue
            relative_paths.append(posixpath.join(*rel.parts))
        return sorted(set(relative_paths))
