"""Comandos de navegação do ambiente: `sen get ...` e `sen export api`.

Pensados para explorar uma API do Manager **sem ter o repositório local** —
por um humano no terminal ou por um agente de código que só fala CLI. O nível
de detalhe cresce comando a comando, e toda saída tem `-o json`/`-o yaml`:

    sen list api                          quais APIs existem
    sen get api --id 400                  identidade, ambientes, revisões
    sen get resources --id 400            raiz → recursos → operações
    sen get interceptors --id 400         fluxo de cada escopo (--effective, --content)
    sen get interceptors --id 400 --item 19220   um interceptor inteiro
    sen get custom --custom-id 31         script de um Custom do catálogo
    sen get swagger --id 400              contrato OpenAPI da revisão
    sen export api --id 400 --dir ./repo  árvore canônica (o que o validate lê)

Só leitura: nenhum comando daqui escreve no Manager.
"""

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, cast

import typer
from rich import print as rprint
from rich.markup import escape
from rich.text import Text

from apiops_orchestrator.adapters.inbound.cli.output_display import display_output
from apiops_orchestrator.adapters.inbound.cli.output_format import OutputFormat
from apiops_orchestrator.application.exceptions.navigation_exceptions import (
    NavigationError,
)
from apiops_orchestrator.application.services.api_navigation_service import (
    ApiNavigationService,
)

SERVICE_KEY = "api_navigation_service_factory"

get_app = typer.Typer(
    name="get",
    help=(
        "Lê uma API do Manager em níveis de detalhe crescentes, sem precisar do "
        "repositório local: api → resources → interceptors → custom/swagger."
    ),
    no_args_is_help=True,
)

export_app = typer.Typer(
    name="export",
    help="Exporta a árvore canônica de uma revisão (o layout que `sen validate` lê).",
    no_args_is_help=True,
)

reveal_app = typer.Typer(
    name="reveal",
    help="Desmascara, de propósito e um por vez, um valor que as listagens escondem.",
    no_args_is_help=True,
)


# --------------------------------------------------------------------------- apoio


def _base():
    """Helpers compartilhados do CLI, importados tarde para evitar ciclo de import."""
    from apiops_orchestrator.adapters.inbound.cli import cli_adapter

    return cli_adapter


def _literal(value: Any) -> str:
    return escape(str(value))


def _print_error(message: Any) -> None:
    rprint(f"[bold red]Erro:[/bold red] {_literal(message)}")


def _service(ctx: typer.Context) -> ApiNavigationService:
    factory = (ctx.obj or {}).get(SERVICE_KEY)
    if not callable(factory):
        _print_error("Serviço de navegação indisponível no contexto.")
        raise typer.Exit(code=1)
    return cast(Callable[[], ApiNavigationService], factory)()


def _check_revision_options(revision: Optional[int], revision_id: Optional[int]) -> None:
    if revision is not None and revision_id is not None:
        _print_error(
            "Use --revision (número, como na UI) OU --revision-id (id do Manager), "
            "nunca os dois."
        )
        raise typer.Exit(code=1)


def _run(ctx: typer.Context, command: str, output: OutputFormat, work: Callable[[], Any]):
    """Executa a leitura com o feedback padrão e a tradução de erros do CLI."""
    base = _base()
    try:
        return base._run_with_feedback(
            work, label="Consultando o Manager...", narrate=output is OutputFormat.TEXT
        )
    except typer.Exit:
        raise
    except NavigationError as e:
        _print_error(e.message)
        raise typer.Exit(code=e.exit_code)
    except Exception as e:  # noqa: BLE001 - rede de segurança do comando
        base._exit_on_unexpected(e, command=command)


def _revision_option() -> Any:
    return typer.Option(
        None,
        "--revision",
        help="NÚMERO da revisão (REV #, como na UI). Ausente: a revisão corrente.",
    )


def _revision_id_option() -> Any:
    return typer.Option(
        None, "--revision-id", help="Id da revisão no Manager (REV ID), alternativa a --revision."
    )


def _output_option() -> Any:
    return typer.Option(
        OutputFormat.TEXT, "--output", "-o", help="Formato da saída (text, json, yaml)."
    )


def _dim(text: str) -> str:
    return f"[grey53]{text}[/grey53]"


def _header_line(api: Dict[str, Any], revision: Dict[str, Any]) -> str:
    deployed = ", ".join(revision.get("deployedIn") or [])
    cycle = revision.get("lifeCycle") or "-"
    live = f" · no ar em {_literal(deployed)}" if deployed else ""
    return (
        f"[bold]{_literal(api.get('name'))}[/bold]  "
        + _dim(
            f"API {api.get('id')} · revisão #{revision.get('number')} "
            f"(id {revision.get('id')}, {_literal(cycle)}){live}"
        )
    )


def _destination_text(destination: Dict[str, Any]) -> str:
    url = destination.get("url")
    timeout = destination.get("timeout")
    if not url and not timeout:
        return ""
    parts = [f"destino: {_literal(url)}" if url else "destino: (herdado)"]
    if timeout:
        parts.append(f"timeout {_literal(timeout)}")
    return " · ".join(parts)


def _counts_text(counts: Dict[str, int], inherits: Optional[bool]) -> str:
    own = counts.get("own", 0)
    effective = counts.get("effective", 0)
    removes = counts.get("removes", 0)
    if inherits is None:
        head = f"{own} próprio(s)"
    elif inherits:
        head = f"herda · {own} próprio(s)"
    else:
        head = f"quebra herança (remove {removes}) · {own} próprio(s)"
    tail = f" → executa {effective}"
    preserved = counts.get("preserved", 0)
    other = f" · {preserved} fora de FIRST/SECOND" if preserved else ""
    return head + tail + other


# --------------------------------------------------------------------------- get api


