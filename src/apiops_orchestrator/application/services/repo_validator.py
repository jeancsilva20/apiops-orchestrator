from pathlib import Path
from typing import Dict, List


class RepoValidator:
    def __init__(self, rules: Dict[str, List[str]]):
        """
        Exemplo de rules:
        rules = {
          "Templates": ["api-basic-info.yaml", "default-interceptors.yaml"],
          "Resources": [],
          "Env-Variables": []
        }
        """
        self.rules = rules

    def validate_artifact_struct(self, artifacts_folder: Path) -> None:
        errors = []

        if not artifacts_folder.exists() or not artifacts_folder.is_dir():
            raise ValueError(f"Folder 'artifacts' not found.")

        for folder, required_files in self.rules.items():
            folder_path = artifacts_folder / folder

            if not folder_path.exists() or not folder_path.is_dir():
                errors.append(f"Mandatory folder missing: {folder_path}")
                continue

            for filename in required_files:
                file_path = folder_path / filename
                if not file_path.exists():
                    errors.append(f"Mandatory file missing: {file_path}")

        if errors:
            raise ValueError(
                "Artifact repository validation failed:\n" + "\n".join(errors)
            )
