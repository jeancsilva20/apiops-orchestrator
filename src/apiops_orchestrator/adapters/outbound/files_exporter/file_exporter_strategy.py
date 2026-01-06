from pathlib import Path
from typing import Any, Callable

import yaml

from apiops_orchestrator.application.enums.file_type_enum import FileTypeEnum


class PrettyYAMLDumper(yaml.SafeDumper):
    """Custom YAML dumper for proper list indentation."""

    def increase_indent(self, flow=False, indentless=False):
        return super(PrettyYAMLDumper, self).increase_indent(flow, indentless)


def represent_list(dumper, sequence):
    return dumper.represent_sequence(
        "tag:yaml.org,2002:seq", sequence, flow_style=False
    )


PrettyYAMLDumper.add_representer(list, represent_list)


def _export_yaml(file_path: Path, content) -> Any:
    """Exports a YAML file."""
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.dump(
            content,
            f,
            Dumper=PrettyYAMLDumper,
            sort_keys=False,
            allow_unicode=True,
            indent=2,
            default_flow_style=False,
        )


FILE_EXPORTER_STRATEGIES: dict[str, Callable[[Path, Any], Any]] = {
    FileTypeEnum.YAML.value: _export_yaml,
    FileTypeEnum.YML.value: _export_yaml,
}