@get_app.command("api")
def get_api(
    ctx: typer.Context,
    api_id: int = typer.Option(..., "--id", help="ID da API no Manager."),
    output: OutputFormat = _output_option(),
):
    """Identidade, visibilidade, ambientes e revisões de UMA API (nível 1)."""
    document = _run(ctx, "get api", output, lambda: _service(ctx).api_detail(api_id))

    def _text() -> None:
        base = _base()
        current = document.get("lastRevisionNumber")
        rprint(
            f"[bold]{_literal(document.get('name'))}[/bold]  "
            + _dim(f"API {document.get('id')}")
        )
        rprint(
            _dim(
                f"versão {_literal(document.get('version') or '-')} · basePath "
                f"{_literal(document.get('basePath') or '-')} · "
                f"{_literal(document.get('apiType') or '-')} · revisão corrente "
                f"#{current if current is not None else '-'}"
            )
        )
        if document.get("description"):
            rprint(_literal(document["description"]))
        visibility = document.get("visibility") or {}
        bits = [f"visibilidade: {_literal(visibility.get('type') or '-')}"]
        if visibility.get("owner"):
            bits.append(f"dono {_literal(visibility['owner'])}")
        if visibility.get("groupName"):
            bits.append(f"grupo {_literal(visibility['groupName'])}")
        if visibility.get("users"):
            bits.append("usuários " + _literal(", ".join(visibility["users"])))
        rprint(_dim(" · ".join(bits)))
        responsible = (document.get("responsible") or {}).get("username")
        if responsible:
            rprint(_dim(f"responsável: {_literal(responsible)}"))
        tags = [
            f"{t.get('attributeName')}={', '.join(t.get('tags') or []) or '-'}"
            for t in document.get("apiTags") or []
        ]
        if tags:
            rprint(_dim("tags: " + _literal(" · ".join(tags))))

        environments = document.get("environments") or []
        if environments:
            rprint("\n[bold cyan]AMBIENTES[/bold cyan]")
            base._render_grade(
                [
                    (
                        str(env.get("id")),
                        str(env.get("name") or ""),
                        str(env.get("inboundUrl") or "-"),
                        (
                            f"rev #{env['deployedRevision'].get('number')} "
                            f"(id {env['deployedRevision'].get('id')})"
                            if env.get("deployedRevision")
                            else "-"
                        ),
                    )
                    for env in environments
                ],
                header=("ENV ID", "AMBIENTE", "INBOUND URL", "NO AR"),
                column_justify=("right", None, None, None),
            )

        revisions = document.get("revisions") or []
        rprint("\n[bold cyan]REVISÕES[/bold cyan]")
        if revisions:
            base._render_grade(
                [
                    (
                        f"{r.get('number')}{' *' if r.get('current') else ''}",
                        str(r.get("id")),
                        str(r.get("lifeCycle") or "-"),
                        str(r.get("stageName") or r.get("workflowStageId") or "-"),
                        str(r.get("resources")),
                        str(r.get("operations")),
                        str(r.get("rootInterceptors")),
                        ", ".join(r.get("deployedIn") or []) or "-",
                    )
                    for r in revisions
                ],
                header=("REV #", "REV ID", "CICLO", "STAGE", "RECURSOS", "OPERAÇÕES", "RAIZ", "NO AR"),
                column_justify=("right", "right", None, None, "right", "right", "right", None),
                column_decorators=((lambda v: Text(str(v), style="bold white")),),
            )
            rprint(_dim("* revisão corrente"))
        else:
            rprint("[yellow]Nenhuma revisão.[/yellow]")
        rev = f" --revision {current}" if current is not None else ""
        rprint(
            _dim(
                f"\npróximos passos: sen get resources --id {document.get('id')}{rev} · "
                f"sen get interceptors --id {document.get('id')}{rev} · "
                f"sen get governance --id {document.get('id')}{rev} · "
                f"sen get impact --id {document.get('id')}"
            )
        )

    display_output(document, output_format=output, text_callback=_text)


# --------------------------------------------------------------------------- get resources


@get_app.command("resources")
def get_resources(
    ctx: typer.Context,
    api_id: int = typer.Option(..., "--id", help="ID da API no Manager."),
    revision: Optional[int] = _revision_option(),
    revision_id: Optional[int] = _revision_id_option(),
    output: OutputFormat = _output_option(),
):
    """Raiz → recursos → operações de uma revisão, com destino e contagens (nível 2)."""
    _check_revision_options(revision, revision_id)
    document = _run(
        ctx,
        "get resources",
        output,
        lambda: _service(ctx).structure(api_id, revision, revision_id),
    )

    def _text() -> None:
        rprint(_header_line(document["api"], document["revision"]))
        totals = document.get("totals") or {}
        rprint(
            _dim(f"{totals.get('resources', 0)} recurso(s) · {totals.get('operations', 0)} operação(ões)\n")
        )
        root = document["root"]
        line = "[bold]all[/bold]  " + _dim(_counts_text(root["interceptors"], None))
        dest = _destination_text(root["destination"])
        rprint(line + (f"  {_dim(dest)}" if dest else ""))
        for resource in document.get("resources") or []:
            line = (
                f"  [bold]{_literal(resource.get('name'))}[/bold]  "
                + _dim(f"recurso {resource.get('id')} · slug {_literal(resource.get('slug'))}")
            )
            rprint(line)
            rprint("     " + _dim(_counts_text(resource["interceptors"], resource.get("inherits"))))
            dest = _destination_text(resource["destination"])
            if dest:
                rprint("     " + _dim(dest))
            for op in resource.get("operations") or []:
                rprint(
                    f"     {_literal(op.get('method')):<7} {_literal(op.get('path'))}  "
                    + _dim(f"operação {op.get('id')}")
                )
                rprint("        " + _dim(_counts_text(op["interceptors"], op.get("inherits"))))
                dest = _destination_text(op["destination"])
                if dest:
                    rprint("        " + _dim(dest))
        api = document["api"]
        rev = document["revision"]
        rprint(
            _dim(
                f"\npróximos passos: sen get interceptors --id {api.get('id')} --revision "
                f"{rev.get('number')} [--resource <nome> | --operation \"<MÉTODO> <path>\"] "
                "[--effective] [--content]"
            )
        )

    display_output(document, output_format=output, text_callback=_text)


# --------------------------------------------------------------------------- get interceptors


def _print_items(items: List[Dict[str, Any]], indent: str, own_ids=None, content: bool = False) -> None:
    for item in items:
        origin = ""
        if own_ids is not None:
            origin = "  " + _dim("próprio" if item.get("id") in own_ids else "herdado")
        label = _literal(item.get("type") or "-")
        summary = item.get("summary") or ""
        rprint(
            f"{indent}[cyan][{item.get('id')}][/cyan] {str(item.get('position')):<3} "
            f"{label:<22} {_dim(_literal(summary))}{origin}"
        )
        if content and "content" in item and item["content"] is not None:
            text = (
                json.dumps(item["content"], indent=2, ensure_ascii=False)
                if isinstance(item["content"], (dict, list))
                else str(item["content"])
            )
            for line in text.splitlines():
                rprint(f"{indent}      {_literal(line)}")


