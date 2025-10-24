class ApiInfoNotFoundException(Exception):
    """Raised when ApiBasicInfo is not found in the YAML files."""

    def __init__(self, message="ApiBasicInfo not found. It is a mandatory component."):
        self.message = message
        super().__init__(self.message)


class ResourcesListNotFoundException(Exception):
    """Raised when ResourcesList is not found in the YAML files."""

    def __init__(self, message="ResourcesList not found. It is a mandatory component."):
        self.message = message
        super().__init__(self.message)


class InterceptorsNotFoundException(Exception):
    """Raised when Interceptors is not found in the YAML files."""

    def __init__(self, message="Interceptors not found. It is a mandatory component."):
        self.message = message
        super().__init__(self.message)
