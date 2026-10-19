import importlib.metadata
import logging
import platform
import sys
import textwrap
from contextlib import contextmanager
import time
from datetime import datetime, timezone
from pathlib import Path

import typer
from typing import Any, Callable, Dict, NoReturn, Optional, cast
from rich import print as rprint
from rich import box
from rich import get_console
from rich.align import Align
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from apiops_orchestrator.application.services.api_listing_service import (
    ApiListingService,
)
from apiops_orchestrator.application.services.completeness_service import (
    CompletenessService,
)
from apiops_orchestrator.adapters.inbound.cli.output_format import OutputFormat
from apiops_orchestrator.adapters.inbound.cli.output_display import display_output
from apiops_orchestrator.application.exceptions.login_exceptions import LoginError
from apiops_orchestrator.application.exceptions.completeness_exceptions import (
    CompletenessError,
)
from apiops_orchestrator.application.exceptions.validate_exceptions import (
    ValidateError,
)
from apiops_orchestrator.domain.models.completeness_view import CompletenessView
from apiops_orchestrator.domain.models.publish_view import PublishView
from apiops_orchestrator.domain.models.validate_view import (
    ESCOPO_REPOSITORIO,
    SEVERIDADE_WARNING,
    Achado,
    ValidateView,
)
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.models.catalog_revision_model import CatalogRevisionInfo
from apiops_orchestrator.application.exceptions.listing_exceptions import (
    ApiCollectionError,
)
from apiops_orchestrator.application.exceptions.manager_failure_messages import (
    INTERNAL_ERROR_MESSAGE,
)
from apiops_orchestrator.application.services.manager_failure_translator import (
    classify_manager_failure,
    manager_failure_message,
)
from apiops_orchestrator.domain.ports.manager_api_port import ManagerApiError

logger = logging.getLogger(__name__)

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


@list_app.callback(invoke_without_command=True)
def list_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        rprint(
            "[bold yellow]Nenhum subcomando informado.[/bold yellow] "
            "O disponível hoje é: sen list api "
            "(consulte: sen list api --help)"
        )
        raise typer.Exit(code=2)


sen_app.add_typer(list_app)

main_app.add_typer(sen_app)

app = main_app

WELCOME_TITLE = "BEM-VINDO AO SENSEDIA API ORCHESTRATOR"

_CLI_PACKAGE = "apiops-orchestrator"


def cli_version() -> str:
    """Single source of truth: version declared in pyproject.toml, resolved
    from the installed package metadata; falls back for frozen/dev runs
    where metadata is unavailable."""
    try:
        return importlib.metadata.version(_CLI_PACKAGE)
    except importlib.metadata.PackageNotFoundError:
        return "-"


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


def _supports_text(text: str) -> bool:
    """True when stdout can fully render `text`, glyph by glyph.

    Single source of terminal-glyph capability detection: treats utf*/latin*
    as capable without probing, conservatively reports False on unknown
    encodings, and keeps every glyph consumer (logo, panels, loader) in
    sync so visual degradation is all-or-nothing.
    """
    encoding = (getattr(sys.stdout, "encoding", None) or "").lower()
    if encoding.startswith(("utf", "latin")):
        return True
    if not encoding:
        return False
    try:
        text.encode(encoding)
        return True
    except UnicodeEncodeError:
        return False


def _adapt_encoding(text: str) -> str:
    """Adapta box-drawing/blocos quando o stdout não é UTF-8 (cp1252 etc.)."""
    if _supports_text(text):
        return text
    for original, replacement in _BOX_ASCII_REPLACEMENTS.items():
        text = text.replace(original, replacement)
    return text.replace("\u2588", "#")


class CliError(Exception):
    """Basic exception for friendly CLI errors."""

    def __init__(self, message: str, exit_code: int = 1):
        self.message = message
        self.exit_code = exit_code
        super().__init__(self.message)


def _exit_on_unexpected(exc: Exception, command: str, exit_code: int = 1) -> NoReturn:
    """Last-resort handler of a command: never shows raw exception text.

    Two categorized errors can still arrive here because service factories
    run inside the command's `try`: incomplete configuration (`CliError`) and
    the admin-token resolution refusal (`LoginError`, which orients
    `sen login`). Both keep their educational message. A Manager signal that
    no use case translated (e.g. a 401 on a call the service does not wrap)
    gets the shared family message, so an expired session still says
    `sen login`. Anything else is an internal error for the user; type and
    stacktrace go to the log only, at INFO (with logging not wired, WARNING+
    would leak to stderr).
    """
    if isinstance(exc, CliError):
        rprint(f"[bold red]Erro:[/bold red] {exc.message}")
        raise typer.Exit(code=exc.exit_code)
    if isinstance(exc, LoginError):
        rprint(f"[bold red]Erro:[/bold red] {exc.message}")
        raise typer.Exit(code=1)
    if isinstance(exc, ManagerApiError):
        message = manager_failure_message(classify_manager_failure(exc))
        logger.info(
            "cli.manager_failure command=%s type=%s", command, type(exc).__name__
        )
        rprint(f"[bold red]Erro:[/bold red] {message or INTERNAL_ERROR_MESSAGE}")
        raise typer.Exit(code=exit_code)
    logger.info(
        "cli.unexpected_error command=%s type=%s",
        command,
        type(exc).__name__,
        exc_info=exc,
    )
    rprint(f"[bold red]Erro:[/bold red] {INTERNAL_ERROR_MESSAGE}")
    raise typer.Exit(code=exit_code)


def _authenticate_with_feedback(service_builder: Callable[[], Any], narrar: bool = True):
    """Runs the login flow with a spinner only when stdout is a terminal.

    In non-interactive stdout (CI runner, redirected output, docker logs),
    Rich's Live turns each animation frame into plain new lines polluting
    machine-readable output, so we fall back to a single dim status line.

    With `narrar=False` (`-o json`/`-o yaml`) there is no feedback at all: stdout
    carries only the document the pipeline will parse.
    """
    if not narrar:
        return service_builder().login()
    if not get_console().is_terminal:
        rprint("[dim]Autenticando...[/dim]")
        return service_builder().login()

    live = Live(
        Align.center(_LoadingBar()),
        console=get_console(),
        refresh_per_second=10,
        transient=True,
    )
    live.start()
    try:
        return service_builder().login()
    finally:
        live.stop()