def _print_scope(scope: Dict[str, Any], effective: bool, content: bool) -> None:
    kind = scope.get("kind")
    indent = {"root": "", "resource": "  ", "operation": "     "}.get(kind, "")
    inner = indent + "  "
    if kind == "root":
        title = "[bold]all[/bold]  " + _dim("raiz")
    elif kind == "resource":
        title = f"[bold]{_literal(scope.get('label'))}[/bold]  " + _dim(f"recurso {scope.get('id')}")
    else:
        title = f"[bold]{_literal(scope.get('label'))}[/bold]  " + _dim(f"operação {scope.get('id')}")
    rprint(indent + title + "  " + _dim(_counts_text(scope["counts"], scope.get("inherits"))))
    dest = _destination_text(scope.get("destination") or {})
    if dest:
        rprint(inner + _dim(dest))
    for removal in scope.get("removes") or []:
        marker = "" if removal.get("resolved") else "  (não está no fluxo herdado)"
        rprint(
            f"{inner}[red]remove[/red]    ← [cyan][{removal.get('targetId')}][/cyan] "
            f"{_literal(removal.get('type'))} ({_literal(removal.get('executionPoint'))}){_dim(marker)}"
        )
    flows = scope["effective"] if effective else scope["own"]
    own_ids = (
        {i.get("id") for point in scope["own"].values() for i in point} if effective else None
    )
    for point, title in (("request", "request "), ("response", "response")):
        items = flows.get(point) or []
        if not items:
            continue
        rprint(f"{inner}[bold]{title}[/bold]")
        _print_items(items, inner + "   ", own_ids=own_ids, content=content)
    if not any(flows.get(p) for p in ("request", "response")):
        rprint(inner + _dim("(nenhum interceptor " + ("executa" if effective else "próprio") + ")"))


@get_app.command("interceptors")
def get_interceptors(
    ctx: typer.Context,
    api_id: int = typer.Option(..., "--id", help="ID da API no Manager."),
    revision: Optional[int] = _revision_option(),
    revision_id: Optional[int] = _revision_id_option(),
    resource: Optional[str] = typer.Option(
        None, "--resource", help="Recorta um recurso: nome, slug ou id (e as suas operações)."
    ),
    operation: Optional[str] = typer.Option(
        None,
        "--operation",
        help='Recorta uma operação: "<MÉTODO> <path>" (ex.: "POST /oauth2/token") ou id.',
    ),
    effective: bool = typer.Option(
        False,
        "--effective",
        help="Mostra o fluxo que cada escopo EXECUTA (herdado − removido + próprio), não só o próprio.",
    ),
    content: bool = typer.Option(
        False, "--content", help="Inclui o conteúdo (configuração) de cada interceptor."
    ),
    item: Optional[int] = typer.Option(
        None, "--item", help="Zoom em UM interceptor pelo id do Manager: conteúdo inteiro."
    ),
    output: OutputFormat = _output_option(),
):
    """Fluxo de interceptors por escopo (nível 3) ou um interceptor inteiro (--item)."""
    _check_revision_options(revision, revision_id)
    if item is not None and (resource or operation or effective or content):
        _print_error("--item não combina com --resource, --operation, --effective ou --content.")
        raise typer.Exit(code=1)

    if item is not None:
        document = _run(
            ctx,
            "get interceptors",
            output,
            lambda: _service(ctx).interceptor(api_id, item, revision, revision_id),
        )

        def _text_item() -> None:
            rprint(_header_line(document["api"], document["revision"]))
            scope = document["scope"]
            where = {
                "root": "raiz (all)",
                "resource": f"recurso {_literal(scope.get('label'))} ({scope.get('id')})",
                "operation": (
                    f"operação {_literal(scope.get('label'))} ({scope.get('id')}) "
                    f"do recurso {_literal(scope.get('resource'))}"
                ),
            }.get(scope.get("kind"), _literal(scope.get("label")))
            data = document["interceptor"]
            rprint(_dim(f"escopo: {where}\n"))
            rprint(
                f"[cyan][{data.get('id')}][/cyan] [bold]{_literal(data.get('type'))}[/bold]  "
                + _dim(
                    f"{_literal(data.get('executionPoint'))} · posição {data.get('position')} · "
                    f"status {_literal(data.get('status'))}"
                    + (" · não governado" if not data.get("governed") else "")
                )
            )
            if data.get("customInterceptorId") is not None:
                rprint(
                    _dim(
                        f"custom interceptor #{data['customInterceptorId']}"
                        + (f' "{_literal(data.get("customName"))}"' if data.get("customName") else "")
                        + f" → sen get custom --custom-id {data['customInterceptorId']}"
                    )
                )
            if data.get("parentId") is not None:
                rprint(_dim(f"marcação REMOVED do item herdado [{data['parentId']}]"))
            body = data.get("content")
            rprint("\n[bold]content[/bold]")
            if isinstance(body, dict) and data.get("type") == "Custom" and "script" in body:
                meta = {k: v for k, v in body.items() if k != "script"}
                rprint(_literal(json.dumps(meta, indent=2, ensure_ascii=False)))
                rprint("\n[bold]script[/bold]")
                rprint(_literal(body.get("script") or ""))
            elif isinstance(body, (dict, list)):
                rprint(_literal(json.dumps(body, indent=2, ensure_ascii=False)))
            else:
                rprint(_literal(body if body is not None else "(vazio)"))

        display_output(document, output_format=output, text_callback=_text_item)
        return

    document = _run(
        ctx,
        "get interceptors",
        output,
        lambda: _service(ctx).interceptors(
            api_id,
            revision,
            revision_id,
            resource=resource,
            operation=operation,
            effective=effective,
            include_content=content,
        ),
    )

    def _text() -> None:
        rprint(_header_line(document["api"], document["revision"]))
        mode = (
            "fluxo que cada escopo EXECUTA (herdado − removido + próprio)"
            if effective
            else "interceptors PRÓPRIOS de cada escopo"
        )
        hints = []
        if not effective:
            hints.append("--effective mostra o que executa")
        if not content:
            hints.append("--content inclui a configuração")
        hints.append("--item <id> abre um interceptor")
        rprint(_dim(f"modo: {mode}  ({' · '.join(hints)})\n"))
        for scope in document.get("scopes") or []:
            _print_scope(scope, effective=effective, content=content)

    display_output(document, output_format=output, text_callback=_text)


# --------------------------------------------------------------------------- get custom


@get_app.command("custom")
def get_custom(
    ctx: typer.Context,
    custom_id: int = typer.Option(
        ..., "--custom-id", help="Id do custom interceptor no catálogo (customInterceptorId)."
    ),
    script_only: bool = typer.Option(
        False, "--script-only", help="Escreve só o script, cru (para redirecionar a um arquivo)."
    ),
    output: OutputFormat = _output_option(),
):
    """Nome e script de um Custom interceptor do catálogo do Manager."""
    document = _run(
        ctx,
        "get custom",
        output if not script_only else OutputFormat.JSON,
        lambda: _service(ctx).custom_interceptor(custom_id),
    )
    if script_only:
        import sys

        script = document.get("script") or ""
        sys.stdout.write(script if script.endswith("\n") else script + "\n")
        return

    def _text() -> None:
        rprint(
            f"[bold]{_literal(document.get('name'))}[/bold]  "
            + _dim(f"custom interceptor #{document.get('id')}")
        )
        rprint("\n[bold]script[/bold]")
        rprint(_literal(document.get("script") or "(vazio)"))

    display_output(document, output_format=output, text_callback=_text)


