"""OpenAI-compatible structured-output client.

Only the provider boundary knows about HTTP. Agent and domain modules depend on the
StructuredLLM protocol and can be tested with a fake implementation.
"""

from __future__ import annotations

import json
from time import perf_counter
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

TModel = TypeVar("TModel", bound=BaseModel)


class LLMConfigurationError(RuntimeError):
    """Raised when the provider cannot be called because configuration is missing."""


class LLMGenerationError(RuntimeError):
    """Raised after provider or schema-validation retries are exhausted."""


class OpenAICompatibleLLM:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model_name: str,
        timeout_seconds: float = 120,
        max_retries: int = 2,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self.model_name = model_name
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[TModel],
        temperature: float = 0.4,
    ) -> tuple[TModel, dict[str, int | str | None]]:
        if not self._api_key:
            raise LLMConfigurationError("LLM_API_KEY is not configured")

        schema = json.dumps(response_model.model_json_schema(), ensure_ascii=False)
        schema_instruction = (
            "Return one JSON object only. It must validate against this JSON Schema. "
            "Do not wrap it in Markdown and do not add prose outside the JSON.\n"
            f"JSON Schema:\n{schema}"
        )
        messages = [
            {"role": "system", "content": f"{system_prompt}\n\n{schema_instruction}"},
            {"role": "user", "content": user_prompt},
        ]
        last_error: Exception | None = None
        started = perf_counter()

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            for attempt in range(self._max_retries + 1):
                try:
                    response = await client.post(
                        f"{self._base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self._api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "model": self.model_name,
                            "messages": messages,
                            "response_format": {"type": "json_object"},
                            "temperature": temperature,
                            "max_tokens": 6_000,
                        },
                    )
                    response.raise_for_status()
                    body = response.json()
                    content = body["choices"][0]["message"]["content"]
                    if not content:
                        raise LLMGenerationError("provider returned empty content")
                    parsed = response_model.model_validate(json.loads(content))
                    usage = body.get("usage") or {}
                    return parsed, {
                        "model_name": body.get("model", self.model_name),
                        "input_tokens": usage.get("prompt_tokens"),
                        "output_tokens": usage.get("completion_tokens"),
                        "duration_ms": round((perf_counter() - started) * 1_000),
                    }
                except (httpx.HTTPError, KeyError, json.JSONDecodeError, ValidationError) as exc:
                    last_error = exc
                    if attempt >= self._max_retries:
                        break
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "The previous response was invalid. Return a complete JSON object "
                                "that exactly follows the supplied schema."
                            ),
                        }
                    )

        message = "structured LLM generation failed"
        if isinstance(last_error, httpx.HTTPStatusError):
            message = f"LLM provider returned HTTP {last_error.response.status_code}"
        raise LLMGenerationError(message) from last_error
