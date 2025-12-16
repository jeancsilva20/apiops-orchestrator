from pathlib import Path
from typing import Dict, List
import logging
from apiops_orchestrator.infrastructure.observability.logging import log_duration, set_span_id, clear_operation_context, set_status


class RepoValidator:
    def __init__(self, rules: Dict[str, List[str]]):
        """
        Example of rules:
        rules = {
          "Templates": ["api-basic-info.yaml", "default-interceptors.yaml"],
          "Resources": [],
          "Env-Variables": []
        }
        """
        self.rules = rules
        self.logger = logging.getLogger(__name__)

    def validate_artifact_struct(self, artifacts_folder: Path) -> None:
        errors = []
        set_span_id()
        self.logger.info(f"Validating folder: {artifacts_folder}")
        with log_duration(__name__):
            if not artifacts_folder.exists() or not artifacts_folder.is_dir():
                set_status("FAILURE")
                self.logger.error(f"Folder 'artifacts' not found.")
                raise ValueError(f"Folder 'artifacts' not found.")

            for folder, required_files in self.rules.items():
                folder_path = artifacts_folder / folder

                if not folder_path.exists() or not folder_path.is_dir():
                    set_status("FAILURE")
                    errors.append(f"Mandatory folder missing: {folder_path}")
                    continue

                for filename in required_files:
                    file_path = folder_path / filename
                    if not file_path.exists():
                        set_status("FAILURE")
                        errors.append(f"Mandatory file missing: {file_path}")

            if errors:
                raise ValueError(
                    "Artifact repository validation failed:\n" + "\n".join(errors)
                )


