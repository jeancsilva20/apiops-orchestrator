from enum import Enum


class JsonKind(Enum):
    API_BASIC_INFO = "ApiBasicInfo"
    INTERCEPTORS = "Interceptors"
    API_OPERATIONS = "ApiOperations"
    RESOURCES = "Resources"
    ENVIRONMENT = "Environment"