"""Deterministic helpers for the Product Definition Workbench.

Everything here is pure and dependency-free so it can be unit-tested without an
LLM or a database:

* ``classify_question`` — a lightweight keyword classifier that decides which
  research context an answer should receive.
* ``category_context_plan`` — which knowledge layers and structured artifacts a
  given category should read.
* ``evaluate_readiness`` — an explainable Definition Readiness check. The LLM is
  never allowed to invent the readiness score; it is computed here.
"""

from __future__ import annotations

import re

from .models import (
    DefinitionStatus,
    KnowledgeLayer,
    ProductDefinitionReadiness,
    ProductSpec,
    QuestionCategory,
    ReadinessItem,
)

# Ordered so that, on a score tie, an earlier category wins. ``general`` is the
# fallback and is intentionally last.
CATEGORY_KEYWORDS: dict[QuestionCategory, tuple[str, ...]] = {
    QuestionCategory.PRIVACY: (
        "隐私",
        "数据保留",
        "保留时间",
        "删除",
        "儿童",
        "老人",
        "访客",
        "人脸",
        "合规",
        "法规",
        "同意",
        "授权",
        "敏感",
        "privacy",
        "data retention",
        "retention",
        "consent",
        "child",
        "children",
        "elder",
        "senior",
        "guest",
        "face",
        "gdpr",
        "compliance",
        "regulation",
    ),
    QuestionCategory.COMPETITION: (
        "竞品",
        "竞争",
        "对手",
        "差异",
        "区别",
        "抄袭",
        "护城河",
        "查重",
        "可防御",
        "ring",
        "nest",
        "arlo",
        "wyze",
        "google",
        "amazon",
        "competitor",
        "competition",
        "moat",
        "defensible",
        "alternative",
        "differentiat",
        "versus",
        " vs ",
    ),
    QuestionCategory.BUSINESS: (
        "商业",
        "价格",
        "定价",
        "订阅",
        "付费",
        "收入",
        "成本",
        "利润",
        "毛利",
        "渠道",
        "愿意购买",
        "愿意付费",
        "变现",
        "盈利",
        "business",
        "price",
        "pricing",
        "subscription",
        "revenue",
        "margin",
        "cost of ownership",
        "channel",
        "willing to pay",
        "monetiz",
        "profit",
        "buy",
        "purchase",
    ),
    QuestionCategory.ECOSYSTEM: (
        "生态",
        "homebase",
        "home base",
        "协同",
        "联动",
        "现有产品",
        "现有设备",
        "中枢",
        "兼容",
        "matter",
        "homekit",
        "ecosystem",
        "integrate",
        "integration",
        "synergy",
        "existing product",
        "hub",
        "interoper",
    ),
    QuestionCategory.TECHNOLOGY: (
        "技术",
        "端侧",
        "边缘",
        "芯片",
        "传感",
        "雷达",
        "算力",
        "电池",
        "功耗",
        "量产",
        "可行",
        "可实现",
        "模型",
        "硬件",
        "断网",
        "离线",
        "延迟",
        "本地运行",
        "technology",
        "technical",
        "edge",
        "on-device",
        "on device",
        "chip",
        "sensor",
        "radar",
        "battery",
        "power",
        "latency",
        "feasib",
        "manufactur",
        "offline",
        "network",
        "run locally",
        "produce",
    ),
    QuestionCategory.USER_EXPERIENCE: (
        "用户体验",
        "体验",
        "场景",
        "安装",
        "使用",
        "旅程",
        "易用",
        "误报",
        "上手",
        "学习成本",
        "user experience",
        "usability",
        "scenario",
        "install",
        "onboarding",
        "journey",
        "false alarm",
        "adoption",
        "ease of use",
    ),
}

