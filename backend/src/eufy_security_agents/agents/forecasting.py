"""LLM agents used before the future validation phase."""

from __future__ import annotations

from uuid import uuid4

from eufy_security_agents.core.serialization import compact_json
from eufy_security_agents.domain.models import (
    CandidateEnvelope,
    CandidateNoveltyAssessment,
    CandidatePairSimilarity,
    CompetitiveAnalysis,
    CompetitiveAnalysisEnvelope,
    CompetitorRecord,
    CurrentCapabilityBaseline,
    CurrentCapabilityBaselineEnvelope,
    EvidenceRecord,
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
    Opportunity,
    OpportunityEnvelope,
    PortfolioDiversityAuditEnvelope,
    ProductCandidate,
    ProductSelectionRequest,
    ProductSpecEnvelope,
    RankedCandidate,
    ReviewEnvelope,
)
from eufy_security_agents.domain.strategy import strategy_brief

from .base import AgentOutput, BaseAgent

LENS_PROMPTS = {
    "user_trends": (
        "You are a senior consumer-research futurist. Forecast changes in household needs, "
        "trust, routines, accessibility and adoption barriers. Separate evidence from inference."
    ),
    "technology_trends": (
        "You are a consumer-electronics technology forecaster. Assess sensing, edge AI, power, "
        "connectivity and manufacturability within the requested horizon. Avoid science fiction."
    ),
    "security_futures": (
        "You are a residential-security threat forecaster. Examine changing threats, failure "
        "modes, false alarms and the shift from detection to prevention and recovery."
    ),
    "market_futures": (
        "You are a global consumer-electronics strategist. Examine price, channels, regional "
        "housing patterns, services, ecosystem pull-through and defensibility."
    ),
}


REVIEW_PROMPTS = {
    "innovation": (
        "Judge originality and whether AI is constitutive of the product rather than decorative."
    ),
    "user_value": "Judge severity of the user problem, frequency, usability and adoption friction.",
    "business_value": (
        "Judge addressable demand, price logic, margin drivers and ecosystem revenue. Stay at the "
        "market and business level; leave the household's price-versus-value trade-off to the "
        "cost_effectiveness reviewer."
    ),
    "cost_effectiveness": (
        "Judge value-for-money for the household, distinct from business_value. Weigh whether the "
        "estimated price matches the delivered user value; whether it reuses existing devices or "
        "infrastructure; whether it adds unnecessary subscription burden; install, maintenance and "
        "battery-replacement costs; total cost of ownership versus alternatives; and any low-price "
        "shortcut that sacrifices reliability or privacy."
    ),
    "feasibility": (
        "Judge three-year technical, power, cost, reliability and manufacturing feasibility."
    ),
    "eufy_synergy": (
        "Judge fit with eufy Security, HomeBase, channels and differentiated capabilities."
    ),
}

PRODUCT_ARCHITECT_BATCH_SIZE = 3
INNOVATION_VECTOR_SEQUENCE = list(InnovationVector)


def _innovation_vector_plan(
    candidate_ids: list[str],
    overrides: dict[str, InnovationVector] | None = None,
) -> dict[str, str]:
    plan: dict[str, str] = {}
    for fallback_index, candidate_id in enumerate(candidate_ids):
        if overrides and candidate_id in overrides:
            plan[candidate_id] = overrides[candidate_id].value
            continue
        try:
            index = max(int(candidate_id.rsplit("-", 1)[-1]) - 1, 0)
        except ValueError:
            index = fallback_index
        vector = INNOVATION_VECTOR_SEQUENCE[index % len(INNOVATION_VECTOR_SEQUENCE)]
        plan[candidate_id] = vector.value
    return plan


def _evidence_digest(evidence: list[EvidenceRecord]) -> list[dict[str, object]]:
    """Keep citation context while avoiding repeated full-record prompt bloat."""
    return [
        {
            "id": item.id,
            "title": item.title,
            "summary": item.content[:600],
            "regions": item.regions,
            "layer": item.layer.value if item.layer else None,
            "topics": item.topics,
            "credibility": item.credibility,
            "claim_status": item.claim_status.value if item.claim_status else None,
            "supports": item.supports,
            "contradicts": item.contradicts,
        }
        for item in evidence
    ]


def _competitor_digest(records: list[CompetitorRecord]) -> list[dict[str, object]]:
    return [
        {
            "id": item.id,
            "brand": item.brand,
            "product_name": item.product_name,
            "product_family": item.product_family,
            "regions": item.regions,
            "verified_capabilities": item.verified_capabilities,
            "documented_constraints": item.documented_constraints,
            "business_model": item.business_model,
            "privacy_and_storage": item.privacy_and_storage,
            "interoperability": item.interoperability,
            "credibility": item.credibility,
            "claim_status": item.claim_status.value,
        }
        for item in records
    ]


def _rejected_candidate_digest(
    history: dict[str, list[ProductCandidate]],
) -> dict[str, list[dict[str, object]]]:
    return {
        candidate_id: [
            {
                "name": item.name,
                "core_problem": item.core_problem,
                "form_factor": item.form_factor,
                "hardware_components": item.hardware_components,
                "ai_native_mechanism": item.ai_native_mechanism,
                "innovation_vector": item.capability_delta.innovation_vector.value,
            }
            for item in versions[-4:]
        ]
        for candidate_id, versions in history.items()
    }


def _novelty_feedback_digest(
    history: dict[str, list[CandidateNoveltyAssessment]],
) -> dict[str, list[dict[str, object]]]:
    return {
        candidate_id: [
            {
                "classification": item.classification.value,
                "overlap_ratio": item.overlap_ratio,
                "reasons": item.reasons[:3],
                "regeneration_brief": item.regeneration_brief,
            }
            for item in assessments[-4:]
        ]
        for candidate_id, assessments in history.items()
    }


