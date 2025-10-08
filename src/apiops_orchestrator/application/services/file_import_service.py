from apiops_orchestrator.domain.ports.file_importer_port import FileLoaderPort
from pathlib import Path


class FileImportService:
    def __init__(self, importer: FileLoaderPort):
        self.importer = importer

    def load_file_path(self, path: Path):
        return self.importer.load_file_path(path)
