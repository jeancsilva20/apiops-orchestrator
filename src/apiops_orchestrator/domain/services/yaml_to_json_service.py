from apiops_orchestrator.domain.models.api_basic_info_model import ApiBasicInfo, ApiInfo
from apiops_orchestrator.domain.models.resources_model import ResourcesList
from apiops_orchestrator.domain.models.interceptors_model import InterceptorsFile
from apiops_orchestrator.domain.models.api_full_model import ApiFull


class YamlToJsonService:
    def __init__(self, yamls):
        self.yaml_files = yamls

    def build_api_json(self) -> ApiFull:
        api_info = ApiInfo()
        interceptors = []
        resources = []

        for data in self.yaml_files:
            kind = data.get("kind")

            if kind == "ApiBasicInfo":
                parsed = ApiBasicInfo(**data)
                spec_api = parsed.spec.get("api", {})
                api_info = ApiInfo(**spec_api)

            elif kind == "Interceptors":
                parsed = InterceptorsFile(**data)
                interceptors.extend(parsed.spec.interceptors)

            elif kind == "ResourcesList":
                parsed = ResourcesList(**data)
                resources.extend(parsed.items)

        return ApiFull(api=api_info, interceptors=interceptors, resources=resources)
