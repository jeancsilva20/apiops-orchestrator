from apiops_orchestrator.domain.ports.file_importer_port import PathLoaderPort
from pathlib import Path
import logging
from apiops_orchestrator.infrastructure.observability.logging import log_duration, set_span_id, clear_operation_context, set_status
from apiops_orchestrator.infrastructure.observability.logging_status_enum import Status


class FileImportService:
    def __init__(self, importer: PathLoaderPort):
        self.importer = importer
        self.logger = logging.getLogger(__name__)

    def load_file_path(self, path: Path):
        set_span_id()
        with log_duration(__name__):
            self.logger.debug("Loading path file")
            files = self.importer.load_path(path)
            self.logger.info(f"Found {len(files)} files in {path}")
            return files
