from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Any
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

    # Auth da CLI (sen login) — obrigatórias, sem fallback/default
    SEN_CREDENTIALS: str | None = None
    AUTH_HOST: str
    AUTH_LOGIN_PATH: str

    # Rota de validação do accessToken do `.sen_session`: default = AUTH_LOGIN_PATH
    # + `/validation` (espelho do namespace do orq-auth). Override total aqui,
    # definindo AUTH_VALIDATE_PATH com o path absoluto (ex.: /cli-2/.../validation).
    AUTH_VALIDATE_PATH: str | None = None

    # --- Modo de execução e alvos (V-11 binding, V-24, D-12) -----------------
    # `local`    → CLI na máquina do dev; a régua vem de `spec.template` no
    #              manifesto, e a publicação exige confirmação (guarda 2, D-9).
    # `pipeline` → esteira; a régua vem de TEMPLATE_API_ID (cofre), fora do
    #              alcance de um commit, e não há confirmação interativa.
    # Ausente assume `local` (V-11 §4).
    EXECUTION_MODE: str = "local"

    # Id da API-régua. Só é lido em `pipeline`; em `local` a régua vem do
    # manifesto. Em `pipeline` SEM este valor a operação é falha de configuração
    # (exit 1): validar contra nada numa esteira é pior do que parar (V-11 §4).
    TEMPLATE_API_ID: int | None = None

    # Revisão alvo, pelo NÚMERO que o humano vê na UI — nunca pelo id, que é
    # detalhe de transporte resolvido no último instante (V-24). Só é lida na
    # esteira: fora dela o `sen validate` grava sempre na 1 (Draft) e o
    # `sen publish` não roda (V-24 §6). Sem default: na esteira o `sen publish`
    # precisa distinguir "ausente" de "1" (P-1), e cada comando decide o que a
    # ausência significa.
    TARGET_REVISION_NUMBER: int | None = None

    # Id, no Manager, do ambiente que recebe o `sen deploy`.
    TARGET_ENVIRONMENT_ID: int | None = None

    @field_validator("EXECUTION_MODE", mode="before")
    @classmethod
    def _normalizar_modo(cls, valor: Any) -> str:
        """Aceita só `local` e `pipeline`; ausente ou vazio assume `local` (V-11 §4)."""
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            return "local"
        modo = str(valor).strip().lower()
        if modo not in ("local", "pipeline"):
            raise ValueError(
                f"EXECUTION_MODE inválido: {valor!r}. Use 'local' ou 'pipeline'."
            )
        return modo

    @property
    def modo_pipeline(self) -> bool:
        """Verdadeiro quando o orquestrador roda na esteira."""
        return self.EXECUTION_MODE == "pipeline"

    # Use the previously defined PROJECT_ROOT.
    PROJECT_ROOT: Path = PROJECT_ROOT
    # Directory hosting the distributed package (holds `.sen` and `.sen_session`).
    PACKAGE_ROOT: Path = PACKAGE_ROOT
    # LEGADO: raiz do repositório para o `VersionerService`.
    API_REPO_FOLDER: Path = "./external-repo"

    # Pasta dos JSON schemas, relativa a `src/`.
    ORCHEST_SCHEMA_FOLDER: str = "apiops_orchestrator/domain/schemas"
