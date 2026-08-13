"""Domain contracts for AI-native product forecasting."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import BaseModel, Field, model_validator


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SelectionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class KnowledgeLayer(StrEnum):
    EUFY_FOUNDATION = "eufy_foundation"
    REGIONAL_MARKET = "regional_market"
    USER_NEEDS = "user_needs"
    TECHNOLOGY = "technology"
    PRIVACY_REGULATION = "privacy_regulation"
    BUSINESS = "business"
    RISK_COUNTEREVIDENCE = "risk_counterevidence"


class ClaimStatus(StrEnum):
    VERIFIED = "verified"
    OFFICIAL_CLAIM = "official_claim"
    RESEARCH_SYNTHESIS = "research_synthesis"
    HYPOTHESIS = "hypothesis"


class ScoreWeights(BaseModel):
    innovation: float = 0.30
    user_value: float = 0.25
    business_value: float = 0.20
    feasibility: float = 0.15
    eufy_synergy: float = 0.10

    @model_validator(mode="after")
    def validate_total(self) -> ScoreWeights:
        if abs(sum(self.model_dump().values()) - 1.0) > 0.001:
            raise ValueError("evaluation weights must sum to 1.0")
        return self


class ResearchContext(BaseModel):
    """Structured household and product-design context for a forecast.

    Every field is optional so previously persisted runs and lightweight API
    clients remain valid.  When supplied, the values participate in retrieval
    and are visible to every forecasting, deliberation and product agent.
    """

    housing_types: list[str] = Field(default_factory=list)
    household_members: list[str] = Field(default_factory=list)
    security_scenarios: list[str] = Field(default_factory=list)
    current_devices: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    allowed_sensors: list[str] = Field(default_factory=list)
    privacy_preferences: list[str] = Field(default_factory=list)
    installation_constraints: list[str] = Field(default_factory=list)
    connectivity_constraints: list[str] = Field(default_factory=list)
    business_preferences: list[str] = Field(default_factory=list)
    desired_outcomes: list[str] = Field(default_factory=list)
    validation_priorities: list[str] = Field(default_factory=list)
    innovation_posture: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def normalize_values(self) -> ResearchContext:
        for field_name in self.__class__.model_fields:
            value = getattr(self, field_name)
            if isinstance(value, list):
                setattr(
                    self,
                    field_name,
                    list(dict.fromkeys(item.strip() for item in value if item.strip())),
                )
        if self.innovation_posture is not None:
            normalized = self.innovation_posture.strip()
            self.innovation_posture = normalized or None
        return self

    def search_terms(self) -> list[str]:
        """Flatten context for deterministic local retrieval."""
        terms: list[str] = []
        for field_name in self.__class__.model_fields:
            value = getattr(self, field_name)
            if isinstance(value, list):
                terms.extend(value)
            elif value:
                terms.append(value)
        return terms


class ForecastRequest(BaseModel):
    question: str = Field(min_length=12, max_length=1_000)
    category: str = Field(default="eufy Security", min_length=2, max_length=100)
    forecast_horizon_years: Annotated[int, Field(ge=1, le=10)] = 3
    regions: list[str] = Field(default_factory=lambda: ["United States"], min_length=1)
    target_users: list[str] = Field(default_factory=lambda: ["Households"], min_length=1)
    price_segment: str | None = None
    constraints: list[str] = Field(default_factory=list)
    research_context: ResearchContext = Field(default_factory=ResearchContext)
    candidate_count: Annotated[int, Field(ge=3, le=10)] = 6
    weights: ScoreWeights = Field(default_factory=ScoreWeights)

    @model_validator(mode="after")
    def normalize_lists(self) -> ForecastRequest:
        self.regions = list(dict.fromkeys(item.strip() for item in self.regions if item.strip()))
        self.target_users = list(
            dict.fromkeys(item.strip() for item in self.target_users if item.strip())
        )
        self.constraints = list(
            dict.fromkeys(item.strip() for item in self.constraints if item.strip())
        )
        if not self.regions or not self.target_users:
            raise ValueError("regions and target_users cannot be empty")
        return self


class EvidenceRecord(BaseModel):
    id: str
    title: str
    content: str
    evidence_type: str
    regions: list[str]
    category: str
    source_name: str
    source_url: str
    published_at: str | None = None
    retrieved_at: str
    credibility: Annotated[float, Field(ge=0, le=1)]
    tags: list[str]
    layer: KnowledgeLayer | None = None
    scope: str | None = None
    topics: list[str] = Field(default_factory=list)
    claim_status: ClaimStatus | None = None
    language: str = "en"
    supports: list[str] = Field(default_factory=list)
    contradicts: list[str] = Field(default_factory=list)
    valid_until: str | None = None

    @model_validator(mode="after")
    def infer_legacy_knowledge_metadata(self) -> EvidenceRecord:
        """Keep legacy JSONL valid while exposing useful RAG metadata."""
        if self.layer is None:
            mapping = {
                "current_product": KnowledgeLayer.EUFY_FOUNDATION,
                "current_capability": KnowledgeLayer.EUFY_FOUNDATION,
                "brand_strategy": KnowledgeLayer.EUFY_FOUNDATION,
                "technology_signal": KnowledgeLayer.TECHNOLOGY,
                "constraint": KnowledgeLayer.RISK_COUNTEREVIDENCE,
                "user_hypothesis": KnowledgeLayer.USER_NEEDS,
                "regional_context": KnowledgeLayer.REGIONAL_MARKET,
                "business_hypothesis": KnowledgeLayer.BUSINESS,
                "safety_principle": KnowledgeLayer.RISK_COUNTEREVIDENCE,
                "regulatory_context": KnowledgeLayer.PRIVACY_REGULATION,
            }
            self.layer = mapping.get(self.evidence_type, KnowledgeLayer.RISK_COUNTEREVIDENCE)
        if self.claim_status is None:
            if self.source_url.startswith("local://"):
                self.claim_status = (
                    ClaimStatus.HYPOTHESIS
                    if "hypothesis" in self.evidence_type
                    else ClaimStatus.RESEARCH_SYNTHESIS
                )
            elif self.source_name.lower().startswith("eufy"):
                self.claim_status = ClaimStatus.OFFICIAL_CLAIM
            else:
                self.claim_status = ClaimStatus.VERIFIED
        if self.scope is None:
            self.scope = "global" if "Global" in self.regions else "regional"
        if not self.topics:
            self.topics = list(self.tags)
        return self


class RegionCoverage(BaseModel):
    region: str
    total_records: int
    verified_records: int
    hypothesis_records: int
    represented_layers: list[KnowledgeLayer]
    missing_layers: list[KnowledgeLayer]
    level: str


class KnowledgeCoverage(BaseModel):
    total_records: int
    records_by_layer: dict[str, int]
    regions: list[RegionCoverage]


class RetrievalPlan(BaseModel):
    requested_regions: list[str]
    query_topics: list[str]
    required_layers: list[KnowledgeLayer]
    excluded_topics: list[str]
    layer_quotas: dict[str, int]
    coverage: list[RegionCoverage]
    fallback_used: bool
    selected_evidence_ids: list[str]
    selection_reasons: dict[str, list[str]]
    explanation: str


class RetrievalPreview(BaseModel):
    plan: RetrievalPlan
    evidence: list[EvidenceRecord]


class TrendSignal(BaseModel):
    title: str
    description: str
    impact_horizon: str
    evidence_ids: list[str]
    confidence: Annotated[float, Field(ge=0, le=1)]
    uncertainty: str


class LensForecast(BaseModel):
    lens: str
    thesis: str
    signals: list[TrendSignal] = Field(min_length=2, max_length=8)
    implications: list[str] = Field(min_length=2, max_length=8)


class AcceptedCrossLensPoint(BaseModel):
    source_lens: str
    claim: str
    acceptance_reason: str
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Only EV-* IDs from the supplied local evidence records.",
    )


class CrossLensChallenge(BaseModel):
    id: str
    target_lens: str
    challenged_claim: str
    challenge_reason: str
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Only EV-* IDs from the supplied local evidence records.",
    )
    severity: str


class LensDeliberation(BaseModel):
    reviewer_lens: str
    original_thesis: str
    accepted_points: list[AcceptedCrossLensPoint] = Field(default_factory=list, max_length=5)
    challenges: list[CrossLensChallenge] = Field(min_length=1, max_length=5)
    revisions_to_own_view: list[str] = Field(default_factory=list, max_length=5)
    unchanged_positions: list[str] = Field(default_factory=list, max_length=5)
    unresolved_questions: list[str] = Field(min_length=1, max_length=5)
    revised_thesis: str
    revised_confidence: Annotated[float, Field(ge=0, le=1)]


class ConsensusClaim(BaseModel):
    claim: str
    supporting_lenses: list[str]
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Only EV-* IDs from the supplied local evidence records.",
    )
    confidence: Annotated[float, Field(ge=0, le=1)]


class DisagreementResolution(BaseModel):
    topic: str
    positions: dict[str, str]
    resolution: str
    rationale: str


class UnresolvedDisagreement(BaseModel):
    topic: str
    positions: dict[str, str]
    why_unresolved: str
    validation_need: str


class ForecastConsensus(BaseModel):
    consensus_claims: list[ConsensusClaim] = Field(min_length=2, max_length=8)
    resolved_disagreements: list[DisagreementResolution] = Field(default_factory=list)
    unresolved_disagreements: list[UnresolvedDisagreement] = Field(default_factory=list)
    rejected_claims: list[str] = Field(default_factory=list)
    minority_views: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    opportunity_implications: list[str] = Field(min_length=2, max_length=8)


class Opportunity(BaseModel):
    id: str
    title: str
    unmet_job: str
    target_users: list[str]
    target_regions: list[str]
    why_now: str
    opportunity_window: str
    enabling_trends: list[str]
    evidence_ids: list[str] = Field(
        description="Only EV-* IDs from the supplied local evidence records; never OPP-* IDs."
    )
    counter_evidence: list[str]
    confidence: Annotated[float, Field(ge=0, le=1)]
    regional_differences: dict[str, list[str]] = Field(default_factory=dict)


class CompetitorRecord(BaseModel):
    id: str
    brand: str
    product_name: str
    product_family: str
    regions: list[str]
    verified_capabilities: list[str]
    documented_constraints: list[str]
    business_model: str
    privacy_and_storage: list[str]
    interoperability: list[str] = Field(default_factory=list)
    source_name: str
    source_url: str
    retrieved_at: str
    credibility: Annotated[float, Field(ge=0, le=1)]
    claim_status: ClaimStatus = ClaimStatus.OFFICIAL_CLAIM
    tags: list[str] = Field(default_factory=list)


class CompetitiveGap(BaseModel):
    id: str
    title: str
    description: str
    affected_opportunity_ids: list[str] = Field(
        description="Only OPP-* IDs from the supplied opportunity portfolio."
    )
    competitor_brands: list[str]
    competitor_evidence_ids: list[str] = Field(
        description="Only COMP-* IDs from supplied competitor records."
    )
    white_space: str
    design_implications: list[str]
    imitation_risk: str
    validation_question: str
    confidence: Annotated[float, Field(ge=0, le=1)]


class CompetitiveAnalysis(BaseModel):
    market_patterns: list[str]
    established_capabilities: list[str]
    competitor_strengths: dict[str, list[str]]
    competitor_limitations: dict[str, list[str]]
    underserved_needs: list[str]
    subscription_or_lock_in_gaps: list[str]
    privacy_and_interoperability_gaps: list[str]
    regional_differences: dict[str, list[str]]
    gaps: list[CompetitiveGap] = Field(min_length=3, max_length=6)


class CompetitivePositioning(BaseModel):
    closest_alternatives: list[str] = Field(default_factory=list)
    borrowed_patterns: list[str] = Field(default_factory=list)
    defensible_differences: list[str] = Field(default_factory=list)
    non_copycat_rationale: str = ""
    copycat_risks: list[str] = Field(default_factory=list)
    competitor_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Only COMP-* IDs from supplied competitor records.",
    )
    validation_questions: list[str] = Field(default_factory=list)


class RegionalFit(BaseModel):
    region: str
    fit_reasons: list[str]
    required_adaptations: list[str]
    evidence_ids: list[str] = Field(
        description="Only EV-* IDs from supplied local evidence; never OPP-* or COMP-* IDs."
    )
    confidence: Annotated[float, Field(ge=0, le=1)]


class ProductCandidate(BaseModel):
    id: str
    name: str
    tagline: str
    opportunity_ids: list[str] = Field(
        description="Only OPP-* IDs from the supplied opportunity portfolio."
    )
    target_users: list[str]
    target_regions: list[str]
    core_problem: str
    value_proposition: str
    form_factor: str
    hardware_components: list[str]
    ai_native_mechanism: str
    key_scenarios: list[str]
    differentiators: list[str]
    estimated_price_range: str
    technical_dependencies: list[str]
    key_assumptions: list[str]
    kill_criteria: list[str]
    evidence_ids: list[str] = Field(
        description="Only EV-* IDs from supplied local evidence; never OPP-* or COMP-* IDs."
    )
    regional_fit: list[RegionalFit] = Field(default_factory=list)
    competitive_positioning: CompetitivePositioning = Field(default_factory=CompetitivePositioning)


class CandidateReview(BaseModel):
    candidate_id: str
    dimension: str
    score: Annotated[float, Field(ge=0, le=100)]
    strengths: list[str]
    concerns: list[str]
    decisive_question: str


class RankedCandidate(BaseModel):
    candidate: ProductCandidate
    reviews: list[CandidateReview]
    dimension_scores: dict[str, float]
    weighted_score: Annotated[float, Field(ge=0, le=100)]
    rank: int


class BusinessModel(BaseModel):
    hardware_revenue: str
    recurring_revenue: str | None = None
    ecosystem_pull_through: list[str]
    cost_drivers: list[str]


class RiskItem(BaseModel):
    category: str
    risk: str
    mitigation: str
    severity: str


class ValidationHypothesis(BaseModel):
    id: str
    assumption: str
    metric: str
    proposed_method: str
    pass_condition: str
    kill_condition: str


class ProductSpec(BaseModel):
    id: str
    source_run_id: str
    source_candidate_id: str
    version: str = "1.0"
    name: str
    one_sentence_definition: str
    category: str
    target_users: list[str]
    target_regions: list[str]
    core_problem: str
    value_proposition: str
    form_factor: str
    hardware_architecture: list[str]
    ai_capabilities: list[str]
    ai_decision_boundary: str
    user_journeys: list[str]
    ecosystem_relationships: list[str]
    privacy_principles: list[str]
    business_model: BusinessModel
    risks: list[RiskItem]
    key_assumptions: list[str]
    kill_criteria: list[str]
    evidence_ids: list[str] = Field(
        description="Only EV-* IDs from supplied local evidence; never OPP-* or COMP-* IDs."
    )
    validation_readiness: list[ValidationHypothesis]
    regional_fit: list[RegionalFit] = Field(default_factory=list)
    competitive_positioning: CompetitivePositioning = Field(default_factory=CompetitivePositioning)
    human_selection_reason: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProductSelectionRequest(BaseModel):
    candidate_id: str
    selection_reason: str | None = Field(default=None, max_length=1_000)
    requested_changes: list[str] = Field(default_factory=list)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class ProductSelectionState(BaseModel):
    run_id: str
    idempotency_key: str
    candidate_id: str
    status: SelectionStatus
    product_id: str | None = None
    error: str | None = None


class AgentEvent(BaseModel):
    id: int | None = None
    run_id: str
    sequence: int
    event_type: str
    agent: str | None = None
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ForecastRun(BaseModel):
    id: str
    status: RunStatus
    stage: str
    request: ForecastRequest
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class ForecastResult(BaseModel):
    run: ForecastRun
    retrieval_plan: RetrievalPlan | None = None
    evidence: list[EvidenceRecord]
    lens_forecasts: list[LensForecast]
    lens_deliberations: list[LensDeliberation] = Field(default_factory=list)
    forecast_consensus: ForecastConsensus | None = None
    opportunities: list[Opportunity]
    competitor_evidence: list[CompetitorRecord]
    competitive_analysis: CompetitiveAnalysis | None = None
    candidates: list[RankedCandidate]


class Artifact(BaseModel):
    id: str
    run_id: str
    kind: str
    producer: str
    payload: Any
    model_name: str | None = None
    prompt_version: str | None = None
    duration_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LensForecastEnvelope(BaseModel):
    forecast: LensForecast


class LensDeliberationEnvelope(BaseModel):
    deliberation: LensDeliberation


class ForecastConsensusEnvelope(BaseModel):
    consensus: ForecastConsensus


class OpportunityEnvelope(BaseModel):
    opportunities: list[Opportunity]


class CompetitiveAnalysisEnvelope(BaseModel):
    analysis: CompetitiveAnalysis


class CandidateEnvelope(BaseModel):
    candidates: list[ProductCandidate]


class ReviewEnvelope(BaseModel):
    reviews: list[CandidateReview]


class ProductSpecEnvelope(BaseModel):
    product: ProductSpec