def _repeats_rejected_version(
    candidate: ProductCandidate,
    history: list[ProductCandidate],
) -> bool:
    def normalized(value: str) -> str:
        return " ".join(value.casefold().split())

    name = normalized(candidate.name)
    form_factor = normalized(candidate.form_factor)
    mechanism = normalized(candidate.ai_native_mechanism)
    return any(
        normalized(item.name) == name
        or (
            normalized(item.form_factor) == form_factor
            and normalized(item.ai_native_mechanism) == mechanism
        )
        for item in history
    )


def _combine_candidate_outputs(
    outputs: list[AgentOutput[CandidateEnvelope]],
    candidates: list[ProductCandidate],
) -> AgentOutput[CandidateEnvelope]:
    if not outputs:
        return AgentOutput(value=CandidateEnvelope(candidates=candidates), metadata={})

    def summed(key: str) -> int | None:
        values = [item.metadata.get(key) for item in outputs]
        numeric = [int(value) for value in values if isinstance(value, int | float)]
        return sum(numeric) if numeric else None

    model_name = next(
        (
            str(output.metadata["model_name"])
            for output in reversed(outputs)
            if output.metadata.get("model_name")
        ),
        None,
    )
    return AgentOutput(
        value=CandidateEnvelope(candidates=candidates),
        metadata={
            "model_name": model_name,
            "input_tokens": summed("input_tokens"),
            "output_tokens": summed("output_tokens"),
            "duration_ms": summed("duration_ms"),
            "batch_count": sum(
                int(output.metadata.get("batch_count") or 1) for output in outputs
            ),
        },
    )


class FuturesLensAgent(BaseAgent):
    def __init__(self, llm: object, lens: str) -> None:
        super().__init__(llm)  # type: ignore[arg-type]
        if lens not in LENS_PROMPTS:
            raise ValueError(f"unsupported forecasting lens: {lens}")
        self.lens = lens
        self.name = f"futures-{lens}"

    async def run(
        self, request: ForecastRequest, evidence: list[EvidenceRecord]
    ) -> AgentOutput[LensForecastEnvelope]:
        prompt = (
            f"Research brief:\n{compact_json(request)}\n\n"
            f"{strategy_brief(request)}\n\n"
            f"Local evidence records:\n{compact_json(evidence)}\n\n"
            f"Your lens identifier is '{self.lens}'. Produce a JSON forecast for that lens. "
            "Interpret the strategy through your lens' own responsibility — do not copy the other "
            "lenses' emphasis. Every signal must cite only evidence IDs present above. Clearly "
            "state uncertainty. Treat claim_status=hypothesis as a proposition to test, not as an "
            "established fact. Do not transfer a regional claim to another region unless a global "
            "record supports it. Treat research_context as explicit user input: use populated "
            "fields to focus the analysis, and never invent preferences for empty fields. "
            "Use the same primary language as the user's question."
        )
        output = await self._generate(
            system_prompt=LENS_PROMPTS[self.lens],
            user_prompt=prompt,
            response_model=LensForecastEnvelope,
            temperature=0.55,
        )
        return output


class OpportunitySynthesizerAgent(BaseAgent):
    name = "opportunity-synthesizer"
    prompt_version = "2.0"

    async def run(
        self,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        forecasts: list[LensForecast],
        deliberations: list[LensDeliberation],
        consensus: ForecastConsensus,
    ) -> AgentOutput[OpportunityEnvelope]:
        prompt = (
            f"Research brief:\n{compact_json(request)}\n\n"
            f"{strategy_brief(request)}\n\n"
            f"Independent forecasts:\n{compact_json(forecasts)}\n\n"
            f"Cross-lens deliberations:\n{compact_json(deliberations)}\n\n"
            f"Consensus and remaining disagreements:\n{compact_json(consensus)}\n\n"
            f"Available evidence:\n{compact_json(evidence)}\n\n"
            "Synthesize 5-9 distinct future opportunity spaces. Do not design products yet. "
            "Let the strategy weights set which opportunities you prioritise and how deeply you "
            "develop them: high innovation admits more new-form, new-interaction or AI-native "
            "spaces; high cost_effectiveness favours affordability, reusing devices and cutting "
            "subscription/install/maintenance cost; high eufy_synergy favours cross-device and "
            "ecosystem capability (never merely bolting existing devices together); high "
            "user_value favours frequent, severe, still-unsolved household jobs; high feasibility "
            "favours a three-year path to production; high business_value favours demand scale, "
            "channels, moats and a sound revenue model. Weights change priority only — they must "
            "not overwrite the counter-evidence or unresolved disagreement the panel surfaced. "
            "Deduplicate overlapping ideas. Use consensus as support, preserve unresolved and "
            "minority views as counter-evidence, and cite only provided EV-* evidence IDs. "
            "Populate regional_differences for every requested region; do not average distinct "
            "markets into one fictional household. "
            "Use IDs OPP-001, OPP-002, etc. Use the user's primary language."
        )
        output = await self._generate(
            system_prompt=(
                "You are an evidence-led opportunity portfolio strategist. Your job is to find "
                "future unmet jobs, not to justify any predetermined product."
            ),
            user_prompt=prompt,
            response_model=OpportunityEnvelope,
            temperature=0.45,
        )
        if not 5 <= len(output.value.opportunities) <= 9:
            output = await self._generate(
                system_prompt=(
                    "You are an evidence-led opportunity portfolio strategist. Find future unmet "
                    "jobs without justifying any predetermined product."
                ),
                user_prompt=f"{prompt}\n\nCorrection: return between 5 and 9 opportunities.",
                response_model=OpportunityEnvelope,
                temperature=0.35,
            )
        return output


