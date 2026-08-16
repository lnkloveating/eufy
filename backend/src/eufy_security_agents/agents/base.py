"""Shared agent mechanics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

from pydantic import BaseModel

from eufy_security_agents.domain.ports import StructuredLLM

TModel = TypeVar("TModel", bound=BaseModel)

DISPLAY_LANGUAGE_POLICY = (
    "\n\n输出语言规则：如果研究问题、用户输入或任务上下文主要使用中文，所有面向用户展示的"
    "自然语言字段必须使用自然、易读的简体中文；但候选产品和产品定义的 name 字段必须使用"
    "简短、自然、可读的英文品牌名，不得翻译成中文。品牌名以及 AI、HomeBase、mmWave、Wi-Fi、"
    "PIPL、GDPR 等必要专有名词可以保留；除产品名外不得输出整段英文说明。JSON 字段名、枚举值、"
    "证据编号和其它机器契约保持原样。"
)


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
            system_prompt=f"{system_prompt}{DISPLAY_LANGUAGE_POLICY}",
            user_prompt=user_prompt,
            response_model=response_model,
            temperature=temperature,
        )
        return AgentOutput(value=value, metadata=metadata)
