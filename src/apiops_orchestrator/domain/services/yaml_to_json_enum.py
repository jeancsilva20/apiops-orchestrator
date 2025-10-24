from enum import Enum


class YamlKind(Enum):
    API_BASIC_INFO = "ApiBasicInfo"
    INTERCEPTORS = "Interceptors"
    API_OPERATIONS = "ApiOperations"
    RESOURCES_LIST = "ResourcesList"