class CurrentProductAuditorAgent(BaseAgent):
    name = "current-product-auditor"
    prompt_version = "1.0"

    async def build_baseline(
        self,
        request: ForecastRequest,
        current_eufy_evidence: list[EvidenceRecord],
    ) -> AgentOutput[CurrentCapabilityBaselineEnvelope]:
        evidence_ids = [item.id for item in current_eufy_evidence]
        prompt = (
            f"Research brief:\n{compact_json(request)}\n\n"
            f"Current eufy product and capability evidence:\n"
            f"{compact_json(_evidence_digest(current_eufy_evidence))}\n\n"
            "Build a factual capability baseline for products available today. Consolidate "
            "duplicate descriptions into 5-15 capability atoms. Include hardware form factors, "
            "local AI, storage, recognition, cross-camera tracking, sensors, automations and "
            "business-model patterns when evidenced. Use IDs CAP-001, CAP-002, etc. Evidence IDs "
            f"may only come from {evidence_ids}. Do not infer that an unmentioned capability is "
            "absent. List warning signs for proposals that merely rename, bundle or add a chat "
            "interface to these existing capabilities. Use the user's primary language."
        )
        return await self._generate(
            system_prompt=(
                "You are a skeptical current-product auditor. Establish what eufy Security can "
                "already do today before any future product is judged. Prefer official evidence "
                "and never reward a new product name as novelty."
            ),
            user_prompt=prompt,
            response_model=CurrentCapabilityBaselineEnvelope,
            temperature=0.15,
        )

    async def audit(
        self,
        request: ForecastRequest,
        baseline: CurrentCapabilityBaseline,
        candidates: list[ProductCandidate],
    ) -> AgentOutput[NoveltyAuditEnvelope]:
        candidate_ids = [item.id for item in candidates]
        capability_ids = [item.id for item in baseline.capabilities]
        prompt = (
            f"Research brief:\n{compact_json(request)}\n\n"
            f"Current eufy capability baseline:\n{compact_json(baseline)}\n\n"
            f"Future product candidates to audit:\n{compact_json(candidates)}\n\n"
            f"Return exactly one assessment for each candidate ID: {candidate_ids}. "
            f"overlapping_capability_ids may only use {capability_ids}. Classify each as "
            "existing_equivalent, feature_extension, adjacent_innovation or "
            "new_product_category. A renamed bundle, smaller HomeBase, local storage, local AI, "
            "no subscription, existing sensor-to-camera automation, or a natural-language/chat "
            "layer over current functions is not a new product. Judge the user outcome, sensing "
            "or actuation mechanism, hardware/system architecture and why-now enabler—not its "
            "branding. Set passes_gate provisionally; the backend will enforce the final rule. "
            "Set innovation_vector_is_credible only when the candidate's actual mechanism matches "
            "its declared capability_delta.innovation_vector; reject relabeling the same radar, "
            "camera, hub or chatbot concept into multiple vectors. "
            "For every failing direction, provide a concrete regeneration brief that preserves "
            "the underlying unmet job but changes the product mechanism. Judge only the current "
            "candidate supplied above; never reuse reasons about an earlier version or a different "
            "candidate. Every reason must name a mechanism actually present in the current "
            "candidate. Use the user's primary language."
        )
        return await self._generate(
            system_prompt=(
                "You are an adversarial prior-art and product-novelty reviewer. Your job is to "
                "reject present-day products disguised as future concepts. Be strict, factual "
                "and consistent across candidates."
            ),
            user_prompt=prompt,
            response_model=NoveltyAuditEnvelope,
            temperature=0.1,
        )


class CandidateNoveltyAuditorAgent(CurrentProductAuditorAgent):
    name = "candidate-novelty-auditor"


class PortfolioDiversityAuditorAgent(BaseAgent):
    """Detect candidates that are the same product architecture under different names."""

    name = "portfolio-diversity-auditor"
    prompt_version = "1.0"

    async def audit(
        self,
        request: ForecastRequest,
        candidates: list[ProductCandidate],
        novelty_audit: NoveltyAudit,
    ) -> AgentOutput[PortfolioDiversityAuditEnvelope]:
        candidate_ids = [item.id for item in candidates]
        expected_pairs = [
            [left, right]
            for index, left in enumerate(candidate_ids)
            for right in candidate_ids[index + 1 :]
        ]
        prompt = (
            f"Research brief:\n{compact_json(request)}\n\n"
            f"Candidates that already passed the current-product novelty gate:\n"
            f"{compact_json(candidates)}\n\n"
            f"Novelty assessments:\n{compact_json(novelty_audit)}\n\n"
            f"Return exactly one pair_assessment for every unordered pair in this list: "
            f"{expected_pairs}. Use the pair order shown. Compare semantics, not names or "
            "taglines, across: (1) user job and outcome, (2) physical form factor, (3) sensing "
            "or actuation mechanism, (4) AI decision mechanism, (5) system/network architecture, "
            "and (6) commercial delivery. Innovation-vector labels alone are not a meaningful "
            "difference. Mark duplicate when the core user job plus at least two mechanism or "
            "architecture dimensions substantially overlap, or when one candidate is mainly a "
            "subset/repackaging of the other. A different enclosure, energy source, price, name, "
            "or marketing claim cannot rescue a duplicate. similarity_score is semantic overlap "
            "from 0 to 1. For duplicates, prefer the candidate with the clearer new user outcome, "
            "lower overlap with current capabilities, more meaningful hardware/system delta, and "
            "more falsifiable proof plan. Provide a regeneration brief that keeps the unmet need "
            "but changes the user job or product mechanism. For non-duplicates still set the two "
            "candidate ID fields to a valid deterministic order, but do not invent a problem. "
            "Use the user's primary language."
        )
        return await self._generate(
            system_prompt=(
                "You are an adversarial product-portfolio editor. Your job is to remove semantic "
                "duplicates so each remaining concept represents a materially different future "
                "product bet. Be strict and globally consistent."
            ),
            user_prompt=prompt,
            response_model=PortfolioDiversityAuditEnvelope,
            temperature=0.1,
        )


