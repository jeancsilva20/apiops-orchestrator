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

    def validate_artifact_struct(self, repo_folder: str) -> None:
        errors = []

        repo_path = Path(repo_folder)
        artifacts_path = repo_path / "artifacts"

        if not repo_path.exists() or not repo_path.is_dir():
            raise ValueError(f"Pasta do repositório não encontrada: {repo_path}")

        if not artifacts_path.exists() or not artifacts_path.is_dir():
            raise ValueError(f"Pasta 'artifacts' não encontrada dentro de {repo_path}")

        for folder, required_files in self.rules.items():
            folder_path = artifacts_path / folder

            if not folder_path.exists() or not folder_path.is_dir():
                errors.append(f"Pasta obrigatória ausente: {folder_path}")
                continue

            for filename in required_files:
                file_path = folder_path / filename
                if not file_path.exists():
                    errors.append(f"Arquivo obrigatório ausente: {file_path}")

        if errors:
            raise ValueError("Validação do repositório falhou:\n" + "\n".join(errors))