SCHEMA_SEN_LOGIN_V1 = "apiops.sen-login/v1"


def _iso_utc(momento: Optional[datetime]) -> Optional[str]:
    if momento is None:
        return None
    if momento.tzinfo is not None:
        momento = momento.astimezone(timezone.utc)
    return momento.strftime("%Y-%m-%dT%H:%M:%SZ")


def _documento_login(session: Any) -> Dict[str, Any]:
    """Contrato `apiops.sen-login/v1`: o mesmo que o painel mostra, por perfil.

    Nenhum token, em nenhum perfil. O super-admin não expõe identidade pessoal.
    """
    documento: Dict[str, Any] = {"schema": SCHEMA_SEN_LOGIN_V1, "authenticated": True}
    if session.is_super_admin:
        documento["profile"] = session.profile
        documento["scope"] = session.scope
    else:
        documento["user"] = {"name": session.userName, "email": session.userEmail}
    documento["expiresAt"] = _iso_utc(session.expiresAt)
    return documento


@sen_app.command("login")
def login(
    ctx: typer.Context,
    output: OutputFormat = typer.Option(
        OutputFormat.TEXT, "--output", "-o", help="Output format (text, json, yaml)."
    ),
):
    """
    Authenticate against the Orchestrator Auth API and store the local session.
    Requires the SEN_CREDENTIALS environment variable (Base64 of client_id:secret).
    """
    estruturado = output is not OutputFormat.TEXT
    try:
        login_service_factory = (ctx.obj or {}).get("login_service_factory")
        if not callable(login_service_factory):
            rprint(
                "[bold red]Erro:[/bold red] Serviço de login indisponível no contexto."
            )
            raise typer.Exit(code=1)

        if not estruturado:
            print_welcome()
        session = _authenticate_with_feedback(
            cast(Callable[[], Any], login_service_factory), narrar=not estruturado
        )
    except LoginError as e:
        rprint(f"[bold red]Erro de login:[/bold red] {e.message}")
        raise typer.Exit(code=e.exit_code)
    except typer.Exit as e:
        raise e

    if estruturado:
        display_output(_documento_login(session), output_format=output)
        return

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
        self.block = "\u2588" if _supports_text("\u2588") else "#"

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
    return _supports_text("\u256d\u2500")


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
        (f" (v{cli_version()})", "white"),
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


LIST_HEADER = ("ID", "NAME", "VERSION", "BASE PATH", "LAST REV")
DEFAULT_WINDOW_LIMIT = 10
DEFAULT_WINDOW_OFFSET = 0


def _listing_cells(api: ApiCatalogEntry) -> tuple:
    return (
        str(api.id if api.id is not None else ""),
        str(api.name or ""),
        str(api.version or "-"),
        str(api.basePath or ""),
        str(api.last_revision_number() or "-"),
    )


_GRADE_BOX = box.ROUNDED if _stdout_supports_rounded_box() else box.ASCII


def _score_cell(value: str) -> Text:
    """Coloração decorativa do score (≤80 verde, 50–79 amarelo, <50 vermelho).

    Política puramente de render — os limiares fixos NÃO substituem o gate
    real por revisão (que vive no `sen completeness`); o dado cru segue idêntico.
    """
    if not value.endswith("%"):
        return Text(value)
    try:
        score = float(value[:-1])
    except ValueError:
        return Text(value)
    style = "green" if score >= 80 else "yellow" if score >= 50 else "red"
    return Text(value, style=style)


def _render_grade(
    cells_rows,
    header=LIST_HEADER,
    column_justify: Optional[tuple] = None,
    column_decorators: Optional[tuple] = None,
) -> None:
    """Grade Rich (estilização da grade canônica C2; mesmas colunas do §4).

    Cai para box ASCII em consoles sem glifos arredondados, coerente com o
    resto do CLI (`_stdout_supports_rounded_box`). Sem `cell_style` os valores
    não recebem marcação — conteúdos ordinários cruzam como str simples.
    """
    table = Table(
        box=_GRADE_BOX,
        header_style="bold cyan",
        border_style="grey53",
        padding=(0, 1),
        pad_edge=False,
    )
    for index, column in enumerate(header):
        table.add_column(
            column,
            justify=(column_justify[index] if column_justify else None) or "left",
        )
    for row in cells_rows:
        values = row if isinstance(row, tuple) else tuple(row)
        decorated = []
        for index, value in enumerate(values):
            decorator = (
                column_decorators[index]
                if column_decorators and index < len(column_decorators)
                else None
            )
            decorated.append(decorator(value) if decorator else value)
        table.add_row(*decorated)
    rprint(table)