class ProductArchitectAgent(BaseAgent):
    name = "product-architect"
    prompt_version = "2.1"

    async def run(
        self,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        opportunities: list[Opportunity],
        competitive_analysis: CompetitiveAnalysis,
        competitor_evidence: list[CompetitorRecord],
        current_baseline: CurrentCapabilityBaseline,
    ) -> AgentOutput[CandidateEnvelope]:
        outputs: list[AgentOutput[CandidateEnvelope]] = []
        candidates: list[ProductCandidate] = []
        for start in range(0, request.candidate_count, PRODUCT_ARCHITECT_BATCH_SIZE):
            stop = min(start + PRODUCT_ARCHITECT_BATCH_SIZE, request.candidate_count)
            expected_ids = [f"CAND-{index:03d}" for index in range(start + 1, stop + 1)]
            output = await self._run_batch(
                request=request,
                evidence=evidence,
                opportunities=opportunities,
                competitive_analysis=competitive_analysis,
                competitor_evidence=competitor_evidence,
                current_baseline=current_baseline,
                expected_ids=expected_ids,
                existing_candidates=candidates,
            )
            outputs.append(output)
            candidates.extend(output.value.candidates)
        return _combine_candidate_outputs(outputs, candidates)

    async def _run_batch(
        self,
        *,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        opportunities: list[Opportunity],
        competitive_analysis: CompetitiveAnalysis,
        competitor_evidence: list[CompetitorRecord],
        current_baseline: CurrentCapabilityBaseline,
        expected_ids: list[str],
        existing_candidates: list[ProductCandidate],
        novelty_feedback: list[CandidateNoveltyAssessment] | None = None,
        portfolio_feedback: list[CandidatePairSimilarity] | None = None,
        rejected_candidate_history: dict[str, list[ProductCandidate]] | None = None,
        novelty_feedback_history: dict[str, list[CandidateNoveltyAssessment]] | None = None,
        innovation_vector_overrides: dict[str, InnovationVector] | None = None,
    ) -> AgentOutput[CandidateEnvelope]:
        valid_opportunity_ids = [item.id for item in opportunities]
        valid_evidence_ids = [item.id for item in evidence]
        valid_competitor_ids = [item.id for item in competitor_evidence]
        prior_summary = [
            {
                "id": item.id,
                "name": item.name,
                "core_problem": item.core_problem,
                "form_factor": item.form_factor,
                "ai_native_mechanism": item.ai_native_mechanism,
                "innovation_vector": item.capability_delta.innovation_vector.value,
            }
            for item in existing_candidates
        ]
        prompt = (
            f"Research brief:\n{compact_json(request)}\n\n"
            f"{strategy_brief(request)}\n\n"
            f"Opportunity portfolio:\n{compact_json(opportunities)}\n\n"
            f"Evidence digest:\n{compact_json(_evidence_digest(evidence))}\n\n"
            f"Competitive white-space analysis:\n{compact_json(competitive_analysis)}\n\n"
            f"Official competitor digest:\n"
            f"{compact_json(_competitor_digest(competitor_evidence))}\n\n"
            f"Current eufy capability baseline (do not repackage this as novelty):\n"
            f"{compact_json(current_baseline)}\n\n"
            f"Candidates already created in earlier batches:\n{compact_json(prior_summary)}\n\n"
            f"Novelty-audit feedback for IDs being regenerated:\n"
            f"{compact_json(novelty_feedback or [])}\n\n"
            f"All previously rejected versions for these IDs:\n"
            f"{compact_json(_rejected_candidate_digest(rejected_candidate_history or {}))}\n\n"
            f"Complete novelty-audit history for these IDs:\n"
            f"{compact_json(_novelty_feedback_digest(novelty_feedback_history or {}))}\n\n"
            f"Portfolio duplicate feedback for IDs being regenerated:\n"
            f"{compact_json(portfolio_feedback or [])}\n\n"
            f"Required innovation vector for each ID:\n"
            f"{compact_json(_innovation_vector_plan(expected_ids, innovation_vector_overrides))}"
            "\n\n"
            f"Generate exactly {len(expected_ids)} genuinely different future consumer-"
            "electronics products. Each must include a meaningful hardware form factor and be "
            "AI-native, not merely an app, chatbot, report or existing product with an AI label. "
            f"Use these candidate IDs in this order: {expected_ids}. Do not repeat a candidate "
            "from an earlier batch. Make this batch materially different from the earlier "
            "candidate summary. When rejected history is present, changing only the name, "
            "enclosure, price, power source, hub/standalone label, or software wording is not a "
            "new mechanism. Do not recreate any rejected combination of user job, form factor, "
            "sensing/actuation and system architecture. "
            "The strategy weights must shape the *portfolio itself*, not just its later ranking: "
            "first state the strategy's main preference, then let the highest-weighted dimensions "
            "appear in more of the candidates and be expressed more strongly. Still keep genuine "
            "diversity — do not produce six near-identical products differing only in name. "
            "Do not let high innovation license science-fiction that cannot ship within the "
            "horizon; do not let high eufy_synergy collapse into simply bundling existing devices; "
            "do not let high cost_effectiveness collapse into merely a cheaper version of a "
            "current product. Respect the requested regions, users, horizon, price segment, "
            "constraints and every populated research_context field. Empty context fields are "
            "unknown, not permission to assume a preference. Ensure the portfolio explores more "
            "than one plausible way to achieve the requested outcomes instead of repeating the "
            "user's current devices. For every candidate populate strategy_alignment: "
            "aligned_dimensions (only from innovation, user_value, business_value, "
            "cost_effectiveness, feasibility, eufy_synergy) naming which strategy dimensions this "
            "product answers; rationale explaining how it responds to the user's strategy; and "
            "tradeoffs stating what was sacrificed for that strategy. Never fabricate numbers in "
            "strategy_alignment. "
            "For every candidate populate capability_delta. today_equivalents must honestly name "
            "the closest current eufy capabilities; new_capabilities must describe a new user "
            "outcome or new sensing, actuation, hardware or system mechanism; explain why it is "
            "not available today, which changes enable it within the horizon, what proof is "
            "needed, and the meaningful hardware_or_system_delta. A new enclosure, bundle, lower "
            "price, local AI, no subscription, or natural-language explanation alone is not an "
            "acceptable delta. "
            "The capability_delta.innovation_vector must exactly match the required vector for "
            "its candidate ID, and the actual product mechanism—not merely the label—must explore "
            "that vector. new_sensing means a genuinely new sensing modality; "
            "proactive_intervention means safe physical or environmental action before harm; "
            "distributed_architecture changes how devices cooperate; resilience_recovery protects "
            "during or after power/network/device failure; trust_privacy creates a new control or "
            "consent mechanism; human_ai_coordination changes how household members and AI decide; "
            "new_business_delivery changes how a security outcome is delivered without disguising "
            "a subscription as hardware. Do not solve every vector with radar or another single "
            "sensor modality. "
            "Follow this ID contract exactly:\n"
            f"- opportunity_ids: only IDs from {valid_opportunity_ids}\n"
            f"- evidence_ids and regional_fit[*].evidence_ids: only IDs from "
            f"{valid_evidence_ids}\n"
            "- competitive_positioning.competitor_evidence_ids: only IDs from "
            f"{valid_competitor_ids}\n"
            "Never place an OPP-* ID in evidence_ids. Never place EV-* or COMP-* IDs in "
            "opportunity_ids. State falsifiable assumptions and kill criteria. Populate "
            "regional_fit for every "
            "requested region with evidence-backed fit reasons and required adaptations. "
            "For every candidate, populate competitive_positioning. Name the closest existing "
            "alternatives, explain what proven patterns may be borrowed, and identify a defensible "
            "difference. A feature combination alone is not a defensible difference. Cite only "
            "competitor evidence IDs supplied above and add questions that can falsify the claimed "
            "advantage. Do not claim a competitor lacks a capability merely because a source does "
            "not mention it. "
            "Use the user's primary language."
        )
        return await self._generate_candidate_batch(
            prompt=prompt,
            expected_ids=expected_ids,
            temperature=0.75,
        )

    async def _generate_candidate_batch(
        self,
        *,
        prompt: str,
        expected_ids: list[str],
        temperature: float,
    ) -> AgentOutput[CandidateEnvelope]:
        outputs = [
            await self._generate(
                system_prompt=(
                    "You are an award-winning consumer-electronics product architect. Generate a "
                    "diverse portfolio from evidence without favoring any hidden or predetermined "
                    "idea. Keep descriptions concise enough to return complete JSON."
                ),
                user_prompt=prompt,
                response_model=CandidateEnvelope,
                temperature=temperature,
            )
        ]
        if len(outputs[-1].value.candidates) != len(expected_ids):
            outputs.append(
                await self._generate(
                    system_prompt=(
                        "You are an award-winning consumer-electronics product architect. Generate "
                        "a diverse portfolio from evidence without favoring a predetermined idea."
                    ),
                    user_prompt=(
                        f"{prompt}\n\nCorrection: return exactly {len(expected_ids)} candidates; "
                        f"the previous response returned {len(outputs[-1].value.candidates)}."
                    ),
                    response_model=CandidateEnvelope,
                    temperature=max(temperature - 0.1, 0.1),
                )
            )
        batch = outputs[-1].value.candidates
        if len(batch) != len(expected_ids):
            raise ValueError(
                f"product architect batch must return exactly {len(expected_ids)} candidates"
            )
        normalized = [
            candidate.model_copy(update={"id": expected_id})
            for candidate, expected_id in zip(batch, expected_ids, strict=True)
        ]
        return _combine_candidate_outputs(outputs, normalized)

    async def repair(
        self,
        *,
        request: ForecastRequest,
        invalid_candidates: list[ProductCandidate],
        validation_error: str,
        opportunities: list[Opportunity],
        evidence: list[EvidenceRecord],
        competitor_evidence: list[CompetitorRecord],
        current_baseline: CurrentCapabilityBaseline,
    ) -> AgentOutput[CandidateEnvelope]:
        valid_opportunity_ids = [item.id for item in opportunities]
        valid_evidence_ids = [item.id for item in evidence]
        valid_competitor_ids = [item.id for item in competitor_evidence]
        outputs: list[AgentOutput[CandidateEnvelope]] = []
        corrected: list[ProductCandidate] = []
        for start in range(0, len(invalid_candidates), PRODUCT_ARCHITECT_BATCH_SIZE):
            invalid_batch = invalid_candidates[start : start + PRODUCT_ARCHITECT_BATCH_SIZE]
            expected_ids = [item.id for item in invalid_batch]
            prompt = (
                f"The previous candidate portfolio failed deterministic validation:\n"
                f"{validation_error}\n\n"
                f"Invalid candidates in this repair batch:\n{compact_json(invalid_batch)}\n\n"
                "Return only the corrected candidates in this batch, preserving genuinely useful "
                "product ideas. "
                f"The research brief remains authoritative:\n{compact_json(request)}\n\n"
                f"Current eufy capability baseline:\n{compact_json(current_baseline)}\n\n"
                f"Required innovation vectors:\n"
                f"{compact_json(_innovation_vector_plan(expected_ids))}\n\n"
                f"Return exactly {len(expected_ids)} candidates using these IDs: {expected_ids}.\n"
                f"opportunity_ids may only use: {valid_opportunity_ids}\n"
                f"evidence_ids and regional_fit evidence_ids may only use: {valid_evidence_ids}\n"
                "competitive_positioning.competitor_evidence_ids may only use: "
                f"{valid_competitor_ids}\n"
                "Preserve each candidate's strategy_alignment (aligned_dimensions restricted to "
                "innovation, user_value, business_value, cost_effectiveness, feasibility, "
                "eufy_synergy; plus rationale and tradeoffs); repair it if malformed but never "
                "drop it. Preserve and repair capability_delta; it must state a meaningful new "
                "hardware/system or sensing/actuation capability beyond the current baseline. "
                "Move misplaced IDs to the correct field only when the relationship is "
                "supported; otherwise remove them. Do not invent replacement IDs. Do not change "
                "factual claims merely to hide a citation error."
            )
            output = await self._generate_candidate_batch(
                prompt=prompt,
                expected_ids=expected_ids,
                temperature=0.15,
            )
            outputs.append(output)
            corrected.extend(output.value.candidates)
        return _combine_candidate_outputs(outputs, corrected)

    async def regenerate_novelty_failures(
        self,
        *,
        request: ForecastRequest,
        failed_candidates: list[ProductCandidate],
        assessments: list[CandidateNoveltyAssessment],
        accepted_candidates: list[ProductCandidate],
        evidence: list[EvidenceRecord],
        opportunities: list[Opportunity],
        competitive_analysis: CompetitiveAnalysis,
        competitor_evidence: list[CompetitorRecord],
        current_baseline: CurrentCapabilityBaseline,
        rejected_candidate_history: dict[str, list[ProductCandidate]] | None = None,
        novelty_feedback_history: dict[str, list[CandidateNoveltyAssessment]] | None = None,
        innovation_vector_overrides: dict[str, InnovationVector] | None = None,
    ) -> AgentOutput[CandidateEnvelope]:
        outputs: list[AgentOutput[CandidateEnvelope]] = []
        replacements: list[ProductCandidate] = []
        assessment_by_id = {item.candidate_id: item for item in assessments}
        for start in range(0, len(failed_candidates), PRODUCT_ARCHITECT_BATCH_SIZE):
            failed_batch = failed_candidates[start : start + PRODUCT_ARCHITECT_BATCH_SIZE]
            expected_ids = [item.id for item in failed_batch]
            feedback = [assessment_by_id[item.id] for item in failed_batch]
            output = await self._run_batch(
                request=request,
                evidence=evidence,
                opportunities=opportunities,
                competitive_analysis=competitive_analysis,
                competitor_evidence=competitor_evidence,
                current_baseline=current_baseline,
                expected_ids=expected_ids,
                existing_candidates=[*accepted_candidates, *replacements],
                novelty_feedback=feedback,
                rejected_candidate_history={
                    item.id: (rejected_candidate_history or {}).get(item.id, [])
                    for item in failed_batch
                },
                novelty_feedback_history={
                    item.id: (novelty_feedback_history or {}).get(item.id, [])
                    for item in failed_batch
                },
                innovation_vector_overrides=innovation_vector_overrides,
            )
            repeated = [
                item
                for item in output.value.candidates
                if _repeats_rejected_version(
                    item, (rejected_candidate_history or {}).get(item.id, [])
                )
            ]
            if repeated:
                repeated_by_id = {item.id: item for item in repeated}
                retry_history = {
                    item.id: [
                        *(rejected_candidate_history or {}).get(item.id, []),
                        *([repeated_by_id[item.id]] if item.id in repeated_by_id else []),
                    ]
                    for item in failed_batch
                }
                retry = await self._run_batch(
                    request=request,
                    evidence=evidence,
                    opportunities=opportunities,
                    competitive_analysis=competitive_analysis,
                    competitor_evidence=competitor_evidence,
                    current_baseline=current_baseline,
                    expected_ids=expected_ids,
                    existing_candidates=[*accepted_candidates, *replacements],
                    novelty_feedback=feedback,
                    rejected_candidate_history=retry_history,
                    novelty_feedback_history={
                        item.id: (novelty_feedback_history or {}).get(item.id, [])
                        for item in failed_batch
                    },
                    innovation_vector_overrides=innovation_vector_overrides,
                )
                output = _combine_candidate_outputs(
                    [output, retry], retry.value.candidates
                )
            outputs.append(output)
            replacements.extend(output.value.candidates)
        return _combine_candidate_outputs(outputs, replacements)

    async def regenerate_portfolio_duplicates(
        self,
        *,
        request: ForecastRequest,
        duplicate_candidates: list[ProductCandidate],
        kept_candidates: list[ProductCandidate],
        pair_feedback: list[CandidatePairSimilarity],
        evidence: list[EvidenceRecord],
        opportunities: list[Opportunity],
        competitive_analysis: CompetitiveAnalysis,
        competitor_evidence: list[CompetitorRecord],
        current_baseline: CurrentCapabilityBaseline,
    ) -> AgentOutput[CandidateEnvelope]:
        outputs: list[AgentOutput[CandidateEnvelope]] = []
        replacements: list[ProductCandidate] = []
        for start in range(0, len(duplicate_candidates), PRODUCT_ARCHITECT_BATCH_SIZE):
            duplicate_batch = duplicate_candidates[start : start + PRODUCT_ARCHITECT_BATCH_SIZE]
            expected_ids = [item.id for item in duplicate_batch]
            relevant_feedback = [
                item
                for item in pair_feedback
                if getattr(item, "regenerate_candidate_id", None) in expected_ids
                or getattr(item, "candidate_a_id", None) in expected_ids
                or getattr(item, "candidate_b_id", None) in expected_ids
            ]
            output = await self._run_batch(
                request=request,
                evidence=evidence,
                opportunities=opportunities,
                competitive_analysis=competitive_analysis,
                competitor_evidence=competitor_evidence,
                current_baseline=current_baseline,
                expected_ids=expected_ids,
                existing_candidates=[*kept_candidates, *replacements],
                portfolio_feedback=relevant_feedback,
            )
            outputs.append(output)
            replacements.extend(output.value.candidates)
        return _combine_candidate_outputs(outputs, replacements)


