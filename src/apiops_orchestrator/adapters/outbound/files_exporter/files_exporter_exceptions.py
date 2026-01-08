class UnmappedKindException(Exception):
    """Raised when mapped kind is not found in the JSON response"""

    def __init__(self, kind: str):
        super().__init__(f"The kind '{kind}' is not mapped to a file type.")


class FileExporterException(Exception):
    """Raised when an error occurs while exporting the file"""

    def __init__(self, full_path: str):
        super().__init__(f"An error occurred while exporting the file: {full_path}")
