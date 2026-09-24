import platform
import sys
import time
import typer
from typing import Any, Callable, Optional, cast
from rich import print as rprint
from rich import box
from rich import get_console
from rich.align import Align
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
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

WELCOME_TITLE = "BEM-VINDO AO SENSEDIA API ORCHESTRATOR"

CLI_VERSION = "0.1.0"

WELCOME_LOGO = """\
  ████    ██████    ██████    ████    ██████    ████████               ███████  ██        ██████
██    ██  ██    ██    ██    ██    ██  ██    ██  ██                    ██        ██          ██
████████  ██████      ██    ██    ██  ██████    ████████   ████████   ██        ██          ██
██    ██  ██          ██    ██    ██  ██              ██              ██        ██          ██
██    ██  ██        ██████    ████    ██        ████████               ███████  ████████  ██████\
"""

WELCOME_HINT = (
    "Digite um comando para começar ou utilize "
    "[italic dark_orange]sen --help[/italic dark_orange] para obter ajuda"
)


def print_welcome() -> None:
    rprint()
    rprint(Align.center(Text(WELCOME_TITLE, style="bold magenta")))
    rprint()
    rprint(Align.center(_framed_logo()))
    rprint()


_BOX_ASCII_REPLACEMENTS = {
    "\u2500": "=",  # ─
    "\u2502": "|",  # │
    "\u250c": "+",  # ┌
    "\u2510": "+",  # ┐
    "\u2514": "+",  # └
    "\u2518": "+",  # ┘
}


def _framed_logo() -> str:
    """Logo de letras cercado por moldura dupla com 1 coluna de folga.

    Todas as medidas são calculadas em runtime a partir do tamanho real das
    linhas do logo; todas as linhas do resultado têm o mesmo comprimento,
    o que torna o desalinhamento impossível.
    """
    lines = [
        "",
        *WELCOME_LOGO.splitlines(),
        "",
    ]  # margem vertical: 1 linha em cima e 1 embaixo
    max_len = max(len(line) for line in lines)
    content_len = max_len + 8  # │ + 3 espaços + logo + 3 espaços + │
    content = ["\u2502   " + line.ljust(max_len) + "   \u2502" for line in lines]
    inner_horizontal = "\u2500" * (content_len - 2)
    framed = [
        "\u250c" + inner_horizontal + "\u2510",
        *content,
        "\u2514" + inner_horizontal + "\u2518",
    ]
    outer_horizontal = "\u2500" * (content_len + 2)
    boxed = ["\u2502 " + line + " \u2502" for line in framed]
    result = [
        "\u250c" + outer_horizontal + "\u2510",
        *boxed,
        "\u2514" + outer_horizontal + "\u2518",
    ]
    return _adapt_encoding("\n".join(result))


def _adapt_encoding(text: str) -> str:
    """Adapta box-drawing/blocos quando o stdout não é UTF-8 (cp1252 etc.)."""
    encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    if not encoding or encoding.startswith(("utf", "latin")):
        return text
    try:
        text.encode(encoding)
        return text
    except UnicodeEncodeError:
        pass
    for original, replacement in _BOX_ASCII_REPLACEMENTS.items():
        text = text.replace(original, replacement)
    return text.replace("\u2588", "#")


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
        live = Live(
            Align.center(_LoadingBar()),
            console=get_console(),
            refresh_per_second=10,
            transient=True,
        )
        live.start()
        try:
            session = service_builder().login()
        finally:
            live.stop()
    except LoginError as e:
        rprint(f"[bold red]Login error:[/bold red] {e.message}")
        raise typer.Exit(code=e.exit_code)
    except typer.Exit as e:
        raise e

    expires_at = (
        session.expiresAt.strftime("%d/%m/%Y %H:%M UTC") if session.expiresAt else "-"
    )
    if session.is_super_admin:
        # Privileged flow: show profile/scope only; no identity, no tokens.
        field_rows = [
            ("perfil:", session.profile),
            ("escopo:", session.scope),
            ("sessão:", f"válida até {expires_at}"),
        ]
    else:
        field_rows = [
            ("usuário:", f"{session.userName} ({session.userEmail})"),
            ("sessão:", f"válida até {expires_at}"),
        ]
    rprint(Align.center(_session_panel(field_rows, width=_framed_logo_width())))
    rprint()


_LOADER_FADE_STYLES = ("white", "grey78", "grey53", "grey35")
_LOADER_TRACK_STYLE = "grey23"


class _LoadingBar:
    """Loader estilo opencode: 'Autenticando...' à esquerda e trilha longa
    onde um trem de blocos brancos desliza com rastro de cinza.

    Renderable Rich: o frame é calculado por time.monotonic(), então o
    refresher do Live anima em thread própria sem bloquear a autenticação.
    """

    TRACK_WIDTH = 20
    TRAIN_WIDTH = 4
    GAP_LABEL_TRACK = "      "

    def __init__(self, label: str = "Autenticando..."):
        self.label = label
        encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
        self.block = "\u2588"
        if encoding:
            try:
                self.block.encode(encoding)
            except UnicodeEncodeError:
                self.block = "#"

    def __rich_console__(self, console, options):
        yield self._frame(time.monotonic())

    def _frame(self, now: float) -> Text:
        head = int(now * 8)
        styles = [_LOADER_TRACK_STYLE] * self.TRACK_WIDTH
        for offset in range(self.TRAIN_WIDTH):
            position = (head - offset) % self.TRACK_WIDTH
            styles[position] = _LOADER_FADE_STYLES[offset]
        text = Text(self.label, style="white")
        text.append(self.GAP_LABEL_TRACK)
        for style in styles:
            text.append(self.block, style=style)
        return text


