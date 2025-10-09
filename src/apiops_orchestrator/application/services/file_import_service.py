from apiops_orchestrator.domain.ports.file_importer_port import PathLoaderPort
from pathlib import Path


class FileImportService:
    def __init__(self, importer: PathLoaderPort):
        self.importer = importer

    def load_file_path(self, path: Path):
        return self.importer.load_path(path)
