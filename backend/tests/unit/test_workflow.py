from __future__ import annotations

import re
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel

from eufy_security_agents.agents import ProductArchitectAgent
from eufy_security_agents.domain.models import (
    BusinessModel,
    CandidateEnvelope,
    CandidateNoveltyAssessment,
    CandidatePairSimilarity,
    CandidateReview,
    CapabilityDelta,
    CompetitiveAnalysis,
    CompetitiveAnalysisEnvelope,
    CompetitiveGap,
    CompetitivePositioning,
    ConsensusClaim,
    CrossLensChallenge,
    CurrentCapability,
    CurrentCapabilityBaseline,
    CurrentCapabilityBaselineEnvelope,
    ForecastConsensus,
    ForecastConsensusEnvelope,
    ForecastRequest,
    InnovationVector,
    LensDeliberation,
    LensDeliberationEnvelope,
    LensForecast,
    LensForecastEnvelope,
    NoveltyAudit,
    NoveltyAuditEnvelope,
    NoveltyClassification,
    Opportunity,
    OpportunityEnvelope,
    PortfolioDiversityAudit,
    PortfolioDiversityAuditEnvelope,
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
from eufy_security_agents.infrastructure.llm import LLMGenerationError
from eufy_security_agents.infrastructure.memory import InMemoryRunRepository
from eufy_security_agents.orchestration.workflow import ForecastWorkflow

T = TypeVar("T", bound=BaseModel)


class FakeStructuredLLM:
    model_name = "fake-model"

    def __init__(
        self,
        *,
        duplicate_first_portfolio: bool = False,
        portfolio_always_duplicate: bool = False,
        novelty_failures_before_pass: int = 0,
        novelty_always_fail_id: str | None = None,
    ) -> None:
        self.candidate_calls = 0
        self.portfolio_calls = 0
        self.novelty_calls = 0
        self.novelty_candidate_batches: list[list[str]] = []
        self.duplicate_first_portfolio = duplicate_first_portfolio
        self.portfolio_always_duplicate = portfolio_always_duplicate
        self.novelty_failures_before_pass = novelty_failures_before_pass
        self.novelty_always_fail_id = novelty_always_fail_id

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
            expected_match = re.search(
                r"(?:Use these candidate IDs in this order:|using these IDs:) "
                r"(\[[^\]]+\])",
                user_prompt,
            )
            expected_ids = (
                re.findall(r"CAND-\d{3}", expected_match.group(1))
                if expected_match
                else [f"CAND-{index:03d}" for index in range(1, 4)]
            )
            candidates = [
                _candidate(int(candidate_id.rsplit("-", 1)[-1]))
                for candidate_id in expected_ids
            ]
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
        elif response_model is CurrentCapabilityBaselineEnvelope:
            value = CurrentCapabilityBaselineEnvelope(
                baseline=CurrentCapabilityBaseline(
                    summary="Current eufy baseline",
                    capabilities=[
                        CurrentCapability(
                            id=f"CAP-{index:03d}",
                            capability=f"Existing capability {index}",
                            existing_products=["HomeBase 3"],
                            form_factors=["hub"],
                            evidence_ids=["EV-EUFY-001"],
                        )
                        for index in range(1, 4)
                    ],
                    combination_warning_signs=["renamed bundle"],
                )
            )
        elif response_model is NoveltyAuditEnvelope:
            self.novelty_calls += 1
            candidate_match = re.search(
                r"Return exactly one assessment for each candidate ID: (\[[^\]]+\])",
                user_prompt,
            )
            assert candidate_match is not None
            candidate_ids = re.findall(r"CAND-\d{3}", candidate_match.group(1))
            self.novelty_candidate_batches.append(candidate_ids)
            value = NoveltyAuditEnvelope(
                audit=NoveltyAudit(
                    assessments=[
                        CandidateNoveltyAssessment(
                            candidate_id=candidate_id,
                            classification=(
                                NoveltyClassification.FEATURE_EXTENSION
                                if candidate_id == self.novelty_always_fail_id
                                or self.novelty_calls <= self.novelty_failures_before_pass
                                else NoveltyClassification.ADJACENT_INNOVATION
                            ),
                            overlap_ratio=(
                                0.7
                                if candidate_id == self.novelty_always_fail_id
                                or self.novelty_calls <= self.novelty_failures_before_pass
                                else 0.4
                            ),
                            overlapping_capability_ids=["CAP-001"],
                            genuinely_new_capabilities=["new sensing outcome"],
                            why_not_available_today_is_credible=(
                                candidate_id != self.novelty_always_fail_id
                                and self.novelty_calls > self.novelty_failures_before_pass
                            ),
                            hardware_or_system_delta_is_meaningful=(
                                candidate_id != self.novelty_always_fail_id
                                and self.novelty_calls > self.novelty_failures_before_pass
                            ),
                            innovation_vector_is_credible=(
                                candidate_id != self.novelty_always_fail_id
                                and self.novelty_calls > self.novelty_failures_before_pass
                            ),
                            reasons=["meaningful system delta"],
                            regeneration_brief="",
                            passes_gate=True,
                        )
                        for candidate_id in candidate_ids
                    ]
                )
            )
        elif response_model is PortfolioDiversityAuditEnvelope:
            self.portfolio_calls += 1
            portfolio_match = re.search(
                r"Candidates that already passed the current-product novelty gate:\n"
                r"(.*?)\n\nNovelty assessments:",
                user_prompt,
                re.DOTALL,
            )
            assert portfolio_match is not None
            candidate_ids = sorted(
                set(re.findall(r"CAND-\d{3}", portfolio_match.group(1)))
            )

            def duplicate_pair(index: int, right: str) -> bool:
                return index == 0 and right == candidate_ids[1] and (
                    self.portfolio_always_duplicate
                    or (self.duplicate_first_portfolio and self.portfolio_calls == 1)
                )

            value = PortfolioDiversityAuditEnvelope(
                audit=PortfolioDiversityAudit(
                    pair_assessments=[
                        CandidatePairSimilarity(
                            candidate_a_id=left,
                            candidate_b_id=right,
                            similarity_score=(
                                0.82
                                if duplicate_pair(index, right)
                                else 0.2
                            ),
                            shared_user_jobs=(
                                ["same outage-security job"]
                                if duplicate_pair(index, right)
                                else []
                            ),
                            shared_product_mechanisms=(
                                ["edge mesh", "battery backup"]
                                if duplicate_pair(index, right)
                                else []
                            ),
                            meaningful_differences=["different job and architecture"],
                            duplicate=(
                                duplicate_pair(index, right)
                            ),
                            preferred_candidate_id=left,
                            regenerate_candidate_id=right,
                            regeneration_brief="",
                        )
                        for index, left in enumerate(candidate_ids)
                        for right in candidate_ids[index + 1 :]
                    ]
                )
            )
        elif response_model is ReviewEnvelope:
            dimension_match = re.search(r"only on '([^']+)'", user_prompt)
            dimension = dimension_match.group(1) if dimension_match else "innovation"
            candidate_ids = sorted(set(re.findall(r"CAND-\d{3}", user_prompt)))
            value = ReviewEnvelope(
                reviews=[
                    CandidateReview(
                        candidate_id=candidate_id,
                        dimension=dimension,
                        score=92 - index * 7,
                        strengths=["clear value"],
                        concerns=["requires validation"],
                        decisive_question="Will users adopt it?",
                    )
                    for index, candidate_id in enumerate(candidate_ids, 1)
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
        opportunity_ids=[f"OPP-{min(index, 5):03d}"],
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
        capability_delta=CapabilityDelta(
            today_equivalents=["HomeBase 3 local AI"],
            new_capabilities=["new sensing outcome"],
            why_not_available_today="A required sensor is not yet consumer-ready.",
            enabling_changes=["sensor cost reduction"],
            proof_needed=["field accuracy"],
            hardware_or_system_delta="A new distributed sensing and actuation architecture.",
            innovation_vector=list(InnovationVector)[(index - 1) % len(InnovationVector)],
        ),
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


class BatchRecordingLLM:
    model_name = "batch-model"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
    ) -> tuple[T, dict[str, int | str | None]]:
        del system_prompt, temperature
        assert response_model is CandidateEnvelope
        self.prompts.append(user_prompt)
        match = re.search(
            r"(?:in this order|using these IDs): (\[[^\]]+\])",
            user_prompt,
        )
        assert match is not None
        candidate_ids = re.findall(r"CAND-\d{3}", match.group(1))
        value = CandidateEnvelope(
            candidates=[_candidate(int(candidate_id[-3:])) for candidate_id in candidate_ids]
        )
        return value, {
            "model_name": self.model_name,
            "input_tokens": 100,
            "output_tokens": 200,
            "duration_ms": 10,
        }  # type: ignore[return-value]


class CandidateFailureLLM(FakeStructuredLLM):
    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
    ) -> tuple[T, dict[str, int | str | None]]:
        if response_model is CandidateEnvelope:
            raise LLMGenerationError(
                "structured LLM generation failed after 3 attempts (truncated)",
                failure_kind="truncated",
                attempts=3,
                detail="provider stopped at output limit",
                metadata={
                    "model_name": "fake-model",
                    "input_tokens": 900,
                    "output_tokens": 600,
                    "duration_ms": 30,
                },
            )
        return await super().generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            temperature=temperature,
        )