def _stdout_supports_rounded_box() -> bool:
    """True quando o stdout aceita os glifos de box-drawing arredondado."""
    encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    if not encoding:
        return False
    if encoding.startswith(("utf", "latin")):
        return True
    try:
        "\u256d\u2500".encode(encoding)
        return True
    except UnicodeEncodeError:
        return False


def _framed_logo_width() -> int:
    """Largura do quadro do logo — referência de alinhamento dos outros painéis."""
    return len(_framed_logo().splitlines()[0])


def _session_panel(field_rows: list, width: Optional[int] = None) -> Panel:
    """Painel de sessão estilo '>_ produto': header, status e campos alinhados.

    Toda a tipografia é branca; os rótulos ('usuário:', 'sessão:', etc.)
    ficam em negrito. Em consoles sem suporte aos cantos arredondados,
    cai para box ASCII ('+', '-', '|'). Quando `width` é fornecido, o
    painel usa exatamente essa largura em vez de expandir no terminal.
    """
    header = Text.assemble(
        (">_  ", "bold white"),
        ("APIOps CLI", "bold white"),
        (f" (v{CLI_VERSION})", "white"),
    )
    grid = Table.grid(padding=(0, 1))
    grid.add_column(justify="left", min_width=10, no_wrap=True)
    for label, value in field_rows:
        grid.add_row(
            f"[bold white]{label}[/bold white]",
            f"[white]{value}[/white]",
        )
    body = Group(
        header,
        Text(""),
        Text("Login realizado com sucesso.", style="white"),
        Text(""),
        grid,
        Text(""),
        Text.from_markup(WELCOME_HINT, style="white"),
    )
    return Panel(
        body,
        box=box.ROUNDED if _stdout_supports_rounded_box() else box.ASCII,
        border_style="grey53",
        padding=(0, 1),
        width=width,
    )


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


def _render_grade(cells_rows, header=LIST_HEADER) -> None:
    """Grade alinhada estilo monospace (A3/C2): colunas alinhadas à esquerda."""
    widths = [len(col) for col in header]
    flat_rows = [header] + [
        (cells if isinstance(cells, tuple) else tuple(cells)) for cells in cells_rows
    ]
    for row in flat_rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    rprint(
        "[bold cyan]"
        + "  ".join(header[i].ljust(widths[i]) for i in range(len(header)))
        + "[/bold cyan]"
    )
    for row in cells_rows:
        values = row if isinstance(row, tuple) else tuple(row)
        rprint("  ".join(values[i].ljust(widths[i]) for i in range(len(header))))


def _window_footer(limit_value: Optional[int], offset_value: Optional[int]) -> None:
    shown_limit = limit_value if limit_value is not None else DEFAULT_WINDOW_LIMIT
    shown_offset = offset_value if offset_value is not None else DEFAULT_WINDOW_OFFSET
    if limit_value is None and offset_value is None:
        rprint(
            f"[dim]usando padrões: --limit {shown_limit} "
            f"--offset {shown_offset}  ->  detalhes: sen list api --help[/dim]"
        )
    else:
        rprint(f"[dim]janela: --limit {shown_limit} --offset {shown_offset}[/dim]")


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
                "[bold red]Error:[/bold red] --revisions/-r exige --id (drill-down "
                "revisa UMA API). Consulte: sen list api --help"
            )
            raise typer.Exit(code=1)

        if api_id is not None:
            if revisions:
                _render_revisions_grade(service, api_id, output)
                return
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


REVISIONS_HEADER = (
    "REV ID",
    "REV #",
    "STAGE",
    "ENVS",
    "COMPLETE",
)


def _revision_cells(row: dict) -> tuple:
    return (
        str(row.get("revision_id", "")),
        str(row.get("revision_number", "")),
        str(row.get("stage_name", "-")),
        str(row.get("environments") or "-"),
        str(row.get("complete") or "-"),
    )


def _render_revisions_grade(
    service: ApiListingService, api_id: int, output: OutputFormat
) -> None:
    rows = service.api_revisions(api_id)
    if not rows:
        rprint(f"[yellow]No revisions found for API {api_id}.[/yellow]")
        return

    def print_text():
        _render_grade([_revision_cells(row) for row in rows], header=REVISIONS_HEADER)

    display_output(rows, output_format=output, text_callback=print_text)


def display_version():
    rprint(f"sen {CLI_VERSION}")
    rprint(f"apiops-orchestrator {CLI_VERSION}")
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
    print_welcome()
    if verbose:
        # TODO: Ajustar nível de log quando houver integração com logging
        pass