# --------------------------------------------------------------------------- get swagger


@get_app.command("swagger")
def get_swagger(
    ctx: typer.Context,
    api_id: int = typer.Option(..., "--id", help="ID da API no Manager."),
    revision: Optional[int] = _revision_option(),
    revision_id: Optional[int] = _revision_id_option(),
    output: OutputFormat = typer.Option(
        OutputFormat.YAML, "--output", "-o", help="Formato da saída (yaml, json)."
    ),
):
    """Contrato OpenAPI (swagger) da revisão, como o Manager o guarda."""
    _check_revision_options(revision, revision_id)
    document = _run(
        ctx,
        "get swagger",
        output,
        lambda: _service(ctx).swagger(api_id, revision, revision_id),
    )
    # O contrato é um documento, não uma grade: em `text` sai como YAML.
    display_output(
        document,
        output_format=OutputFormat.YAML if output is OutputFormat.TEXT else output,
    )


# --------------------------------------------------------------------------- export api


@export_app.command("api")
def export_api(
    ctx: typer.Context,
    api_id: int = typer.Option(..., "--id", help="ID da API no Manager."),
    revision: Optional[int] = _revision_option(),
    revision_id: Optional[int] = _revision_id_option(),
    directory: Optional[Path] = typer.Option(
        None,
        "--dir",
        help="Pasta onde escrever a árvore. Ausente: os arquivos saem na tela.",
    ),
    force: bool = typer.Option(
        False, "--force", help="Sobrescreve arquivos já existentes em --dir."
    ),
    output: OutputFormat = _output_option(),
):
    """Materializa a árvore canônica da revisão (api-basic-info, all, resources/...)."""
    _check_revision_options(revision, revision_id)
    api, rev, result = _run(
        ctx,
        "export api",
        output,
        lambda: _service(ctx).export(api_id, revision, revision_id),
    )
    from apiops_orchestrator.domain.services.api_navigation import (
        api_header,
        revision_header,
    )

    header = {"api": api_header(api), "revision": revision_header(api, rev)}
    files = [{"path": f.file_path, "text": f.text} for f in result.files]

    written: List[str] = []
    if directory is not None:
        existing = [
            f.file_path for f in result.files if (directory / f.file_path).exists()
        ]
        if existing and not force:
            _print_error(
                f"{len(existing)} arquivo(s) já existem em {directory} "
                f"(ex.: {existing[0]}). Use --force para sobrescrever."
            )
            raise typer.Exit(code=1)
        for f in result.files:
            target = directory / f.file_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(f.text, encoding="utf-8")
            written.append(f.file_path)

    document = {
        **header,
        "directory": str(directory) if directory is not None else None,
        "files": (
            [{"path": p} for p in written] if directory is not None else files
        ),
        "warnings": list(result.warnings),
    }

    def _text() -> None:
        rprint(_header_line(header["api"], header["revision"]))
        if directory is not None:
            rprint(_dim(f"{len(written)} arquivo(s) escritos em {_literal(directory)}\n"))
            for path in written:
                rprint(f"  {_literal(path)}")
        else:
            rprint(_dim(f"{len(files)} arquivo(s) · use --dir <pasta> para gravar\n"))
            for f in files:
                rprint(f"[bold cyan]# ==> {_literal(f['path'])}[/bold cyan]")
                rprint(_literal(f["text"].rstrip("\n")))
                rprint("")
        for warning in result.warnings:
            rprint(f"[yellow]AVISO[/yellow] {_literal(warning)}")

    display_output(document, output_format=output, text_callback=_text)


# ===========================================================================
# Catálogos do tenant (sen list ...) e governança (sen get workflow|governance|impact)
# Fundados no mapeamento APIM/AG: rotas de leitura capturadas do wire real.
# ===========================================================================


def _grade(rows, header, justify=None) -> None:
    _base()._render_grade(rows, header=header, column_justify=justify)


def list_environments(
    ctx: typer.Context,
    output: OutputFormat = _output_option(),
):
    """Ambientes do tenant: id (usado pelo deploy na esteira), nome, inbound URL."""
    rows = _run(ctx, "list environments", output, lambda: _service(ctx).environments())

    def _text() -> None:
        if not rows:
            rprint("[yellow]Nenhum ambiente.[/yellow]")
            return
        _grade(
            [
                (
                    str(e.get("id")),
                    str(e.get("name") or ""),
                    str(e.get("inboundUrl") or "-"),
                    "sim" if e.get("isDeployable") else "não",
                    str(e.get("description") or "-"),
                )
                for e in rows
            ],
            header=("ENV ID", "AMBIENTE", "INBOUND URL", "DEPLOY?", "DESCRIÇÃO"),
            justify=("right", None, None, None, None),
        )

    display_output(rows, output_format=output, text_callback=_text)


def list_workflows(
    ctx: typer.Context,
    output: OutputFormat = _output_option(),
):
    """Workflows do Adaptive Governance e os seus stages, em ordem."""
    rows = _run(ctx, "list workflows", output, lambda: _service(ctx).workflows())

    def _text() -> None:
        if not rows:
            rprint("[yellow]Nenhum workflow.[/yellow]")
            return
        for w in rows:
            group = f" · grupo {_literal(w.get('group'))}" if w.get("group") else ""
            rprint(
                f"[bold]{_literal(w.get('name'))}[/bold]  "
                + _dim(f"workflow {w.get('id')} · {_literal(w.get('category'))}{group}")
            )
            for s in w.get("stages") or []:
                needs = []
                if s.get("maturityRequired"):
                    needs.append(f"maturidade ≥ {s['maturityRequired']:g}%")
                if s.get("interceptors"):
                    needs.append(f"{s['interceptors']} interceptor(es)")
                if s.get("attributes"):
                    needs.append(f"{s['attributes']} atributo(s)")
                envs = s.get("deployableEnvironments") or []
                deploy = (
                    "deploy em " + ", ".join(str(e) for e in envs) if envs else "sem deploy"
                )
                rprint(
                    f"  {s.get('position')}. [bold]{_literal(s.get('name'))}[/bold]  "
                    + _dim(f"stage {s.get('id')} · {deploy}"
                           + (" · exige " + ", ".join(needs) if needs else " · sem requisitos"))
                )
        rprint(_dim("\ndetalhe dos requisitos: sen get workflow --id <workflow>"))

    display_output(rows, output_format=output, text_callback=_text)


