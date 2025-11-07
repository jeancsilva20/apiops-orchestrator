from pathlib import Path
import typer
from rich import print as rprint

app = typer.Typer(
    help="APIOps CLI - compose/validate/plan/apply para Sensedia Manager API", no_args_is_help=True
)

@app.command("sync-openapi")
def sync_openapi(
    repo: Path = typer.Option(
        ..., "--repo", "-r", help="Caminho do Repositório da API"
    ),
    env: str = typer.Option(..., "--env", "-e", help="Ambiente alvo (ex.: dev, hmg, prd)"),
    apply: bool = typer.Option(
        False, "--apply/--no-apply", help="POST /revisions; se não, DRY-RUN."
    ),
    out_dir: Path | None = typer.Option(
        None, "--out-dir", help="Diretório para salvar o plano gerado"
    ),
) -> None:
    try:
        rprint(f"{repo}, {env}, {apply}, {out_dir}")
    except Exception as e:
        rprint({"error": str(e)})
        raise typer.Exit(code=1)

# Necessário ter outro comando para o typer reconhecer o sync_openapi, caso contrário, qualquer chamada direta ao arquivo main.py caira no sync-openapi, sem receber parametros
# Considerando que será implementado outros comandos no futuro para substituir esse placeholder, não vejo problema.
@app.command("placeholder")
def placeholder() -> None:
    try:
        rprint("placeholder")
    except Exception as e:
        rprint({"error": str(e)})
        raise typer.Exit(code=1)