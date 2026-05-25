import platform
import typer
from typing import Optional
from rich import print as rprint
from apiops_orchestrator.application.services.api_listing_service import (
    ApiListingService,
)
from apiops_orchestrator.adapters.outbound.http.manager_api.manager_api_adapter import (
    ManagerApiAdapter,
)
from apiops_orchestrator.adapters.outbound.http.user_management_api.sensedia_authentication_adapter import (
    SensediaAuthenticationAdapter,
)
from apiops_orchestrator.config.settings import Settings

app = typer.Typer(
    name="sen",
    help=" APIOps CLI - Framework GitOps to automate, standardize and manage your APIs.",
    no_args_is_help=True,
    add_completion=False,
)

api_app = typer.Typer(name="api", help="Manage APIs.")
app.add_typer(api_app)


class CliError(Exception):
    """Basic exception for friendly CLI errors."""

    def __init__(self, message: str, exit_code: int = 1):
        self.message = message
        self.exit_code = exit_code
        super().__init__(self.message)


@api_app.command("list")
def list_apis(
    ctx: typer.Context,
    api_id: Optional[int] = typer.Option(None, "--id", help="Filter by API ID."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show more details."),
):
    """
    List APIs from Sensedia Manager.
    """
    try:
        service: ApiListingService = ctx.obj.get("api_listing_service")
        if not service:
            rprint(
                "[bold red]Error:[/bold red] ApiListingService not found in context."
            )
            raise typer.Exit(code=1)

        apis = service.list_apis(api_id=api_id)

        if not apis:
            rprint("[yellow]No APIs found.[/yellow]")
            return

        if api_id is not None and verbose:
            # Header: id, name, basepath, description, environments, revisions
            rprint(
                "[bold cyan]id, name, basePath, description, environments count, revisions count[/bold cyan]"
            )
            for api in apis:
                env_count = len(api.get("environments", []))
                rev_count = len(api.get("revisions", []))
                rprint(
                    f"{api.get('id')}, {api.get('name')}, {api.get('basePath')}, {api.get('description')}, {env_count}, {rev_count}"
                )
        elif api_id is not None:
            # Header: id, name, basepath, description
            rprint("[bold cyan]id, name, basePath, description[/bold cyan]")
            for api in apis:
                rprint(
                    f"{api.get('id')}, {api.get('name')}, {api.get('basePath')}, {api.get('description')}"
                )
        elif verbose:
            # Header: id, name, basepath, version, description
            rprint("[bold cyan]id, name, basePath, version, description,[/bold cyan]")
            for api in apis:
                rprint(
                    f"{api.get('id')}, {api.get('name')}, {api.get('basePath')}, {api.get('version')}, {api.get('description')}"
                )
        else:
            # Header: id, name, basepath
            rprint("[bold cyan]id, name, basePath[/bold cyan]")
            for api in apis:
                rprint(f"{api.get('id')}, {api.get('name')}, {api.get('basePath')}")

    except Exception as e:
        if isinstance(e, typer.Exit):
            raise e
        rprint(f"[bold red]Error listing APIs:[/bold red] {e}")
        raise typer.Exit(code=1)


def display_version():
    rprint(f"sen 0.1.0")
    rprint(f"apiops-orchestrator 0.1.0")
    rprint(f"python {platform.python_version()}")


def version_callback(value: bool):
    if value:
        display_version()
        raise typer.Exit()


@app.callback()
def main_callback(
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Increases verbosity in logs."
    ),
    version: bool = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Shows CLI version.",
    ),
):
    """
    APIOps CLI Sensedia.
    """
    if verbose:
        # TODO: Ajustar nível de log quando houver integração com logging
        pass
