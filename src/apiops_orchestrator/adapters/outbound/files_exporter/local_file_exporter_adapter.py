import logging
import os
from pathlib import Path
from typing import Any, List, Dict, Callable
import re

from apiops_orchestrator.adapters.outbound.files_exporter.file_exporter_strategy import (
    FILE_EXPORTER_STRATEGIES,
    FileExportMessages,
)

from apiops_orchestrator.domain.ports.file_exporter_port import PathExporterPort

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
            kind = part.get('kind')
            part_content = part.get('content')
            file_name = None

            # Determine filename based on kind
            if kind == 'ApiBasicInfo':
                file_name = "api-basic-info.yaml"
                part_content = part
            elif kind == 'Interceptors':
                file_name = "default-interceptors.yaml"
                part_content = part
            elif kind == 'Resources':
                file_name = "resources.yaml"
                part_content = part
            elif kind == 'ApiOperations':
                method = part.get('method')
                path = part.get('path')
                file_name = self.generate_filename(method, path)
                part_content = part
            elif kind == 'Deployment':
                file_name = "deployment.yaml"
                part_content = part
            else:
                self.logger.warning(f"O kind não está mapeado: {kind}. Tentando o próximo.")
                continue

            full_path = Path(output_folder) / file_name
            try:
                exporter = self._exporter_strategies.get('.yaml')
                if exporter:
                    exporter(full_path, part_content)
                    self.logger.info(f"{file_name} criado")
                else:
                    self.logger.error("Estratégia de exportação YAML não encontrada")
            except Exception as e:
                self.logger.error(f"Erro ao criar arquivo {file_name}: {str(e)}")


    def generate_filename(self, method: str, path: str) -> str:
        """
        Transforms path and method into file name
        """
        base_name = f"{str(method).lower()}{str(path).lower()}"
        clean_name = base_name.replace('/', '_')
        clean_name = re.sub(r'[<>:"\\|?*]', '', clean_name)
        # Removes duplicated underscores in beginning or end after concatenation
        clean_name = clean_name.strip('_')

        return f"{clean_name}.yaml"