@pytest.mark.asyncio
async def test_product_architect_generates_large_portfolio_in_bounded_batches() -> None:
    llm = BatchRecordingLLM()
    request = ForecastRequest(
        question="Predict future eufy Security products",
        regions=["United States"],
        target_users=["Households"],
        candidate_count=6,
    )
    evidence_store = LocalEvidenceStore(Path(__file__).resolve().parents[2] / "data" / "evidence")
    _, evidence = evidence_store.retrieve(request)
    competitor_store = LocalCompetitorStore(
        Path(__file__).resolve().parents[2] / "data" / "competitors"
    )
    competitor_evidence = competitor_store.retrieve(request)
    opportunities = [
        Opportunity(
            id=f"OPP-{index:03d}",
            title=f"Opportunity {index}",
            unmet_job="Unmet security job",
            target_users=["Households"],
            target_regions=["United States"],
            why_now="Technology and need converge.",
            opportunity_window="1-3 years",
            enabling_trends=["edge AI"],
            evidence_ids=[evidence[0].id],
            counter_evidence=["cost uncertainty"],
            confidence=0.7,
        )
        for index in range(1, 7)
    ]
    analysis = CompetitiveAnalysis(
        market_patterns=["hardware plus optional service"],
        established_capabilities=["object detection"],
        competitor_strengths={"Ring": ["monitoring"]},
        competitor_limitations={"Ring": ["plan-gated features"]},
        underserved_needs=["local prevention"],
        subscription_or_lock_in_gaps=["plan dependency"],
        privacy_and_interoperability_gaps=["fragmented context"],
        regional_differences={"United States": ["monitoring is mature"]},
        gaps=[
            CompetitiveGap(
                id=f"GAP-{index:03d}",
                title=f"Gap {index}",
                description="Testable white space",
                affected_opportunity_ids=[f"OPP-{index:03d}"],
                competitor_brands=["Ring"],
                competitor_evidence_ids=[competitor_evidence[0].id],
                white_space="Local prevention",
                design_implications=["local decisions"],
                imitation_risk="medium",
                validation_question="Does it reduce incidents?",
                confidence=0.7,
            )
            for index in range(1, 4)
        ],
    )

    output = await ProductArchitectAgent(llm).run(
        request,
        evidence,
        opportunities,
        analysis,
        competitor_evidence,
        CurrentCapabilityBaseline(
            summary="Current baseline",
            capabilities=[
                CurrentCapability(
                    id=f"CAP-{index:03d}",
                    capability=f"Existing capability {index}",
                    existing_products=["HomeBase 3"],
                    form_factors=["hub"],
                    evidence_ids=[evidence[0].id],
                )
                for index in range(1, 4)
            ],
        ),
    )

    assert len(llm.prompts) == 2
    assert [candidate.id for candidate in output.value.candidates] == [
        f"CAND-{index:03d}" for index in range(1, 7)
    ]
    assert "Product 1" in llm.prompts[1]
    assert output.metadata["input_tokens"] == 200
    assert output.metadata["output_tokens"] == 400