def list_attributes(
    ctx: typer.Context,
    output: OutputFormat = _output_option(),
):
    """Atributos de governança (os `apiTags` do api-basic-info) e as tags válidas."""
    rows = _run(ctx, "list attributes", output, lambda: _service(ctx).attributes())

    def _text() -> None:
        if not rows:
            rprint("[yellow]Nenhum atributo.[/yellow]")
            return
        _grade(
            [
                (
                    str(a.get("id")),
                    str(a.get("name") or ""),
                    ", ".join(a.get("tags") or []) or "-",
                    "sim" if a.get("inUse") else "não",
                )
                for a in rows
            ],
            header=("ID", "ATRIBUTO", "TAGS VÁLIDAS", "EM USO"),
            justify=("right", None, None, None),
        )
        rprint(
            _dim(
                "atributo com tags cadastradas só conta para a governança se o apiTags "
                "declarar ao menos uma delas"
            )
        )

    display_output(rows, output_format=output, text_callback=_text)


def list_interceptors(
    ctx: typer.Context,
    custom: bool = typer.Option(False, "--custom", help="Só os customs (JavaScript/Java)."),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtra pela tag do catálogo."),
    output: OutputFormat = _output_option(),
):
    """Catálogo de tipos de interceptor: o `type` aceito nos YAML e o id dos customs."""
    rows = _run(
        ctx,
        "list interceptors",
        output,
        lambda: _service(ctx).interceptor_catalog(custom_only=custom, tag=tag),
    )

    def _text() -> None:
        if not rows:
            rprint("[yellow]Nenhum interceptor no catálogo com esse filtro.[/yellow]")
            return
        _grade(
            [
                (
                    str(i.get("name") or ""),
                    "custom" if i.get("kind") == "custom" else "nativo",
                    str(i.get("id")) if i.get("id") is not None else "-",
                    "+".join(i.get("executionPoints") or []) or "-",
                    str(i.get("flowType") or "-"),
                    ", ".join(i.get("tags") or []) or "-",
                )
                for i in rows
            ],
            header=("TYPE", "ORIGEM", "CUSTOM ID", "PONTOS", "FLOW", "TAGS"),
            justify=(None, None, "right", None, None, None),
        )
        rprint(_dim("script de um custom: sen get custom --custom-id <CUSTOM ID>"))

    display_output(rows, output_format=output, text_callback=_text)


# --------------------------------------------------------------------------- get workflow


def _print_requisites(stage: Dict[str, Any], indent: str = "  ") -> None:
    printed = False
    if stage.get("maturityRequired"):
        rprint(f"{indent}maturidade ≥ {stage['maturityRequired']:g}%")
        printed = True
    for r in stage.get("interceptors") or []:
        rprint(f"{indent}{_literal(r.get('description'))}")
        printed = True
    for a in stage.get("attributes") or []:
        verb = "deve declarar" if a.get("mustHave") else "não pode declarar"
        label = a.get("name") or f"atributo {a.get('attributeId')}"
        rprint(f"{indent}{verb} o atributo {_literal(label)}")
        printed = True
    for e in stage.get("environments") or []:
        if e.get("mandatoryDeployment"):
            rprint(
                f"{indent}deploy {_literal(e['mandatoryDeployment'])} em "
                f"{_literal(e.get('name') or e.get('id'))}"
            )
            printed = True
    allowed = stage.get("deployableEnvironments") or []
    if allowed:
        rprint(
            f"{indent}"
            + _dim("deploy permitido em: " + ", ".join(
                _literal(f"{e.get('name')} ({e.get('id')})" if e.get("name") else e.get("id"))
                for e in allowed
            ))
        )
    elif not printed:
        rprint(f"{indent}" + _dim("sem requisitos · sem ambiente de deploy"))
    else:
        rprint(f"{indent}" + _dim("nenhum ambiente de deploy permitido"))


@get_app.command("workflow")
def get_workflow(
    ctx: typer.Context,
    workflow_id: int = typer.Option(..., "--id", help="Id do workflow (veja sen list workflows)."),
    output: OutputFormat = _output_option(),
):
    """Stages de um workflow e o que cada um exige (maturidade, interceptors, atributos, ambientes)."""
    document = _run(ctx, "get workflow", output, lambda: _service(ctx).workflow(workflow_id))

    def _text() -> None:
        group = f" · grupo {_literal(document.get('group'))}" if document.get("group") else ""
        rprint(
            f"[bold]{_literal(document.get('name'))}[/bold]  "
            + _dim(f"workflow {document.get('id')} · {_literal(document.get('category'))}{group}")
        )
        if document.get("description"):
            rprint(_dim(_literal(document["description"])))
        for s in document.get("stages") or []:
            rprint(f"\n{s.get('position')}. [bold]{_literal(s.get('name'))}[/bold]  " + _dim(f"stage {s.get('id')}"))
            _print_requisites(s, indent="   ")

    display_output(document, output_format=output, text_callback=_text)


# --------------------------------------------------------------------------- get governance


_STATUS_STYLE = {"ok": "[green]OK  [/green]", "fail": "[red]FALHA[/red]", "unknown": "[yellow]?   [/yellow]"}


def _print_verdicts(block: Dict[str, Any], title: str) -> None:
    stage = block["stage"]
    summary = block["summary"]
    overall = {"ok": "[green]atende[/green]", "fail": "[red]não atende[/red]", "unknown": "[yellow]não verificável[/yellow]"}[
        summary["overall"]
    ]
    rprint(
        f"\n[bold cyan]{title}[/bold cyan] [bold]{_literal(stage.get('name'))}[/bold]  "
        + _dim(f"stage {stage.get('id')} · posição {stage.get('position')}")
        + f"  → {overall}"
    )
    if not block["verdicts"]:
        rprint("  " + _dim("sem requisitos"))
    for v in block["verdicts"]:
        line = f"  {_STATUS_STYLE[v['status']]} {_literal(v['requirement'])}"
        if v.get("detail"):
            line += "  " + _dim(_literal(v["detail"]))
        rprint(line)
        for scope in v.get("failingScopes") or []:
            rprint(f"           [red]↳[/red] {_literal(scope)}")
    allowed = stage.get("deployableEnvironments") or []
    if allowed:
        rprint(
            "  "
            + _dim("deploy permitido em: " + ", ".join(
                _literal(f"{e.get('name')} ({e.get('id')})" if e.get("name") else e.get("id"))
                for e in allowed
            ))
        )


