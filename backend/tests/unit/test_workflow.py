from __future__ import annotations

import re
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel

from eufy_security_agents.domain.models import (
    BusinessModel,
    CandidateEnvelope,
    CandidateReview,
    CompetitiveAnalysis,
    CompetitiveAnalysisEnvelope,
    CompetitiveGap,
    CompetitivePositioning,
    ConsensusClaim,
    CrossLensChallenge,
    ForecastConsensus,
    ForecastConsensusEnvelope,
    ForecastRequest,
    LensDeliberation,
    LensDeliberationEnvelope,
    LensForecast,
    LensForecastEnvelope,
    Opportunity,
    OpportunityEnvelope,
    ProductCandidate,
    ProductSelectionRequest,
    ProductSpec,
    ProductSpecEnvelope,
    ReviewEnvelope,
    RiskItem,
    RunStatus,
    TrendSignal,
    ValidationHypothesis,
)
from eufy_security_agents.infrastructure.competitors import LocalCompetitorStore
from eufy_security_agents.infrastructure.evidence import LocalEvidenceStore
from eufy_security_agents.infrastructure.memory import InMemoryRunRepository
from eufy_security_agents.orchestration.workflow import ForecastWorkflow

T = TypeVar("T", bound=BaseModel)


class FakeStructuredLLM:
    model_name = "fake-model"

    def __init__(self) -> None:
        self.candidate_calls = 0

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
    ) -> tuple[T, dict[str, int | str | None]]:
        del system_prompt, temperature
        if response_model is LensForecastEnvelope:
            lens_match = re.search(r"lens identifier is '([^']+)'", user_prompt)
            assert lens_match is not None
            lens = lens_match.group(1)
            value = LensForecastEnvelope(
                forecast=LensForecast(
                    lens=lens,
                    thesis=f"{lens} thesis",
                    signals=[
                        TrendSignal(
                            title="signal one",
                            description="description",
                            impact_horizon="1-3 years",
                            evidence_ids=["EV-EUFY-001"],
                            confidence=0.8,
                            uncertainty="adoption speed",
                        ),
                        TrendSignal(
                            title="signal two",
                            description="description",
                            impact_horizon="2-3 years",
                            evidence_ids=["EV-USER-001"],
                            confidence=0.7,
                            uncertainty="regional variation",
                        ),
                    ],
                    implications=["implication one", "implication two"],
                )
            )
        elif response_model is OpportunityEnvelope:
            value = OpportunityEnvelope(
                opportunities=[
                    Opportunity(
                        id=f"OPP-{index:03d}",
                        title=f"Opportunity {index}",
                        unmet_job=f"Unmet job {index}",
                        target_users=["Households"],
                        target_regions=["United States"],
                        why_now="Evidence and technology converge.",
                        opportunity_window="1-3 years",
                        enabling_trends=["edge AI"],
                        evidence_ids=["EV-EUFY-001"],
                        counter_evidence=["cost uncertainty"],
                        confidence=0.7,
                    )
                    for index in range(1, 6)
                ]
            )
        elif response_model is CandidateEnvelope:
            self.candidate_calls += 1
            candidates = [_candidate(index) for index in range(1, 4)]
            if self.candidate_calls == 1:
                candidates[0] = candidates[0].model_copy(update={"evidence_ids": ["OPP-001"]})
            value = CandidateEnvelope(candidates=candidates)
        elif response_model is LensDeliberationEnvelope:
            lens_match = re.search(r"Review from the '([^']+)' perspective", user_prompt)
            lens = lens_match.group(1) if lens_match else "user_trends"
            value = LensDeliberationEnvelope(
                deliberation=LensDeliberation(
                    reviewer_lens=lens,
                    original_thesis="original thesis",
                    challenges=[
                        CrossLensChallenge(
                            id=f"CH-{lens.upper()}-01",
                            target_lens="market_futures",
                            challenged_claim="adoption is guaranteed",
                            challenge_reason="evidence does not establish adoption",
                            evidence_ids=["EV-EUFY-001"],
                            severity="high",
                        )
                    ],
                    revisions_to_own_view=["reduce confidence"],
                    unchanged_positions=["local inference remains useful"],
                    unresolved_questions=["installation friction"],
                    revised_thesis="revised thesis",
                    revised_confidence=0.68,
                )
            )
        elif response_model is ForecastConsensusEnvelope:
            value = ForecastConsensusEnvelope(
                consensus=ForecastConsensus(
                    consensus_claims=[
                        ConsensusClaim(
                            claim=f"Consensus {index}",
                            supporting_lenses=["user_trends", "technology_trends"],
                            evidence_ids=["EV-EUFY-001"],
                            confidence=0.7,
                        )
                        for index in range(1, 3)
                    ],
                    unresolved_disagreements=[],
                    minority_views=["installation friction may dominate"],
                    evidence_gaps=["measured false-alarm reduction"],
                    opportunity_implications=["validate adoption", "validate accuracy"],
                )
            )
        elif response_model is CompetitiveAnalysisEnvelope:
            value = CompetitiveAnalysisEnvelope(
                analysis=CompetitiveAnalysis(
                    market_patterns=["hardware plus optional service"],
                    established_capabilities=["object detection"],
                    competitor_strengths={"Ring": ["integrated monitoring"]},
                    competitor_limitations={"Ring": ["advanced features are plan-gated"]},
                    underserved_needs=["privacy-preserving prevention"],
                    subscription_or_lock_in_gaps=["advanced intelligence is often plan-gated"],
                    privacy_and_interoperability_gaps=["cross-brand context is fragmented"],
                    regional_differences={"United States": ["monitoring is mature"]},
                    gaps=[
                        CompetitiveGap(
                            id=f"GAP-{index:03d}",
                            title=f"Gap {index}",
                            description="Testable white space",
                            affected_opportunity_ids=[f"OPP-{index:03d}"],
                            competitor_brands=["Ring"],
                            competitor_evidence_ids=["COMP-RING-001"],
                            white_space="Local multi-sensor prevention",
                            design_implications=["preserve local decision making"],
                            imitation_risk="medium",
                            validation_question="Does it outperform camera-only alerts?",
                            confidence=0.7,
                        )
                        for index in range(1, 4)
                    ],
                )
            )
        elif response_model is ReviewEnvelope:
            dimension_match = re.search(r"only on '([^']+)'", user_prompt)
            dimension = dimension_match.group(1) if dimension_match else "innovation"
            value = ReviewEnvelope(
                reviews=[
                    CandidateReview(
                        candidate_id=f"CAND-{index:03d}",
                        dimension=dimension,
                        score=92 - index * 7,
                        strengths=["clear value"],
                        concerns=["requires validation"],
                        decisive_question="Will users adopt it?",
                    )
                    for index in range(1, 4)
                ]
            )
        elif response_model is ProductSpecEnvelope:
            value = ProductSpecEnvelope(product=_product_spec())
        else:  # pragma: no cover
            raise AssertionError(response_model)
        return value, {
            "model_name": self.model_name,
            "input_tokens": 100,
            "output_tokens": 200,
            "duration_ms": 10,
        }  # type: ignore[return-value]