@pytest.mark.asyncio
async def test_candidate_generation_failure_persists_safe_diagnostics() -> None:
    repository = InMemoryRunRepository()
    workflow = ForecastWorkflow(
        repository=repository,
        evidence_store=LocalEvidenceStore(
            Path(__file__).resolve().parents[2] / "data" / "evidence"
        ),
        competitor_store=LocalCompetitorStore(
            Path(__file__).resolve().parents[2] / "data" / "competitors"
        ),
        llm=CandidateFailureLLM(),
    )
    run_id = workflow.create(
        ForecastRequest(
            question=(
                "Predict three-year eufy Security products for United States households, "
                "including user needs, technology trends, security risks and market change"
            ),
            regions=["United States"],
            target_users=["Households"],
            candidate_count=3,
        )
    )

    await workflow.execute(run_id)

    run = repository.get_run(run_id)
    assert run is not None
    assert run.status == RunStatus.FAILED
    artifact = repository.get_artifact(run_id, "candidate_generation_failure")
    assert artifact is not None
    assert artifact.payload["failure_kind"] == "truncated"
    assert artifact.input_tokens == 900
    assert artifact.output_tokens == 600
    assert any(
        event.event_type == "structured_generation_failed"
        for event in repository.list_events(run_id)
    )


def test_novelty_gate_overrides_a_model_pass_when_capability_delta_is_empty() -> None:
    candidate = _candidate(1).model_copy(update={"capability_delta": CapabilityDelta()})
    baseline = CurrentCapabilityBaseline(
        summary="Current baseline",
        capabilities=[
            CurrentCapability(
                id=f"CAP-{index:03d}",
                capability=f"Existing capability {index}",
                existing_products=["HomeBase 3"],
                form_factors=["hub"],
                evidence_ids=["EV-EUFY-001"],
            )
            for index in range(1, 4)
        ],
    )
    model_audit = NoveltyAudit(
        assessments=[
            CandidateNoveltyAssessment(
                candidate_id=candidate.id,
                classification=NoveltyClassification.ADJACENT_INNOVATION,
                overlap_ratio=0.2,
                overlapping_capability_ids=["CAP-001"],
                genuinely_new_capabilities=["claimed novelty"],
                why_not_available_today_is_credible=True,
                hardware_or_system_delta_is_meaningful=True,
                innovation_vector_is_credible=True,
                reasons=["model says pass"],
                regeneration_brief="replace the mechanism",
                passes_gate=True,
            )
        ]
    )

    normalized = ForecastWorkflow._normalize_novelty_audit(
        model_audit, [candidate], baseline
    )

    assert normalized.assessments[0].passes_gate is False


