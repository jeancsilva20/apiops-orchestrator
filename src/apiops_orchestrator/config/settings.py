from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import List, Any
from apiops_orchestrator.domain.models.api_partial_model import ApiTag
import os
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent

dotenv_path = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=dotenv_path)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(dotenv_path), env_file_encoding="utf-8"
    )

    HOST: str
    AUTHORIZATION: str
    OAUTH_CLIENT_ID: str
    OAUTH_CLIENT_SECRET: str
    REQUEST_TIMEOUT: int

    # API Data
    API_ID: str

    # Adaptive Governance Data
    WORKFLOW_ID: str | None = None
    WORKFLOW_STAGE_ID: str | None = None

    api_tags: List[ApiTag] = []

    def model_post_init(self, __context: Any):
        """Loads all API_TAGS_* variables and converts them into ApiTag objects."""
        tags: List[ApiTag] = []

        for key, value in os.environ.items():
            if key.startswith("API_TAGS_") and value:
                parts = value.split(":", 1)
                if len(parts) == 2:
                    attr, tags_str = parts
                    tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
                    tags.append(ApiTag(attributeName=attr.strip(), tags=tags_list))

        self.api_tags = tags

    # Use the previously defined PROJECT_ROOT.
    PROJECT_ROOT: Path = PROJECT_ROOT
    API_REPO_FOLDER: Path = "./external-repo"
    PROJECT_SRC_DIR: Path = PROJECT_ROOT / "src"
    API_REPO_ARTIFACTS_PATH: str = (
        "artifacts"  # This is where the developer makes changes.
    )
    API_REPO_REVISIONS_PATH: str = (
        "src/api/revisions"  # This is where folders 1, 2, 3 etc… are located.
    )
    ORCHEST_SCHEMA_FOLDER: str = "apiops_orchestrator/domain/schemas"

    ARTIFACTS_FILE_FOLDER_VALIDATION_RULES: dict = {
        "Templates": [
            "api-basic-info.yaml",
            "default-interceptors.yaml",
        ],
        "Resources": [],
        "Env-Variables": [],
    }