class LensDeliberationAgent(BaseAgent):
    def __init__(self, llm: object, lens: str) -> None:
        super().__init__(llm)  # type: ignore[arg-type]
        if lens not in LENS_PROMPTS:
            raise ValueError(f"unsupported deliberation lens: {lens}")
        self.lens = lens
        self.name = f"deliberator-{lens}"

    async def run(
        self,
        request: ForecastRequest,
        own_forecast: LensForecast,
        other_forecasts: list[LensForecast],
        evidence: list[EvidenceRecord],
    ) -> AgentOutput[LensDeliberationEnvelope]:
        prompt = (
            f"Research brief:\n{compact_json(request)}\n\n"
            f"Your original forecast:\n{compact_json(own_forecast)}\n\n"
            f"Other independent forecasts:\n{compact_json(other_forecasts)}\n\n"
            f"Evidence cited by the panel:\n{compact_json(evidence)}\n\n"
            f"Review from the '{self.lens}' perspective. Accept well-supported cross-lens "
            "points, issue 1-5 specific challenges, revise your own position when warranted, and "
            "retain unresolved questions. Challenges must target a claim rather than an agent. "
            "Use only supplied EV-* evidence IDs. Do not force agreement. Set reviewer_lens "
            f"exactly to '{self.lens}' and use challenge IDs CH-{self.lens.upper()}-01, etc. "
            "Use the user's primary language."
        )
        return await self._generate(
            system_prompt=(
                f"{LENS_PROMPTS[self.lens]} You are now performing adversarial peer review. "
                "Reward evidence, expose overreach, and update your confidence honestly."
            ),
            user_prompt=prompt,
            response_model=LensDeliberationEnvelope,
            temperature=0.3,
        )


