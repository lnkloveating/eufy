"""Deterministic pre-validation roles and the final adjudicator.

Every role here is a pure function over a snapshotted :class:`ProductSpec`, a
:class:`ValidationHypothesis` and (optionally) a deterministic scenario result.
The roles produce observations and findings; the adjudicator maps them to one
:class:`ExperimentVerdict`. Nothing fabricates a pass rate, an accuracy number or
a user-study result — empirical claims are surfaced as ``requires_real_world_test``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from .models import ProductSpec, QuestionCategory, ValidationHypothesis
from .product_workbench import classify_question
from .scenario_simulation import Capabilities, detect_capabilities
from .validation import (
    ExperimentType,
    ExperimentVerdict,
    FindingSeverity,
    ObservationSourceType,
    ScenarioSimulation,
    ScenarioTemplate,
    ValidationRole,
)

# Keywords marking a claim as inherently empirical: something the current
# simulation cannot prove, so a positive result must become
# ``requires_real_world_test`` rather than ``supported_in_simulation``.
_EMPIRICAL_KEYWORDS = (
    "付费", "愿意", "价格", "定价", "订阅", "price", "pay", "willing", "purchase",
    "采用", "adoption", "接受度", "acceptance", "满意", "satisfaction",
    "误报率", "漏报", "false positive", "false alarm", "accuracy", "准确率", "准确性",
    "完成率", "completion", "留存", "retention", "转化", "conversion",
    "续航", "battery life", "功耗", "power draw", "量产", "manufactur", "成本", "cost",
    "真实用户", "real user", "field", "现场", "市场", "market",
)

_OFFLINE_KEYWORDS = ("断网", "离线", "offline", "本地", "端侧", "edge", "on-device", "弱网")
_PRESENCE_KEYWORDS = ("雷达", "presence", "存在", "夜间", "跌倒", "fall", "老人", "elder")
_AUTOMATION_KEYWORDS = ("自动", "联动", "执行", "门锁", "lock", "布防", "action", "干预")
_SENSITIVE_KEYWORDS = ("老人", "儿童", "访客", "child", "elder", "guest", "隐私", "卧室")

_CATEGORY_TO_TYPE: dict[QuestionCategory, ExperimentType] = {
    QuestionCategory.TECHNOLOGY: ExperimentType.TECHNOLOGY,
    QuestionCategory.PRIVACY: ExperimentType.PRIVACY_SECURITY,
    QuestionCategory.USER_EXPERIENCE: ExperimentType.USER_SCENARIO,
    QuestionCategory.BUSINESS: ExperimentType.BUSINESS,
    QuestionCategory.COMPETITION: ExperimentType.BUSINESS,
    QuestionCategory.ECOSYSTEM: ExperimentType.TECHNOLOGY,
    QuestionCategory.GENERAL: ExperimentType.DETERMINISTIC_SIMULATION,
}


class Stance(StrEnum):
    SUPPORTIVE = "supportive"
    CONCERN = "concern"
    BLOCKING = "blocking"
    NEEDS_REAL_WORLD = "needs_real_world"
    NEUTRAL = "neutral"


class FindingDraft(BaseModel):
    category: str
    title: str
    detail: str
    severity: FindingSeverity
    recommended_change: str
    source_type: ObservationSourceType
    target_section: str = "risks"


class RoleReport(BaseModel):
    role: ValidationRole
    stance: Stance
    headline: str
    rationale: str
    source_type: ObservationSourceType
    supports_hypothesis: bool | None = None
    findings: list[FindingDraft] = Field(default_factory=list)


def _kw(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def hypothesis_text(hypothesis: ValidationHypothesis) -> str:
    return " ".join(
        [
            hypothesis.assumption,
            hypothesis.metric,
            hypothesis.proposed_method,
            hypothesis.pass_condition,
        ]
    ).casefold()


def metric_requires_real_world(hypothesis: ValidationHypothesis) -> bool:
    """True when the claim is inherently empirical (cannot be proven in simulation)."""

    return _kw(hypothesis_text(hypothesis), _EMPIRICAL_KEYWORDS)


def plan_experiment_type(hypothesis: ValidationHypothesis) -> ExperimentType:
    category = classify_question(
        f"{hypothesis.assumption} {hypothesis.metric} {hypothesis.proposed_method}"
    )
    return _CATEGORY_TO_TYPE[category]


def plan_scenario_template(hypothesis: ValidationHypothesis) -> ScenarioTemplate:
    text = hypothesis_text(hypothesis)
    if _kw(text, ("断网", "离线", "offline", "网络", "network", "弱网", "outage")):
        return ScenarioTemplate.HOME_NETWORK_OUTAGE
    if _kw(text, ("老人", "夜间", "跌倒", "照护", "elder", "senior", "night", "fall")):
        return ScenarioTemplate.ELDERLY_NIGHT_ANOMALY
    if _kw(text, ("宠物", "误报", "pet", "false alarm", "false positive")):
        return ScenarioTemplate.PET_FALSE_ALARM
    return ScenarioTemplate.URBAN_APARTMENT_INTRUSION


# --------------------------------------------------------------------------- #
# Roles                                                                         #
# --------------------------------------------------------------------------- #


def analyze_technology(
    spec: ProductSpec, hypothesis: ValidationHypothesis, caps: Capabilities
) -> RoleReport:
    text = hypothesis_text(hypothesis)
    findings: list[FindingDraft] = []
    stance = Stance.NEUTRAL

    if _kw(text, _OFFLINE_KEYWORDS) and any(
        token in text for token in ("断网", "离线", "offline", "本地", "端侧", "edge")
    ):
        if caps.local_first:
            stance = Stance.SUPPORTIVE
        else:
            stance = Stance.BLOCKING
            findings.append(
                FindingDraft(
                    category="technology",
                    title="缺少本地/端侧兜底以支撑离线假设",
                    detail="该假设依赖断网或本地运行，但硬件架构与决策边界未体现端侧/本地中枢能力。",
                    severity=FindingSeverity.CRITICAL,
                    recommended_change="在硬件架构补充端侧算力或本地中枢，并在决策边界明确断网降级路径。",
                    source_type=ObservationSourceType.EXISTING_EVIDENCE,
                    target_section="hardware",
                )
            )

    if _kw(text, _PRESENCE_KEYWORDS) and not (caps.radar or caps.motion):
        stance = Stance.BLOCKING
        findings.append(
            FindingDraft(
                category="technology",
                title="缺少适配的存在/运动感知模态",
                detail="该假设需要感知人员在场或活动，但产品定义未包含雷达或运动传感等适配模态。",
                severity=FindingSeverity.WARNING,
                recommended_change="在硬件架构中补充雷达或运动感知，以支撑相关场景的可靠判断。",
                source_type=ObservationSourceType.EXISTING_EVIDENCE,
                target_section="hardware",
            )
        )

    if stance not in (Stance.BLOCKING,):
        if caps.entry_modalities >= 2 or caps.ai_classification:
            stance = Stance.SUPPORTIVE
        if metric_requires_real_world(hypothesis):
            stance = Stance.NEEDS_REAL_WORLD

    headline = {
        Stance.SUPPORTIVE: "现有硬件与 AI 能力在结构上足以支撑该假设的判断链路",
        Stance.BLOCKING: "当前技术定义无法支撑该假设，存在结构性缺口",
        Stance.NEEDS_REAL_WORLD: "结构上可行，但关键指标属经验数据，需真实测试",
        Stance.NEUTRAL: "技术上未见明显阻碍，也未见强支撑",
        Stance.CONCERN: "技术可行性存在需要澄清的问题",
    }[stance]
    return RoleReport(
        role=ValidationRole.TECHNOLOGY,
        stance=stance,
        headline=headline,
        rationale=(
            f"可用入口感知模态数：{caps.entry_modalities}；本地/端侧能力："
            f"{'是' if caps.local_first else '否'}；"
            f"AI 分类：{'是' if caps.ai_classification else '否'}。"
        ),
        source_type=ObservationSourceType.EXISTING_EVIDENCE,
        supports_hypothesis=_supports(stance),
        findings=findings,
    )


def analyze_privacy_security(
    spec: ProductSpec, hypothesis: ValidationHypothesis, caps: Capabilities
) -> RoleReport:
    text = hypothesis_text(hypothesis)
    findings: list[FindingDraft] = []
    stance = (
        Stance.SUPPORTIVE
        if (spec.privacy_principles and caps.privacy_local)
        else Stance.CONCERN
    )

    if caps.camera and not caps.privacy_local:
        stance = Stance.CONCERN
        findings.append(
            FindingDraft(
                category="privacy",
                title="室内摄像头缺少本地处理/最小化承诺",
                detail="产品包含摄像头但隐私原则未明确本地处理、分区遮蔽或数据最小化。",
                severity=FindingSeverity.WARNING,
                recommended_change="在隐私原则补充默认本地处理、敏感区域分区遮蔽与数据最小化。",
                source_type=ObservationSourceType.EXISTING_EVIDENCE,
                target_section="privacy",
            )
        )

    if _kw(text, _AUTOMATION_KEYWORDS) and not caps.human_gate:
        stance = Stance.CONCERN
        findings.append(
            FindingDraft(
                category="privacy",
                title="高影响自动化缺少人工确认边界",
                detail="该假设涉及自动执行或设备联动，但决策边界未要求高影响动作经过人工确认。",
                severity=FindingSeverity.WARNING,
                recommended_change="在决策边界约束：高影响设备动作需用户确认或经过可审计策略。",
                source_type=ObservationSourceType.EXISTING_EVIDENCE,
                target_section="ai",
            )
        )

    if _kw(text, _SENSITIVE_KEYWORDS) and not findings and caps.privacy_local:
        stance = Stance.SUPPORTIVE

    headline = {
        Stance.SUPPORTIVE: "隐私原则与敏感场景相容，边界在结构上成立",
        Stance.CONCERN: "隐私/安全边界存在需补强的缺口",
        Stance.BLOCKING: "隐私边界与该假设存在冲突",
        Stance.NEEDS_REAL_WORLD: "隐私接受度需真实用户验证",
        Stance.NEUTRAL: "未见明显隐私冲突",
    }[stance]
    return RoleReport(
        role=ValidationRole.PRIVACY_SECURITY,
        stance=stance,
        headline=headline,
        rationale=(
            f"隐私原则数：{len(spec.privacy_principles)}；"
            f"本地处理：{'有' if caps.privacy_local else '不足'}；"
            f"人工确认边界：{'有' if caps.human_gate else '缺'}。"
        ),
        source_type=ObservationSourceType.EXISTING_EVIDENCE,
        supports_hypothesis=_supports(stance),
        findings=findings,
    )


def analyze_user_scenario(
    spec: ProductSpec, hypothesis: ValidationHypothesis, scenario: ScenarioSimulation
) -> RoleReport:
    findings: list[FindingDraft] = []
    verdict = scenario.verdict
    if verdict == ExperimentVerdict.CONTRADICTED:
        stance = Stance.BLOCKING
        findings.append(
            FindingDraft(
                category="user_scenario",
                title=f"场景『{scenario.title}』出现反例",
                detail=scenario.verdict_rationale,
                severity=FindingSeverity.CRITICAL,
                recommended_change=(
                    scenario.failure_conditions[0]
                    if scenario.failure_conditions
                    else "补齐该场景所需的感知或决策能力。"
                ),
                source_type=ObservationSourceType.DETERMINISTIC_SIMULATION,
                target_section=_scenario_section(scenario.template),
            )
        )
    elif verdict == ExperimentVerdict.SUPPORTED_IN_SIMULATION:
        stance = Stance.SUPPORTIVE
    elif verdict == ExperimentVerdict.REQUIRES_REAL_WORLD_TEST:
        stance = Stance.NEEDS_REAL_WORLD
    else:
        stance = Stance.CONCERN
        findings.append(
            FindingDraft(
                category="user_scenario",
                title=f"场景『{scenario.title}』证据不足",
                detail=scenario.verdict_rationale,
                severity=FindingSeverity.WARNING,
                recommended_change="澄清该场景下的感知方式或决策路径，使模拟能够形成明确结论。",
                source_type=ObservationSourceType.DETERMINISTIC_SIMULATION,
                target_section=_scenario_section(scenario.template),
            )
        )

    return RoleReport(
        role=ValidationRole.USER_SCENARIO,
        stance=stance,
        headline=f"场景推演『{scenario.title}』模拟结论：{_verdict_label(verdict)}",
        rationale=scenario.verdict_rationale,
        source_type=ObservationSourceType.DETERMINISTIC_SIMULATION,
        supports_hypothesis=_supports(stance),
        findings=findings,
    )


def analyze_business(
    spec: ProductSpec, hypothesis: ValidationHypothesis, caps: Capabilities
) -> RoleReport:
    text = hypothesis_text(hypothesis)
    findings: list[FindingDraft] = []
    recurring = (spec.business_model.recurring_revenue or "").casefold()

    # Specific forced-subscription phrases only — a bare "锁定" would also match
    # the negated "不锁定", so we never trigger on a single ambiguous token.
    if _kw(recurring, ("强制订阅", "强制付费", "必须订阅", "mandatory subscription")):
        findings.append(
            FindingDraft(
                category="business",
                title="经常性收入可能依赖强制订阅",
                detail="商业模式中的经常性收入描述带有强制/锁定含义，可能与隐私定位和用户接受度冲突。",
                severity=FindingSeverity.WARNING,
                recommended_change="将核心安全能力与订阅解耦，仅将增值服务作为可选经常性收入。",
                source_type=ObservationSourceType.EXISTING_EVIDENCE,
                target_section="business",
            )
        )

    if _kw(text, _EMPIRICAL_KEYWORDS) or _kw(text, ("付费", "价格", "订阅", "revenue", "商业")):
        stance = Stance.NEEDS_REAL_WORLD
        headline = "付费意愿、价格与市场表现属经验指标，模拟无法证明，需真实测试"
    elif findings:
        stance = Stance.CONCERN
        headline = "商业模式存在需要澄清的结构性问题"
    else:
        stance = Stance.NEUTRAL
        headline = "该假设与商业模式无直接冲突"

    return RoleReport(
        role=ValidationRole.BUSINESS,
        stance=stance,
        headline=headline,
        rationale=(
            f"硬件收入：{spec.business_model.hardware_revenue[:40] or '未定义'}；"
            f"经常性收入：{spec.business_model.recurring_revenue or '未定义'}。"
        ),
        source_type=ObservationSourceType.EXISTING_EVIDENCE,
        supports_hypothesis=_supports(stance),
        findings=findings,
    )


def analyze_adversarial(
    spec: ProductSpec,
    hypothesis: ValidationHypothesis,
    prior_reports: list[RoleReport],
    scenario: ScenarioSimulation,
) -> RoleReport:
    blocking = [report for report in prior_reports if report.stance == Stance.BLOCKING]
    findings: list[FindingDraft] = []
    if blocking or scenario.verdict == ExperimentVerdict.CONTRADICTED:
        stance = Stance.BLOCKING
        headline = "反方审查确认存在阻断性缺口或场景反例，正向结论不成立"
        rationale = "存在至少一个角色或场景给出阻断性结论；在缺口修复前不能视为模拟支持。"
    else:
        stance = Stance.NEEDS_REAL_WORLD
        headline = "即便模拟正向，真实误报率、付费意愿、量产成本与用户接受度仍无法由本系统证明"
        rationale = "本实验室为预验证：任何经验性指标都需要真实硬件或真实用户测试，模拟不可替代。"

    return RoleReport(
        role=ValidationRole.ADVERSARIAL,
        stance=stance,
        headline=headline,
        rationale=rationale,
        source_type=ObservationSourceType.DETERMINISTIC_SIMULATION,
        supports_hypothesis=False if stance == Stance.BLOCKING else None,
        findings=findings,
    )


# --------------------------------------------------------------------------- #
# Adjudicator                                                                   #
# --------------------------------------------------------------------------- #


def adjudicate(
    hypothesis: ValidationHypothesis,
    reports: list[RoleReport],
    scenario: ScenarioSimulation,
) -> tuple[ExperimentVerdict, str, str]:
    """Combine role stances and the scenario into one honest verdict."""

    stances = {report.stance for report in reports}
    empirical = metric_requires_real_world(hypothesis)

    if Stance.BLOCKING in stances or scenario.verdict == ExperimentVerdict.CONTRADICTED:
        verdict = ExperimentVerdict.CONTRADICTED
        rationale = "至少一个角色或 场景推演给出阻断性结论/反例，假设在当前定义下被模拟证伪。"
    elif empirical:
        verdict = ExperimentVerdict.REQUIRES_REAL_WORLD_TEST
        rationale = "关键指标属经验数据（付费、准确率、接受度或成本），必须真实测试，模拟无法替代。"
    else:
        has_support = Stance.SUPPORTIVE in stances or (
            scenario.verdict == ExperimentVerdict.SUPPORTED_IN_SIMULATION
        )
        has_concern = Stance.CONCERN in stances or (
            scenario.verdict == ExperimentVerdict.INCONCLUSIVE
        )
        needs_real = (
            Stance.NEEDS_REAL_WORLD in stances
            or scenario.verdict == ExperimentVerdict.REQUIRES_REAL_WORLD_TEST
        )
        if has_support and not has_concern:
            verdict = ExperimentVerdict.SUPPORTED_IN_SIMULATION
            rationale = "多个角色与 场景推演在结构上一致支持该假设；仅为模拟支持，非真实验证。"
        elif has_concern and not has_support:
            verdict = ExperimentVerdict.INCONCLUSIVE
            rationale = "角色意见与场景结论存在缺口，现有信息不足以形成模拟支持结论。"
        elif has_support and has_concern:
            verdict = ExperimentVerdict.INCONCLUSIVE
            rationale = "存在支持与顾虑并存的混合结论，需先澄清缺口再复评。"
        elif needs_real:
            verdict = ExperimentVerdict.REQUIRES_REAL_WORLD_TEST
            rationale = "结构上未见阻碍，但结论依赖真实测试才能确认。"
        else:
            verdict = ExperimentVerdict.INCONCLUSIVE
            rationale = "角色未形成明确的支持或反对，判为证据不足。"

    supportive = sorted(r.role.value for r in reports if r.stance == Stance.SUPPORTIVE)
    blocking = sorted(r.role.value for r in reports if r.stance == Stance.BLOCKING)
    finding_count = sum(len(r.findings) for r in reports)
    summary = (
        f"裁决：{_verdict_label(verdict)}。支持角色：{', '.join(supportive) or '无'}；"
        f"阻断角色：{', '.join(blocking) or '无'}；生成 {finding_count} 条改进项。"
    )
    return verdict, rationale, summary


def overall_verdict(experiment_verdicts: list[ExperimentVerdict]) -> ExperimentVerdict:
    """Roll up experiment verdicts, most-negative first."""

    priority = [
        ExperimentVerdict.CONTRADICTED,
        ExperimentVerdict.INCONCLUSIVE,
        ExperimentVerdict.REQUIRES_REAL_WORLD_TEST,
        ExperimentVerdict.SUPPORTED_IN_SIMULATION,
    ]
    present = set(experiment_verdicts)
    for verdict in priority:
        if verdict in present:
            return verdict
    return ExperimentVerdict.NOT_RUN


def _supports(stance: Stance) -> bool | None:
    if stance == Stance.SUPPORTIVE:
        return True
    if stance == Stance.BLOCKING:
        return False
    return None


def _scenario_section(template: ScenarioTemplate) -> str:
    return {
        ScenarioTemplate.URBAN_APARTMENT_INTRUSION: "hardware",
        ScenarioTemplate.ELDERLY_NIGHT_ANOMALY: "privacy",
        ScenarioTemplate.PET_FALSE_ALARM: "ai",
        ScenarioTemplate.HOME_NETWORK_OUTAGE: "hardware",
    }[template]


_VERDICT_LABELS = {
    ExperimentVerdict.NOT_RUN: "未运行",
    ExperimentVerdict.SUPPORTED_IN_SIMULATION: "模拟支持",
    ExperimentVerdict.INCONCLUSIVE: "证据不足",
    ExperimentVerdict.CONTRADICTED: "出现反例",
    ExperimentVerdict.REQUIRES_REAL_WORLD_TEST: "需真实测试",
}


def _verdict_label(verdict: ExperimentVerdict) -> str:
    return _VERDICT_LABELS[verdict]


def build_capabilities(spec: ProductSpec) -> Capabilities:
    return detect_capabilities(spec)
