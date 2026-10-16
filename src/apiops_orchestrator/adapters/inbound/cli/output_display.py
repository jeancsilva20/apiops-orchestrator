import json
import sys

import yaml
from typing import Any
from rich import print as rprint
from rich.console import Console
from rich.syntax import Syntax
from apiops_orchestrator.adapters.inbound.cli.output_format import OutputFormat

console = Console()


def display_output(
    data: Any,
    output_format: OutputFormat = OutputFormat.TEXT,
    text_callback: callable = None,
):
    """
    Displays output in the specified format.

    :param data: The data to display (usually a list or dict).
    :param output_format: The format to use (TEXT, JSON, YAML).
    :param text_callback: A function to call if output_format is TEXT.
                          It should handle the rich printing.
    """
    if output_format in (OutputFormat.JSON, OutputFormat.YAML):
        if output_format == OutputFormat.JSON:
            texto = json.dumps(data, indent=4, ensure_ascii=False)
            linguagem = "json"
        else:
            texto = yaml.dump(data, sort_keys=False, allow_unicode=True)
            linguagem = "yaml"

        # Saída legível por máquina NÃO pode passar por renderizador que quebra
        # linha: o `rich.Syntax` ajusta à largura do console e corta valores
        # longos no meio, produzindo JSON inválido. Quem consome isso é a
        # esteira, então o texto sai cru quando stdout não é terminal, e com
        # realce apenas para leitura humana — aí com `soft_wrap`, que preserva
        # as linhas intactas.
        if console.is_terminal:
            console.print(
                Syntax(texto, linguagem, theme="monokai", background_color="default"),
                soft_wrap=True,
            )
        else:
            sys.stdout.write(texto if texto.endswith("\n") else texto + "\n")
    else:
        if text_callback:
            text_callback()
        else:
            rprint(data)
