import asyncio
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI

from app.core.settings import Settings
from app.schemas.summary import AiProvider, AiProviderOverride, AiSummaryRequest, AiSummaryResponse


@dataclass
class ProviderConfig:
    provider: AiProvider
    model: str
    base_url: str | None = None
    api_key: str | None = None


class AiSummaryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def summarize_pull_request(self, payload: AiSummaryRequest) -> AiSummaryResponse:
        provider_config = self._resolve_provider_config(payload.provider_override)
        prompt = self._build_summary_prompt(payload)

        if provider_config.provider == AiProvider.fallback:
            return self._build_fallback_response(payload, provider_config.model)

        if provider_config.provider == AiProvider.inhouse:
            summary = await self._summarize_with_ollama(prompt, provider_config)
            if not summary:
                return self._build_fallback_response(payload, provider_config.model)
            return AiSummaryResponse(summary=summary, generated_by="inhouse", model=provider_config.model)

        summary = await self._summarize_with_openai(prompt, provider_config)
        if not summary:
            return self._build_fallback_response(payload, provider_config.model)
        return AiSummaryResponse(summary=summary, generated_by="openai", model=provider_config.model)

    def _resolve_provider_config(self, override: AiProviderOverride | None) -> ProviderConfig:
        if override is not None:
            provider = override.provider
            if provider == AiProvider.inhouse:
                return ProviderConfig(
                    provider=provider,
                    model=override.model or self.settings.inhouse_model,
                    base_url=override.base_url or self.settings.inhouse_base_url,
                )
            if provider == AiProvider.openai:
                return ProviderConfig(
                    provider=provider,
                    model=override.model or self.settings.openai_model,
                    base_url=override.base_url or self.settings.openai_base_url,
                    api_key=override.api_key or self.settings.openai_api_key,
                )
            return ProviderConfig(provider=AiProvider.fallback, model=override.model or self.settings.inhouse_model)

        default_provider = AiProvider(self.settings.ai_default_provider)
        if default_provider == AiProvider.inhouse:
            return ProviderConfig(
                provider=default_provider,
                model=self.settings.inhouse_model,
                base_url=self.settings.inhouse_base_url,
            )
        if default_provider == AiProvider.openai:
            return ProviderConfig(
                provider=default_provider,
                model=self.settings.openai_model,
                base_url=self.settings.openai_base_url,
                api_key=self.settings.openai_api_key,
            )
        return ProviderConfig(provider=AiProvider.fallback, model=self.settings.inhouse_model)

    async def _summarize_with_ollama(self, prompt: str, provider_config: ProviderConfig) -> str:
        if not provider_config.base_url:
            return ""

        try:
            async with httpx.AsyncClient(base_url=provider_config.base_url) as client:
                async with asyncio.timeout(self.settings.http_timeout_seconds):
                    response = await client.post(
                        "/api/generate",
                        json={
                            "model": provider_config.model,
                            "prompt": prompt,
                            "stream": False,
                        },
                    )
                    response.raise_for_status()
                    return str(response.json().get("response", "")).strip()
        except (httpx.HTTPError, TimeoutError):
            return ""

    async def _summarize_with_openai(self, prompt: str, provider_config: ProviderConfig) -> str:
        api_key = (provider_config.api_key or "").strip()
        if not api_key or api_key == "replace-me":
            return ""

        try:
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=provider_config.base_url,
            )
            response = await client.responses.create(
                model=provider_config.model,
                input=prompt,
            )
            return (response.output_text or "").strip()
        except Exception:
            return ""

    def _build_fallback_response(self, payload: AiSummaryRequest, model: str) -> AiSummaryResponse:
        return AiSummaryResponse(
            summary=self._build_fallback_summary(payload),
            generated_by="fallback",
            model=model,
        )

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

    def _build_summary_prompt(self, payload: AiSummaryRequest) -> str:
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
