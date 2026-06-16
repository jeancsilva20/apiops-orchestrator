import json
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
    if output_format == OutputFormat.JSON:
        json_str = json.dumps(data, indent=4)
        syntax = Syntax(json_str, "json", theme="monokai", background_color="default")
        console.print(syntax)
    elif output_format == OutputFormat.YAML:
        yaml_str = yaml.dump(data, sort_keys=False)
        syntax = Syntax(yaml_str, "yaml", theme="monokai", background_color="default")
        console.print(syntax)
    else:
        if text_callback:
            text_callback()
        else:
            rprint(data)
