import yaml
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from apiops_orchestrator.config.settings import Settings


class NewStructureRepositoryReader:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)

    def load_normalized_documents(
        self, repo_path: Path, revision_number: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        # 1. Resolve revision
        if revision_number is None:
            revision_number = self._get_latest_revision(repo_path)

        self.logger.info(f"Loading revision {revision_number} from {repo_path}")

        documents = []

        # 0. Revision info (Top level)
        documents.append({
            "kind": "RevisionInfo",
            "revisionNumber": revision_number
        })

        # 2. ApiBasicInfo
        api_info_path = (
            repo_path / self.settings.API_REPO_API_INFO_FOLDER / "api-basic-info.yaml"
        )
        if api_info_path.exists():
            api_info = self._read_yaml(api_info_path)
            documents.append(self._normalize_api_basic_info(api_info, repo_path))

        # 3. Interceptors (from revision-flow.yaml)
        rev_path = (
            repo_path / self.settings.API_REPO_REVISIONS_FOLDER / str(revision_number)
        )
        rev_flow_path = rev_path / "revision-flow.yaml"
        if rev_flow_path.exists():
            rev_flow = self._read_yaml(rev_flow_path)
            documents.append(self._normalize_interceptors(rev_flow))

        # 4. Resources and Operations
        resources_list = self._synthesize_resources_list(rev_path)
        documents.append(resources_list)

        # 5. ApiOperations
        operations = self._read_all_operations(rev_path)
        documents.extend(operations)

        return documents

    def _get_latest_revision(self, repo_path: Path) -> int:
        revisions_dir = repo_path / self.settings.API_REPO_REVISIONS_FOLDER
        if not revisions_dir.exists():
            raise ValueError(f"Revisions directory not found: {revisions_dir}")

        revisions = []
        for d in revisions_dir.iterdir():
            if d.is_dir() and d.name.isdigit():
                revisions.append(int(d.name))

        if not revisions:
            raise ValueError(f"No numeric revisions found in {revisions_dir}")

        return max(revisions)

    def _read_yaml(self, path: Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _normalize_api_basic_info(self, data: Dict[str, Any], repo_path: Path) -> Dict[str, Any]:
        new_spec = {"api": data.get("spec", {})}
        # Remove fields that are not used by the script
        for field in ["id", "lastUpdate"]:
            if field in new_spec["api"]:
                del new_spec["api"][field]

        new_spec["api"]["revisions"] = []
        new_spec["api"]["lastRevision"] = {}

        return {
            "apiVersion": data.get("apiVersion"),
            "kind": "ApiBasicInfo",
            "spec": new_spec,
        }

    def _normalize_interceptors(self, data: Dict[str, Any]) -> Dict[str, Any]:
        interceptors = data.get("spec", {}).get("interceptors", [])
        return {
            "apiVersion": data.get("apiVersion"),
            "kind": "Interceptors",
            "spec": {"interceptors": interceptors},
        }

    def _synthesize_resources_list(self, revision_path: Path) -> Dict[str, Any]:
        resources_dir = revision_path / "resources"
        items = []
        api_version = "api-management.sensedia.com/v1"

        if resources_dir.exists():
            for res_dir in resources_dir.iterdir():
                if res_dir.is_dir():
                    res_file = res_dir / "resource.yaml"
                    if res_file.exists():
                        res_data = self._read_yaml(res_file)
                        api_version = res_data.get("apiVersion", api_version)

                        for item in res_data.get("items", []):
                            resource_name = item.get("name")
                            resource_description = item.get("description")

                            # Scan operations
                            ops_dir = res_dir / "operations"
                            ops_refs = []
                            if ops_dir.exists():
                                for op_file in ops_dir.glob("*.yaml"):
                                    op_data = self._read_yaml(op_file)

                                    for op in op_data.get("spec", {}).get(
                                        "operation", []
                                    ):
                                        ops_refs.append(
                                            {
                                                "method": op.get("method"),
                                                "path": op.get("path"),
                                                "file": f"{res_dir.name}/{op_file.name}",
                                            }
                                        )

                            items.append(
                                {
                                    "name": resource_name,
                                    "description": resource_description,
                                    "operations": ops_refs,
                                }
                            )

        return {
            "apiVersion": api_version,
            "kind": "ResourcesList",  # TODO, mudar para usar o enum.
            "items": items,
        }

    def _read_all_operations(self, revision_path: Path) -> List[Dict[str, Any]]:
        resources_dir = revision_path / "resources"
        operations = []

        if resources_dir.exists():
            for res_dir in resources_dir.iterdir():
                if res_dir.is_dir():
                    ops_dir = res_dir / "operations"
                    if ops_dir.exists():
                        for op_file in ops_dir.glob("*.yaml"):
                            op_data = self._read_yaml(op_file)
                            if "metadata" not in op_data:
                                op_data["metadata"] = {}
                            op_data["metadata"][
                                "fileName"
                            ] = f"{res_dir.name}/{op_file.name}"
                            operations.append(op_data)
        return operations
