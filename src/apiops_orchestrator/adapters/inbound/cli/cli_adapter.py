import importlib.metadata
import platform
import sys
import textwrap
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
from apiops_orchestrator.application.services.completeness_service import (
    CompletenessService,
)
from apiops_orchestrator.adapters.inbound.cli.output_format import OutputFormat
from apiops_orchestrator.adapters.inbound.cli.output_display import display_output
from apiops_orchestrator.application.exceptions.login_exceptions import LoginError
from apiops_orchestrator.application.exceptions.completeness_exceptions import (
    CompletenessError,
)
from apiops_orchestrator.domain.models.completeness_view import CompletenessView
from apiops_orchestrator.domain.models.api_catalog_model import ApiCatalogEntry
from apiops_orchestrator.domain.models.catalog_revision_model import CatalogRevisionInfo
from apiops_orchestrator.application.exceptions.listing_exceptions import (
    ApiCollectionError,
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


def _authenticate_with_feedback(service_builder: Callable[[], Any]):
    """Runs the login flow with a spinner only when stdout is a terminal.

    In non-interactive stdout (CI runner, redirected output, docker logs),
    Rich's Live turns each animation frame into plain new lines polluting
    machine-readable output, so we fall back to a single dim status line.
    """
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


@sen_app.command("login")
def login(ctx: typer.Context):
    """
    Authenticate against the Orchestrator Auth API and store the local session.
    Requires the SEN_CREDENTIALS environment variable (Base64 of client_id:secret).
    """
    try:
        login_service_factory = (ctx.obj or {}).get("login_service_factory")
        if not callable(login_service_factory):
            rprint(
                "[bold red]Erro:[/bold red] Serviço de login indisponível no contexto."
            )
            raise typer.Exit(code=1)

        print_welcome()
        session = _authenticate_with_feedback(
            cast(Callable[[], Any], login_service_factory)
        )
    except LoginError as e:
        rprint(f"[bold red]Erro de login:[/bold red] {e.message}")
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
                _window_footer(limit, offset)

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
        rprint(f"[bold red]Erro ao listar APIs:[/bold red] {e}")
        raise typer.Exit(code=1)


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
        rprint(f"[bold red]Erro ao consultar completude:[/bold red] {e}")
        raise typer.Exit(code=1)