def _window_footer(
    limit_value: Optional[int], offset_value: Optional[int], all_visible: bool = False
) -> None:
    if all_visible:
        rprint("[dim]janela: todas as APIs visíveis (--all)[/dim]")
        return
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
        None, "--query", help="Search on name/description, performed by the Manager."
    ),
    limit: Optional[int] = typer.Option(None, "--limit", help="Page size."),
    offset: Optional[int] = typer.Option(None, "--offset", help="Offset from start."),
    all_apis: bool = typer.Option(
        False, "--all", help="List every visible API (not combinable with --limit/--offset/--id)."
    ),
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
        service_factory = (ctx.obj or {}).get("api_listing_service_factory")
        if not callable(service_factory):
            rprint(
                "[bold red]Erro:[/bold red] Serviço de listagem de APIs "
                "indisponível no contexto."
            )
            raise typer.Exit(code=1)
        service = cast(Callable[[], ApiListingService], service_factory)()

        # Validações pré-rede (A3-3, A3-1)
        if query and api_id is not None:
            rprint(
                "[bold red]Erro:[/bold red] Use --query OU --id, nunca os dois "
                "juntos. Consulte: sen list api --help"
            )
            raise typer.Exit(code=1)
        if all_apis and (limit is not None or offset is not None or api_id is not None):
            rprint(
                "[bold red]Erro:[/bold red] --all lista todas as APIs visíveis e não "
                "combina com --limit, --offset ou --id. Consulte: sen list api --help"
            )
            raise typer.Exit(code=1)
        if limit is not None and limit <= 0:
            rprint(
                "[bold red]Erro:[/bold red] --limit deve ser maior que zero. "
                "Consulte: sen list api --help"
            )
            raise typer.Exit(code=1)
        if offset is not None and offset < 0:
            rprint(
                "[bold red]Erro:[/bold red] --offset deve ser maior ou igual a "
                "zero. Consulte: sen list api --help"
            )
            raise typer.Exit(code=1)
        if revisions and api_id is None:
            rprint(
                "[bold red]Erro:[/bold red] --revisions/-r exige --id (drill-down "
                "revisa UMA API). Consulte: sen list api --help"
            )
            raise typer.Exit(code=1)

        if api_id is not None:
            if revisions:
                _render_revisions_grade(service, api_id, output)
                return
            apis = service.list_apis(api_id=api_id)
        elif all_apis:
            # Sem janela: o service lê o catálogo em páginas até o fim.
            apis = service.list_apis(query=query, offset=0, limit=None)
        else:
            # Caso desnudo envia os defaults AO PIPELINE (A3-2): a janela
            # client-side so eh real se os valores alcancarem o window().
            apis = service.list_apis(
                query=query,
                offset=offset if offset is not None else DEFAULT_WINDOW_OFFSET,
                limit=limit if limit is not None else DEFAULT_WINDOW_LIMIT,
            )

        if not apis:
            rprint("[yellow]Nenhuma API encontrada.[/yellow]")
            return

        def print_text():
            _render_grade(
                [_listing_cells(entry) for entry in apis],
                column_justify=("right", None, None, None, "right"),
                column_decorators=(
                    (lambda v: Text(str(v), style="dim")),
                    None,
                    None,
                    None,
                    None,
                ),
            )
            if api_id is None:
                _window_footer(limit, offset, all_visible=all_apis)

        display_output(
            [entry.to_listing_dict() for entry in apis],
            output_format=output,
            text_callback=print_text,
        )

    except typer.Exit:
        raise
    except ApiCollectionError as e:
        rprint(f"[bold red]Erro:[/bold red] {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        _exit_on_unexpected(e, command="list api")


REVISIONS_HEADER = (
    "REV #",
    "REV ID",
    "STAGE",
    "ENVS",
    "COMPLETE",
)


def _format_score(score):
    return "-" if score is None else f"{score:.0f}%"


def _revision_cells(row: CatalogRevisionInfo) -> tuple:
    return (
        str(row.revision_number),
        str(row.revision_id),
        str(row.stage_name),
        str(row.environments or "-"),
        _format_score(row.completeness_score),
    )


def _render_revisions_grade(
    service: ApiListingService, api_id: int, output: OutputFormat
) -> None:
    rows = service.api_revisions(api_id)
    if not rows:
        rprint(f"[yellow]Nenhuma revisão encontrada para a API {api_id}.[/yellow]")
        return

    def print_text():
        _render_grade(
            [_revision_cells(row) for row in rows],
            header=REVISIONS_HEADER,
            column_justify=(None, None, None, None, "right"),
            column_decorators=(
                (lambda v: Text(str(v), style="bold white")),
                None,
                None,
                None,
                _score_cell,
            ),
        )

    display_output(
        [row.to_dict() for row in rows], output_format=output, text_callback=print_text
    )


def display_version():
    rprint(f"sen {cli_version()}")
    rprint(f"apiops-orchestrator {cli_version()}")
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


# ---------------------------------------------------------------------------
# sen completeness — espelho integral de completude por revisão
# ---------------------------------------------------------------------------

COMPLETENESS_BAR_WIDTH = 30
COMPLETENESS_WRAP_WIDTH = 92


def _completeness_glyph(kind: str) -> str:
    """Glifo ASCII-seguro: portável em cp1252 sem adaptations especiais."""
    return {"fill": "#", "empty": ".", "gate": "|", "warn": "!"}[kind]


def _completeness_bar(score: float, gate_percent: float) -> Text:
    """Barra de 30 glifos escalada ao score, com marcador fixo de gate.

    Honesto com o wire: percentuais fora de 0..100 saturam na borda — o
    clamp é política de RENDER (o dado cru permanece no contrato).
    """
    clamped = max(0.0, min(100.0, score))
    filled = round(clamped / 100 * COMPLETENESS_BAR_WIDTH)
    gate_index = round(gate_percent / 100 * COMPLETENESS_BAR_WIDTH)
    cells = []
    for position in range(COMPLETENESS_BAR_WIDTH):
        if position == gate_index:
            cells.append(_completeness_glyph("gate"))
        elif position < filled:
            cells.append(_completeness_glyph("fill"))
        else:
            cells.append(_completeness_glyph("empty"))
    text = Text("", style="white")
    text.append(f"[{''.join(cells)}]")
    return text


def _completeness_below_gate(score: float, gate_percent: float) -> Optional[str]:
    if score >= gate_percent:
        return None
    deficit = round(gate_percent - max(0.0, min(100.0, score)), 1)
    return f"faltam {deficit} pts para o gate"


def _completeness_field_grid(view: CompletenessView) -> Table:
    api = view.api
    grid = Table.grid(padding=(0, 1))
    grid.add_column(justify="left", min_width=11, no_wrap=True)
    grid.add_column(justify="left")

    name = api.name or "-"
    version = api.version or "-"
    grid.add_row(
        Text("API:", style="bold white"),
        Text(f"{name} ({version}) · #{api.manager_id}"),
    )
    revision_label = str(view.revision_id)
    if view.revision_number is not None:
        revision_label += f" (#{view.revision_number})"
    grid.add_row(Text("REVISÃO:", style="bold white"), Text(revision_label))
    if api.context:
        label_bits = [bit for bit in (api.context.type,) if bit]
        owner_bits = [bit for bit in (api.context.group_name, api.context.owner) if bit]
        possession = " · ".join(label_bits + owner_bits) or "-"
        grid.add_row(Text("POSSE:", style="bold white"), Text(possession))
    return grid


def _render_completeness_headline(view: CompletenessView, score_only: bool) -> Group:
    body_bits: list[Any] = [_completeness_field_grid(view), Text("")]

    bar_line = Text.assemble(
        ("COMPLETUDE  ", "bold white"),
        (f"{view.score:.1f}%", "bold white"),
        ("  ", "white"),
        _completeness_bar(view.score, view.gate_percent),
        (f" (gate: ≥{view.gate_percent:.0f}%)", "white"),
    )
    body_bits.append(bar_line)

    deficit = _completeness_below_gate(view.score, view.gate_percent)
    if deficit:
        body_bits.append(
            Text(f"{_completeness_glyph('warn')} {deficit}", style="yellow")
        )

    if score_only:
        return Group(*body_bits)

    suggestions = view.suggestions
    body_bits.append(Text(""))
    if not suggestions:
        body_bits.append(
            Text("Nenhuma sugestão de melhoria para esta revisão.", style="white")
        )
        return Group(*body_bits)

    body_bits.append(Text(f"SUGESTÕES ({len(suggestions)}):", style="bold white"))
    wrapper = textwrap.TextWrapper(
        width=COMPLETENESS_WRAP_WIDTH,
        subsequent_indent="      ",
    )
    for item in suggestions:
        lines = wrapper.wrap(item.text)
        if not lines:
            continue
        numbered = Text("")
        numbered.append(f"  {item.index:>2}. ", style="bold white")
        numbered.append(lines[0])
        body_bits.append(numbered)
        for continuation in lines[1:]:
            body_bits.append(Text(f"      {continuation}"))
    return Group(*body_bits)


def _render_completeness_text(view: CompletenessView, score_only: bool) -> None:
    width = _framed_logo_width()
    body = _render_completeness_headline(view, score_only)
    panel = Panel(
        body,
        box=box.ROUNDED if _stdout_supports_rounded_box() else box.ASCII,
        border_style="grey53",
        padding=(0, 1),
        width=width,
    )
    rprint(Align.center(panel))
    rprint()


MISSING_TARGET_MESSAGE = (
    "Informe a API e a revisão: --id e --revision são obrigatórios. "
    "Para descobrir os REV ID: sen list api --id X --revisions. "
    "Detalhes: sen completeness --help"
)


@sen_app.command("completeness")
def completeness(
    ctx: typer.Context,
    api_id: Optional[int] = typer.Option(None, "--id", help="Manager ID of the API."),
    revision: Optional[int] = typer.Option(
        None, "--revision", help="Revision ID (REV ID from the revisions drill-down)."
    ),
    score_only: bool = typer.Option(
        False, "--score-only", help="Show only headline and bar/gate."
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TEXT, "--output", "-o", help="Output format (text, json, yaml)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbosity only."),
):
    """
    Show the completeness report of one API revision (Sensedia Manager).
    """
    if api_id is None or revision is None:
        rprint(f"[bold red]Erro:[/bold red] {MISSING_TARGET_MESSAGE}")
        raise typer.Exit(code=1)

    try:
        service_factory = (ctx.obj or {}).get("completeness_service_factory")
        if not callable(service_factory):
            rprint(
                "[bold red]Erro:[/bold red] Serviço de completude indisponível "
                "no contexto."
            )
            raise typer.Exit(code=1)

        service = cast(Callable[[], CompletenessService], service_factory)()
        view = service.get_completeness(api_id=api_id, revision_id=revision)

        display_output(
            view.to_document(),
            output_format=output,
            text_callback=lambda: _render_completeness_text(view, score_only),
        )

    except typer.Exit:
        raise
    except CompletenessError as e:
        rprint(f"[bold red]Erro:[/bold red] {e.message}")
        raise typer.Exit(code=e.exit_code)
    except Exception as e:
        _exit_on_unexpected(e, command="completeness", exit_code=CompletenessError.exit_code)


# ---------------------------------------------------------------------------
# sen validate
# ---------------------------------------------------------------------------

_SEVERIDADE_ESTILO = {"WARNING": "yellow", "INFO": "cyan"}


def _painel_validate(titulo: str, corpo, width=None) -> Panel:
    """Caixa de seção, no mesmo desenho do painel de sessão do `sen login`."""
    return Panel(
        corpo,
        title=f"[bold white]{titulo}[/bold white]",
        title_align="left",
        box=box.ROUNDED if _stdout_supports_rounded_box() else box.ASCII,
        border_style="grey53",
        padding=(0, 1),
        width=width,
    )


def _grade_de_campos(linhas) -> Table:
    """Pares rótulo/valor alinhados — mesma grade do `_session_panel`."""
    grid = Table.grid(padding=(0, 1))
    grid.add_column(justify="left", min_width=12, no_wrap=True)
    grid.add_column(justify="left", overflow="fold")
    for rotulo, valor in linhas:
        grid.add_row(f"[bold white]{rotulo}[/bold white]", valor)
    return grid


def _largura_validate() -> int:
    """Largura única das seções do `validate`.

    Tudo — painel, tabela e avisos — usa a mesma referência do `sen login`, e
    nunca ultrapassa o terminal. Sem isso o painel sai com 108 colunas e a
    tabela com a largura do console, e as bordas não se alinham.
    """
    return min(_framed_logo_width(), get_console().width)


def _tabela_achados(achados, largura: Optional[int] = None) -> Table:
    """Achados em tabela, como o `sen list` faz com as APIs.

    Em lista corrida de 38 achados nada se distingue; em colunas, o olho varre
    a severidade e para no que interessa.
    """
    tabela = Table(
        box=_GRADE_BOX,
        header_style="bold cyan",
        border_style="grey53",
        padding=(0, 1),
        pad_edge=False,
        width=largura,
    )
    # ONDE quebra em vez de truncar: `POST /tarefas/{id}/atribuicao-responsavel`
    # cortado em "…atribuicao-res…" não identifica rota nenhuma.
    tabela.add_column("SEVERIDADE", no_wrap=True, width=10)
    tabela.add_column("ONDE", overflow="fold", max_width=30)
    tabela.add_column("O QUE", overflow="fold", ratio=1)
    for achado in achados:
        estilo = _SEVERIDADE_ESTILO.get(achado.severity, "white")
        tabela.add_row(
            Text(achado.severity, style=estilo),
            Text(achado.scope or "-", style="white"),
            Text(achado.message, style="white"),
        )
    return tabela


def _render_avisos_do_repo(avisos) -> None:
    """Avisos do repositório, em blocos — não em tabela.

    São textos de várias frases, com quebra de linha própria, que dizem o que
    vai mudar na plataforma. Espremidos numa coluna de tabela viram uma coluna
    de palavras soltas; em bloco, de largura inteira, continuam legíveis.
    """
    marcador = "▸" if _supports_text("▸") else "!"
    grid = Table.grid(padding=(0, 1))
    grid.width = _largura_validate()
    grid.add_column(justify="left", width=1, no_wrap=True)
    grid.add_column(overflow="fold", ratio=1)
    for achado in avisos:
        grid.add_row(f"[yellow]{marcador}[/yellow]", Text(achado.message, style="white"))
    rprint(grid)


def _render_validate_text(view: ValidateView) -> None:
    """Renderiza a resposta do `validate` para leitura no terminal.

    Mesma árvore que alimenta `json`/`yaml` — os três formatos nunca divergem.
    O desenho segue o do `sen login` e do `sen list`: caixa para identidade,
    tabela para itens repetidos, grade de rótulos para pares chave/valor.
    """
    width = _largura_validate()

    # --- identidade: quem está sendo validado, e onde ------------------------
    identidade = [("API", f"[bold white]{view.api.name or '-'}[/bold white]")]
    detalhe = f"id {view.api.manager_id}"
    if view.api.version:
        detalhe += f"  ·  v{view.api.version}"
    if view.api.base_path:
        detalhe += f"  ·  {view.api.base_path}"
    identidade.append(("", f"[grey53]{detalhe}[/grey53]"))

    revisao = f"[white]#{view.revision.revision_number}[/white]" if (
        view.revision.revision_number is not None
    ) else "[white]-[/white]"
    identidade.append(
        ("Rascunho", f"{revisao} [grey53](id {view.revision.manager_id})[/grey53]")
    )

    if view.regua.template_id is not None:
        alvo = f"[white]API {view.regua.template_id}[/white]"
        complemento = []
        if view.regua.revision_number is not None:
            complemento.append(f"revisão #{view.regua.revision_number}")
        if view.regua.interceptors_count is not None:
            complemento.append(f"{view.regua.interceptors_count} interceptor(es)")
        if view.regua.flow_hash:
            # O snapshot é o que torna um achado reproduzível depois (D-4/P-3).
            complemento.append(view.regua.flow_hash)
        if complemento:
            alvo += f"  [grey53]{'  ·  '.join(complemento)}[/grey53]"
    else:
        alvo = "[grey53]não vinculada — conformidade não executada[/grey53]"
    identidade.append(("Template", alvo))
    identidade.append(("Modo", f"[grey53]{view.execution_mode}[/grey53]"))

    rprint()
    rprint(_painel_validate("Validação", _grade_de_campos(identidade), width=width))
    rprint()

    # --- conformidade: nunca bloqueia (V-11 §3) ------------------------------
    do_repo = [a for a in view.achados if a.scope == ESCOPO_REPOSITORIO]
    da_template = [a for a in view.achados if a.scope != ESCOPO_REPOSITORIO]

    if da_template:
        avisos = sum(
            1 for a in da_template if a.severity == SEVERIDADE_WARNING
        )
        rprint(
            f"[bold]Conformidade com a API-template[/bold]  "
            f"[yellow]{avisos} aviso(s)[/yellow] · "
            f"[cyan]{len(da_template) - avisos} informativo(s)[/cyan]"
        )
        rprint(_tabela_achados(da_template, largura=width))
        rprint("[grey53]Nenhum deles impede a publicação.[/grey53]")
        rprint()
    elif view.regua.template_id is not None:
        rprint(
            "[bold]Conformidade com a API-template[/bold]  "
            "[green]sem divergências[/green]"
        )
        rprint()

    # --- o que o repositório vai mudar na plataforma -------------------------
    if do_repo:
        rprint(
            f"[bold]O que vai mudar no Manager[/bold]  "
            f"[yellow]{len(do_repo)} aviso(s)[/yellow]"
        )
        _render_avisos_do_repo(do_repo)
        rprint()

    # --- governança: o faltante é calculado, não extraído de texto (V-23 §4) --
    gov = view.governanca
    if gov.stage_id is not None:
        if gov.missing:
            faltantes = ", ".join((m.name or str(m.attribute_id)) for m in gov.missing)
            rprint(f"[bold red]Governança[/bold red]  falta: {faltantes}")
        else:
            rprint(
                f"[bold]Governança[/bold]  [green]liberada[/green] "
                f"[grey53]({len(gov.required)} atributo(s) exigido(s), nenhum "
                "faltando)[/grey53]"
            )
        rprint(
            f"  [grey53]workflow {gov.workflow_id} · stage {gov.stage_id} "
            "(lidos da revisão)[/grey53]"
        )
        rprint()

    # --- publicação: HTTP 200 não é prova de sucesso (W-8) -------------------
    pub = view.publicacao
    if pub.attempted:
        if pub.verified:
            rprint(
                "[bold]Rascunho[/bold]  [green]gravado e conferido[/green] "
                "[grey53](nenhum ambiente recebeu deploy)[/grey53]"
            )
        elif pub.accepted:
            rprint(
                "[bold red]Rascunho[/bold red]  aceito pelo Manager, mas o que "
                "ficou gravado não é o que foi enviado:"
            )
            for d in pub.divergences:
                rprint(f"  [red]•[/red] {d}")
        else:
            rprint("[bold red]Rascunho[/bold red]  recusado")
        rprint()
    # Sem `attempted`, o comando já encerrou com "Validação cancelada".

    # --- quality score: informativo aqui; o gate trava em DEV+ ---------------
    comp = view.completeness
    if comp.score is not None:
        # `≥` quebra em console cp1252 (UnicodeEncodeError), e o comando não
        # pode morrer por causa de um glifo decorativo.
        maior_igual = "≥" if _supports_text("≥") else ">="
        gate = (
            f"  [grey53]Quality gate: {maior_igual}{comp.gate_percent:.0f}%[/grey53]"
            if comp.gate_percent is not None
            else ""
        )
        rprint(f"[bold]Quality score[/bold]  {comp.score:.1f}%{gate}")
        if comp.suggestions:
            sugestoes = Table.grid(padding=(0, 1))
            sugestoes.add_column(justify="right", width=3, no_wrap=True)
            sugestoes.add_column(overflow="fold")
            for i, s in enumerate(comp.suggestions, start=1):
                sugestoes.add_row(f"[grey53]{i}.[/grey53]", f"[white]{s}[/white]")
            rprint(sugestoes)
        rprint()


_STDERR_CONSOLE: Optional[Console] = None


def _stderr_console() -> Console:
    """Console de stderr, para o que é progresso e não resultado."""
    global _STDERR_CONSOLE
    if _STDERR_CONSOLE is None:
        _STDERR_CONSOLE = Console(stderr=True)
    return _STDERR_CONSOLE


class _ProgressoValidate:
    """Barra de etapas do `validate`, com pausa para a confirmação.

    O comando faz cinco chamadas de rede em sequência e pode parar no meio para
    perguntar se grava o rascunho. Uma `Live` animando por baixo de um
    `typer.confirm` embaralha o prompt — então a confirmação a suspende e a
    retoma depois.

    Duas salvaguardas para não contaminar saída legível por máquina:

    * em `-o json`/`-o yaml` o progresso **não existe** — nem animação, nem
      linha. O stdout carrega o documento que a esteira vai parsear, e muita
      esteira captura `2>&1`, então stderr também não serve;
    * fora de terminal, cada etapa sai como uma linha só em **stderr**, porque a
      animação viraria uma enxurrada de frames no log — mesmo motivo do `login`.
    """

    def __init__(self, rotulo_inicial: str = "Validando", narrar: bool = True):
        self._interativo = narrar and get_console().is_terminal
        self._narrar = narrar
        self._barra = _LoadingBar(f"{rotulo_inicial}...")
        self._live = (
            Live(
                Align.center(self._barra),
                console=get_console(),
                refresh_per_second=10,
                transient=True,
            )
            if self._interativo
            else None
        )

    def __enter__(self):
        if self._live is not None:
            self._live.start()
        return self

    def __exit__(self, *_exc):
        if self._live is not None:
            self._live.stop()
        return False

    def etapa(self, texto: str) -> None:
        """Narra em que ponto a espera está — a `Live` relê o rótulo no refresh."""
        self._barra.label = f"{texto}..."
        if self._live is None and self._narrar:
            _stderr_console().print(f"[dim]{texto}...[/dim]")

    @contextmanager
    def pausado(self):
        if self._live is None:
            yield
            return
        self._live.stop()
        try:
            yield
        finally:
            self._live.start()


class _OperacaoCancelada(Exception):
    """Ctrl+C (ou fim da entrada) no prompt: interrompe o comando inteiro."""


# Código de saída convencional de interrupção (128 + SIGINT), para que script ou
# esteira distingam "cancelado" de "recusado" (0) e de falha (1).
EXIT_CANCELADO = 130


def _encerrar_sem_gravar(comando: str, codigo: int = 0) -> NoReturn:
    """Sem a cascata completa não há relatório — só o desfecho."""
    rprint(f"[yellow]{comando} cancelada.[/yellow] Nada foi gravado.")
    raise typer.Exit(code=codigo)


def _confirmar_publicacao(
    mensagem: str, progresso: Optional["_ProgressoValidate"] = None
) -> bool:
    """Guarda 2: confirmação interativa, só em EXECUTION_MODE=local.

    Vive na CLI, não no service — o use-case recebe isto como callable e nunca
    lê `stdin`. O texto vem pronto do serviço; o que a borda acrescenta é a
    pergunta de sim/não e a caixa, para que o aviso não se perca numa linha
    solta no meio da saída.

    `n` devolve `False` e o comando encerra sem gravar. Ctrl+C não é resposta:
    interrompe o comando (`_OperacaoCancelada`).
    """
    def _perguntar() -> bool:
        rprint()
        rprint(
            Align.center(
                Panel(
                    Text(mensagem, style="white"),
                    title="[bold yellow]Confirmação[/bold yellow]",
                    title_align="left",
                    box=box.ROUNDED if _stdout_supports_rounded_box() else box.ASCII,
                    border_style="yellow",
                    padding=(0, 1),
                    width=_largura_validate(),
                )
            )
        )
        try:
            return typer.confirm("Deseja prosseguir?", default=False)
        except typer.Abort as exc:
            # Ctrl+C ou fim da entrada: o Click entrega os dois como `Abort`.
            # Não é um "não" — é interromper. Nada foi gravado até aqui.
            raise _OperacaoCancelada() from exc

    if progresso is None:
        return _perguntar()
    with progresso.pausado():
        return _perguntar()


@sen_app.command("validate")
def validate(
    ctx: typer.Context,
    repo: Optional[Path] = typer.Option(
        None, "--repo", help="Repositório da API (default: diretório atual)."
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TEXT, "--output", "-o", help="Output format (text, json, yaml)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbosity only."),
):
    """
    Validate the API repository and publish to the Draft to get the governance verdict.
    """
    try:
        service_factory = (ctx.obj or {}).get("validate_service_factory")
        if not callable(service_factory):
            rprint(
                "[bold red]Erro:[/bold red] Serviço de validação indisponível "
                "no contexto."
            )
            raise typer.Exit(code=1)

        service = cast(Callable[[], Any], service_factory)()
        progresso = _ProgressoValidate(narrar=output is OutputFormat.TEXT)
        with progresso:
            view = service.validate(
                repo_path=repo or Path.cwd(),
                confirmar=lambda m: _confirmar_publicacao(m, progresso),
                progresso=progresso.etapa,
            )

        if not view.publicacao.attempted:
            _encerrar_sem_gravar("Validação")

        display_output(
            view.to_document(),
            output_format=output,
            text_callback=lambda: _render_validate_text(view),
        )

    except typer.Exit:
        raise
    except _OperacaoCancelada:
        _encerrar_sem_gravar("Validação", EXIT_CANCELADO)
    except ValidateError as e:
        rprint(f"[bold red]Erro:[/bold red] {e.message}")
        raise typer.Exit(code=e.exit_code)
    except Exception as e:
        _exit_on_unexpected(e, command="validate")


def _render_publish_text(view: PublishView) -> None:
    """Renderiza a resposta do `publish` — mesma árvore de `json`/`yaml`."""
    width = _largura_validate()

    identidade = [("API", f"[bold white]{view.api.name or '-'}[/bold white]")]
    detalhe = f"id {view.api.manager_id}"
    if view.api.version:
        detalhe += f"  ·  v{view.api.version}"
    if view.api.base_path:
        detalhe += f"  ·  {view.api.base_path}"
    identidade.append(("", f"[grey53]{detalhe}[/grey53]"))
    identidade.append(
        (
            "Revisão",
            f"[white]#{view.revision.revision_number}[/white] "
            f"[grey53](id {view.revision.manager_id})[/grey53]",
        )
    )
    identidade.append(("Modo", f"[grey53]{view.execution_mode}[/grey53]"))

    rprint()
    rprint(_painel_validate("Publicação", _grade_de_campos(identidade), width=width))
    rprint()

    if view.avisos:
        rprint(
            f"[bold]O que vai mudar no Manager[/bold]  "
            f"[yellow]{len(view.avisos)} aviso(s)[/yellow]"
        )
        _render_avisos_do_repo(
            [
                Achado(severity=SEVERIDADE_WARNING, scope=ESCOPO_REPOSITORIO, message=a)
                for a in view.avisos
            ]
        )
        rprint()

    gov = view.governanca
    if gov.stage_id is not None:
        rprint(
            f"[bold]Governança[/bold]  [green]liberada[/green] "
            f"[grey53]({len(gov.required)} atributo(s) exigido(s), nenhum "
            "faltando)[/grey53]"
        )
        rprint(
            f"  [grey53]workflow {gov.workflow_id} · stage {gov.stage_id} "
            "(lidos da revisão)[/grey53]"
        )
        rprint()

    # Recusa, divergência e erro encerram antes de chegar aqui: só o
    # sucesso conferido é renderizado.
    numero = view.revision.revision_number
    rprint(f"[bold]Revisão {numero}[/bold]  [green]gravada e conferida[/green]")
    rprint()


@sen_app.command("publish")
def publish(
    ctx: typer.Context,
    repo: Optional[Path] = typer.Option(
        None, "--repo", help="Repositório da API (default: diretório atual)."
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TEXT, "--output", "-o", help="Output format (text, json, yaml)."
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbosity only."),
):
    """
    Publish the API repository to the revision set in TARGET_REVISION_NUMBER.
    """
    try:
        service_factory = (ctx.obj or {}).get("publish_service_factory")
        if not callable(service_factory):
            rprint(
                "[bold red]Erro:[/bold red] Serviço de publicação indisponível "
                "no contexto."
            )
            raise typer.Exit(code=1)

        service = cast(Callable[[], Any], service_factory)()
        progresso = _ProgressoValidate(
            rotulo_inicial="Publicando", narrar=output is OutputFormat.TEXT
        )
        with progresso:
            view = service.publish(
                repo_path=repo or Path.cwd(),
                confirmar=lambda m: _confirmar_publicacao(m, progresso),
                progresso=progresso.etapa,
            )

        if not view.publicacao.attempted:
            _encerrar_sem_gravar("Publicação")

        display_output(
            view.to_document(),
            output_format=output,
            text_callback=lambda: _render_publish_text(view),
        )

    except typer.Exit:
        raise
    except _OperacaoCancelada:
        _encerrar_sem_gravar("Publicação", EXIT_CANCELADO)
    except ValidateError as e:
        rprint(f"[bold red]Erro:[/bold red] {e.message}")
        raise typer.Exit(code=e.exit_code)
    except Exception as e:
        _exit_on_unexpected(e, command="publish")


# ---------------------------------------------------------------------------
# sen diag — subcomandos de diagnóstico, ocultos (D-19)
#
# Servem a teste e investigação, não ao uso diário: expõem as etapas da cascata
# isoladamente. Ficam fora de `sen validate` porque ele é um comando com opções
# próprias, e transformá-lo em grupo mudaria a invocação do comando principal.
# ---------------------------------------------------------------------------

diag_app = typer.Typer(
    name="diag",
    help="Diagnóstico das etapas do validate (uso interno).",
    hidden=True,
    no_args_is_help=True,
)


@diag_app.command("structure")
def diag_structure(
    repo: Optional[Path] = typer.Option(
        None, "--repo", help="Repositório da API (default: diretório atual)."
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TEXT, "--output", "-o", help="Output format (text, json, yaml)."
    ),
):
    """Mostra a estrutura que a E1 descobre no repositório, sem tocar a rede."""
    from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
        LocalFileImporterAdapter,
    )
    from apiops_orchestrator.application.services.repo_importer_service import (
        RepoCanonicalReader,
    )

    alvo = repo or Path.cwd()
    lido = RepoCanonicalReader(LocalFileImporterAdapter()).carregar(str(alvo))

    documento = {
        "repo": str(alvo),
        "completo": lido.completo,
        "faltando": lido.faltando,
        "ignorados": lido.ignorados,
        "ilegiveis": lido.ilegiveis,
        "recursos": [
            {
                "slug": r.slug,
                "nome": r.nome,
                "operacoes": [
                    {"metodo": o.metodo, "path": o.path, "arquivo": o.arquivo}
                    for o in r.operacoes
                ],
            }
            for r in lido.recursos
        ],
    }

    def _texto() -> None:
        marca = "[green]completo[/green]" if lido.completo else "[red]incompleto[/red]"
        rprint(f"[bold]{alvo}[/bold]  {marca}")
        rprint(
            f"[grey53]{len(lido.recursos)} recurso(s) · "
            f"{lido.total_operacoes} operação(ões)[/grey53]\n"
        )
        for r in lido.recursos:
            rprint(f"  [bold]{r.slug}[/bold]  [grey53]{r.nome or '-'}[/grey53]")
            for o in r.operacoes:
                rprint(f"     {o.metodo:<7} {o.path or '-'}  [grey53]{o.arquivo}[/grey53]")
        for rotulo, itens, cor in (
            ("faltando", lido.faltando, "red"),
            ("ilegíveis", lido.ilegiveis, "red"),
            ("ignorados", lido.ignorados, "yellow"),
        ):
            if itens:
                rprint(f"\n[{cor}]{rotulo}:[/{cor}]")
                for i in itens:
                    rprint(f"  [{cor}]•[/{cor}] {i}")

    display_output(documento, output_format=output, text_callback=_texto)


sen_app.add_typer(diag_app)


@diag_app.command("template")
def diag_template(
    ctx: typer.Context,
    repo: Optional[Path] = typer.Option(
        None, "--repo", help="Repositório da API (default: diretório atual)."
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TEXT, "--output", "-o", help="Output format (text, json, yaml)."
    ),
):
    """Mostra a régua resolvida, o fluxo que ela exige e o snapshot."""
    from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
        LocalFileImporterAdapter,
    )
    from apiops_orchestrator.application.services.repo_importer_service import (
        RepoCanonicalReader,
    )

    try:
        fabrica = (ctx.obj or {}).get("regua_service_factory")
        if not callable(fabrica):
            rprint(
                "[bold red]Erro:[/bold red] Serviço de API-template "
                "indisponível no contexto."
            )
            raise typer.Exit(code=1)

        alvo = repo or Path.cwd()
        lido = RepoCanonicalReader(LocalFileImporterAdapter()).carregar(str(alvo))
        regua = cast(Callable[[], Any], fabrica)().carregar(lido.basic_info)

        documento = {
            "ruler": {
                "templateId": regua.template_id,
                "revisionNumber": regua.revision_number,
                "flowHash": regua.flow_hash,
                "interceptorsCount": regua.total,
            },
            "warnings": regua.avisos,
            "flow": [
                {
                    "executionPoint": i.get("executionPoint"),
                    "type": i.get("type"),
                    "customInterceptorId": i.get("customInterceptorId"),
                }
                for i in regua.interceptors
            ],
        }

        def _texto() -> None:
            rprint(
                f"[bold]API-template {regua.template_id}[/bold]  "
                f"[grey53]revisão #{regua.revision_number} · "
                f"{regua.total} interceptor(es) · {regua.flow_hash}[/grey53]\n"
            )
            for i in regua.interceptors:
                cid = i.get("customInterceptorId")
                rotulo = f"{i.get('type')}{'#' + str(cid) if cid else ''}"
                rprint(f"  [grey53]{i.get('executionPoint'):<7}[/grey53] {rotulo}")
            for aviso in regua.avisos:
                rprint(f"\n[yellow]WARNING[/yellow] {aviso}")

        display_output(documento, output_format=output, text_callback=_texto)

    except typer.Exit:
        raise
    except ValidateError as e:
        rprint(f"[bold red]Erro:[/bold red] {e.message}")
        raise typer.Exit(code=e.exit_code)
    except Exception as e:
        _exit_on_unexpected(e, command="diag template")


