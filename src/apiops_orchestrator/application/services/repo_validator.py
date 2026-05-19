from pathlib import Path
from typing import Dict, List
import logging
from apiops_orchestrator.infrastructure.observability.logging import (
    log_duration,
    set_span_id,
    clear_operation_context,
    set_status,
)


class RepoValidator:
    def __init__(self, rules: Dict[str, List[str]]):
        self.rules = rules
        self.logger = logging.getLogger(__name__)

    def validate_new_structure(self, repo_path: Path) -> None:
        errors = []
        set_span_id()
        self.logger.info(f"Validating folder (new structure): {repo_path}")
        with log_duration(__name__):
            if not repo_path.exists() or not repo_path.is_dir():
                set_status("FAILURE")
                self.logger.error(f"Repository folder not found: {repo_path}")
                raise ValueError(f"Repository folder not found: {repo_path}")

            for folder, required_files in self.rules.items():
                folder_path = repo_path / folder

                if not folder_path.exists() or not folder_path.is_dir():
                    set_status("FAILURE")
                    errors.append(f"Mandatory folder missing: {folder_path}")
                    continue

                for filename in required_files:
                    file_path = folder_path / filename
                    if not file_path.exists():
                        set_status("FAILURE")
                        errors.append(f"Mandatory file missing: {file_path}")

            # Validate revisions
            revisions_dir = repo_path / "revisions"
            if not revisions_dir.exists() or not revisions_dir.is_dir():
                set_status("FAILURE")
                errors.append(f"Mandatory folder missing: {revisions_dir}")
            else:
                # Check for at least one numeric revision
                revisions = [
                    d
                    for d in revisions_dir.iterdir()
                    if d.is_dir() and d.name.isdigit()
                ]
                if not revisions:
                    set_status("FAILURE")
                    errors.append("No numeric revisions found in 'revisions' folder.")
                else:
                    # Validate each revision basic structure
                    for rev in revisions:
                        if not (rev / "revision.yaml").exists():
                            errors.append(
                                f"Mandatory file missing in revision {rev.name}: revision.yaml"
                            )
                        if not (rev / "revision-flow.yaml").exists():
                            errors.append(
                                f"Mandatory file missing in revision {rev.name}: revision-flow.yaml"
                            )

                        # Resources validation
                        resources_dir = rev / "resources"
                        if not resources_dir.exists():
                            errors.append(
                                f"Mandatory folder missing in revision {rev.name}: resources"
                            )
                        else:
                            for res_dir in resources_dir.iterdir():
                                if res_dir.is_dir():
                                    if not (res_dir / "resource.yaml").exists():
                                        errors.append(
                                            f"Mandatory file missing in resource {res_dir.name} in revision {rev.name}: resource.yaml"
                                        )
                                    
                                    ops_dir = res_dir / "operations"
                                    if not ops_dir.exists() or not ops_dir.is_dir():
                                        errors.append(
                                            f"Mandatory folder missing in resource {res_dir.name} in revision {rev.name}: operations"
                                        )
                                    else:
                                        # Check for at least one operation file
                                        ops_files = list(ops_dir.glob("*.yaml"))
                                        if not ops_files:
                                            errors.append(
                                                f"Resource {res_dir.name} in revision {rev.name} must contain at least one operation (.yaml file) in 'operations' folder."
                                            )

            if errors:
                raise ValueError(
                    "Repository validation (new structure) failed:\n"
                    + "\n".join(errors)
                )
