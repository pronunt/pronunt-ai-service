from openai import AsyncOpenAI

from app.core.settings import Settings
from app.schemas.summary import AiSummaryRequest, AiSummaryResponse


class AiSummaryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def summarize_pull_request(self, payload: AiSummaryRequest) -> AiSummaryResponse:
        if not self._should_use_openai():
            return AiSummaryResponse(
                summary=self._build_fallback_summary(payload),
                generated_by="fallback",
                model=self.settings.openai_model,
            )

        client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        response = await client.responses.create(
            model=self.settings.openai_model,
            input=self._build_openai_prompt(payload),
        )
        summary_text = (response.output_text or "").strip()
        if not summary_text:
            summary_text = self._build_fallback_summary(payload)

        return AiSummaryResponse(
            summary=summary_text,
            generated_by="openai",
            model=self.settings.openai_model,
        )

    def _should_use_openai(self) -> bool:
        api_key = (self.settings.openai_api_key or "").strip()
        return bool(api_key and api_key != "replace-me")

    def _build_fallback_summary(self, payload: AiSummaryRequest) -> str:
        label_text = ", ".join(payload.labels) if payload.labels else "no labels"
        impact_text = ", ".join(payload.impact_services) if payload.impact_services else "no downstream impact"
        stale_text = "stale" if payload.stale else "active"
        return (
            f"PR #{payload.number} in {payload.repository_full_name} is {stale_text} and targets "
            f"a {payload.criticality} service. It changes {payload.changed_files} files with "
            f"{payload.additions} additions and {payload.deletions} deletions. Current review status is "
            f"{payload.review_status}, risk score is {payload.risk_score}, priority score is {payload.priority_score}, "
            f"labels are {label_text}, and dependency impact is {impact_text}."
        )

    def _build_openai_prompt(self, payload: AiSummaryRequest) -> str:
        impact_text = ", ".join(payload.impact_services) if payload.impact_services else "none"
        label_text = ", ".join(payload.labels) if payload.labels else "none"
        return (
            "Write a concise engineering pull request summary in 2 sentences. "
            "Do not invent facts. Mention review urgency and downstream impact.\n\n"
            f"Repository: {payload.repository_full_name}\n"
            f"PR Number: {payload.number}\n"
            f"Title: {payload.title}\n"
            f"Author: {payload.author_username}\n"
            f"Review Status: {payload.review_status}\n"
            f"Criticality: {payload.criticality}\n"
            f"Changed Files: {payload.changed_files}\n"
            f"Additions: {payload.additions}\n"
            f"Deletions: {payload.deletions}\n"
            f"Risk Score: {payload.risk_score}\n"
            f"Priority Score: {payload.priority_score}\n"
            f"Stale: {payload.stale}\n"
            f"Labels: {label_text}\n"
            f"Impact Services: {impact_text}\n"
        )