def test_portfolio_diversity_gate_enforces_threshold_and_keeps_one_per_cluster() -> None:
    candidates = [_candidate(index) for index in range(1, 4)]
    novelty = NoveltyAudit(
        assessments=[
            CandidateNoveltyAssessment(
                candidate_id=candidate.id,
                classification=NoveltyClassification.ADJACENT_INNOVATION,
                overlap_ratio=0.3,
                overlapping_capability_ids=[],
                genuinely_new_capabilities=["new capability"],
                why_not_available_today_is_credible=True,
                hardware_or_system_delta_is_meaningful=True,
                innovation_vector_is_credible=True,
                reasons=["material delta"],
                regeneration_brief="",
                passes_gate=True,
            )
            for candidate in candidates
        ]
    )
    audit = PortfolioDiversityAudit(
        pair_assessments=[
            CandidatePairSimilarity(
                candidate_a_id="CAND-001",
                candidate_b_id="CAND-002",
                similarity_score=0.82,
                shared_user_jobs=["security during outages"],
                shared_product_mechanisms=["edge mesh", "battery backup"],
                meaningful_differences=["different enclosure"],
                duplicate=False,
                preferred_candidate_id="CAND-001",
                regenerate_candidate_id="CAND-002",
                regeneration_brief="change the user job and mechanism",
            ),
            CandidatePairSimilarity(
                candidate_a_id="CAND-001",
                candidate_b_id="CAND-003",
                similarity_score=0.2,
                duplicate=False,
                preferred_candidate_id="CAND-001",
                regenerate_candidate_id="CAND-003",
                regeneration_brief="",
            ),
            CandidatePairSimilarity(
                candidate_a_id="CAND-002",
                candidate_b_id="CAND-003",
                similarity_score=0.25,
                duplicate=False,
                preferred_candidate_id="CAND-002",
                regenerate_candidate_id="CAND-003",
                regeneration_brief="",
            ),
        ]
    )

    normalized = ForecastWorkflow._normalize_portfolio_diversity_audit(audit, candidates)
    duplicate_ids = ForecastWorkflow._duplicate_candidate_ids(normalized, candidates, novelty)

    assert normalized.pair_assessments[0].duplicate is True
    assert len(duplicate_ids) == 1
    assert duplicate_ids <= {"CAND-001", "CAND-002"}


