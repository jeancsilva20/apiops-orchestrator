import yaml
from pathlib import Path
from typing import Dict, Any, List
from apiops_orchestrator.domain.ports.local_file_importer_port import LocalFileImporterPort

class LocalFileImporterAdapter(LocalFileImporterPort):
    def read(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def exists(self, path: str) -> bool:
        return Path(path).exists()

    def list_directories(self, path: str) -> List[str]:
        p = Path(path)
        if not p.exists():
            return []
        return [str(d) for d in p.iterdir() if d.is_dir()]

    def glob_files(self, path: str, pattern: str) -> List[str]:
        p = Path(path)
        if not p.exists():
            return []
        return [str(f) for f in p.glob(pattern)]