@get_app.command("governance")
def get_governance(
    ctx: typer.Context,
    api_id: int = typer.Option(..., "--id", help="ID da API no Manager."),
    revision: Optional[int] = _revision_option(),
    revision_id: Optional[int] = _revision_id_option(),
    output: OutputFormat = _output_option(),
):
    """A revisão contra o Adaptive Governance: stage atual, requisitos atendidos e o que falta para o próximo."""
    _check_revision_options(revision, revision_id)
    document = _run(
        ctx,
        "get governance",
        output,
        lambda: _service(ctx).governance(api_id, revision, revision_id),
    )

    def _text() -> None:
        rprint(_header_line(document["api"], document["revision"]))
        workflow = document.get("workflow")
        stage = document.get("stage")
        if workflow:
            rprint(
                _dim(
                    f"workflow {_literal(workflow.get('name'))} ({workflow.get('id')}, "
                    f"{_literal(workflow.get('category'))})"
                    + (f" · stage atual {_literal(stage.get('name'))} ({stage.get('id')})" if stage else "")
                )
            )
        maturity = document.get("maturity") or {}
        if maturity.get("score") is not None:
            rprint(
                _dim(
                    f"maturidade (completeness): {maturity['score']:g}% · "
                    f"{maturity.get('suggestions')} sugestão(ões) → sen completeness --id "
                    f"{document['api'].get('id')} --revision {document['revision'].get('id')}"
                )
            )
        deployed = document.get("deployedIn") or []
        if deployed:
            rprint(_dim("no ar em: " + ", ".join(
                _literal(f"{e.get('name')} ({e.get('id')})" if e.get("name") else e.get("id")) for e in deployed
            )))
        if document.get("current"):
            _print_verdicts(document["current"], "stage atual")
        if document.get("next"):
            _print_verdicts(document["next"], "próximo stage")
        elif document.get("current"):
            rprint(_dim("\núltimo stage do workflow: não há próximo"))
        for warning in document.get("warnings") or []:
            rprint(f"[yellow]AVISO[/yellow] {_literal(warning)}")

    display_output(document, output_format=output, text_callback=_text)


# --------------------------------------------------------------------------- get impact


@get_app.command("impact")
def get_impact(
    ctx: typer.Context,
    api_id: int = typer.Option(..., "--id", help="ID da API no Manager."),
    environment_id: Optional[int] = typer.Option(
        None, "--env", help="Id do ambiente (sen list environments). Ausente: o primeiro onde a API está no ar."
    ),
    output: OutputFormat = _output_option(),
):
    """Grafo de impacto da API: rotas com destino, planos e apps que a consomem."""
    document = _run(ctx, "get impact", output, lambda: _service(ctx).impact(api_id, environment_id))

    def _text() -> None:
        api = document["api"]
        env = document.get("environment") or {}
        totals = document.get("totals") or {}
        rprint(
            f"[bold]{_literal(api.get('name'))}[/bold]  "
            + _dim(
                f"API {api.get('id')} · ambiente {_literal(env.get('name') or env.get('id'))} "
                f"({env.get('id')}) · revisão #{document.get('revisionNumber')}"
            )
        )
        rprint(
            _dim(
                f"{totals.get('routes', 0)} rota(s) · {totals.get('operations', 0)} operação(ões) · "
                f"{totals.get('plans', 0)} plano(s) · {totals.get('apps', 0)} app(s)\n"
            )
        )
        rprint("[bold cyan]ROTAS[/bold cyan]")
        for route in document.get("routes") or []:
            rprint(f"  {_literal(route.get('path'))}")
            for m in route.get("methods") or []:
                dest = f"  → {_literal(m.get('destination'))}" if m.get("destination") else ""
                rprint(f"     {_literal(m.get('method')):<7}" + _dim(f"operação {m.get('operationId')}{dest}"))
        rprint("\n[bold cyan]CONSUMO[/bold cyan]")
        plans = document.get("plans") or []
        if not plans:
            rprint("  " + _dim("nenhum plano vinculado neste ambiente"))
        for plan in plans:
            rprint(f"  plano [bold]{_literal(plan.get('name'))}[/bold]")
            for app in plan.get("apps") or []:
                rprint(
                    f"     app {_literal(app.get('name'))}  "
                    + _dim(f"{_literal(app.get('status') or '-')} · appId {app.get('appId')}")
                )
            if not plan.get("apps"):
                rprint("     " + _dim("sem apps"))

    display_output(document, output_format=output, text_callback=_text)


# ===========================================================================
# Consumo e infraestrutura: apps, planos, tokens, variáveis, pessoas, gateway
# (sen list apps|plans|tokens|variables|users|teams|inbounds|gateway-pools,
#  sen get app|plan|environment). Credenciais nunca aparecem: a plataforma
# mascara clientId/secret/código e o domínio descarta esses campos.
# ===========================================================================


def _api_option(help_text: str = "Recorta pela API (id no Manager).") -> Any:
    return typer.Option(None, "--api", help=help_text)


def list_apps(
    ctx: typer.Context,
    api_id: Optional[int] = _api_option("Só apps inscritos num plano desta API (id)."),
    query: Optional[str] = typer.Option(None, "--query", help="Filtra por nome ou desenvolvedor."),
    output: OutputFormat = _output_option(),
):
    """Apps (consumidores) e as APIs/planos que cada um assina. Sem credenciais."""
    rows = _run(ctx, "list apps", output, lambda: _service(ctx).apps(api_id=api_id, query=query))

    def _text() -> None:
        if not rows:
            rprint("[yellow]Nenhum app com esse filtro.[/yellow]")
            return
        _grade(
            [
                (
                    str(a.get("id")),
                    str(a.get("name") or ""),
                    str(a.get("status") or "-"),
                    str(a.get("developer") or "-"),
                    "; ".join(
                        f"{s.get('name')} [{', '.join(p.get('name') or '' for p in s.get('plans') or []) or 'sem plano'}]"
                        for s in a.get("apis") or []
                    )
                    or "-",
                    str(a.get("accessTokens")),
                )
                for a in rows
            ],
            header=("APP ID", "APP", "STATUS", "DEV", "APIS [PLANOS]", "TOKENS"),
            justify=("right", None, None, None, None, "right"),
        )
        rprint(_dim("detalhe: sen get app --id <APP ID> · tokens: sen list tokens --app <APP ID>"))

    display_output(rows, output_format=output, text_callback=_text)