# Which knowledge layers each category should pull local evidence from.
CATEGORY_LAYERS: dict[QuestionCategory, tuple[KnowledgeLayer, ...]] = {
    QuestionCategory.TECHNOLOGY: (
        KnowledgeLayer.TECHNOLOGY,
        KnowledgeLayer.RISK_COUNTEREVIDENCE,
        KnowledgeLayer.EUFY_FOUNDATION,
    ),
    QuestionCategory.PRIVACY: (
        KnowledgeLayer.PRIVACY_REGULATION,
        KnowledgeLayer.RISK_COUNTEREVIDENCE,
        KnowledgeLayer.REGIONAL_MARKET,
    ),
    QuestionCategory.COMPETITION: (
        KnowledgeLayer.EUFY_FOUNDATION,
        KnowledgeLayer.TECHNOLOGY,
        KnowledgeLayer.BUSINESS,
    ),
    QuestionCategory.BUSINESS: (
        KnowledgeLayer.BUSINESS,
        KnowledgeLayer.REGIONAL_MARKET,
        KnowledgeLayer.EUFY_FOUNDATION,
    ),
    QuestionCategory.ECOSYSTEM: (
        KnowledgeLayer.EUFY_FOUNDATION,
        KnowledgeLayer.TECHNOLOGY,
    ),
    QuestionCategory.USER_EXPERIENCE: (
        KnowledgeLayer.USER_NEEDS,
        KnowledgeLayer.REGIONAL_MARKET,
        KnowledgeLayer.RISK_COUNTEREVIDENCE,
    ),
    QuestionCategory.GENERAL: (
        KnowledgeLayer.EUFY_FOUNDATION,
        KnowledgeLayer.USER_NEEDS,
        KnowledgeLayer.TECHNOLOGY,
        KnowledgeLayer.BUSINESS,
        KnowledgeLayer.PRIVACY_REGULATION,
    ),
}

# Categories that should also see competitor records / the current-capability
# baseline / the novelty assessment for the selected candidate.
CATEGORIES_WITH_COMPETITORS = frozenset(
    {QuestionCategory.COMPETITION, QuestionCategory.BUSINESS, QuestionCategory.GENERAL}
)
CATEGORIES_WITH_BASELINE = frozenset(
    {QuestionCategory.COMPETITION, QuestionCategory.ECOSYSTEM, QuestionCategory.GENERAL}
)
CATEGORIES_WITH_NOVELTY = frozenset({QuestionCategory.COMPETITION})
CATEGORIES_WITH_CONSENSUS = frozenset(
    {QuestionCategory.GENERAL, QuestionCategory.USER_EXPERIENCE}
)

# Which forecasting lenses / reviewer dimensions each category should read.
CATEGORY_LENSES: dict[QuestionCategory, tuple[str, ...]] = {
    QuestionCategory.TECHNOLOGY: ("technology_trends", "security_futures"),
    QuestionCategory.PRIVACY: ("security_futures",),
    QuestionCategory.COMPETITION: ("market_futures",),
    QuestionCategory.BUSINESS: ("market_futures",),
    QuestionCategory.ECOSYSTEM: ("technology_trends",),
    QuestionCategory.USER_EXPERIENCE: ("user_trends",),
    QuestionCategory.GENERAL: (),
}
CATEGORY_REVIEW_DIMENSIONS: dict[QuestionCategory, frozenset[str]] = {
    QuestionCategory.TECHNOLOGY: frozenset({"feasibility", "innovation"}),
    QuestionCategory.PRIVACY: frozenset({"feasibility"}),
    QuestionCategory.COMPETITION: frozenset({"innovation", "business_value"}),
    QuestionCategory.BUSINESS: frozenset({"business_value", "cost_effectiveness"}),
    QuestionCategory.ECOSYSTEM: frozenset({"eufy_synergy"}),
    QuestionCategory.USER_EXPERIENCE: frozenset({"user_value"}),
    QuestionCategory.GENERAL: frozenset(),
}

# Canonical ProductSpec section keys a suggested change may target.
SPEC_SECTIONS: tuple[str, ...] = (
    "overview",
    "users_problem",
    "hardware",
    "ai",
    "capability_delta",
    "ecosystem",
    "privacy",
    "regional",
    "competition",
    "business",
    "risks",
    "assumptions",
    "validation",
)