@pytest.mark.asyncio
async def test_duplicate_candidate_is_regenerated_and_reaudited_before_review() -> None:
    repository = InMemoryRunRepository()
    llm = FakeStructuredLLM(duplicate_first_portfolio=True)
    workflow = ForecastWorkflow(
        repository=repository,
        evidence_store=LocalEvidenceStore(
            Path(__file__).resolve().parents[2] / "data" / "evidence"
        ),
        competitor_store=LocalCompetitorStore(
            Path(__file__).resolve().parents[2] / "data" / "competitors"
        ),
        llm=llm,
    )
    run_id = workflow.create(
        ForecastRequest(
            question="预测未来三年美国eufy Security的差异化AI原生产品机会",
            regions=["United States"],
            target_users=["Households"],
            candidate_count=3,
        )
    )

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    assert result.portfolio_diversity_audit is not None
    assert result.portfolio_diversity_audit.regeneration_rounds == 1
    assert len(result.portfolio_diversity_audit.regenerated_candidate_ids) == 1
    assert not any(item.duplicate for item in result.portfolio_diversity_audit.pair_assessments)
    event_types = [event.event_type for event in repository.list_events(run_id)]
    assert "portfolio_duplicate_found" in event_types
    assert event_types.index("portfolio_duplicate_found") < event_types.index("reviews_completed")
    assert len(llm.novelty_candidate_batches[0]) == 3
    assert len(llm.novelty_candidate_batches[1]) == 1


@pytest.mark.asyncio
async def test_persistent_portfolio_duplicate_degrades_without_failing_run() -> None:
    repository = InMemoryRunRepository()
    workflow = ForecastWorkflow(
        repository=repository,
        evidence_store=LocalEvidenceStore(
            Path(__file__).resolve().parents[2] / "data" / "evidence"
        ),
        competitor_store=LocalCompetitorStore(
            Path(__file__).resolve().parents[2] / "data" / "competitors"
        ),
        llm=FakeStructuredLLM(portfolio_always_duplicate=True),
    )
    run_id = workflow.create(
        ForecastRequest(
            question="预测未来三年美国eufy Security的差异化AI原生产品机会",
            regions=["United States"],
            target_users=["Households"],
            candidate_count=3,
        )
    )

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    assert len(result.candidates) == 2
    assert result.portfolio_diversity_audit is not None
    assert result.portfolio_diversity_audit.degraded is True
    assert len(result.portfolio_diversity_audit.dropped_candidate_ids) == 1
    assert any(
        event.event_type == "portfolio_diversity_degraded"
        for event in repository.list_events(run_id)
    )


