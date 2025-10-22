from pydantic import BaseModel
from typing import List, Optional
from .api_basic_info_model import ApiInfo
from .resources_model import Resource
from .interceptors_model import Interceptor


class ApiFull(BaseModel):
    api: ApiInfo
    revisionNumber: int = 999
    workflowId: int = 139
    workflowStageId: int = 420
    interceptors: List[Interceptor] = []
    resources: List[Resource] = []