def _normalize(text: str) -> str:
    return f" {text.casefold()} "


def classify_question(question: str) -> QuestionCategory:
    """Classify a question into a single category by keyword frequency.

    Deterministic: the category with the most keyword hits wins; ties are broken
    by the fixed ``CATEGORY_KEYWORDS`` order. No LLM involved so context
    selection is reproducible and testable.
    """

    haystack = _normalize(question)
    best_category = QuestionCategory.GENERAL
    best_score = 0
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword.casefold() in haystack)
        if score > best_score:
            best_score = score
            best_category = category
    return best_category


def _is_filled(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list | tuple | set | dict):
        return len(value) > 0
    return True


def evaluate_readiness(
    product: ProductSpec,
    *,
    outstanding_suggestions: int = 0,
    outstanding_issues: int = 0,
) -> ProductDefinitionReadiness:
    """Compute an explainable Definition Readiness result.

    Only completeness of the definition is checked here — never technical,
    commercial, privacy or scenario validity. ``ready`` and ``blocking_items``
    are fully deterministic so the decision can always be explained.
    """

    delta = product.capability_delta
    positioning = product.competitive_positioning
    risks_have_mitigation = bool(product.risks) and all(
        _is_filled(risk.mitigation) for risk in product.risks
    )
    high_severity_risks = [
        risk
        for risk in product.risks
        if any(token in risk.severity.casefold() for token in ("high", "critical", "高", "严重"))
    ]

    blocking_specs: list[tuple[str, str, bool, str | None]] = [
        ("core_problem", "核心问题已明确", _is_filled(product.core_problem), None),
        ("target_users", "目标用户已明确", _is_filled(product.target_users), None),
        ("form_factor", "产品形态已明确", _is_filled(product.form_factor), None),
        ("hardware", "硬件架构非空", _is_filled(product.hardware_architecture), None),
        (
            "ai_boundary",
            "AI 能力与决策边界已定义",
            _is_filled(product.ai_capabilities) and _is_filled(product.ai_decision_boundary),
            None,
        ),
        (
            "capability_delta",
            "与现有产品的差异已定义",
            _is_filled(delta.new_capabilities) and _is_filled(delta.hardware_or_system_delta),
            None,
        ),
        ("ecosystem", "eufy 生态关系已明确", _is_filled(product.ecosystem_relationships), None),
        ("privacy", "隐私原则已明确", _is_filled(product.privacy_principles), None),
        (
            "business",
            "商业模式已明确",
            _is_filled(product.business_model.hardware_revenue),
            None,
        ),
        (
            "risks_mitigation",
            "风险均有缓解方案",
            risks_have_mitigation,
            None if risks_have_mitigation else "存在缺少缓解方案的风险项",
        ),
        ("key_assumptions", "关键假设已列出", _is_filled(product.key_assumptions), None),
        ("kill_criteria", "Kill Criteria 已列出", _is_filled(product.kill_criteria), None),
        (
            "validation_hypotheses",
            "关键风险已转化为验证假设",
            _is_filled(product.validation_readiness),
            None,
        ),
        (
            "no_outstanding_suggestions",
            "没有尚未处理的修改建议",
            outstanding_suggestions == 0,
            None if outstanding_suggestions == 0 else f"{outstanding_suggestions} 条建议待处理",
        ),
        (
            "no_open_issues",
            "没有未处理的产品定义缺口",
            outstanding_issues == 0,
            None if outstanding_issues == 0 else f"{outstanding_issues} 个缺口待处理",
        ),
    ]

    warning_specs: list[tuple[str, str, bool, str | None]] = [
        ("regional_fit", "已提供地区适配", _is_filled(product.regional_fit), "缺少地区适配说明"),
        (
            "competitive_positioning",
            "竞争定位完整",
            _is_filled(positioning.closest_alternatives)
            and _is_filled(positioning.defensible_differences)
            and _is_filled(positioning.validation_questions),
            "竞争定位信息不完整",
        ),
        (
            "high_severity_coverage",
            "高严重度风险已有验证假设",
            not high_severity_risks or bool(product.validation_readiness),
            "高严重度风险尚未对应验证假设",
        ),
        (
            "evidence_labeling",
            "重要结论已经过证据审查",
            product.definition_status != DefinitionStatus.DRAFT,
            "尚未通过问答对定义进行证据/推断/假设标注",
        ),
    ]

    completed: list[ReadinessItem] = []
    blocking: list[ReadinessItem] = []
    for item_id, label, ok, detail in blocking_specs:
        item = ReadinessItem(id=item_id, label=label, ok=ok, detail=detail)
        (completed if ok else blocking).append(item)

    warnings: list[ReadinessItem] = []
    for item_id, label, ok, detail in warning_specs:
        if ok:
            completed.append(ReadinessItem(id=item_id, label=label, ok=True, detail=None))
        else:
            warnings.append(ReadinessItem(id=item_id, label=label, ok=False, detail=detail))

    total_blocking = len(blocking_specs)
    passed_blocking = total_blocking - len(blocking)
    score = round(passed_blocking / total_blocking * 100) if total_blocking else 100
    ready = not blocking

    return ProductDefinitionReadiness(
        product_id=product.id,
        version=product.version,
        definition_status=product.definition_status,
        ready=ready,
        score=score,
        completed_items=completed,
        blocking_items=blocking,
        warnings=warnings,
        outstanding_suggestions=outstanding_suggestions,
        next_recommended_questions=recommended_questions(product, blocking, warnings),
    )


