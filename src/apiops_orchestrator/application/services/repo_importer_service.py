import logging
import os
from typing import List, Dict, Any, Optional
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.application.enums.yaml_to_json_enum import YamlKind
from apiops_orchestrator.domain.ports.local_file_importer_port import (
    LocalFileImporterPort,
)


class RepoImporterService:
    """
    Imports and organizes the API Repository for use in the Conversor Service.
    """

    def __init__(self, settings: Settings, importer: LocalFileImporterPort):
        self.settings = settings
        self.importer = importer
        self.logger = logging.getLogger(__name__)

    def load_normalized_documents(
        self, repo_path: str, revision_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        # 1. Resolve revision
        if revision_number is None:
            raise ValueError("revision_number must be provided")

        self.logger.info(f"Loading revision {revision_number} from {repo_path}")

        documents = []

        # 0. Revision info (Top level)
        documents.append(
            {"kind": YamlKind.REVISION_INFO.value, "revisionNumber": revision_number}
        )

        # 2. ApiBasicInfo
        api_info_path = os.path.join(
            repo_path, self.settings.API_REPO_API_INFO_FOLDER, "api-basic-info.yaml"
        )
        if self.importer.exists(api_info_path):
            api_info = self.importer.read(api_info_path)
            documents.append(self._normalize_api_basic_info(api_info, repo_path))

        # 3. Interceptors (from revision-flow.yaml)
        rev_path = os.path.join(
            repo_path, self.settings.API_REPO_REVISIONS_FOLDER, str(revision_number)
        )
        rev_flow_path = os.path.join(rev_path, "revision-flow.yaml")
        if self.importer.exists(rev_flow_path):
            rev_flow = self.importer.read(rev_flow_path)
            documents.append(self._normalize_interceptors(rev_flow))

        # 4. Resources and Operations
        resources_list = self._synthesize_resources_list(rev_path)
        documents.append(resources_list)

        # 5. ApiOperations
        operations = self._read_all_operations(rev_path)
        documents.extend(operations)

        return documents

    def _get_latest_revision(self, repo_path: str) -> int:
        revisions_dir = os.path.join(repo_path, self.settings.API_REPO_REVISIONS_FOLDER)
        if not self.importer.exists(revisions_dir):
            raise ValueError(f"Revisions directory not found: {revisions_dir}")

        revisions = []
        for d_path in self.importer.list_directories(revisions_dir):
            d_name = os.path.basename(d_path)
            if d_name.isdigit():
                revisions.append(int(d_name))

        if not revisions:
            raise ValueError(f"No numeric revisions found in {revisions_dir}")

        return max(revisions)

    def _normalize_api_basic_info(
        self, data: Dict[str, Any], repo_path: str
    ) -> Dict[str, Any]:
        new_spec = {"api": data.get("spec", {})}
        # Remove fields that are not used by the script
        for field in ["id", "lastUpdate", "creationDate"]:
            if field in new_spec["api"]:
                del new_spec["api"][field]

        new_spec["api"]["revisions"] = []
        new_spec["api"]["lastRevision"] = {}

        return {
            "apiVersion": data.get("apiVersion"),
            "kind": YamlKind.API_BASIC_INFO.value,
            "spec": new_spec,
        }

    def _normalize_interceptors(self, data: Dict[str, Any]) -> Dict[str, Any]:
        interceptors = data.get("spec", {}).get("interceptors", [])
        return {
            "apiVersion": data.get("apiVersion"),
            "kind": YamlKind.INTERCEPTORS.value,
            "spec": {"interceptors": interceptors},
        }

    def _synthesize_resources_list(self, revision_path: str) -> Dict[str, Any]:
        resources_dir = os.path.join(revision_path, "resources")
        items = []
        api_version = "api-management.sensedia.com/v1"

        if self.importer.exists(resources_dir):
            for res_dir in self.importer.list_directories(resources_dir):
                res_file = os.path.join(res_dir, "resource.yaml")
                if self.importer.exists(res_file):
                    res_data = self.importer.read(res_file)
                    api_version = res_data.get("apiVersion", api_version)

                    for item in res_data.get("items", []):
                        resource_name = item.get("name")
                        resource_description = item.get("description")

                        # Scan operations
                        ops_dir = os.path.join(res_dir, "operations")
                        ops_refs = []
                        if self.importer.exists(ops_dir):
                            for op_file in self.importer.glob_files(ops_dir, "*.yaml"):
                                op_data = self.importer.read(op_file)

                                for op in op_data.get("spec", {}).get("operation", []):
                                    ops_refs.append(
                                        {
                                            "method": op.get("method"),
                                            "path": op.get("path"),
                                            "file": f"{os.path.basename(res_dir)}/{os.path.basename(op_file)}",
                                        }
                                    )

                        items.append(
                            {
                                "name": resource_name,
                                "description": resource_description,
                                "operations": ops_refs,
                            }
                        )

        return {
            "apiVersion": api_version,
            "kind": YamlKind.RESOURCES_LIST.value,
            "items": items,
        }

    def _read_all_operations(self, revision_path: str) -> List[Dict[str, Any]]:
        resources_dir = os.path.join(revision_path, "resources")
        operations = []

        if self.importer.exists(resources_dir):
            for res_dir in self.importer.list_directories(resources_dir):
                ops_dir = os.path.join(res_dir, "operations")
                if self.importer.exists(ops_dir):
                    for op_file in self.importer.glob_files(ops_dir, "*.yaml"):
                        op_data = self.importer.read(op_file)
                        if "metadata" not in op_data:
                            op_data["metadata"] = {}
                        op_data["metadata"][
                            "fileName"
                        ] = f"{os.path.basename(res_dir)}/{os.path.basename(op_file)}"
                        operations.append(op_data)
        return operations


# =============================================================================
# Leitor do layout CANÔNICO (D-005 §4 · V-18) — a E1 do `sen validate`
#
# Convive com `RepoImporterService` acima, que lê o layout ANTIGO
# (`revisions/<n>/`, `revision-flow.yaml`, `resource.yaml` com `items[]`) e
# alimenta o `ConversorService` do pipeline bare. Os dois layouts não podem ser
# válidos ao mesmo tempo; o legado sai quando a fase 3 substituir o publisher.
# =============================================================================

import posixpath
from dataclasses import dataclass, field
from pathlib import Path

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
