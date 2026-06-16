from enum import Enum

class OutputFormat(str, Enum):
    TEXT = "text"
    JSON = "json"
    YAML = "yaml"
