import sys
from pathlib import Path
from typing import cast

import pydantic
import typer
from rich import print as rprint

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
from apiops_orchestrator.adapters.outbound.http.user_management_api.sensedia_authentication_adapter import (
    SensediaAuthenticationAdapter,
)
from apiops_orchestrator.application.services.admin_token_provider import (
    resolve_admin_token,
)
from apiops_orchestrator.application.services.api_listing_service import (
    ApiListingService,
)
from apiops_orchestrator.application.services.conversor_service import ConversorService
from apiops_orchestrator.application.services.login_service import LoginService
from apiops_orchestrator.application.services.repo_importer_service import (
    RepoImporterService,
)
from apiops_orchestrator.application.services.repo_validator import RepoValidator
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.application.services.schema_validator import SchemaValidator
from apiops_orchestrator.infrastructure.secure_storage.session_store import SessionStore


repo_path = Path(
    r"C:\Users\Sensedia\Downloads\Projetos\Nexus\apiops-orchestrator\apiops_newstruct"
)

revision = 1


def build_login_service_factory(settings: Settings):
    def factory() -> LoginService:
        return LoginService(
            auth_adapter=OrchestratorAuthAdapter(settings=settings, max_retries=3),
            session_store=SessionStore(directory=settings.PACKAGE_ROOT),
            settings=settings,
        )

    return factory


def build_listing_service_factory(settings: Settings):
    def factory() -> ApiListingService:
        manager_adapter = ManagerApiAdapter(
            token=resolve_admin_token(settings),
            base_path="/api-manager/api/v3/",
            max_retries=3,
            api_id=cast(int, settings.API_ID),
            settings=settings,
        )
        session = SessionStore(directory=settings.PACKAGE_ROOT).load()
        return ApiListingService(manager_adapter, session=session)

    return factory


def build_invoked_context(settings: Settings) -> dict:
    return {
        "login_service_factory": build_login_service_factory(settings),
        "api_listing_service_factory": build_listing_service_factory(settings),
    }


def validate_recursively(
    path: Path, importer, schema_validator, kind_to_schema: dict
) -> None:
    for item in path.iterdir():
        if item.is_dir():
            validate_recursively(item, importer, schema_validator, kind_to_schema)
        elif item.suffix in [".yaml", ".yml"]:
            try:
                data = importer.read(str(item))
                if not data:
                    continue
                kind = data.get("kind")
                if kind and kind in kind_to_schema:
                    schema_validator.validate(data, kind_to_schema[kind], item)
            except Exception as e:
                rprint(f"[bold yellow]Skipping/Error in {item.name}:[/bold yellow] {e}")


def run_bare_pipeline(settings: Settings) -> dict:
    """Runs the legacy pipeline flow (repository preprocessing + API composition), preserving historical behavior."""
    validator = RepoValidator(settings.NEW_STRUCTURE_VALIDATION_RULES)
    validator.validate_new_structure(repo_path)

    importer = LocalFileImporterAdapter()

    schema_folder = settings.PROJECT_ROOT / "src" / settings.ORCHEST_SCHEMA_FOLDER
    schema_validator = SchemaValidator(importer, schema_folder)

    catalog_path = schema_folder / "catalog.json"
    catalog_data = importer.read(str(catalog_path))
    kind_to_schema = (
        catalog_data.get("schemas", {}) if isinstance(catalog_data, dict) else {}
    )

    reader = RepoImporterService(settings, importer)
    result = reader.load_normalized_documents(str(repo_path), revision_number=revision)

    auth_adapter = SensediaAuthenticationAdapter(
        base_path="user-management/v1", max_retries=3, settings=settings
    )
    token = cast(str, auth_adapter.authenticate())

    manager_adapter = ManagerApiAdapter(
        token=token,
        base_path="/api-manager/api/v3/",
        max_retries=3,
        api_id=cast(int, settings.API_ID),
        settings=settings,
    )
    api_listing_service = ApiListingService(manager_adapter)

    rprint("[bold green]Starting Schema Validation...[/bold green]")
    validate_recursively(repo_path, importer, schema_validator, kind_to_schema)
    rprint("[bold green]Schema Validation completed successfully![/bold green]")

    service = ConversorService(result, settings, manager_adapter)
    api_full = service.build_api_json()
    rprint(api_full.model_dump_json(indent=4))

    return {
        "api_listing_service": api_listing_service,
        "login_service_factory": build_login_service_factory(settings),
        "api_listing_service_factory": build_listing_service_factory(settings),
    }


def main():
    """
    Composition Root: Orchestrates the instantiation of adapters and services,
    and injects them into the CLI adapter.

    Bare invocation (`python main.py`) runs the legacy pipeline flow as before.
    Invoked mode (`python main.py sen <cmd>`) skips the pipeline and boots the CLI only.
    """
    try:
        settings = Settings()  # type: ignore[call-arg]
        if len(sys.argv) > 1:
            ctx_obj = build_invoked_context(settings)
        else:
            ctx_obj = run_bare_pipeline(settings)

        app(obj=ctx_obj)

    except CliError as e:
        rprint(f"[bold red]Error:[/bold red] {e.message}")
        sys.exit(e.exit_code)
    except pydantic.ValidationError as e:
        missing = ", ".join(
            str(err.get("loc", ("<unknown>",))[0]).upper() for err in e.errors()
        )
        rprint(
            f"[bold red]Invalid configuration:[/bold red] missing/invalid settings: {missing}"
        )
        sys.exit(1)
    except typer.Exit as e:
        sys.exit(e.exit_code)
    except typer.Abort:
        rprint("[bold red]Aborted.[/bold red]")
        sys.exit(1)
    except Exception as e:
        rprint(f"[bold red]Unexpected error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
