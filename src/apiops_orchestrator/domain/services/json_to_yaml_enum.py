from enum import Enum


class JsonKind(Enum):
    API_BASIC_INFO = "ApiBasicInfo"
    INTERCEPTORS = "Interceptors"
    API_OPERATIONS = "ApiOperations"
    RESOURCES = "Resources"
    ENVIRONMENT = "Environment"


class JsonKindFileName(Enum):
    API_BASIC_INFO = "api-basic-info.yaml"
    INTERCEPTORS = "default-interceptors.yaml"
    RESOURCES = "resources.yaml"
    ENVIRONMENT = "deployment.yaml"