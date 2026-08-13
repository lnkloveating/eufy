"""Shared agent mechanics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel

from eufy_security_agents.domain.ports import StructuredLLM

TModel = TypeVar("TModel", bound=BaseModel)


@dataclass(frozen=True)
class AgentOutput[TModel: BaseModel]:
    value: TModel
    metadata: dict[str, int | str | None]


class BaseAgent:
    name = "base-agent"
    prompt_version = "1.0"

    def __init__(self, llm: StructuredLLM) -> None:
        self._llm = llm

    async def _generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[TModel],
        temperature: float = 0.4,
    ) -> AgentOutput[TModel]:
        value, metadata = await self._llm.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            temperature=temperature,
        )
        return AgentOutput(value=value, metadata=metadata)
