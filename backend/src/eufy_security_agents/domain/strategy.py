"""Product-prediction strategy: presets, deterministic RAG routing, agent brief.

The strategy layer never hardcodes a specific product and never overrides
evidence. It only (1) supplies named weight presets, (2) deterministically
tilts local-evidence layer quotas and in-layer ordering, and (3) injects a
uniform "Strategy Brief" telling each agent how strongly to *focus* — not what
to conclude.
"""

from __future__ import annotations

from eufy_security_agents.core.serialization import compact_json
from eufy_security_agents.domain.models import (
    ForecastRequest,
    KnowledgeLayer,
    ScoreWeights,
    StrategyProfile,
)

# The balanced default doubles as the neutral baseline: a dimension is only
# "emphasized" when its weight rises meaningfully above this baseline. Because
# the baseline equals the balanced preset, the balanced profile applies no
# tilt at all (pure base quotas), which keeps the feature auditable.
BALANCED_BASELINE: dict[str, float] = ScoreWeights().model_dump()

# Chinese labels for user-facing explanations.
DIMENSION_LABELS_ZH: dict[str, str] = {
    "innovation": "创新性",
    "user_value": "用户价值",
    "business_value": "商业价值",
    "cost_effectiveness": "性价比",
    "feasibility": "可行性",
    "eufy_synergy": "eufy 协同性",
}

LAYER_LABELS_ZH: dict[str, str] = {
    "eufy_foundation": "eufy 基础",
    "regional_market": "地区市场",
    "user_needs": "用户需求",
    "technology": "技术",
    "privacy_regulation": "隐私法规",
    "business": "商业",
    "risk_counterevidence": "反证",
}

# Which knowledge layers a high weight in a dimension should reinforce. The
# first layer in each list is the primary (larger) boost. Every layer still
# keeps its base quota; strategy only *adds*, so no layer is ever removed.
DIMENSION_LAYER_AFFINITY: dict[str, list[KnowledgeLayer]] = {
    "innovation": [
        KnowledgeLayer.TECHNOLOGY,
        KnowledgeLayer.USER_NEEDS,
        KnowledgeLayer.RISK_COUNTEREVIDENCE,
    ],
    "cost_effectiveness": [
        KnowledgeLayer.BUSINESS,
        KnowledgeLayer.USER_NEEDS,
        KnowledgeLayer.RISK_COUNTEREVIDENCE,
    ],
    "eufy_synergy": [
        KnowledgeLayer.EUFY_FOUNDATION,
        KnowledgeLayer.TECHNOLOGY,
    ],
    "feasibility": [
        KnowledgeLayer.TECHNOLOGY,
        KnowledgeLayer.RISK_COUNTEREVIDENCE,
    ],
    "user_value": [KnowledgeLayer.USER_NEEDS],
    "business_value": [KnowledgeLayer.BUSINESS, KnowledgeLayer.REGIONAL_MARKET],
}

# In-layer ordering hints: topics (from the retrieval TOPIC_ALIASES vocabulary)
# whose evidence should rank higher when a dimension is emphasized.
DIMENSION_TOPIC_AFFINITY: dict[str, list[str]] = {
    "innovation": ["edge_ai", "low_power"],
    "cost_effectiveness": ["subscription", "low_power", "interoperability"],
    "eufy_synergy": ["interoperability", "edge_ai"],
    "feasibility": ["low_power"],
    "user_value": [],
    "business_value": ["subscription"],
}

# Upper bound on how much strategy may add to a single layer's quota, so a tilt
# stays a tilt rather than swamping every other layer.
MAX_LAYER_BOOST = 4


def _emphasis(excess: float) -> int:
    """Integer emphasis for a dimension weighted ``excess`` above baseline."""
    if excess >= 0.12:
        return 2
    if excess >= 0.04:
        return 1
    return 0


def emphasized_dimensions(weights: ScoreWeights) -> dict[str, int]:
    """Dimensions weighted above baseline, mapped to their emphasis (1 or 2)."""
    dumped = weights.model_dump()
    result: dict[str, int] = {}
    for dimension, value in dumped.items():
        emphasis = _emphasis(value - BALANCED_BASELINE.get(dimension, 0.0))
        if emphasis > 0:
            result[dimension] = emphasis
    return result


def strategy_layer_adjustments(weights: ScoreWeights) -> dict[str, int]:
    """Deterministic per-layer quota deltas (layer value -> positive int).

    Only non-zero deltas are returned. Every layer still receives at least its
    base quota elsewhere, so this never drops a layer below its minimum.
    """
    deltas: dict[str, int] = {}
    for dimension, emphasis in emphasized_dimensions(weights).items():
        layers = DIMENSION_LAYER_AFFINITY.get(dimension, [])
        for index, layer in enumerate(layers):
            bump = emphasis if index == 0 else 1
            deltas[layer.value] = deltas.get(layer.value, 0) + bump
    return {layer: min(delta, MAX_LAYER_BOOST) for layer, delta in deltas.items() if delta > 0}


