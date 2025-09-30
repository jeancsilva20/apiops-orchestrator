from pathlib import Path
import typer
from rich import print as rprint

app = typer.Typer(
    help="APIOps CLI - compose/validate/plan/apply para Sensedia Manager API", no_args_is_help=True
)

@app.command("sync-openapi")
def sync_openapi(
    file: Path = typer.Option(
        None, "--file", "-f", help="Caminho do OpenAPI (default: settings.DEFAULT_OPENAPI_FILE)"
    ),
    env: str = typer.Option(..., "--env", "-e", help="Ambiente alvo (ex.: dev, hmg, prd)"),
    apply: bool = typer.Option(
        False, "--apply/--no-apply", help="POST /revisions; se não, DRY-RUN."
    ),
    out_dir: Path | None = typer.Option(
        None, "--out-dir", help="Diretório para salvar o plano gerado"
    ),
    create_templates: bool = typer.Option(
        True,
        "--create-templates/--no-create-templates",
        help="Gerar templates para operações novas",
    ),
    templates_root: list[Path] = typer.Option(
        None, "--templates-root", help="Raiz extra de templates (pode repetir)"
    ),
    write_templates_dir: Path | None = typer.Option(
        None, "--write-templates-dir", help="Salvar templates gerados neste diretório"
    ),
) -> None:
    try:
        pass
    except Exception as e:
        rprint({"error": str(e)})
        raise typer.Exit(code=1)


@app.command("placeholder")
def placeholder() -> None:
    try:
        rprint("placeholder")
    except Exception as e:
        rprint({"error": str(e)})
        raise typer.Exit(code=1)