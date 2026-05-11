import sys
import typer
from rich import print as rprint
from apiops_orchestrator.adapters.inbound.cli.cli_adapter import app, CliError

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