class ForecastConsensusAgent(BaseAgent):
    name = "forecast-consensus"

    async def run(
        self,
        request: ForecastRequest,
        forecasts: list[LensForecast],
        deliberations: list[LensDeliberation],
        evidence: list[EvidenceRecord],
    ) -> AgentOutput[ForecastConsensusEnvelope]:
        prompt = (
            f"Research brief:\n{compact_json(request)}\n\n"
            f"Independent forecasts:\n{compact_json(forecasts)}\n\n"
            f"Cross-lens deliberations:\n{compact_json(deliberations)}\n\n"
            f"Cited evidence:\n{compact_json(evidence)}\n\n"
            "Form an evidence-weighted decision record. Identify 2-8 supported consensus claims, "
            "resolved disagreements, genuinely unresolved disagreements, rejected claims, "
            "minority views, evidence gaps, and implications for opportunity discovery. Consensus "
            "does not mean unanimity. Never erase a material dissent. Cite only supplied EV-* "
            "evidence IDs and use the user's primary language."
        )
        return await self._generate(
            system_prompt=(
                "You are an independent chair of a product-futures review board. You did not "
                "author the forecasts. Your job is to distinguish supported consensus from "
                "groupthink."
            ),
            user_prompt=prompt,
            response_model=ForecastConsensusEnvelope,
            temperature=0.25,
        )