def _candidate(index: int) -> ProductCandidate:
    return ProductCandidate(
        id=f"CAND-{index:03d}",
        name=f"Product {index}",
        tagline="A future security device",
        opportunity_ids=[f"OPP-00{index}"],
        target_users=["Households"],
        target_regions=["United States"],
        core_problem="A real household security problem",
        value_proposition="A distinct value proposition",
        form_factor="Purpose-built hardware",
        hardware_components=["sensor", "processor"],
        ai_native_mechanism="Local model combines weak signals into decisions.",
        key_scenarios=["home security event"],
        differentiators=["local intelligence"],
        estimated_price_range="$100-$200",
        technical_dependencies=["edge AI"],
        key_assumptions=["Users value the outcome"],
        kill_criteria=["Adoption below threshold"],
        evidence_ids=["EV-EUFY-001"],
        competitive_positioning=_competitive_positioning(),
    )


def _competitive_positioning() -> CompetitivePositioning:
    return CompetitivePositioning(
        closest_alternatives=["Ring camera system"],
        borrowed_patterns=["local hub"],
        defensible_differences=["cross-sensor predictive context"],
        non_copycat_rationale="It validates a different user outcome rather than adding features.",
        copycat_risks=["incumbents may add similar orchestration"],
        competitor_evidence_ids=["COMP-RING-001"],
        validation_questions=["Does prediction reduce incidents?"],
    )


