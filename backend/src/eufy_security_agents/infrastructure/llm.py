"""OpenAI-compatible structured-output client.

Only the provider boundary knows about HTTP. Agent and domain modules depend on the
StructuredLLM protocol and can be tested with a fake implementation.
"""

from __future__ import annotations

import json
from time import perf_counter
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

TModel = TypeVar("TModel", bound=BaseModel)


class LLMConfigurationError(RuntimeError):
    """Raised when the provider cannot be called because configuration is missing."""


class LLMGenerationError(RuntimeError):
    """Raised after provider or schema-validation retries are exhausted.

    The structured attributes are intentionally safe to persist in an artifact or
    SSE event. They contain failure categories and token counts, never prompts,
    responses, API keys or authorization headers.
    """

    def __init__(
        self,
        message: str,
        *,
        failure_kind: str = "unknown",
        attempts: int = 0,
        detail: str | None = None,
        metadata: dict[str, int | str | None] | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_kind = failure_kind
        self.attempts = attempts
        self.detail = detail
        self.metadata = metadata or {}

    def diagnostic_payload(self) -> dict[str, Any]:
        return {
            "failure_kind": self.failure_kind,
            "attempts": self.attempts,
            "detail": self.detail,
            "model_name": self.metadata.get("model_name"),
            "input_tokens": self.metadata.get("input_tokens"),
            "output_tokens": self.metadata.get("output_tokens"),
            "duration_ms": self.metadata.get("duration_ms"),
        }


class _StructuredResponseError(ValueError):
    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(detail)
        self.kind = kind
        self.detail = detail


class OpenAICompatibleLLM:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model_name: str,
        timeout_seconds: float = 120,
        max_retries: int = 2,
        max_output_tokens: int = 6_000,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self.model_name = model_name
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._max_output_tokens = max_output_tokens
        self._transport = transport

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
        last_kind = "unknown"
        last_detail = "provider did not return a valid structured response"
        input_tokens = 0
        output_tokens = 0
        saw_input_usage = False
        saw_output_usage = False
        started = perf_counter()

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
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
                            "max_tokens": self._max_output_tokens,
                        },
                    )
                    response.raise_for_status()
                    body = response.json()
                    choice = body["choices"][0]
                    usage = body.get("usage") or {}
                    prompt_tokens = usage.get("prompt_tokens")
                    completion_tokens = usage.get("completion_tokens")
                    if isinstance(prompt_tokens, int):
                        input_tokens += prompt_tokens
                        saw_input_usage = True
                    if isinstance(completion_tokens, int):
                        output_tokens += completion_tokens
                        saw_output_usage = True

                    finish_reason = choice.get("finish_reason")
                    if finish_reason == "length":
                        raise _StructuredResponseError(
                            "truncated",
                            f"provider stopped at the {self._max_output_tokens}-token output limit",
                        )
                    content = choice["message"]["content"]
                    if not content:
                        raise _StructuredResponseError(
                            "empty_response", "provider returned empty content"
                        )
                    try:
                        decoded = json.loads(content)
                    except json.JSONDecodeError as exc:
                        raise _StructuredResponseError(
                            "invalid_json",
                            f"JSON decoding failed at line {exc.lineno}, column {exc.colno}",
                        ) from exc
                    try:
                        parsed = response_model.model_validate(decoded)
                    except ValidationError as exc:
                        raise _StructuredResponseError(
                            "schema_validation", _validation_detail(exc)
                        ) from exc
                    return parsed, {
                        "model_name": body.get("model", self.model_name),
                        "input_tokens": input_tokens if saw_input_usage else None,
                        "output_tokens": output_tokens if saw_output_usage else None,
                        "duration_ms": round((perf_counter() - started) * 1_000),
                    }
                except (
                    httpx.HTTPError,
                    KeyError,
                    json.JSONDecodeError,
                    _StructuredResponseError,
                ) as exc:
                    last_error = exc
                    last_kind, last_detail = _classify_failure(exc)
                    if attempt >= self._max_retries:
                        break
                    messages.append(
                        {
                            "role": "user",
                            "content": _retry_instruction(last_kind, last_detail),
                        }
                    )

        attempts = self._max_retries + 1
        metadata: dict[str, int | str | None] = {
            "model_name": self.model_name,
            "input_tokens": input_tokens if saw_input_usage else None,
            "output_tokens": output_tokens if saw_output_usage else None,
            "duration_ms": round((perf_counter() - started) * 1_000),
        }
        message = (
            f"structured LLM generation failed after {attempts} attempts "
            f"({last_kind}: {last_detail})"
        )
        raise LLMGenerationError(
            message,
            failure_kind=last_kind,
            attempts=attempts,
            detail=last_detail,
            metadata=metadata,
        ) from last_error


def _validation_detail(exc: ValidationError) -> str:
    failures = [
        {
            "location": ".".join(str(part) for part in item.get("loc", ())),
            "type": item.get("type"),
            "message": item.get("msg"),
        }
        for item in exc.errors(include_url=False)[:5]
    ]
    return f"response failed schema validation: {json.dumps(failures, ensure_ascii=False)}"


def _classify_failure(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, _StructuredResponseError):
        return exc.kind, exc.detail
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code in {401, 403}:
            return "authentication", f"provider rejected credentials (HTTP {status_code})"
        return "provider_http", f"provider returned HTTP {status_code}"
    if isinstance(exc, httpx.TimeoutException):
        return "provider_timeout", "provider request timed out"
    if isinstance(exc, httpx.RequestError):
        return "provider_request", type(exc).__name__
    if isinstance(exc, json.JSONDecodeError):
        return "invalid_provider_json", "provider response body was not valid JSON"
    if isinstance(exc, KeyError):
        return "malformed_provider_response", f"provider response omitted {exc.args[0]!r}"
    return "unknown", type(exc).__name__


def _retry_instruction(failure_kind: str, detail: str) -> str:
    if failure_kind == "truncated":
        correction = (
            "The previous JSON was truncated. Be substantially more concise in every text field "
            "while preserving all required fields and requested items."
        )
    elif failure_kind == "schema_validation":
        correction = f"The previous JSON did not match the schema. Fix these errors: {detail}"
    elif failure_kind in {"invalid_json", "invalid_provider_json"}:
        correction = "The previous response was not complete valid JSON."
    else:
        correction = "The previous provider attempt failed."
    return (
        f"{correction} Return one complete JSON object only, exactly following the supplied "
        "schema. Do not add Markdown or prose."
    )
