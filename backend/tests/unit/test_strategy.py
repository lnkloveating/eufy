"""Tests for the product-prediction strategy: weights, presets, RAG routing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from eufy_security_agents.domain.models import (
    ForecastRequest,
    KnowledgeLayer,
    ScoreWeights,
    StrategyAlignment,
    StrategyProfile,
)
from eufy_security_agents.domain.strategy import (
    dominant_dimensions,
    strategy_layer_adjustments,
    strategy_presets,
)
from eufy_security_agents.infrastructure.evidence import DEFAULT_LAYER_QUOTAS, LocalEvidenceStore

EVIDENCE_PATH = Path(__file__).resolve().parents[2] / "data" / "evidence"


def test_new_six_dimension_default_sums_to_one() -> None:
    weights = ScoreWeights()
    dumped = weights.model_dump()
    assert set(dumped) == {
        "innovation",
        "user_value",
        "business_value",
        "cost_effectiveness",
        "feasibility",
        "eufy_synergy",
    }
    assert abs(sum(dumped.values()) - 1.0) < 1e-9
    assert dumped["cost_effectiveness"] == 0.15


def test_legacy_five_dimension_weights_parse() -> None:
    legacy = {
        "innovation": 0.30,
        "user_value": 0.25,
        "business_value": 0.20,
        "feasibility": 0.15,
        "eufy_synergy": 0.10,
    }
    weights = ScoreWeights.model_validate(legacy)
    assert abs(sum(weights.model_dump().values()) - 1.0) < 1e-9


def test_legacy_weights_backfill_cost_effectiveness_to_zero() -> None:
    legacy = {
        "innovation": 0.30,
        "user_value": 0.25,
        "business_value": 0.20,
        "feasibility": 0.15,
        "eufy_synergy": 0.10,
    }
    weights = ScoreWeights.model_validate(legacy)
    assert weights.cost_effectiveness == 0.0
    # The other five historical weights are preserved unchanged.
    assert weights.innovation == 0.30
    assert weights.eufy_synergy == 0.10


def test_invalid_total_still_rejected() -> None:
    with pytest.raises(ValidationError):
        ScoreWeights(
            innovation=0.5,
            user_value=0.5,
            business_value=0.5,
            cost_effectiveness=0.5,
            feasibility=0.5,
            eufy_synergy=0.5,
        )


def test_every_preset_weights_sum_to_one() -> None:
    presets = strategy_presets()
    assert {preset["id"] for preset in presets} == {
        "balanced",
        "breakthrough",
        "value",
        "ecosystem",
    }
    for preset in presets:
        weights = preset["weights"]
        assert isinstance(weights, dict)
        assert abs(sum(weights.values()) - 1.0) < 1e-9


def test_legacy_forecast_request_without_strategy_profile_defaults_to_balanced() -> None:
    legacy_json = json.dumps(
        {
            "question": "预测未来三年美国家庭的AI原生安防产品机会",
            "regions": ["United States"],
            "target_users": ["Households"],
            "weights": {
                "innovation": 0.30,
                "user_value": 0.25,
                "business_value": 0.20,
                "feasibility": 0.15,
                "eufy_synergy": 0.10,
            },
        }
    )
    request = ForecastRequest.model_validate_json(legacy_json)
    assert request.strategy_profile == StrategyProfile.BALANCED
    assert request.weights.cost_effectiveness == 0.0
    assert abs(sum(request.weights.model_dump().values()) - 1.0) < 1e-9


def test_new_request_without_weights_uses_six_dimension_default() -> None:
    request = ForecastRequest(question="预测未来三年欧洲家庭的AI原生安防产品机会")
    assert request.weights.cost_effectiveness == 0.15
    assert request.strategy_profile == StrategyProfile.BALANCED


def test_strategy_alignment_rejects_invalid_dimensions() -> None:
    alignment = StrategyAlignment(
        aligned_dimensions=["innovation", "not_a_dimension", "cost_effectiveness"],
        rationale="focuses on affordable innovation",
        tradeoffs=["higher unit cost of edge silicon"],
    )
    # Invalid dimension names are dropped, valid ones (deduped) preserved.
    assert alignment.aligned_dimensions == ["innovation", "cost_effectiveness"]


def test_balanced_strategy_applies_no_layer_tilt() -> None:
    assert strategy_layer_adjustments(ScoreWeights()) == {}


def test_dominant_dimensions_are_top_two_weighted() -> None:
    breakthrough = next(p for p in strategy_presets() if p["id"] == "breakthrough")
    weights = ScoreWeights.model_validate(breakthrough["weights"])
    assert dominant_dimensions(weights)[0] == "innovation"


def _weights(profile_id: str) -> ScoreWeights:
    preset = next(p for p in strategy_presets() if p["id"] == profile_id)
    return ScoreWeights.model_validate(preset["weights"])


def test_strategies_produce_different_rag_quotas() -> None:
    store = LocalEvidenceStore(EVIDENCE_PATH)
    base = {
        "question": "预测未来三年美国城市家庭的AI原生安防产品机会",
        "regions": ["United States"],
        "target_users": ["Urban households"],
    }
    breakthrough = store.plan(
        ForecastRequest(
            **base, strategy_profile=StrategyProfile.BREAKTHROUGH, weights=_weights("breakthrough")
        )
    )
    ecosystem = store.plan(
        ForecastRequest(
            **base, strategy_profile=StrategyProfile.ECOSYSTEM, weights=_weights("ecosystem")
        )
    )
    value = store.plan(
        ForecastRequest(**base, strategy_profile=StrategyProfile.VALUE, weights=_weights("value"))
    )

    # Distinct strategies tilt distinct layers.
    assert breakthrough.layer_quotas != ecosystem.layer_quotas
    assert value.layer_quotas != ecosystem.layer_quotas
    # Breakthrough raises the technology layer; ecosystem raises eufy_foundation.
    assert (
        breakthrough.layer_quotas[KnowledgeLayer.TECHNOLOGY.value]
        > DEFAULT_LAYER_QUOTAS[KnowledgeLayer.TECHNOLOGY]
    )
    assert (
        ecosystem.layer_quotas[KnowledgeLayer.EUFY_FOUNDATION.value]
        > DEFAULT_LAYER_QUOTAS[KnowledgeLayer.EUFY_FOUNDATION]
    )
    assert breakthrough.strategy_adjustments != ecosystem.strategy_adjustments


def test_every_layer_keeps_at_least_its_base_quota_under_any_strategy() -> None:
    store = LocalEvidenceStore(EVIDENCE_PATH)
    base = {
        "question": "预测未来三年美国城市家庭的AI原生安防产品机会",
        "regions": ["United States"],
        "target_users": ["Urban households"],
    }
    for profile_id in ("balanced", "breakthrough", "value", "ecosystem"):
        plan = store.plan(
            ForecastRequest(
                **base,
                strategy_profile=StrategyProfile(profile_id),
                weights=_weights(profile_id),
            )
        )
        assert set(plan.required_layers) == set(KnowledgeLayer)
        for layer in KnowledgeLayer:
            assert plan.layer_quotas[layer.value] >= DEFAULT_LAYER_QUOTAS[layer]


def test_strategy_changes_in_layer_ordering_of_selected_evidence() -> None:
    store = LocalEvidenceStore(EVIDENCE_PATH)
    base = {
        "question": "预测未来三年美国城市家庭的AI原生安防产品机会",
        "regions": ["United States"],
        "target_users": ["Urban households"],
    }
    _, value_records = store.retrieve(
        ForecastRequest(**base, strategy_profile=StrategyProfile.VALUE, weights=_weights("value"))
    )
    _, breakthrough_records = store.retrieve(
        ForecastRequest(
            **base, strategy_profile=StrategyProfile.BREAKTHROUGH, weights=_weights("breakthrough")
        )
    )
    assert [record.id for record in value_records] != [record.id for record in breakthrough_records]
