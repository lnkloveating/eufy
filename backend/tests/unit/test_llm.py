from __future__ import annotations

import asyncio

import httpx
import pytest
from pydantic import BaseModel

from eufy_security_agents.infrastructure.llm import (
    LLMGenerationError,
    OpenAICompatibleLLM,
)


class SmallResponse(BaseModel):
    status: str


@pytest.mark.asyncio
async def test_truncated_structured_output_is_retried_and_diagnosed() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "test-model",
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": '{"status":"incomplete'},
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )

    client = OpenAICompatibleLLM(
        api_key="test-key",
        base_url="https://provider.invalid",
        model_name="test-model",
        max_retries=2,
        max_output_tokens=123,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMGenerationError) as caught:
        await client.generate(
            system_prompt="test",
            user_prompt="test",
            response_model=SmallResponse,
            temperature=0,
        )

    error = caught.value
    assert request_count == 3
    assert error.failure_kind == "truncated"
    assert error.attempts == 3
    assert error.metadata["input_tokens"] == 300
    assert error.metadata["output_tokens"] == 150
    assert "123-token output limit" in str(error)


@pytest.mark.asyncio
async def test_retry_usage_is_included_when_second_attempt_succeeds() -> None:
    request_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        content = "not json" if request_count == 1 else '{"status":"ok"}'
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "test-model",
                "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 80, "completion_tokens": 20},
            },
        )

    client = OpenAICompatibleLLM(
        api_key="test-key",
        base_url="https://provider.invalid",
        model_name="test-model",
        max_retries=1,
        transport=httpx.MockTransport(handler),
    )
    result, metadata = await client.generate(
        system_prompt="test",
        user_prompt="test",
        response_model=SmallResponse,
        temperature=0,
    )

    assert result == SmallResponse(status="ok")
    assert metadata["input_tokens"] == 160
    assert metadata["output_tokens"] == 40


@pytest.mark.asyncio
async def test_logical_timeout_bounds_all_retries() -> None:
    request_count = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        await asyncio.sleep(1)
        return httpx.Response(200, request=request, json={})

    client = OpenAICompatibleLLM(
        api_key="test-key",
        base_url="https://provider.invalid",
        model_name="test-model",
        timeout_seconds=0.01,
        max_retries=2,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMGenerationError) as caught:
        await client.generate(
            system_prompt="test",
            user_prompt="test",
            response_model=SmallResponse,
            temperature=0,
        )

    assert request_count == 1
    assert caught.value.failure_kind == "provider_timeout"
    assert caught.value.metadata["duration_ms"] is not None
