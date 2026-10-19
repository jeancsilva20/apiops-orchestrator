from pydantic import field_validator
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
    #
    # DEPRECADAS (D-020, 2026-10-15): o stage do Adaptive Governance é PROPRIEDADE
    # DA REVISÃO, pré-configurada na plataforma. O orquestrador lê `workflowId` e
    # `workflowStageId` do `GET /revisions/{id}` da revisão alvo e os reenvia
    # intactos — nunca os configura, infere ou avança. Configurá-los aqui foi o que
    # a D-020 proibiu: o valor varia por API e por ambiente, e o CLI não precisa
    # conhecê-lo de antemão.
    #
    # Mantidas apenas porque o pipeline LEGADO (`ConversorService`) ainda as
    # consome; saem quando a fase 3 da change `add-sen-validate` substituir o
    # publisher. Nenhum código novo deve lê-las.
    WORKFLOW_ID: int | None = None
    WORKFLOW_STAGE_ID: int | None = None

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

    # Revisão alvo do publish, pelo NÚMERO que o humano vê na UI — nunca pelo id,
    # que é detalhe de transporte resolvido no último instante (V-24). Em modo
    # `local` o único valor aceito é 1 (Draft), que não é ambiente e não tem
    # deploy: publicar nela é diagnóstico, não promoção. Sem default: em
    # `pipeline` o `sen publish` precisa distinguir "ausente" de "1" (P-1), e
    # cada comando decide o que a ausência significa.
    TARGET_REVISION_NUMBER: int | None = None

    # Id, no Manager, do ambiente que recebe o `sen deploy`.
    TARGET_ENVIRONMENT_ID: int | None = None

    KIND_VERSION: str | None = None

    # DEPRECADA (fila de templates/schemas, item 10): os `apiTags` são fonte
    # DECLARATIVA e vêm do `api-basic-info.yaml`, não de variáveis `API_TAGS_*`.
    # É sobre eles que o Adaptive Governance calcula o faltante no PUT da revision,
    # então lê-los do ambiente colocaria governança fora do versionamento.
    # Mantida enquanto o `ConversorService` legado a consumir.
    api_tags: List[ApiTag] = []

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