@get_app.command("app")
def get_app_command(
    ctx: typer.Context,
    app_id: int = typer.Option(..., "--id", help="Id do app (sen list apps)."),
    output: OutputFormat = _output_option(),
):
    """Um app: status, desenvolvedor e as assinaturas API → planos. Sem credenciais."""
    document = _run(ctx, "get app", output, lambda: _service(ctx).app(app_id))

    def _text() -> None:
        rprint(
            f"[bold]{_literal(document.get('name'))}[/bold]  "
            + _dim(f"app {document.get('id')} · {_literal(document.get('status'))} · dev {_literal(document.get('developer') or '-')}")
        )
        if document.get("description"):
            rprint(_dim(_literal(document["description"])))
        rprint(_dim(f"{document.get('accessTokens')} access token(s) · criado em {_literal(document.get('creationDate') or '-')}"))
        rprint("\n[bold cyan]ASSINATURAS[/bold cyan]")
        apis = document.get("apis") or []
        if not apis:
            rprint("  " + _dim("nenhuma API assinada"))
        for api in apis:
            plans = ", ".join(
                f"{p.get('name')}{' (default)' if p.get('defaultPlan') else ''}" for p in api.get("plans") or []
            ) or "sem plano"
            rprint(f"  [bold]{_literal(api.get('name'))}[/bold] v{_literal(api.get('version') or '-')}  " + _dim(f"API {api.get('id')} · planos: {_literal(plans)}"))
        rprint(_dim(f"\ntokens deste app: sen list tokens --app {document.get('id')}"))

    display_output(document, output_format=output, text_callback=_text)


def list_plans(
    ctx: typer.Context,
    api_id: Optional[int] = _api_option("Só os planos desta API (id)."),
    query: Optional[str] = typer.Option(None, "--query", help="Filtra por nome do plano ou da API."),
    output: OutputFormat = _output_option(),
):
    """Planos de consumo: a que API pertencem, se são default e quantos interceptors têm."""
    rows = _run(ctx, "list plans", output, lambda: _service(ctx).plans(api_id=api_id, query=query))

    def _text() -> None:
        if not rows:
            rprint("[yellow]Nenhum plano com esse filtro.[/yellow]")
            return
        _grade(
            [
                (
                    str(p.get("id")),
                    str(p.get("name") or ""),
                    "sim" if p.get("defaultPlan") else "não",
                    f"{(p.get('api') or {}).get('name')} ({(p.get('api') or {}).get('id')})" if p.get("api") else "-",
                    str(p.get("interceptors")),
                )
                for p in rows
            ],
            header=("PLAN ID", "PLANO", "DEFAULT", "API", "INTERCEPTORS"),
            justify=("right", None, None, None, "right"),
        )
        rprint(_dim("fluxo do plano: sen get plan --id <PLAN ID> · quem assina: sen list apps --api <API>"))

    display_output(rows, output_format=output, text_callback=_text)


@get_app.command("plan")
def get_plan_command(
    ctx: typer.Context,
    plan_id: int = typer.Option(..., "--id", help="Id do plano (sen list plans)."),
    output: OutputFormat = _output_option(),
):
    """Um plano e os interceptors que ele acrescenta ao fluxo (request/response)."""
    document = _run(ctx, "get plan", output, lambda: _service(ctx).plan(plan_id))

    def _text() -> None:
        api = document.get("api") or {}
        rprint(
            f"[bold]{_literal(document.get('name'))}[/bold]  "
            + _dim(f"plano {document.get('id')}{' · default' if document.get('defaultPlan') else ''} · API {_literal(api.get('name'))} ({api.get('id')})")
        )
        if document.get("description"):
            rprint(_dim(_literal(document["description"])))
        flow = document.get("flow") or {}
        if not any(flow.get(p) for p in ("request", "response")):
            rprint("\n" + _dim("o plano não acrescenta interceptors ao fluxo"))
        for point, title in (("request", "request "), ("response", "response")):
            items = flow.get(point) or []
            if items:
                rprint(f"\n[bold]{title}[/bold]")
                _print_items(items, "   ", content=True)

    display_output(document, output_format=output, text_callback=_text)


def list_tokens(
    ctx: typer.Context,
    app_id: Optional[int] = typer.Option(None, "--app", help="Só os tokens deste app (id)."),
    api_id: Optional[int] = _api_option("Só os tokens que alcançam esta API (id)."),
    output: OutputFormat = _output_option(),
):
    """Access tokens emitidos: dono, app, status e validade. O código nunca é exibido."""
    rows = _run(ctx, "list tokens", output, lambda: _service(ctx).tokens(app_id=app_id, api_id=api_id))

    def _text() -> None:
        if not rows:
            rprint("[yellow]Nenhum access token com esse filtro.[/yellow]")
            return
        _grade(
            [
                (
                    str(t.get("id")),
                    str(t.get("owner") or "-"),
                    f"{(t.get('app') or {}).get('name')} ({(t.get('app') or {}).get('id')})",
                    str(t.get("status") or "-"),
                    str(t.get("expiredDate") or "-"),
                    ", ".join(str(a.get("name")) for a in t.get("apis") or []) or "-",
                )
                for t in rows
            ],
            header=("TOKEN ID", "DONO", "APP", "STATUS", "EXPIRA EM", "APIS"),
        )

    display_output(rows, output_format=output, text_callback=_text)


def list_variables(
    ctx: typer.Context,
    environment_id: Optional[int] = typer.Option(None, "--env", help="Id do ambiente (sen list environments). Ausente: todos."),
    key: Optional[str] = typer.Option(None, "--key", help="Filtra pelo nome da variável (substring)."),
    output: OutputFormat = _output_option(),
):
    """Variáveis de ambiente (mapas e chaves). Valores sensíveis saem sempre mascarados."""
    rows = _run(
        ctx,
        "list variables",
        output,
        lambda: _service(ctx).variables(environment_id, key=key),
    )

    def _text() -> None:
        if not rows:
            rprint("[yellow]Nenhuma variável com esse filtro.[/yellow]")
            return
        _grade(
            [
                (
                    f"{v.get('environmentName')} ({v.get('environmentId')})",
                    str(v.get("map") or "-"),
                    str(v.get("key") or ""),
                    str(v.get("variableType") or "-"),
                    str(v.get("value") if v.get("value") is not None else "-"),
                )
                for v in rows
            ],
            header=("AMBIENTE", "MAPA", "CHAVE", "TIPO", "VALOR"),
        )
        if any(v.get("masked") for v in rows):
            rprint(_dim("••••• = valor mascarado (credencial ou SECURED); para ver um valor: sen reveal variable --env <E> --key <CHAVE>"))

    display_output(rows, output_format=output, text_callback=_text)


