from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    PROD_URL: str
    AUTHORIZATION: str
    REQUEST_TIMEOUT: int
    DEBUG: bool
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
