from pydantic import BaseModel, model_validator
from typing import List, Optional
from .api_partial_model import ApiPartialInfo
from .resources_model import Resource
from .interceptors_model import Interceptor


class ApiFull(BaseModel):
    api: ApiPartialInfo
    revisionNumber: int = 999
    # workflowId: Optional[int] = None # MAG Não tem AG
    # workflowStageId: Optional[int] = None # MAG Não tem AG
    lifeCycle: str = "AVAILABLE"
    interceptors: List[Interceptor] = []
    resources: List[Resource] = []

    @model_validator(mode="after")
    def set_interceptor_positions(self) -> "ApiFull":
        position_counter = 1
        processed_interceptors = set()

        for interceptor in self.interceptors:
            if id(interceptor) not in processed_interceptors:
                interceptor.position = position_counter
                interceptor.id = position_counter
                interceptor.idTemp = position_counter
                position_counter += 1
                processed_interceptors.add(id(interceptor))

        for resource in self.resources:
            for operation in resource.operations:
                for interceptor in operation.interceptors:
                    if id(interceptor) not in processed_interceptors:
                        interceptor.position = position_counter
                        interceptor.id = position_counter
                        interceptor.idTemp = position_counter
                        position_counter += 1
                        processed_interceptors.add(id(interceptor))

        return self
