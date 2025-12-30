import logging
import os
from pathlib import Path
from typing import Any, Dict, Callable
import re

from apiops_orchestrator.adapters.outbound.files_exporter.file_exporter_strategy import (
    FILE_EXPORTER_STRATEGIES,
)

from apiops_orchestrator.adapters.outbound.files_exporter.files_exporter_exceptions import (
    FileExporterException,
    UnmappedKindException,
)

from apiops_orchestrator.domain.ports.file_exporter_port import PathExporterPort
from apiops_orchestrator.domain.services.json_to_yaml_enum import JsonKind


class LocalFileExporterAdapter(PathExporterPort):
    def __init__(self, exporter_strategies: Dict[str, Callable[[Path], Any]] = None):
        self._exporter_strategies = exporter_strategies or FILE_EXPORTER_STRATEGIES
        self.logger = logging.getLogger(__name__)

    def export_path(self, content: Any, output_folder="output_yaml"):
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        self._export_yaml(output_folder, content)

    def _export_yaml(self, output_folder: Path, content: Any) -> Any:
        """Exports a YAML file."""
        self.logger.info(f"Criando arquivos na pasta: {output_folder}")

        for part in content:
            kind = part.get("kind")
            part_content = part.get("content")
            file_name = None

            # Determine filename based on kind
            if kind == JsonKind.API_BASIC_INFO.value:
                file_name = "api-basic-info.yaml"
                part_content = part
            elif kind == JsonKind.INTERCEPTORS.value:
                file_name = "default-interceptors.yaml"
                part_content = part
            elif kind == JsonKind.RESOURCES.value:
                file_name = "resources.yaml"
                part_content = part
            elif kind == JsonKind.API_OPERATIONS.value:
                method = part.get("method")
                path = part.get("path")
                file_name = self.generate_filename(method, path)
                part_content = part
            elif kind == JsonKind.ENVIRONMENT.value:
                file_name = "deployment.yaml"
                part_content = part
            else:
                self.logger.warning(f"O kind não está mapeado: {kind}.")
                raise UnmappedKindException(kind)

            full_path = Path(output_folder) / file_name
            try:
                exporter = self._exporter_strategies.get(".yaml")
                if exporter:
                    exporter(full_path, part_content)
                    self.logger.debug(f"Arquivo {file_name} criado")

            except Exception as e:
                self.logger.error(f"Erro ao criar arquivo {file_name}", exc_info=e)
                raise FileExporterException(str(full_path))

    @staticmethod
    def generate_filename(method: str, path: str) -> str:
        """
        Transforms path and method into file name
        """
        base_name = f"{str(method).lower()}{str(path).lower()}"
        clean_name = base_name.replace("/", "_")
        clean_name = re.sub(r'[<>:"\\|?*]', "", clean_name)
        # Removes duplicated underscores in beginning or end after concatenation
        clean_name = clean_name.strip("_")

        return f"{clean_name}.yaml"
