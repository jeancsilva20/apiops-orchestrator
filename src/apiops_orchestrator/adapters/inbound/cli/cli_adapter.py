from pathlib import Path
import typer
from rich import print as rprint

app = typer.Typer(
    help="APIOps CLI - compose/validate/plan/apply para Sensedia Manager API", no_args_is_help=True
)

@app.command("sync-openapi")
def sync_openapi(
    repo: Path = typer.Option(
        ..., "--repo", "-r", help="API Repository Path"
    ),
    env: str = typer.Option(..., "--env", "-e", help="Target environment (e.g., dev, hmg, prd)"),
    apply: bool = typer.Option(
        False, "--apply/--no-apply", help="POST /revisions; otherwise, DRY-RUN."
    ),
    out_dir: Path | None = typer.Option(
        None, "--out-dir", help="Directory to save the generated plan"
    ),
) -> None:
    try:
        rprint(f"{repo}, {env}, {apply}, {out_dir}")
    except Exception as e:
        rprint({"error": str(e)})
        raise typer.Exit(code=1)

# Another command is required for Typer to recognize sync_openapi; otherwise, any direct call to main.py will fall back to sync-openapi without receiving parameters.
# Considering that other commands will be implemented in the future to replace this placeholder, I don't see an issue..
@app.command("placeholder")
def placeholder() -> None:
    try:
        rprint("placeholder")
    except Exception as e:
        rprint({"error": str(e)})
        raise typer.Exit(code=1)