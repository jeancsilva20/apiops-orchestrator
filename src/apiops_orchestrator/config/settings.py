from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APIS_REPO_ARTIFACTS_PATH: str = "src/artifacts"  # onde o dev mexe
    APIS_REPO_REVISIONS_PATH: str = (
        "src/apis/revisions"  # onde ficam as pastas 1,2,3...
    )

    ARTIFACTS_FILE_FOLDER_VALIDATION_RULES: dict = {
        "Templates": [
            "basic-api-info.yaml",
            "default-interceptors.yaml",
        ],
        "Resources": [],
        "Env-Variables": [],
    }


model_config = SettingsConfigDict(
    env_prefix="APIOPS_",
    env_file=".env",
    extra="ignore",
)

settings = Settings()
