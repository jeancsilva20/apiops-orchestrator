from typing import Optional

from pydantic import BaseModel


class WorkflowStage(BaseModel):
    workflowStageId: int
    workflowStageName: Optional[str] = None