# Deterministic question suggestions keyed to a readiness gap.
_GAP_QUESTIONS: dict[str, str] = {
    "privacy": "断网后，儿童、老人和访客的数据如何保留、脱敏和删除？",
    "capability_delta": "这个产品与现在主流的 eufy 产品有哪些本质区别？",
    "business": "如果不采用强制订阅，这个产品在商业上如何成立？",
    "hardware": "它可能使用哪些未来三年可以量产的硬件与传感技术？",
    "ecosystem": "它与 HomeBase 3 及现有 eufy 设备是什么关系？",
    "validation_hypotheses": "进入验证实验室前，最需要优先验证哪些关键假设？",
    "risks_mitigation": "当前最大的技术与落地风险是什么，如何缓解？",
    "regional_fit": "在不同目标地区，这个产品需要哪些必要的本地化调整？",
    "competitive_positioning": "最接近的竞品是什么，我们的可防御差异在哪里？",
    "evidence_labeling": "当前产品定义里，哪些内容仍然只是 AI 的设计假设？",
}

_DEFAULT_QUESTIONS: tuple[str, ...] = (
    "哪些能力可以在端侧运行，哪些必须依赖云端？",
    "为什么用户愿意购买这个产品？",
    "进入验证实验室前最需要验证什么？",
)


def recommended_questions(
    product: ProductSpec,
    blocking: list[ReadinessItem],
    warnings: list[ReadinessItem],
) -> list[str]:
    """Suggest next questions from the concrete readiness gaps (deterministic)."""

    questions: list[str] = []
    for item in [*blocking, *warnings]:
        mapped = _GAP_QUESTIONS.get(item.id)
        if mapped and mapped not in questions:
            questions.append(mapped)
    for fallback in _DEFAULT_QUESTIONS:
        if len(questions) >= 3:
            break
        if fallback not in questions:
            questions.append(fallback)
    return questions[:5]


def question_tokens(text: str) -> set[str]:
    """English words plus Chinese uni/bi-grams; matches the evidence tokenizer."""

    lowered = text.casefold()
    tokens = set(re.findall(r"[a-z0-9][a-z0-9_-]+", lowered))
    for sequence in re.findall(r"[一-鿿]+", lowered):
        tokens.update(sequence)
        tokens.update(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return tokens
