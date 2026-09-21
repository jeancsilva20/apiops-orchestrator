import platform
import typer
from typing import Any, Callable, Optional, cast
from rich import print as rprint
from apiops_orchestrator.application.services.api_listing_service import (
    ApiListingService,
)
from apiops_orchestrator.adapters.inbound.cli.output_format import OutputFormat
from apiops_orchestrator.adapters.inbound.cli.output_display import display_output
from apiops_orchestrator.application.exceptions.login_exceptions import LoginError
from apiops_orchestrator.domain.models.api_collection_model import (
    ApiCollectionError,
    last_revision_number,
    life_cycle_of,
)

main_app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
)

sen_app = typer.Typer(
    name="sen",
    help="APIOps CLI - Framework GitOps to automate, standardize and manage your APIs.",
    no_args_is_help=True,
)

list_app = typer.Typer(name="list", help="List resources.")
sen_app.add_typer(list_app)

main_app.add_typer(sen_app)

app = main_app


class CliError(Exception):
    """Basic exception for friendly CLI errors."""

    def __init__(self, message: str, exit_code: int = 1):
        self.message = message
        self.exit_code = exit_code
        super().__init__(self.message)


@sen_app.command("login")
def login(ctx: typer.Context):
    """
    Authenticate against the Orchestrator Auth API and store the local session.
    Requires the SEN_CREDENTIALS environment variable (Base64 of client_id:secret).
    """
    try:
        login_service_factory = (ctx.obj or {}).get("login_service_factory")
        if not callable(login_service_factory):
            rprint("[bold red]Error:[/bold red] LoginService not found in context.")
            raise typer.Exit(code=1)

        service_builder = cast(Callable[[], Any], login_service_factory)
        session = service_builder().login()
    except LoginError as e:
        rprint(f"[bold red]Login error:[/bold red] {e.message}")
        raise typer.Exit(code=e.exit_code)
    except typer.Exit as e:
        raise e

    expires_at = (
        session.expiresAt.strftime("%d/%m/%Y %H:%M UTC") if session.expiresAt else "-"
    )
    rprint("[bold green]Login realizado com sucesso.[/bold green]")
    if session.is_super_admin:
        # Privileged flow: show profile/scope only; no identity, no tokens.
        rprint(f"Perfil: {session.profile} | Escopo: {session.scope}")
        return
    rprint(f"Usuário: {session.userName} ({session.userEmail})")
    rprint(f"Sessão expira em: {expires_at}")


LIST_HEADER = ("ID", "NAME", "VERSION", "BASE PATH", "LAST REV", "LIFE CYCLE")
DEFAULT_WINDOW_LIMIT = 10
DEFAULT_WINDOW_OFFSET = 0


def _listing_cells(api: dict) -> tuple:
    return (
        str(api.get("id", "")),
        str(api.get("name", "")),
        str(api.get("version", "") or "-"),
        str(api.get("basePath", "") or ""),
        str(last_revision_number(api) or "-"),
        str(life_cycle_of(api) or "-"),
    )


def _render_grade(cells_rows) -> None:
    """Grade alinhada estilo monospace (A3/C2): colunas alinhadas à esquerda."""
    widths = [len(col) for col in LIST_HEADER]
    flat_rows = [LIST_HEADER] + [
        (cells if isinstance(cells, tuple) else tuple(cells))
        for cells in cells_rows
    ]
    for row in flat_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    rprint("[bold cyan]" + "  ".join(
        LIST_HEADER[i].ljust(widths[i]) for i in range(len(LIST_HEADER))
    ) + "[/bold cyan]")
    for row in cells_rows:
        values = row if isinstance(row, tuple) else tuple(row)
        rprint("  ".join(
            values[i].ljust(widths[i]) for i in range(len(LIST_HEADER))
        ))


