from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import List, Any
from apiops_orchestrator.domain.models.api_partial_model import ApiTag
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    PROD_URL: str
    AUTHORIZATION: str
    REQUEST_TIMEOUT: int

    # Dados da API
    API_ID: str

    # Dados do Adaptive Governance
    WORKFLOW_ID: str | None = None
    WORKFLOW_STAGE_ID: str | None = None

    api_tags: List[ApiTag] = []

    def model_post_init(self, __context: Any):
        """Carrega todas as variáveis API_TAGS_* e converte em objetos ApiTag"""
        tags: List[ApiTag] = []

        for key, value in os.environ.items():
            if key.startswith("API_TAGS_") and value:
                parts = value.split(":", 1)
                if len(parts) == 2:
                    attr, tags_str = parts
                    tags_list = [t.strip() for t in tags_str.split(",") if t.strip()]
                    tags.append(ApiTag(attributeName=attr.strip(), tags=tags_list))

        self.api_tags = tags

    # Paths não podem começar com /, pois isso as torna Paths literais, e queremos usar Paths relativas.
    PROJECT_ROOT: Path = Path(__file__).parent.parent.parent
    API_REPO_ARTIFACTS_PATH: str = "artifacts"  # onde o dev mexe
    API_REPO_REVISIONS_PATH: str = "src/api/revisions"  # onde ficam as pastas 1,2,3...
    ORCHEST_SCHEMA_FOLDER: str = "apiops_orchestrator/domain/schemas"

    ARTIFACTS_FILE_FOLDER_VALIDATION_RULES: dict = {
        "Templates": [
            "api-basic-info.yaml",
            "default-interceptors.yaml",
        ],
        "Resources": [],
        "Env-Variables": [],
    }


settings = Settings()
