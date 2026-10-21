import logging
import sys
from pathlib import Path

import pydantic
import typer
from rich import print as rprint
from rich.markup import escape

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app, CliError
from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    ManagerApiAdapter,
)
from apiops_orchestrator.adapters.outbound.http.orchestrator_auth_api.orchestrator_auth_adapter import (
    OrchestratorAuthAdapter,
)
from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    INTERNAL_ERROR_MESSAGE,
)
from apiops_orchestrator.application.services.admin_token_provider import (
    AdminTokenProvider,
)
from apiops_orchestrator.application.services.api_listing_service import (
    ApiListingService,
)
from apiops_orchestrator.application.services.deploy_service import DeployService
from apiops_orchestrator.application.services.publish_service import PublishService
from apiops_orchestrator.application.services.regua_service import ReguaService
from apiops_orchestrator.application.services.validate_service import (
    ValidateService,
)
from apiops_orchestrator.application.services.completeness_service import (
    CompletenessService,
)
from apiops_orchestrator.application.services.login_service import LoginService
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.infrastructure.secure_storage.session_store import SessionStore


logger = logging.getLogger(__name__)

_PACKAGE_LOGGER = "apiops_orchestrator"


def _mute_unconfigured_logging() -> None:
    """Impede que logs internos vazem para o terminal via `logging.lastResort`."""
    package_logger = logging.getLogger(_PACKAGE_LOGGER)
    if not any(isinstance(h, logging.NullHandler) for h in package_logger.handlers):
        package_logger.addHandler(logging.NullHandler())


def _load_settings() -> Settings:
    """Carregamento lazy de configuração (ADR 0006).

    ValidationError é traduzido em CliError educativa (D1-b): curta, lista as
    chaves ausentes, aponta .env/.sen e o sub-help — sem stacktrace/segredos.
    """
    try:
        return Settings()  # type: ignore[call-arg]
    except pydantic.ValidationError as e:
        missing = ", ".join(
            str(err.get("loc", ("<unknown>",))[0]).upper() for err in e.errors()
        )
        raise CliError(
            f"Configuração incompleta (ausente/inválida): {missing}. "
            "Defina as variáveis no .env do repositório ou no .sen do diretório "
            "do pacote. Detalhes: consulte o sub-help do comando "
            "(ex.: sen list api --help).",
            exit_code=1,
        ) from e


def _build_session_store(settings: Settings) -> SessionStore:
    """Única fábrica de `SessionStore` (evita stores divergentes: um dia cada
    factory apontar um diretório diferente é bug silencioso de sessão)."""
    return SessionStore(directory=settings.PACKAGE_ROOT)


def build_login_service_factory():
    def factory() -> LoginService:
        settings = _load_settings()
        return LoginService(
            auth_adapter=OrchestratorAuthAdapter(settings=settings, max_retries=3),
            session_store=_build_session_store(settings),
            settings=settings,
        )

    return factory


def _build_admin_token(settings: Settings) -> str:
    """Montagem concreta (composition root): adapter + store + provider.

    Aqui É o lugar da instância concreta — a application recebe apenas ports.
    """
    provider = AdminTokenProvider(
        auth_adapter=OrchestratorAuthAdapter(settings=settings, max_retries=3),
        settings=settings,
        session_store=_build_session_store(settings),
    )
    return provider.obtain()


def build_listing_service_factory():
    def factory() -> ApiListingService:
        settings = _load_settings()
        manager_adapter = ManagerApiAdapter(
            token=_build_admin_token(settings),
            base_path="/api-manager/api/v3/",
            max_retries=3,
            settings=settings,
        )
        session = _build_session_store(settings).load()
        return ApiListingService(manager_adapter, session=session)

    return factory


def build_completeness_service_factory():
    def factory() -> CompletenessService:
        settings = _load_settings()
        manager_adapter = ManagerApiAdapter(
            token=_build_admin_token(settings),
            base_path="/api-manager/api/v3/",
            max_retries=3,
            settings=settings,
        )
        session = _build_session_store(settings).load()
        return CompletenessService(manager_adapter, session=session)

    return factory


def build_validate_service_factory():
    """Factory do `sen validate`, montada preguiçosamente.

    `Settings` só é lida quando o comando roda — assim `sen --help` e os demais
    comandos não exigem configuração do `validate`.
    """

    def factory() -> ValidateService:
        settings = _load_settings()
        manager_adapter = ManagerApiAdapter(
            token=_build_admin_token(settings),
            base_path="/api-manager/api/v3/",
            max_retries=3,
            settings=settings,
        )
        session = _build_session_store(settings).load()
        return ValidateService(
            manager_api=manager_adapter,
            importer=LocalFileImporterAdapter(),
            settings=settings,
            session=session,
        )

    return factory


