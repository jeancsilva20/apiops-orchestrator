import sys
import typer
from pathlib import Path
from rich import print as rprint
from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app, CliError
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    ManagerApiAdapter,
)
from apiops_orchestrator.adapters.outbound.http.user_management_api.sensedia_authentication_adapter import (
    SensediaAuthenticationAdapter,
)
from apiops_orchestrator.application.services.conversor_service import ConversorService
from apiops_orchestrator.application.services.new_structure_repository_reader import (
    NewStructureRepositoryReader,
)
from apiops_orchestrator.application.services.repo_validator import RepoValidator
from apiops_orchestrator.config.settings import Settings
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiPort


repo_path = Path(
    r"C:\Users\Sensedia\Downloads\Projetos\Nexus\apiops-orchestrator\apiops_newstruct"
)

revision = 1

settings = Settings()
validator = RepoValidator(settings.NEW_STRUCTURE_VALIDATION_RULES)
validator.validate_new_structure(repo_path)

reader = NewStructureRepositoryReader(settings)
result = reader.load_normalized_documents(repo_path, revision_number=revision)

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

service = ConversorService(result, settings, manager_adapter)
api_full = service.build_api_json()
rprint(api_full.model_dump_json(indent=4))


def main():
    try:
        app()
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
