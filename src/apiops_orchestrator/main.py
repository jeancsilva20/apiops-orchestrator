import sys
from pathlib import Path

import typer
from rich import print as rprint

from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app, CliError
from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
    LocalFileImporterAdapter,
)
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    ManagerApiAdapter,
)
from apiops_orchestrator.adapters.outbound.http.user_management_api.sensedia_authentication_adapter import (
    SensediaAuthenticationAdapter,
)
from apiops_orchestrator.application.services.api_listing_service import (
    ApiListingService,
)
from apiops_orchestrator.application.services.conversor_service import ConversorService
from apiops_orchestrator.application.services.repo_importer_service import (
    RepoImporterService,
)
from apiops_orchestrator.application.services.repo_validator import RepoValidator
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.application.services.schema_validator import SchemaValidator


repo_path = Path(
    r"C:\Users\Sensedia\Downloads\Projetos\Nexus\apiops-orchestrator\apiops_newstruct"
)

revision = 1

settings = Settings()
validator = RepoValidator(settings.NEW_STRUCTURE_VALIDATION_RULES)
validator.validate_new_structure(repo_path)

importer = LocalFileImporterAdapter()

# --- Schema Validation ---
schema_folder = settings.PROJECT_ROOT / "src" / settings.ORCHEST_SCHEMA_FOLDER
schema_validator = SchemaValidator(importer, schema_folder)

catalog_path = schema_folder / "catalog.json"
# Using LocalFileImporterAdapter to read catalog.json (which is JSON)
# Note: read() uses yaml.safe_load which works for JSON too
catalog_data = importer.read(str(catalog_path))
kind_to_schema = catalog_data.get("schemas", {})


def validate_recursively(path: Path):
    for item in path.iterdir():
        if item.is_dir():
            validate_recursively(item)
        elif item.suffix in [".yaml", ".yml"]:
            try:
                data = importer.read(str(item))
                if not data:
                    continue
                kind = data.get("kind")
                if kind and kind in kind_to_schema:
                    schema_name = kind_to_schema[kind]
                    rprint(
                        f"[bold blue]Validating:[/bold blue] {item.relative_to(repo_path)} (Kind: {kind})"
                    )
                    schema_validator.validate(data, schema_name, item)
            except Exception as e:
                rprint(f"[bold yellow]Skipping/Error in {item.name}:[/bold yellow] {e}")


reader = RepoImporterService(settings, importer)
result = reader.load_normalized_documents(str(repo_path), revision_number=revision)

auth_adapter = SensediaAuthenticationAdapter(
    base_path="user-management/v1", max_retries=3, settings=settings
)
token = auth_adapter.authenticate()

manager_adapter = ManagerApiAdapter(
    token=token,
    base_path="/api-manager/api/v3/",
    max_retries=3,
    api_id=settings.API_ID,
    settings=settings,
)

rprint("[bold green]Starting Schema Validation...[/bold green]")
validate_recursively(repo_path)
rprint("[bold green]Schema Validation completed successfully![/bold green]")
service = ConversorService(result, settings, manager_adapter)
api_full = service.build_api_json()
rprint(api_full.model_dump_json(indent=4))


def main():
    """
    Composition Root: Orchestrates the instantiation of adapters and services,
    and injects them into the CLI adapter.
    """
    try:
        # 1. Initialize Application Services
        api_listing_service = ApiListingService(manager_adapter)

        # 2. Inject Services into CLI Context and Run
        # Typer allows passing an object (obj) that will be available in the Context (ctx.obj)
        app(obj={"api_listing_service": api_listing_service})

    except CliError as e:
        rprint(f"[bold red]Error:[/bold red] {e.message}")
        sys.exit(e.exit_code)
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
