from pathlib import Path
from typing import Dict, List


class RepoValidator:
    def __init__(self, rules: Dict[str, List[str]]):
        """
        Exemplo de rules:
        rules = {
          "Templates": ["basic info.yaml", "default interceptors.yaml"],
          "Resources": [],
          "Env-Variables": []
        }
        """
        self.rules = rules

    def validate_artifact_struct(self, artifacts_path: Path) -> None:
        errors = []

        if not artifacts_path.exists():
            raise ValueError(f"Pasta artifacts não encontrada: {artifacts_path}")

        for folder, required_files in self.rules.items():
            folder_path = artifacts_path / folder

            # Validar se pasta existe
            if not folder_path.exists() or not folder_path.is_dir():
                errors.append(f"Pasta obrigatória ausente: {folder_path}")
                continue

            # Validar arquivos obrigatórios
            for filename in required_files:
                file_path = folder_path / filename
                if not file_path.exists():
                    errors.append(f"Arquivo obrigatório ausente: {file_path}")

        if errors:
            raise ValueError("Validação do repositório falhou:\n" + "\n".join(errors))