@get_app.command("environment")
def get_environment_command(
    ctx: typer.Context,
    environment_id: int = typer.Option(..., "--id", help="Id do ambiente (sen list environments)."),
    output: OutputFormat = _output_option(),
):
    """Um ambiente: gateway, mapas de variáveis (mascaradas) e todas as APIs/revisões no ar nele."""
    document = _run(ctx, "get environment", output, lambda: _service(ctx).environment(environment_id))

    def _text() -> None:
        gw = document.get("gateway") or {}
        rprint(
            f"[bold]{_literal(document.get('name'))}[/bold]  "
            + _dim(f"ambiente {document.get('id')} · {_literal(document.get('inboundUrl') or '-')} · visibilidade {_literal(document.get('visibility') or '-')}")
        )
        if document.get("description"):
            rprint(_dim(_literal(document["description"])))
        rprint(_dim(f"gateway: pool {_literal(gw.get('pool') or '-')} ({_literal(gw.get('type') or '-')}) · host {_literal(gw.get('host') or '-')} · {_literal(gw.get('protocol') or '-')}/{_literal(gw.get('tls') or '-')}"))
        maps = document.get("variableMaps") or []
        rprint("\n[bold cyan]VARIÁVEIS[/bold cyan]  " + _dim(f"{len(maps)} mapa(s) · {len(document.get('variables') or [])} variável(is)"))
        for v in document.get("variables") or []:
            rprint(f"  {_literal(v.get('map'))} / [bold]{_literal(v.get('key'))}[/bold] = {_literal(v.get('value'))}  " + _dim(_literal(v.get("variableType"))))
        deployed = document.get("deployed") or []
        rprint("\n[bold cyan]NO AR[/bold cyan]  " + _dim(f"{len(deployed)} API(s)"))
        for d in deployed:
            rprint(f"  {_literal(d.get('apiName'))} v{_literal(d.get('apiVersion') or '-')}  " + _dim(f"API {d.get('apiId')} · revisão #{d.get('revisionNumber')} (id {d.get('revisionId')})"))

    display_output(document, output_format=output, text_callback=_text)


def list_users(
    ctx: typer.Context,
    query: Optional[str] = typer.Option(None, "--query", help="Busca por nome, username ou e-mail (no Manager)."),
    output: OutputFormat = _output_option(),
):
    """Usuários do tenant (Access Control): username, status e provedor."""
    rows = _run(ctx, "list users", output, lambda: _service(ctx).users(query))

    def _text() -> None:
        if not rows:
            rprint("[yellow]Nenhum usuário com esse filtro.[/yellow]")
            return
        _grade(
            [
                (str(u.get("username") or ""), str(u.get("name") or "-"), str(u.get("email") or "-"), str(u.get("status") or "-"), str(u.get("providerType") or "-"))
                for u in rows
            ],
            header=("USERNAME", "NOME", "E-MAIL", "STATUS", "PROVEDOR"),
        )

    display_output(rows, output_format=output, text_callback=_text)


def list_teams(
    ctx: typer.Context,
    query: Optional[str] = typer.Option(None, "--query", help="Busca pelo nome do time (no Manager)."),
    output: OutputFormat = _output_option(),
):
    """Times (groups) do tenant: os nomes usados em visibilidade GROUP e nos workflows."""
    rows = _run(ctx, "list teams", output, lambda: _service(ctx).teams(query))

    def _text() -> None:
        if not rows:
            rprint("[yellow]Nenhum time com esse filtro.[/yellow]")
            return
        _grade([(str(g.get("name") or ""), str(g.get("description") or "-")) for g in rows], header=("TIME", "DESCRIÇÃO"))

    display_output(rows, output_format=output, text_callback=_text)


def list_inbounds(
    ctx: typer.Context,
    output: OutputFormat = _output_option(),
):
    """Endereços de entrada do gateway (host, protocolo, TLS, data plane)."""
    rows = _run(ctx, "list inbounds", output, lambda: _service(ctx).inbounds())

    def _text() -> None:
        if not rows:
            rprint("[yellow]Nenhum inbound.[/yellow]")
            return
        _grade(
            [
                (str(i.get("id")), str(i.get("name") or ""), str(i.get("host") or "-"), f"{i.get('protocol') or '-'}/{i.get('tls') or '-'}", f"{i.get('minTlsVersion') or '-'}…{i.get('maxTlsVersion') or '-'}", str(i.get("gatewayType") or "-"))
                for i in rows
            ],
            header=("ID", "NOME", "HOST", "PROTO/TLS", "TLS VERSÕES", "GATEWAY"),
            justify=("right", None, None, None, None, None),
        )

    display_output(rows, output_format=output, text_callback=_text)


def list_gateway_pools(
    ctx: typer.Context,
    output: OutputFormat = _output_option(),
):
    """Pools de gateway e quantas rotas cada um serve."""
    rows = _run(ctx, "list gateway-pools", output, lambda: _service(ctx).gateway_pools())

    def _text() -> None:
        if not rows:
            rprint("[yellow]Nenhum pool.[/yellow]")
            return
        _grade(
            [(str(p.get("id")), str(p.get("name") or ""), str(p.get("type") or "-"), str(p.get("routes") if p.get("routes") is not None else "-"), str(p.get("description") or "-")) for p in rows],
            header=("ID", "POOL", "TIPO", "ROTAS", "DESCRIÇÃO"),
            justify=("right", None, None, "right", None),
        )

    display_output(rows, output_format=output, text_callback=_text)


# ===========================================================================
# sen reveal — o único caminho que escreve um valor sensível na tela.
# ===========================================================================


@reveal_app.command("variable")
def reveal_variable_command(
    ctx: typer.Context,
    environment_id: int = typer.Option(..., "--env", help="Id do ambiente (sen list environments)."),
    key: str = typer.Option(..., "--key", help="Nome EXATO da variável (sen list variables)."),
    map_name: Optional[str] = typer.Option(None, "--map", help="Mapa da variável, quando a chave se repete."),
    raw: bool = typer.Option(False, "--raw", help="Escreve só o valor, cru (para redirecionar ou exportar)."),
    output: OutputFormat = _output_option(),
):
    """Mostra em claro o valor de UMA variável de ambiente, como o Manager o devolve."""
    document = _run(
        ctx,
        "reveal variable",
        output if not raw else OutputFormat.JSON,
        lambda: _service(ctx).reveal_variable(environment_id, key, map_name),
    )
    if raw:
        import sys

        value = document.get("value")
        value = "" if value is None else str(value)
        sys.stdout.write(value if value.endswith("\n") else value + "\n")
        return

    def _text() -> None:
        rprint(
            f"[bold]{_literal(document.get('key'))}[/bold]  "
            + _dim(
                f"{_literal(document.get('environmentName'))} ({document.get('environmentId')}) · mapa "
                f"{_literal(document.get('map'))} · {_literal(document.get('variableType'))}"
                + (" · sensível" if document.get("sensitive") else "")
            )
        )
        rprint(_literal(document.get("value") if document.get("value") is not None else "(vazio)"))

    display_output(document, output_format=output, text_callback=_text)