def _window_footer(limit_value: Optional[int], offset_value: Optional[int]) -> None:
    shown_limit = (
        limit_value if limit_value is not None else DEFAULT_WINDOW_LIMIT
    )
    shown_offset = (
        offset_value if offset_value is not None else DEFAULT_WINDOW_OFFSET
    )
    if limit_value is None and offset_value is None:
        rprint(
            f"[dim]usando padrões: --limit {shown_limit} "
            f"--offset {shown_offset}  ->  detalhes: sen list api --help[/dim]"
        )
    else:
        rprint(
            f"[dim]janela: --limit {shown_limit} "
            f"--offset {shown_offset}[/dim]"
        )


@list_app.command("api")
def list_apis(
    ctx: typer.Context,
    api_id: Optional[int] = typer.Option(None, "--id", help="Filter by API ID."),
    query: Optional[str] = typer.Option(
        None, "--query", help="Client-side search on name/description."
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Page size."),
    offset: Optional[int] = typer.Option(None, "--offset", help="Offset from start."),
    revisions: bool = typer.Option(
        False, "--revisions", "-r", help="Show revisions drill-down (incoming slice)."
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TEXT, "--output", "-o", help="Output format (text, json, yaml)."
    ),
):
    """
    List APIs from Sensedia Manager.
    """
    try:
        service: Optional[ApiListingService] = (ctx.obj or {}).get(
            "api_listing_service"
        )
        if not service:
            service_factory = (ctx.obj or {}).get("api_listing_service_factory")
            if callable(service_factory):
                service = cast(Callable[[], ApiListingService], service_factory)()
        if not service:
            rprint(
                "[bold red]Error:[/bold red] ApiListingService not found in context."
            )
            raise typer.Exit(code=1)

        # Validações pré-rede (A3-3, A3-1)
        if query and api_id is not None:
            rprint(
                "[bold red]Error:[/bold red] Use --query OU --id, nunca os dois "
                "juntos. Consulte: sen list api --help"
            )
            raise typer.Exit(code=1)
        if limit is not None and limit <= 0:
            rprint(
                "[bold red]Error:[/bold red] --limit deve ser maior que zero. "
                "Consulte: sen list api --help"
            )
            raise typer.Exit(code=1)
        if offset is not None and offset < 0:
            rprint(
                "[bold red]Error:[/bold red] --offset deve ser maior ou igual a "
                "zero. Consulte: sen list api --help"
            )
            raise typer.Exit(code=1)
        if revisions and api_id is None:
            rprint(
                "[yellow]Nota:[/yellow] drill-down de revisões (--revisions/-r) "
                "chega em fatia posterior — exibindo cabeçalho por ora."
            )

        if api_id is not None:
            apis = service.list_apis(api_id=api_id)
        else:
            # Caso desnudo envia os defaults AO PIPELINE (A3-2): a janela
            # client-side so eh real se os valores alcancarem o window().
            apis = service.list_apis(
                query=query,
                offset=offset if offset is not None else DEFAULT_WINDOW_OFFSET,
                limit=limit if limit is not None else DEFAULT_WINDOW_LIMIT,
            )

        if not apis:
            rprint("[yellow]No APIs found.[/yellow]")
            return

        if revisions and api_id is None:
            for api in apis[:1]:
                rprint(f"hint: use sen list api --id {api.get('id')} --revisions")
            raise typer.Exit(code=0)

        def print_text():
            _render_grade([_listing_cells(api) for api in apis])
            if api_id is None:
                _window_footer(limit, offset)

        display_output(apis, output_format=output, text_callback=print_text)

    except ApiCollectionError as e:
        rprint(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        if isinstance(e, typer.Exit):
            raise e
        rprint(f"[bold red]Error listing APIs:[/bold red] {e}")
        raise typer.Exit(code=1)


def display_version():
    rprint("sen 0.1.0")
    rprint("apiops-orchestrator 0.1.0")
    rprint(f"python {platform.python_version()}")


def version_callback(value: bool):
    if value:
        display_version()
        raise typer.Exit()


@sen_app.callback()
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