@diag_app.command("draft")
def diag_draft(
    ctx: typer.Context,
    repo: Optional[Path] = typer.Option(
        None, "--repo", help="Repositório da API (default: diretório atual)."
    ),
    output: OutputFormat = typer.Option(
        OutputFormat.TEXT, "--output", "-o", help="Output format (text, json, yaml)."
    ),
):
    """Mostra o estado da revisão alvo — somente leitura, nada é publicado."""
    from apiops_orchestrator.adapters.inbound.local_files_importer.local_file_importer_adapter import (
        LocalFileImporterAdapter,
    )
    from apiops_orchestrator.application.services.repo_importer_service import (
        RepoCanonicalReader,
    )
    from apiops_orchestrator.domain.services.interceptor_flow import particionar

    try:
        fabrica = (ctx.obj or {}).get("manager_api_factory")
        if not callable(fabrica):
            rprint("[bold red]Erro:[/bold red] Acesso ao Manager indisponível no contexto.")
            raise typer.Exit(code=1)

        alvo = repo or Path.cwd()
        lido = RepoCanonicalReader(LocalFileImporterAdapter()).carregar(str(alvo))
        spec = (lido.basic_info or {}).get("spec") or {}

        manager, settings = cast(Callable[[], Any], fabrica)()
        api = manager.get_api_by_id(spec.get("id")) or {}
        numero = settings.TARGET_REVISION_NUMBER or 1
        revisao = next(
            (r for r in (api.get("revisions") or []) if r.get("revisionNumber") == numero),
            None,
        )
        if revisao is None:
            rprint(
                f"[bold red]Erro:[/bold red] a API {spec.get('id')} não tem revisão "
                f"de número {numero}."
            )
            raise typer.Exit(code=1)

        draft = manager.get_revision(revisao["id"]) or {}
        governados, preservados = particionar(draft.get("interceptors"))

        documento = {
            "api": {"managerId": api.get("id"), "name": api.get("name")},
            "revision": {
                "managerId": draft.get("id"),
                "revisionNumber": draft.get("revisionNumber"),
                "workflowId": draft.get("workflowId"),
                "workflowStageId": draft.get("workflowStageId"),
            },
            "root": {"governed": len(governados), "preserved": len(preservados)},
            "resources": [
                {
                    "name": r.get("name"),
                    "interceptors": len(particionar(r.get("interceptors"))[0]),
                    "operations": [
                        {"method": o.get("method"), "path": o.get("path")}
                        for o in (r.get("operations") or [])
                    ],
                }
                for r in (draft.get("resources") or [])
            ],
        }

        def _texto() -> None:
            rev = documento["revision"]
            rprint(
                f"[bold]{api.get('name')}[/bold]  [grey53]API {api.get('id')}[/grey53]\n"
                f"revisão {rev['managerId']} (#{rev['revisionNumber']})  "
                f"[grey53]workflow {rev['workflowId']} · stage {rev['workflowStageId']} "
                "— lidos da revisão, reenviados intactos[/grey53]\n"
            )
            rprint(
                f"  raiz: {len(governados)} governado(s), "
                f"{len(preservados)} preservado(s)"
            )
            for r in documento["resources"]:
                rprint(
                    f"  [bold]{r['name']}[/bold]  [grey53]{r['interceptors']} "
                    f"interceptor(es)[/grey53]"
                )
                for o in r["operations"]:
                    rprint(f"     {str(o['method']):<7} {o['path']}")

        display_output(documento, output_format=output, text_callback=_texto)

    except typer.Exit:
        raise
    except ValidateError as e:
        rprint(f"[bold red]Erro:[/bold red] {e.message}")
        raise typer.Exit(code=e.exit_code)
    except Exception as e:
        _exit_on_unexpected(e, command="diag draft")
