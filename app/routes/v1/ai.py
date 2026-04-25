from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.auth import AuthContext, require_roles
from app.core.settings import Settings, get_settings
from app.schemas.summary import AiSummaryRequest, AiSummaryResponse
from app.services.ai import AiSummaryService

router = APIRouter(tags=["ai"])
AiAccessDependency = Annotated[
    AuthContext,
    Depends(require_roles("developer", "reviewer", "release")),
]


def get_ai_summary_service(settings: Annotated[Settings, Depends(get_settings)]) -> AiSummaryService:
    return AiSummaryService(settings)


AiSummaryServiceDependency = Annotated[AiSummaryService, Depends(get_ai_summary_service)]


@router.post("/summaries/pr")
async def summarize_pull_request(
    payload: AiSummaryRequest,
    _: AiAccessDependency,
    service: AiSummaryServiceDependency,
) -> AiSummaryResponse:
    return await service.summarize_pull_request(payload)
