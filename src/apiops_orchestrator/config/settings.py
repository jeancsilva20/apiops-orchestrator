from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import List, Any
from apiops_orchestrator.domain.models.api_partial_model import ApiTag
import os
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
PACKAGE_ROOT = Path(__file__).resolve().parents[1]

dotenv_path = PROJECT_ROOT / ".env"
sen_path = PACKAGE_ROOT / ".sen"

# Credential/config sources precedence (high -> low):
#   process environment > .sen (package dir) > .env (repo root)
# Both files are merged into os.environ gap-fill style (load_dotenv never
# overrides existing values), keeping that exact order, so native secrets
# always win and the package-level .sen beats the repo-level .env.
load_dotenv(dotenv_path=sen_path, override=False)
load_dotenv(dotenv_path=dotenv_path, override=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(dotenv_path), str(sen_path)),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    HOST: str
    OAUTH_CLIENT_ID: str | None = None
    OAUTH_CLIENT_SECRET: str | None = None
    REQUEST_TIMEOUT: int

    # API Data
    API_ID: int

    # Auth da CLI (sen login) — obrigatórias, sem fallback/default
    SEN_CREDENTIALS: str | None = None
    AUTH_HOST: str
    AUTH_LOGIN_PATH: str

    # Rota de validação do accessToken do `.sen_session`: default = AUTH_LOGIN_PATH
    # + `/validation` (espelho do namespace do orq-auth). Override total aqui,
    # definindo AUTH_VALIDATE_PATH com o path absoluto (ex.: /cli-2/.../validation).
    AUTH_VALIDATE_PATH: str | None = None

    # Adaptive Governance Data
    WORKFLOW_ID: int | None = None
    WORKFLOW_STAGE_ID: int | None = None

    KIND_VERSION: str | None = None

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
    # Directory hosting the distributed package (holds `.sen` and `.sen_session`).
    PACKAGE_ROOT: Path = PACKAGE_ROOT
    API_REPO_FOLDER: Path = "./external-repo"
    PROJECT_SRC_DIR: Path = PROJECT_ROOT / "src"
    API_REPO_ARTIFACTS_PATH: str = (
        "artifacts"  # This is where the developer makes changes.
    )
    API_REPO_REVISIONS_PATH: str = (
        "src/api/revisions"  # This is where folders 1, 2, 3 etc… are located.
    )
    # New Layout Folders
    API_REPO_API_INFO_FOLDER: str = "api-info"
    API_REPO_ENVIRONMENTS_FOLDER: str = "environments"
    API_REPO_REVISIONS_FOLDER: str = "revisions"

    ORCHEST_SCHEMA_FOLDER: str = "apiops_orchestrator/domain/schemas"

    NEW_STRUCTURE_VALIDATION_RULES: dict = {
        "api-info": ["api-basic-info.yaml"],
        "environments": [],
        "revisions": [],
    }