class CandidateReviewerAgent(BaseAgent):
    def __init__(self, llm: object, dimension: str) -> None:
        super().__init__(llm)  # type: ignore[arg-type]
        if dimension not in REVIEW_PROMPTS:
            raise ValueError(f"unsupported review dimension: {dimension}")
        self.dimension = dimension
        self.name = f"reviewer-{dimension}"

    async def run(
        self,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        candidates: list[ProductCandidate],
        competitor_evidence: list[CompetitorRecord],
    ) -> AgentOutput[ReviewEnvelope]:
        anonymous_candidates = [
            candidate.model_copy(update={"name": f"Anonymous concept {index}"})
            for index, candidate in enumerate(candidates, 1)
        ]
        prompt = (
            f"Research brief:\n{compact_json(request)}\n\n"
            f"Anonymous candidates:\n{compact_json(anonymous_candidates)}\n\n"
            f"Evidence records:\n{compact_json(evidence)}\n\n"
            f"Official competitor records:\n{compact_json(competitor_evidence)}\n\n"
            f"Review every candidate only on '{self.dimension}'. Return exactly one review per "
            "candidate, preserve candidate_id, and set dimension exactly to the requested value. "
            "Use a discriminating 0-100 score; do not make all concepts look equally strong. "
            "Challenge copycat claims and unsupported competitive differences using the supplied "
            "competitor records. "
            "Use the user's primary language."
        )
        output = await self._generate(
            system_prompt=(
                f"You are an independent blind product reviewer. {REVIEW_PROMPTS[self.dimension]} "
                "You did not generate the concepts and must challenge unsupported claims."
            ),
            user_prompt=prompt,
            response_model=ReviewEnvelope,
            temperature=0.25,
        )
        expected_ids = {candidate.id for candidate in candidates}
        returned_ids = {review.candidate_id for review in output.value.reviews}
        if returned_ids != expected_ids or len(output.value.reviews) != len(candidates):
            output = await self._generate(
                system_prompt=(
                    "You are an independent blind product reviewer. "
                    f"{REVIEW_PROMPTS[self.dimension]}"
                ),
                user_prompt=(
                    f"{prompt}\n\nCorrection: return exactly one review for each of these IDs: "
                    f"{sorted(expected_ids)}."
                ),
                response_model=ReviewEnvelope,
                temperature=0.2,
            )
        return output


