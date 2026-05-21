import platform
import typer
from rich import print as rprint

app = typer.Typer(
    name="sen",
    help=" APIOps CLI - Framework GitOps to automate, standardize and manage your APIs.",
    no_args_is_help=True,
    add_completion=False,
)


class CliError(Exception):
    """Exceção base para erros da CLI que devem ser exibidos de forma amigável."""

    def __init__(self, message: str, exit_code: int = 1):
        self.message = message
        self.exit_code = exit_code
        super().__init__(self.message)


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
        False, "--verbose", "-v", help="Aumenta nivel de log."
    ),
    version: bool = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Exibe versao da CLI.",
    ),
):
    """
    APIOps CLI Sensedia.
    """
    if verbose:
        # TODO: Ajustar nível de log quando houver integração com logging
        pass