def strategy_topic_boosts(weights: ScoreWeights) -> dict[str, float]:
    """Topic -> in-layer ranking boost driven by emphasized dimensions."""
    boosts: dict[str, float] = {}
    for dimension, emphasis in emphasized_dimensions(weights).items():
        for topic in DIMENSION_TOPIC_AFFINITY.get(dimension, []):
            boosts[topic] = boosts.get(topic, 0.0) + float(emphasis)
    return boosts


def dominant_dimensions(weights: ScoreWeights, count: int = 2) -> list[str]:
    """The ``count`` highest-weighted dimensions, ties broken by canonical order."""
    dumped = weights.model_dump()
    order = list(ScoreWeights.model_fields)
    ranked = sorted(order, key=lambda dimension: (-dumped[dimension], order.index(dimension)))
    return ranked[:count]


# ---------------------------------------------------------------------------
# Preset catalogue (single source of truth; the frontend never copies weights).
# ---------------------------------------------------------------------------

_PRESET_SPECS: list[tuple[str, str, str, dict[str, float]]] = [
    (
        "balanced",
        "平衡模式",
        "在创新、价值、商业与落地之间保持平衡",
        {
            "innovation": 0.25,
            "user_value": 0.20,
            "business_value": 0.15,
            "cost_effectiveness": 0.15,
            "feasibility": 0.15,
            "eufy_synergy": 0.10,
        },
    ),
    (
        "breakthrough",
        "突破创新",
        "提高 AI 原生程度、新硬件形态和前沿技术探索比例",
        {
            "innovation": 0.40,
            "user_value": 0.20,
            "business_value": 0.10,
            "cost_effectiveness": 0.10,
            "feasibility": 0.10,
            "eufy_synergy": 0.10,
        },
    ),
    (
        "value",
        "极致性价比",
        "优先考虑用户获得价值、价格、维护成本和普及能力",
        {
            "innovation": 0.10,
            "user_value": 0.25,
            "business_value": 0.10,
            "cost_effectiveness": 0.35,
            "feasibility": 0.15,
            "eufy_synergy": 0.05,
        },
    ),
    (
        "ecosystem",
        "eufy 生态优先",
        "优先利用 HomeBase、现有设备、渠道和生态协同形成壁垒",
        {
            "innovation": 0.15,
            "user_value": 0.20,
            "business_value": 0.15,
            "cost_effectiveness": 0.10,
            "feasibility": 0.10,
            "eufy_synergy": 0.30,
        },
    ),
]


def strategy_presets() -> list[dict[str, object]]:
    """API-shaped preset catalogue with validated weights (each sums to 1.0)."""
    presets: list[dict[str, object]] = []
    for preset_id, label, description, weights in _PRESET_SPECS:
        validated = ScoreWeights(**weights)  # raises if a preset ever drifts off 1.0
        presets.append(
            {
                "id": preset_id,
                "label": label,
                "description": description,
                "weights": validated.model_dump(),
            }
        )
    return presets


def preset_label(profile: StrategyProfile) -> str:
    for preset_id, label, _description, _weights in _PRESET_SPECS:
        if preset_id == profile.value:
            return label
    return "自定义权重"


def strategy_explanation(weights: ScoreWeights, profile: StrategyProfile) -> str:
    """Human-readable, data-derived summary of the RAG tilt (Chinese)."""
    adjustments = strategy_layer_adjustments(weights)
    label = preset_label(profile)
    if not adjustments:
        return f"本次为{label}策略，七个知识层保持基础配额、未做倾斜；所有七层均被保留。"
    parts = [
        f"{LAYER_LABELS_ZH.get(layer, layer)}层证据配额提高 {delta} 条"
        for layer, delta in sorted(adjustments.items(), key=lambda item: (-item[1], item[0]))
    ]
    return f"本次为{label}策略，因此{'；'.join(parts)}；所有七层仍被保留。"


def strategy_brief(request: ForecastRequest) -> str:
    """Uniform Strategy Brief injected into every agent prompt.

    Tells the model the profile, the six weights and the top two dimensions, and
    fences the interpretation: weights are research *focus*, not permission to
    ignore or fabricate evidence.
    """
    dominant = dominant_dimensions(request.weights)
    dominant_text = ", ".join(
        f"{dim} ({request.weights.model_dump()[dim]:.2f})" for dim in dominant
    )
    return (
        "Product prediction strategy:\n"
        f"- strategy_profile: {request.strategy_profile.value}\n"
        f"- six-dimension weights: {compact_json(request.weights)}\n"
        f"- highest-priority dimensions: {dominant_text}\n"
        "Interpret weights as how much research attention to spend on each "
        "dimension, not as a licence to ignore evidence. Do not invent, inflate "
        "or omit trends, jobs, risks or scores to satisfy a weight. Empty "
        "research_context fields remain unknown. Every claim must still cite only "
        "valid EV-* evidence IDs supplied in this run. A high weight raises focus "
        "and depth on that dimension; it never overrides counter-evidence or "
        "unresolved disagreement."
    )