class CompetitorAnalysisAgent(BaseAgent):
    name = "competitor-analysis"

    async def run(
        self,
        request: ForecastRequest,
        opportunities: list[Opportunity],
        competitor_evidence: list[CompetitorRecord],
    ) -> AgentOutput[CompetitiveAnalysisEnvelope]:
        prompt = (
            f"Research brief:\n{compact_json(request)}\n\n"
            f"Future opportunity portfolio:\n{compact_json(opportunities)}\n\n"
            f"Official competitor records:\n{compact_json(competitor_evidence)}\n\n"
            "Analyze the competitive landscape after opportunity discovery and before product "
            "design. Identify established capabilities, documented strengths and constraints, "
            "subscription or lock-in gaps, privacy/interoperability gaps, and 3-6 meaningful "
            "white spaces. Link each gap to opportunity IDs and competitor evidence IDs. "
            "Do not equate absence from a source with absence from a product. Distinguish official "
            "claims from your synthesis. Do not design or name the final eufy products yet. "
            "Populate regional_differences for every requested region. Use GAP-001 style IDs and "
            "the user's primary language."
        )
        return await self._generate(
            system_prompt=(
                "You are a rigorous consumer-security competitive-intelligence strategist. "
                "Your role is to prevent copycat products and expose testable market white space, "
                "not to force a predetermined concept."
            ),
            user_prompt=prompt,
            response_model=CompetitiveAnalysisEnvelope,
            temperature=0.35,
        )


class ProductDefinitionAgent(BaseAgent):
    name = "product-definition"

    async def run(
        self,
        *,
        run_id: str,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        ranked_candidate: RankedCandidate,
        selection: ProductSelectionRequest,
        competitive_analysis: CompetitiveAnalysis | None,
        competitor_evidence: list[CompetitorRecord],
    ) -> AgentOutput[ProductSpecEnvelope]:
        prompt = (
            f"Research brief:\n{compact_json(request)}\n\n"
            f"{strategy_brief(request)}\n\n"
            f"User-selected candidate and reviews:\n{compact_json(ranked_candidate)}\n\n"
            f"User selection input:\n{compact_json(selection)}\n\n"
            f"Evidence records:\n{compact_json(evidence)}\n\n"
            f"Competitive analysis:\n{compact_json(competitive_analysis)}\n\n"
            f"Competitor records:\n{compact_json(competitor_evidence)}\n\n"
            "Turn the chosen concept into a coherent version-1 product definition. Preserve the "
            "core idea, capability_delta and the candidate's strategy_alignment orientation while "
            "resolving reviewer "
            "concerns and applying explicit requested changes. Carry the strategy costs the "
            "reviewers raised (and the candidate's own strategy_alignment.tradeoffs) into risks, "
            "key_assumptions or validation_readiness rather than dropping them. Turn "
            "cost_effectiveness assumptions into falsifiable items — willingness-to-pay, a BOM or "
            "target-cost assumption, install/maintenance cost, and whether an optional (never "
            "mandatory) subscription is acceptable. "
            "Trace every populated research_context preference into the product definition, a "
            "regional adaptation, a risk, or a validation hypothesis; do not silently drop it. "
            "Leave empty context fields open rather than inventing user requirements. "
            "Do not invent validation results or claim any business/technical outcome is already "
            "proven. Populate validation_readiness with falsifiable tests "
            "that a later technical, commercial, privacy, UX or spatial simulator could execute. "
            "Preserve or strengthen regional_fit for every requested market. Use only provided "
            "evidence IDs. Use the user's primary language."
            " Preserve competitive_positioning, resolve any reviewer concerns about imitation, "
            "and make its validation questions executable by the later validation system."
        )
        output = await self._generate(
            system_prompt=(
                "You are a principal product-definition lead. You turn a human-selected AI concept "
                "into a testable product specification without claiming that it has been validated."
            ),
            user_prompt=prompt,
            response_model=ProductSpecEnvelope,
            temperature=0.4,
        )
        product = output.value.product.model_copy(
            update={
                "id": f"product-{uuid4().hex[:12]}",
                "source_run_id": run_id,
                "source_candidate_id": ranked_candidate.candidate.id,
                "version": "1.0",
                "human_selection_reason": selection.selection_reason,
                "capability_delta": ranked_candidate.candidate.capability_delta,
            }
        )
        return AgentOutput(
            value=ProductSpecEnvelope(product=product),
            metadata=output.metadata,
        )
