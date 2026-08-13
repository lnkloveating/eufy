"""LLM agents used before the future validation phase."""

from __future__ import annotations

from uuid import uuid4

from eufy_security_agents.core.serialization import compact_json
from eufy_security_agents.domain.models import (
    CandidateEnvelope,
    CompetitiveAnalysis,
    CompetitiveAnalysisEnvelope,
    CompetitorRecord,
    EvidenceRecord,
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
    ProductSpecEnvelope,
    RankedCandidate,
    ReviewEnvelope,
)

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
        "Judge addressable demand, price logic, margin drivers and ecosystem revenue."
    ),
    "feasibility": (
        "Judge three-year technical, power, cost, reliability and manufacturing feasibility."
    ),
    "eufy_synergy": (
        "Judge fit with eufy Security, HomeBase, channels and differentiated capabilities."
    ),
}


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
            f"Local evidence records:\n{compact_json(evidence)}\n\n"
            f"Your lens identifier is '{self.lens}'. Produce a JSON forecast for that lens. "
            "Every signal must cite only evidence IDs present above. Clearly state uncertainty. "
            "Treat claim_status=hypothesis as a proposition to test, not as an established fact. "
            "Do not transfer a regional claim to another region unless a global record "
            "supports it. Treat research_context as explicit user input: use populated fields "
            "to focus the analysis, and never invent preferences for empty fields. "
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
            f"Independent forecasts:\n{compact_json(forecasts)}\n\n"
            f"Cross-lens deliberations:\n{compact_json(deliberations)}\n\n"
            f"Consensus and remaining disagreements:\n{compact_json(consensus)}\n\n"
            f"Available evidence:\n{compact_json(evidence)}\n\n"
            "Synthesize 5-9 distinct future opportunity spaces. Do not design products yet. "
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


class ProductArchitectAgent(BaseAgent):
    name = "product-architect"
    prompt_version = "2.0"

    async def run(
        self,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        opportunities: list[Opportunity],
        competitive_analysis: CompetitiveAnalysis,
        competitor_evidence: list[CompetitorRecord],
    ) -> AgentOutput[CandidateEnvelope]:
        valid_opportunity_ids = [item.id for item in opportunities]
        valid_evidence_ids = [item.id for item in evidence]
        valid_competitor_ids = [item.id for item in competitor_evidence]
        prompt = (
            f"Research brief:\n{compact_json(request)}\n\n"
            f"Opportunity portfolio:\n{compact_json(opportunities)}\n\n"
            f"Evidence records:\n{compact_json(evidence)}\n\n"
            f"Competitive white-space analysis:\n{compact_json(competitive_analysis)}\n\n"
            f"Official competitor records:\n{compact_json(competitor_evidence)}\n\n"
            f"Generate exactly {request.candidate_count} genuinely different future consumer-"
            "electronics products. Each must include a meaningful hardware form factor and be "
            "AI-native, not merely an app, chatbot, report or existing product with an AI label. "
            "Spread concepts across several opportunity spaces; do not make cosmetic variants. "
            "Respect the requested regions, users, horizon, price segment, constraints and every "
            "populated research_context field. Empty context fields are unknown, not permission "
            "to assume a preference. Ensure the portfolio explores more than one plausible way "
            "to achieve the requested outcomes instead of repeating the user's current devices. "
            "Use candidate IDs CAND-001, CAND-002, etc. Follow this ID contract exactly:\n"
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
        output = await self._generate(
            system_prompt=(
                "You are an award-winning consumer-electronics product architect. Generate a "
                "diverse portfolio from evidence without favoring any hidden or predetermined idea."
            ),
            user_prompt=prompt,
            response_model=CandidateEnvelope,
            temperature=0.75,
        )
        if len(output.value.candidates) != request.candidate_count:
            output = await self._generate(
                system_prompt=(
                    "You are an award-winning consumer-electronics product architect. Generate a "
                    "diverse portfolio from evidence without favoring a predetermined idea."
                ),
                user_prompt=(
                    f"{prompt}\n\nCorrection: return exactly {request.candidate_count} candidates; "
                    f"the previous response returned {len(output.value.candidates)}."
                ),
                response_model=CandidateEnvelope,
                temperature=0.65,
            )
        return output

    async def repair(
        self,
        *,
        request: ForecastRequest,
        invalid_candidates: list[ProductCandidate],
        validation_error: str,
        opportunities: list[Opportunity],
        evidence: list[EvidenceRecord],
        competitor_evidence: list[CompetitorRecord],
    ) -> AgentOutput[CandidateEnvelope]:
        valid_opportunity_ids = [item.id for item in opportunities]
        valid_evidence_ids = [item.id for item in evidence]
        valid_competitor_ids = [item.id for item in competitor_evidence]
        prompt = (
            f"The previous candidate portfolio failed deterministic validation:\n"
            f"{validation_error}\n\n"
            f"Invalid portfolio:\n{compact_json(invalid_candidates)}\n\n"
            "Return the complete corrected portfolio, preserving genuinely useful product ideas. "
            f"The research brief remains authoritative:\n{compact_json(request)}\n\n"
            f"Return exactly {request.candidate_count} candidates with unique CAND-* IDs.\n"
            f"opportunity_ids may only use: {valid_opportunity_ids}\n"
            f"evidence_ids and regional_fit evidence_ids may only use: {valid_evidence_ids}\n"
            "competitive_positioning.competitor_evidence_ids may only use: "
            f"{valid_competitor_ids}\n"
            "Move misplaced IDs to the correct field only when the relationship is supported; "
            "otherwise remove them. Do not invent replacement IDs. Do not change factual claims "
            "merely to hide a citation error."
        )
        return await self._generate(
            system_prompt=(
                "You are repairing a structured product portfolio after deterministic contract "
                "validation. Accuracy and ID-field separation are mandatory."
            ),
            user_prompt=prompt,
            response_model=CandidateEnvelope,
            temperature=0.15,
        )


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
            f"User-selected candidate and reviews:\n{compact_json(ranked_candidate)}\n\n"
            f"User selection input:\n{compact_json(selection)}\n\n"
            f"Evidence records:\n{compact_json(evidence)}\n\n"
            f"Competitive analysis:\n{compact_json(competitive_analysis)}\n\n"
            f"Competitor records:\n{compact_json(competitor_evidence)}\n\n"
            "Turn the chosen concept into a coherent version-1 product definition. Preserve the "
            "core idea while resolving reviewer concerns and applying explicit requested changes. "
            "Trace every populated research_context preference into the product definition, a "
            "regional adaptation, a risk, or a validation hypothesis; do not silently drop it. "
            "Leave empty context fields open rather than inventing user requirements. "
            "Do not invent validation results. Populate validation_readiness with "
            "falsifiable tests "
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
            }
        )
        return AgentOutput(
            value=ProductSpecEnvelope(product=product),
            metadata=output.metadata,
        )
