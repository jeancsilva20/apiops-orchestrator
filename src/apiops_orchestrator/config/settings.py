from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8')

    PROD_URL: str
    AUTHORIZATION: str
    REQUEST_TIMEOUT: int
    DEBUG: bool

    APIS_REPO_ARTIFACTS_PATH: str = "src/artifacts"  # onde o dev mexe
    APIS_REPO_REVISIONS_PATH: str = "src/apis/revisions"  # onde ficam as pastas 1,2,3...


settings = Settings()