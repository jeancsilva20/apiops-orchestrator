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
class OperacaoCarregada:
    """Uma operação lida do disco. O método vem do NOME do arquivo."""

    metodo: str
    path: Optional[str]
    arquivo: str
    caminho: str
    dados: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RecursoCarregado:
    slug: str
    caminho: str
    dados: Dict[str, Any] = field(default_factory=dict)
    operacoes: List[OperacaoCarregada] = field(default_factory=list)

    @property
    def nome(self) -> Optional[str]:
        return self.dados.get("name")


@dataclass(frozen=True)
class RepositorioCarregado:
    """Resultado da E1: o repositório inteiro em memória, sem rede.

    `faltando` e `ilegiveis` não são exceção aqui de propósito — a camada de
    aplicação é que decide o desfecho e o exit code. O domínio e o leitor apenas
    relatam.
    """

    raiz_path: str
    basic_info: Dict[str, Any] = field(default_factory=dict)
    raiz: Dict[str, Any] = field(default_factory=dict)
    recursos: List[RecursoCarregado] = field(default_factory=list)
    faltando: List[str] = field(default_factory=list)
    ignorados: List[str] = field(default_factory=list)
    ilegiveis: List[str] = field(default_factory=list)

    @property
    def completo(self) -> bool:
        return not self.faltando and not self.ilegiveis

    @property
    def total_operacoes(self) -> int:
        return sum(len(r.operacoes) for r in self.recursos)


def _motivo_da_leitura(exc: Exception) -> str:
    """Por que o arquivo não pôde ser lido, em termos de quem vai corrigi-lo.

    O adapter embrulha o erro do parser numa mensagem com o caminho absoluto da
    máquina e o rastro inteiro do PyYAML. O que interessa ao dev é a linha, a
    coluna e o problema — o erro original vem encadeado e tem as três coisas.
    """
    origem = exc.__cause__ or exc.__context__
    marca = getattr(origem, "problem_mark", None)
    if marca is not None:
        problema = getattr(origem, "problem", None)
        local = f"linha {marca.line + 1}, coluna {marca.column + 1}"
        return f"erro de sintaxe YAML na {local}" + (f" ({problema})" if problema else "")
    if isinstance(exc, PermissionError) or isinstance(origem, PermissionError):
        return "sem permissão de leitura"
    if isinstance(origem, UnicodeDecodeError):
        return "o arquivo não está em UTF-8"
    return "conteúdo inválido"


class RepoCanonicalReader:
    """Lê um repositório no layout canônico. Sem rede — esta é a E1 inteira."""

    def __init__(self, importer: LocalFileImporterPort):
        self.importer = importer
        self.logger = logging.getLogger(__name__)

    def carregar(self, repo_path: str) -> RepositorioCarregado:
        raiz = Path(repo_path)
        relativos = self._listar(raiz)
        descoberta = _layout.descobrir(relativos)

        ilegiveis: List[str] = []

        def ler(caminho_relativo: Optional[str]) -> Dict[str, Any]:
            if not caminho_relativo:
                return {}
            absoluto = str(raiz / Path(caminho_relativo))
            try:
                return self.importer.read(absoluto) or {}
            except Exception as exc:  # YAML malformado, permissão, encoding
                # Não engolir: um arquivo ilegível é falha do repositório, e o
                # caso real existe — `replaceChar: *****` sem aspas torna o
                # arquivo imparseável.
                ilegiveis.append(f"{caminho_relativo}: {_motivo_da_leitura(exc)}")
                self.logger.info("repo.arquivo_ilegivel caminho=%s", caminho_relativo)
                return {}

        basic_info = ler(descoberta.caminho_basic_info)
        conteudo_raiz = ler(descoberta.caminho_raiz)

        recursos: List[RecursoCarregado] = []
        for recurso in descoberta.recursos:
            operacoes = [
                OperacaoCarregada(
                    metodo=op.metodo,
                    path=(dados := ler(op.caminho)).get("path"),
                    arquivo=op.arquivo,
                    caminho=op.caminho,
                    dados=dados,
                )
                for op in recurso.operacoes
            ]
            recursos.append(
                RecursoCarregado(
                    slug=recurso.slug,
                    caminho=recurso.caminho_recurso,
                    dados=ler(recurso.caminho_recurso)
                    if recurso.caminho_recurso not in descoberta.faltando
                    else {},
                    operacoes=operacoes,
                )
            )

        return RepositorioCarregado(
            raiz_path=str(raiz),
            basic_info=basic_info,
            raiz=conteudo_raiz,
            recursos=recursos,
            faltando=list(descoberta.faltando),
            ignorados=list(descoberta.ignorados),
            ilegiveis=ilegiveis,
        )

    def _listar(self, raiz: Path) -> List[str]:
        """Caminhos relativos, com `/`, de todo `.yaml`/`.yml` sob a raiz."""
        achados = self.importer.glob_files(str(raiz), "**/*.yaml")
        achados += self.importer.glob_files(str(raiz), "**/*.yml")
        relativos = []
        for bruto in achados:
            try:
                rel = Path(bruto).resolve().relative_to(raiz.resolve())
            except ValueError:
                continue
            relativos.append(posixpath.join(*rel.parts))
        return sorted(set(relativos))
