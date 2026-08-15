"""Optional LLM enrichment for the pre-validation lab.

The verdict and every structural finding are decided deterministically by the
domain roles. This agent only adds a short supplemental narrative (an
``ai_analysis`` observation) per experiment. Any failure is caught by the
workflow and the experiment still completes on deterministic results, so the LLM
is never on the critical path.
"""

from __future__ import annotations

from eufy_security_agents.domain.validation import (
    RoleAnalysisEnvelope,
    ValidationExperiment,
)

from .base import AgentOutput, BaseAgent

VALIDATION_ANALYST_SYSTEM = (
    "你是产品预验证实验室的分析助手。你只做补充解读，不下最终结论，也不得声称任何真实"
    "测试、真实用户或真实市场结果已经完成。你面对的是确定性模拟与产品定义，禁止编造具体"
    "百分比、准确率、通过率或用户研究数字。用用户的主要语言、简洁地输出。"
)


class ValidationAnalysisAgent(BaseAgent):
    """Adds a short, honest supplemental analysis to one experiment."""

    name = "validation-analyst"
    prompt_version = "1.0"

    async def analyze(
        self,
        *,
        experiment: ValidationExperiment,
        deterministic_summary: str,
        scenario_summary: str,
    ) -> AgentOutput[RoleAnalysisEnvelope]:
        prompt = (
            "以下是一个预验证实验的确定性分析结果，请在不改变裁决的前提下补充一段简短解读。\n\n"
            f"实验类型：{experiment.experiment_type.value}\n"
            f"假设：{experiment.assumption}\n"
            f"度量：{experiment.metric}\n"
            f"通过条件：{experiment.pass_condition}\n"
            f"确定性裁决摘要：{deterministic_summary}\n"
            f"场景推演摘要：{scenario_summary}\n\n"
            "请输出 JSON：analysis.headline（一句话补充观点）、analysis.rationale（简短理由）、"
            "analysis.open_questions（1-3 个仍需真实测试才能回答的问题）。"
            "不要给出任何具体数字或声称验证已通过。"
        )
        return await self._generate(
            system_prompt=VALIDATION_ANALYST_SYSTEM,
            user_prompt=prompt,
            response_model=RoleAnalysisEnvelope,
            temperature=0.3,
        )
