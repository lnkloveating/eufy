"""Opt-in smoke test for the configured OpenAI-compatible provider."""

import os
from pathlib import Path

import pytest
from pydantic import BaseModel

from eufy_security_agents.agents import CompetitorAnalysisAgent
from eufy_security_agents.core.config import get_settings
from eufy_security_agents.domain.models import ForecastRequest, Opportunity
from eufy_security_agents.infrastructure.competitors import LocalCompetitorStore
from eufy_security_agents.infrastructure.llm import OpenAICompatibleLLM


class LiveSmokeResponse(BaseModel):
    status: str
    region: str


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_LLM_TEST") != "1",
    reason="set RUN_LIVE_LLM_TEST=1 to call the external LLM",
)
async def test_live_provider_returns_schema_valid_json() -> None:
    settings = get_settings()
    assert settings.llm_api_key, "LLM_API_KEY must be configured in backend/.env"

    client = OpenAICompatibleLLM(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model_name=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=0,
    )
    user_prompt = """Return status exactly "ok" and region exactly "Global".
Do not add product analysis."""
    result, usage = await client.generate(
        system_prompt="You are a connectivity smoke test.",
        user_prompt=user_prompt,
        response_model=LiveSmokeResponse,
        temperature=0,
    )

    assert result == LiveSmokeResponse(status="ok", region="Global")
    assert usage["model_name"]


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("RUN_LIVE_LLM_TEST") != "1",
    reason="set RUN_LIVE_LLM_TEST=1 to call the external LLM",
)
async def test_live_competitor_agent_returns_auditable_gaps() -> None:
    settings = get_settings()
    client = OpenAICompatibleLLM(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        model_name=settings.llm_model,
        timeout_seconds=settings.llm_timeout_seconds,
        max_retries=1,
    )
    request = ForecastRequest(
        question="预测未来三年美国家庭无需强制订阅的AI原生安防机会",
        regions=["United States"],
        target_users=["Households"],
    )
    opportunities = [
        Opportunity(
            id=f"OPP-{index:03d}",
            title=f"未来机会 {index}",
            unmet_job="更早识别风险并减少无效通知",
            target_users=["Households"],
            target_regions=["United States"],
            why_now="端侧AI和多传感器能力成熟",
            opportunity_window="1-3 years",
            enabling_trends=["edge AI"],
            evidence_ids=["EV-EUFY-001"],
            counter_evidence=["cost"],
            confidence=0.7,
        )
        for index in range(1, 4)
    ]
    store = LocalCompetitorStore(Path(__file__).resolve().parents[2] / "data" / "competitors")
    evidence = store.retrieve(request, limit=8)

    output = await CompetitorAnalysisAgent(client).run(request, opportunities, evidence)
    analysis = output.value.analysis

    assert 3 <= len(analysis.gaps) <= 6
    assert {item for gap in analysis.gaps for item in gap.competitor_evidence_ids} <= {
        item.id for item in evidence
    }