def build_publish_service_factory():
    """Factory do `sen publish`, montada preguiçosamente como a do `validate`."""

    def factory() -> PublishService:
        settings = _load_settings()
        manager_adapter = ManagerApiAdapter(
            token=_build_admin_token(settings),
            base_path="/api-manager/api/v3/",
            max_retries=3,
            settings=settings,
        )
        return PublishService(
            manager_api=manager_adapter,
            importer=LocalFileImporterAdapter(),
            settings=settings,
        )

    return factory


def build_deploy_service_factory():
    """Factory do `sen deploy`, montada preguiçosamente como a do `publish`."""

    def factory() -> DeployService:
        settings = _load_settings()
        manager_adapter = ManagerApiAdapter(
            token=_build_admin_token(settings),
            base_path="/api-manager/api/v3/",
            max_retries=3,
            settings=settings,
        )
        return DeployService(
            manager_api=manager_adapter,
            importer=LocalFileImporterAdapter(),
            settings=settings,
        )

    return factory


def build_manager_api_factory():
    """Adapter do Manager + settings, para os diagnósticos somente leitura."""

    def factory():
        settings = _load_settings()
        return (
            ManagerApiAdapter(
                token=_build_admin_token(settings),
                base_path="/api-manager/api/v3/",
                max_retries=3,
                settings=settings,
            ),
            settings,
        )

    return factory


def build_regua_service_factory():
    """Factory do serviço de régua, usada pelo diagnóstico `sen diag template`."""

    def factory() -> ReguaService:
        settings = _load_settings()
        manager_adapter = ManagerApiAdapter(
            token=_build_admin_token(settings),
            base_path="/api-manager/api/v3/",
            max_retries=3,
            settings=settings,
        )
        return ReguaService(manager_api=manager_adapter, settings=settings)

    return factory


def main():
    """
    Composition Root lazy (ADR 0006): monta factories preguiçosas de serviços;
    `Settings` só é instanciada quando o comando invocado realmente consome
    configuração — `--help`/`--version` respondem sem nenhum `.env`/`.sen`
    (D1-a). Sem argumentos, mostra o help do `sen`.
    """
    _mute_unconfigured_logging()
    try:
        is_console_script = Path(sys.argv[0]).stem.lower() == "sen"
        if len(sys.argv) <= 1:
            sys.argv[1:] = ["sen"]
        # O console-script `sen` chega com argv[0]="...sen(.cmd)" e o primeiro
        # argumento já é o comando (ex.: "login") — a árvore Typer espera o
        # token "sen" na frente, presente só na forma `python main.py sen ...`.
        elif is_console_script and sys.argv[1] != "sen":
            sys.argv.insert(1, "sen")
        # Sem prog_name vazio, o Usage do console-script sairia "sen sen ...".
        prog_name = "" if is_console_script else None
        ctx_obj = {
            "login_service_factory": build_login_service_factory(),
            "api_listing_service_factory": build_listing_service_factory(),
            "completeness_service_factory": build_completeness_service_factory(),
            "validate_service_factory": build_validate_service_factory(),
            "publish_service_factory": build_publish_service_factory(),
            "deploy_service_factory": build_deploy_service_factory(),
            "regua_service_factory": build_regua_service_factory(),
            "manager_api_factory": build_manager_api_factory(),
        }
        app(obj=ctx_obj, prog_name=prog_name)

    except CliError as e:
        rprint(f"[bold red]Erro:[/bold red] {escape(e.message)}")
        sys.exit(e.exit_code)
    except pydantic.ValidationError as e:
        missing = ", ".join(
            str(err.get("loc", ("<unknown>",))[0]).upper() for err in e.errors()
        )
        rprint(
            f"[bold red]Configuração inválida:[/bold red] variáveis ausentes ou inválidas: {missing}"
        )
        sys.exit(1)
    except typer.Exit as e:
        sys.exit(e.exit_code)
    except typer.Abort:
        rprint("[bold red]Operação abortada.[/bold red]")
        sys.exit(1)
    except Exception as e:
        # Same rule as the commands' fallback: raw exception text never reaches
        # the user; INFO because WARNING+ would leak via logging.lastResort.
        logger.info("cli.unexpected_error type=%s", type(e).__name__, exc_info=e)
        rprint(f"[bold red]Erro:[/bold red] {INTERNAL_ERROR_MESSAGE}")
        sys.exit(1)


if __name__ == "__main__":
    main()