def test_rescue_vector_moves_exhausted_candidate_to_unused_direction() -> None:
    failed = _candidate(5)
    accepted = [_candidate(index) for index in (1, 2, 3, 4, 6)]

    overrides = ForecastWorkflow._rescue_vector_overrides(
        [failed],
        accepted,
        {failed.id: [failed]},
    )

    assert overrides[failed.id] == InnovationVector.NEW_BUSINESS_DELIVERY


@pytest.mark.asyncio
async def test_novelty_rescue_recovers_after_standard_regeneration_is_exhausted() -> None:
    repository = InMemoryRunRepository()
    workflow = ForecastWorkflow(
        repository=repository,
        evidence_store=LocalEvidenceStore(
            Path(__file__).resolve().parents[2] / "data" / "evidence"
        ),
        competitor_store=LocalCompetitorStore(
            Path(__file__).resolve().parents[2] / "data" / "competitors"
        ),
        llm=FakeStructuredLLM(novelty_failures_before_pass=3),
    )
    run_id = workflow.create(
        ForecastRequest(
            question="预测未来三年美国eufy Security的差异化AI原生产品机会",
            regions=["United States"],
            target_users=["Households"],
            candidate_count=3,
        )
    )

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    assert result.novelty_audit is not None
    assert result.novelty_audit.rescue_rounds == 1
    assert result.novelty_audit.dropped_candidate_ids == []
    assert any(
        event.event_type == "novelty_rescue_started"
        for event in repository.list_events(run_id)
    )


@pytest.mark.asyncio
async def test_one_persistent_novelty_failure_is_dropped_without_losing_the_run() -> None:
    repository = InMemoryRunRepository()
    workflow = ForecastWorkflow(
        repository=repository,
        evidence_store=LocalEvidenceStore(
            Path(__file__).resolve().parents[2] / "data" / "evidence"
        ),
        competitor_store=LocalCompetitorStore(
            Path(__file__).resolve().parents[2] / "data" / "competitors"
        ),
        llm=FakeStructuredLLM(novelty_always_fail_id="CAND-005"),
    )
    run_id = workflow.create(
        ForecastRequest(
            question="预测未来三年美国eufy Security的差异化AI原生产品机会",
            regions=["United States"],
            target_users=["Households"],
            candidate_count=6,
        )
    )

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    assert len(result.candidates) == 5
    assert result.novelty_audit is not None
    assert result.novelty_audit.returned_candidate_count == 5
    assert result.novelty_audit.dropped_candidate_ids == ["CAND-005"]
    assert any(
        event.event_type == "novelty_gate_degraded"
        for event in repository.list_events(run_id)
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
    assert result.current_capability_baseline is not None
    assert len(result.current_capability_baseline.capabilities) == 3
    assert result.novelty_audit is not None
    assert all(item.passes_gate for item in result.novelty_audit.assessments)
    assert result.portfolio_diversity_audit is not None
    assert len(result.portfolio_diversity_audit.pair_assessments) == 3
    assert not any(item.duplicate for item in result.portfolio_diversity_audit.pair_assessments)
    assert len(result.current_capability_evidence) >= 3
    assert len(result.competitor_evidence) >= 6
    assert [item.rank for item in result.candidates] == [1, 2, 3]
    assert all(len(item.reviews) == 6 for item in result.candidates)
    assert all(
        {review.dimension for review in item.reviews}
        == {
            "innovation",
            "user_value",
            "business_value",
            "cost_effectiveness",
            "feasibility",
            "eufy_synergy",
        }
        for item in result.candidates
    )
    strategy_events = [
        event for event in repository.events[run_id] if event.event_type == "strategy_applied"
    ]
    assert len(strategy_events) == 1
    assert strategy_events[0].payload["strategy_profile"] == "balanced"
    assert "weights" in strategy_events[0].payload
    assert result.retrieval_plan is not None
    assert result.retrieval_plan.strategy_profile == "balanced"

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
        event.event_type == "novelty_audit_completed" for event in repository.events[run_id]
    )
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
