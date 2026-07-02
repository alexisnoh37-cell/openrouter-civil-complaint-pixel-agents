from typing import Any, Literal

from pydantic import BaseModel, Field


AgentStatus = Literal["waiting", "running", "completed", "error"]


class ComplaintRequest(BaseModel):
    complaint_no: str = Field(..., description="민원신청번호")
    title: str = Field(..., description="민원 제목")
    body: str = Field(..., description="민원 본문")


class AgentEvent(BaseModel):
    agent: str
    label: str
    status: AgentStatus
    message: str | None = None
    result: dict[str, Any] | None = None


class ProcessResponse(BaseModel):
    complaint_no: str
    agents: dict[str, dict[str, Any]]
    final_status: Literal["초안 사용 가능", "수정 후 검토", "담당자 검토 필수"]
    final_draft: str
    review_results: dict[str, dict[str, Any]]

