import asyncio

from app.core.settings import Settings
from app.schemas.summary import AiSummaryRequest
from app.services.ai import AiSummaryService


def test_ai_summary_service_uses_fallback_without_real_api_key() -> None:
    service = AiSummaryService(
        Settings(_env_file=None, allow_unsafe_dev_auth=True, openai_api_key="replace-me"),
    )
    payload = AiSummaryRequest(
        repository_full_name="pronunt/pronunt-aggregator-service",
        number=101,
        title="Add scoring improvements",
        author_username="sowrabh0-0",
        review_status="pending",
        criticality="critical",
        changed_files=12,
        additions=220,
        deletions=40,
        risk_score=59,
        priority_score=61,
        stale=False,
        impact_services=["pronunt-worker-service"],
        labels=["backend"],
    )

    response = asyncio.run(service.summarize_pull_request(payload))

    assert response.generated_by == "fallback"
    assert "risk score is 59" in response.summary