def _product_spec() -> ProductSpec:
    return ProductSpec(
        id="model-placeholder",
        source_run_id="model-placeholder",
        source_candidate_id="model-placeholder",
        name="Defined Product",
        one_sentence_definition="A defined future eufy product.",
        category="eufy Security",
        target_users=["Households"],
        target_regions=["United States"],
        core_problem="Problem",
        value_proposition="Value",
        form_factor="Hardware",
        hardware_architecture=["sensor", "edge processor"],
        ai_capabilities=["local inference"],
        ai_decision_boundary="High-impact actions require approval.",
        user_journeys=["Install and use"],
        ecosystem_relationships=["HomeBase"],
        privacy_principles=["Data minimization"],
        business_model=BusinessModel(
            hardware_revenue="Hardware sale",
            ecosystem_pull_through=["HomeBase"],
            cost_drivers=["Sensors"],
        ),
        risks=[
            RiskItem(
                category="technical",
                risk="Accuracy",
                mitigation="Validate",
                severity="high",
            )
        ],
        key_assumptions=["Assumption"],
        kill_criteria=["Kill condition"],
        evidence_ids=["EV-EUFY-001"],
        validation_readiness=[
            ValidationHypothesis(
                id="H-001",
                assumption="Assumption",
                metric="metric",
                proposed_method="simulation",
                pass_condition="above threshold",
                kill_condition="below threshold",
            )
        ],
        competitive_positioning=_competitive_positioning(),
    )


@pytest.mark.asyncio
async def test_forecast_and_human_selection_complete_without_hardcoded_product() -> None:
    repository = InMemoryRunRepository()
    evidence = LocalEvidenceStore(Path(__file__).resolve().parents[2] / "data" / "evidence")
    competitors = LocalCompetitorStore(Path(__file__).resolve().parents[2] / "data" / "competitors")
    workflow = ForecastWorkflow(
        repository=repository,
        evidence_store=evidence,
        competitor_store=competitors,
        llm=FakeStructuredLLM(),
    )
    request = ForecastRequest(
        question="预测未来三年美国eufy Security的AI原生消费电子产品机会",
        regions=["United States"],
        target_users=["Households"],
        candidate_count=3,
    )
    run_id = workflow.create(request)

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED
    assert len(result.lens_forecasts) == 4
    assert len(result.opportunities) == 5
    assert len(result.lens_deliberations) == 4
    assert result.forecast_consensus is not None
    assert result.competitive_analysis is not None
    assert len(result.competitor_evidence) >= 6
    assert [item.rank for item in result.candidates] == [1, 2, 3]
    assert all(len(item.reviews) == 5 for item in result.candidates)

    chosen = result.candidates[1].candidate
    product = await workflow.define_selected_product(
        run_id,
        ProductSelectionRequest(
            candidate_id=chosen.id,
            selection_reason="The user prefers this product despite its rank.",
        ),
    )

    assert product.source_candidate_id == chosen.id
    assert product.source_run_id == run_id
    assert product.human_selection_reason is not None
    assert repository.get_product(product.id) == product

    duplicate = await workflow.define_selected_product(
        run_id,
        ProductSelectionRequest(
            candidate_id=chosen.id,
            selection_reason="A duplicate browser submission must be idempotent.",
        ),
    )
    assert duplicate.id == product.id
    assert len(repository.products) == 1
    assert workflow.get_result(run_id).retrieval_plan is not None
    assert any(event.event_type == "artifact_ready" for event in repository.events[run_id])
    assert any(
        event.event_type == "candidate_validation_failed" for event in repository.events[run_id]
    )
    assert (
        len(
            [
                artifact
                for artifact in repository.artifacts.values()
                if artifact.kind.startswith("candidate_generation_attempt:")
            ]
        )
        == 2
    )
