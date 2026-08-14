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


class ProductDefinitionLifecycle(StrEnum):
    """Run-scoped lifecycle shown before a concrete ProductSpec exists."""

    RESEARCHING = "researching"
    AWAITING_SELECTION = "awaiting_selection"
    GENERATING = "generating"
    READY = "ready"
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


class NoveltyClassification(StrEnum):
    EXISTING_EQUIVALENT = "existing_equivalent"
    FEATURE_EXTENSION = "feature_extension"
    ADJACENT_INNOVATION = "adjacent_innovation"
    NEW_PRODUCT_CATEGORY = "new_product_category"


class DefinitionStatus(StrEnum):
    """Lifecycle of a ProductSpec inside the definition workbench.

    ``validation_ready`` means the definition is complete enough to enter the
    later validation phase. It never means the product has been validated.
    """

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    VALIDATION_READY = "validation_ready"


class QuestionCategory(StrEnum):
    """Lightweight classification that drives which context an answer receives."""

    TECHNOLOGY = "technology"
    PRIVACY = "privacy"
    COMPETITION = "competition"
    BUSINESS = "business"
    ECOSYSTEM = "ecosystem"
    USER_EXPERIENCE = "user_experience"
    GENERAL = "general"


class EpistemicStatus(StrEnum):
    """How well a single answer claim is supported."""

    EVIDENCE_SUPPORTED = "evidence_supported"
    REASONED_INFERENCE = "reasoned_inference"
    DESIGN_ASSUMPTION = "design_assumption"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AnswerMode(StrEnum):
    """How the analyst is handling a question.

    ``explanation`` is the default: explain the current ProductSpec, never
    propose a revision. ``issue_detected`` surfaces a structured gap but still
    proposes nothing until the user asks. ``change_request`` is the only mode
    that may return suggested changes directly.
    """

    EXPLANATION = "explanation"
    ISSUE_DETECTED = "issue_detected"
    CHANGE_REQUEST = "change_request"


class SuggestionDisposition(StrEnum):
    """What a user chose to do with a suggested change."""

    APPLY = "apply"
    AS_RISK = "as_risk"
    AS_HYPOTHESIS = "as_hypothesis"
    DISMISS = "dismiss"


class SuggestionKind(StrEnum):
    """Distinguishes a definition edit from an opt-in validation candidate."""

    DEFINITION_CHANGE = "definition_change"
    VALIDATION_HYPOTHESIS = "validation_hypothesis"


class InnovationVector(StrEnum):
    NEW_SENSING = "new_sensing"
    PROACTIVE_INTERVENTION = "proactive_intervention"
    DISTRIBUTED_ARCHITECTURE = "distributed_architecture"
    RESILIENCE_RECOVERY = "resilience_recovery"
    TRUST_PRIVACY = "trust_privacy"
    HUMAN_AI_COORDINATION = "human_ai_coordination"
    NEW_BUSINESS_DELIVERY = "new_business_delivery"


class StrategyProfile(StrEnum):
    """Named product-prediction strategy the user selected before a run.

    ``custom`` means the user hand-tuned the weight sliders. The profile is only
    a label describing the user's intent; ``ScoreWeights`` remains the single
    authoritative execution value everywhere in the pipeline.
    """

    BALANCED = "balanced"
    BREAKTHROUGH = "breakthrough"
    VALUE = "value"
    ECOSYSTEM = "ecosystem"
    CUSTOM = "custom"


class ScoreWeights(BaseModel):
    """Six evaluation weights that must sum to 1.0.

    ``cost_effectiveness`` (性价比) is deliberately separate from
    ``business_value``: business_value looks at market size, margin, revenue
    model, channels and moats, while cost_effectiveness looks at the price a
    household pays, hardware/maintenance/install cost, subscription burden and
    the real value received for that spend.

    Backward compatibility: historical runs persisted five weights that already
    summed to 1.0. A ``mode="before"`` step detects a legacy weights mapping
    (any weight supplied but ``cost_effectiveness`` absent) and fills
    ``cost_effectiveness`` with 0.0 so the legacy total stays 1.0. A request that
    omits weights entirely falls back to the six-dimension balanced default.
    """

    innovation: float = 0.25
    user_value: float = 0.20
    business_value: float = 0.15
    cost_effectiveness: float = 0.15
    feasibility: float = 0.15
    eufy_synergy: float = 0.10

    @model_validator(mode="before")
    @classmethod
    def backfill_legacy_cost_effectiveness(cls, data: Any) -> Any:
        """Keep pre-cost_effectiveness five-weight payloads valid."""
        if isinstance(data, dict) and data:
            # Only treat as legacy when at least one weight was explicitly
            # provided but cost_effectiveness is missing. An empty mapping keeps
            # the new six-dimension default (which already sums to 1.0).
            has_any_weight = any(field in data for field in cls.model_fields)
            if has_any_weight and "cost_effectiveness" not in data:
                data = {**data, "cost_effectiveness": 0.0}
        return data

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
    strategy_profile: StrategyProfile = StrategyProfile.BALANCED
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
    # Strategy explainability. Defaulted so historical retrieval-plan artifacts
    # that predate the strategy feature still deserialize.
    strategy_profile: StrategyProfile = StrategyProfile.BALANCED
    strategy_adjustments: dict[str, int] = Field(default_factory=dict)
    strategy_topics: list[str] = Field(default_factory=list)
    strategy_explanation: str = ""


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
    # Lenses that failed after retry and were excluded from this consensus.
    # Backend-populated so the consensus never silently hides a missing view.
    missing_lenses: list[str] = Field(default_factory=list)


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


class CompetitiveLandscape(BaseModel):
    """Competitive landscape summary without the white-space gaps.

    Used when the full competitive analysis has to be produced in two smaller
    LLM calls to stay under the provider output-token limit.
    """

    market_patterns: list[str] = Field(default_factory=list)
    established_capabilities: list[str] = Field(default_factory=list)
    competitor_strengths: dict[str, list[str]] = Field(default_factory=dict)
    competitor_limitations: dict[str, list[str]] = Field(default_factory=dict)
    underserved_needs: list[str] = Field(default_factory=list)
    subscription_or_lock_in_gaps: list[str] = Field(default_factory=list)
    privacy_and_interoperability_gaps: list[str] = Field(default_factory=list)
    regional_differences: dict[str, list[str]] = Field(default_factory=dict)


class CompetitiveAnalysis(BaseModel):
    market_patterns: list[str]
    established_capabilities: list[str]
    competitor_strengths: dict[str, list[str]]
    competitor_limitations: dict[str, list[str]]
    underserved_needs: list[str]
    subscription_or_lock_in_gaps: list[str]
    privacy_and_interoperability_gaps: list[str]
    regional_differences: dict[str, list[str]]
    gaps: list[CompetitiveGap] = Field(default_factory=list, max_length=8)
    # Set when the analysis was produced from a degraded, evidence-derived
    # fallback after the model repeatedly exceeded the output-token limit. A
    # degraded analysis never fabricates white space; it is built only from real
    # CompetitorRecord capabilities and documented constraints.
    degraded: bool = False
    degradation_reason: str | None = None


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


VALID_SCORE_DIMENSIONS = frozenset(ScoreWeights.model_fields)


class StrategyAlignment(BaseModel):
    """How a candidate answers the user's prediction strategy.

    Explainable, never a fabricated score. ``aligned_dimensions`` may only use
    the six valid scoring dimensions. Defaulted empty so historical candidates
    without this field still deserialize.
    """

    aligned_dimensions: list[str] = Field(default_factory=list)
    rationale: str = ""
    tradeoffs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dimensions(self) -> StrategyAlignment:
        self.aligned_dimensions = [
            dimension
            for dimension in dict.fromkeys(self.aligned_dimensions)
            if dimension in VALID_SCORE_DIMENSIONS
        ]
        return self


class CapabilityDelta(BaseModel):
    """Explicit difference between a candidate and products available today."""

    today_equivalents: list[str] = Field(default_factory=list)
    new_capabilities: list[str] = Field(default_factory=list)
    why_not_available_today: str = ""
    enabling_changes: list[str] = Field(default_factory=list)
    proof_needed: list[str] = Field(default_factory=list)
    hardware_or_system_delta: str = ""
    innovation_vector: InnovationVector = InnovationVector.NEW_SENSING


class CurrentCapability(BaseModel):
    id: str
    capability: str
    existing_products: list[str]
    form_factors: list[str]
    evidence_ids: list[str] = Field(
        description="Only EV-* IDs from the current eufy evidence supplied to the auditor."
    )


class CurrentCapabilityBaseline(BaseModel):
    summary: str
    capabilities: list[CurrentCapability] = Field(min_length=3, max_length=20)
    combination_warning_signs: list[str] = Field(default_factory=list)


class CandidateNoveltyAssessment(BaseModel):
    candidate_id: str
    classification: NoveltyClassification
    overlap_ratio: Annotated[float, Field(ge=0, le=1)]
    overlapping_capability_ids: list[str]
    genuinely_new_capabilities: list[str]
    why_not_available_today_is_credible: bool
    hardware_or_system_delta_is_meaningful: bool
    innovation_vector_is_credible: bool
    reasons: list[str]
    regeneration_brief: str
    passes_gate: bool = False


class NoveltyAudit(BaseModel):
    assessments: list[CandidateNoveltyAssessment]
    requested_candidate_count: int | None = None
    returned_candidate_count: int | None = None
    regeneration_rounds: int = 0
    rescue_rounds: int = 0
    dropped_candidate_ids: list[str] = Field(default_factory=list)


class CandidatePairSimilarity(BaseModel):
    """Semantic overlap between two candidates in the same portfolio.

    The model only *describes* overlap. ``preferred_candidate_id`` and
    ``regenerate_candidate_id`` are retained for backward compatibility but the
    backend ignores their control meaning: which candidate survives a duplicate
    cluster is decided deterministically from novelty quality, not by the model.
    Both default to empty so a malformed or omitted choice can never fail a run.
    """

    candidate_a_id: str
    candidate_b_id: str
    similarity_score: Annotated[float, Field(ge=0, le=1)]
    shared_user_jobs: list[str] = Field(default_factory=list)
    shared_product_mechanisms: list[str] = Field(default_factory=list)
    meaningful_differences: list[str] = Field(default_factory=list)
    duplicate: bool = False
    preferred_candidate_id: str = ""
    regenerate_candidate_id: str = ""
    regeneration_brief: str = ""


class PortfolioDiversityAudit(BaseModel):
    """Final pairwise audit plus an auditable record of portfolio regeneration."""

    pair_assessments: list[CandidatePairSimilarity]
    regeneration_rounds: int = 0
    regenerated_candidate_ids: list[str] = Field(default_factory=list)
    degraded: bool = False
    degradation_reason: str | None = None
    # Human-readable record of every non-fatal repair the backend applied to a
    # malformed auditor response (reordered/duplicate/missing/unknown pairs).
    normalization_notes: list[str] = Field(default_factory=list)
    dropped_candidate_ids: list[str] = Field(default_factory=list)
    unresolved_duplicate_pairs: list[list[str]] = Field(default_factory=list)


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
    strategy_alignment: StrategyAlignment = Field(default_factory=StrategyAlignment)
    capability_delta: CapabilityDelta = Field(default_factory=CapabilityDelta)


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
    capability_delta: CapabilityDelta = Field(default_factory=CapabilityDelta)
    human_selection_reason: str | None = None
    # Definition-workbench lifecycle. Defaulted so ProductSpecs persisted before
    # the workbench existed still deserialize as a fresh draft.
    definition_status: DefinitionStatus = DefinitionStatus.DRAFT
    last_change_reason: str | None = None
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


class RunProductDefinitionState(BaseModel):
    """Authoritative product-definition state for one forecast run."""

    run_id: str
    status: ProductDefinitionLifecycle
    product_id: str | None = None
    candidate_id: str | None = None
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


class StageDegradation(BaseModel):
    """Auditable record of a stage that used a bounded local fallback."""

    stage: str
    reason: str
    failure_kind: str


class ForecastRun(BaseModel):
    id: str
    status: RunStatus
    stage: str
    request: ForecastRequest
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class ForecastRunSummary(BaseModel):
    id: str
    status: RunStatus
    stage: str
    question: str
    category: str
    regions: list[str]
    created_at: datetime
    updated_at: datetime


class ForecastRunListResponse(BaseModel):
    items: list[ForecastRunSummary]
    total: int
    limit: int


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
    current_capability_evidence: list[EvidenceRecord] = Field(default_factory=list)
    current_capability_baseline: CurrentCapabilityBaseline | None = None
    novelty_audit: NoveltyAudit | None = None
    portfolio_diversity_audit: PortfolioDiversityAudit | None = None
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


class CompetitiveLandscapeEnvelope(BaseModel):
    landscape: CompetitiveLandscape


class CompetitiveGapsEnvelope(BaseModel):
    gaps: list[CompetitiveGap] = Field(default_factory=list)


class CurrentCapabilityBaselineEnvelope(BaseModel):
    baseline: CurrentCapabilityBaseline


class NoveltyAuditEnvelope(BaseModel):
    audit: NoveltyAudit


class PortfolioDiversityAuditEnvelope(BaseModel):
    audit: PortfolioDiversityAudit


class CandidateEnvelope(BaseModel):
    candidates: list[ProductCandidate]


class ReviewEnvelope(BaseModel):
    reviews: list[CandidateReview]


class ProductSpecEnvelope(BaseModel):
    product: ProductSpec


# --------------------------------------------------------------------------- #
# Product Definition Workbench                                                 #
# --------------------------------------------------------------------------- #


class ProductQuestionRequest(BaseModel):
    question: str = Field(min_length=4, max_length=1_000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class ProductQuestion(BaseModel):
    id: str
    product_id: str
    product_version: str
    question: str
    category: QuestionCategory
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProductAnswerClaim(BaseModel):
    """A single answer claim carrying an explicit epistemic label.

    ``evidence_ids`` and ``competitor_evidence_ids`` are validated by the backend
    against the exact context supplied to the model; illegal references are
    stripped and the claim is downgraded rather than trusted.
    """

    text: str
    epistemic_status: EpistemicStatus
    evidence_ids: list[str] = Field(default_factory=list)
    competitor_evidence_ids: list[str] = Field(default_factory=list)


class ProductSuggestedChange(BaseModel):
    id: str
    section: str
    current_summary: str
    proposed_change: str
    rationale: str
    source_question_id: str
    kind: SuggestionKind = SuggestionKind.DEFINITION_CHANGE
    validation_hypothesis: ValidationHypothesis | None = None
    # Set when the suggestion was generated from a detected design issue.
    source_issue_id: str | None = None
    # Populated at read time from suggestion resolutions: accepted /
    # converted_to_risk / converted_to_hypothesis / dismissed, or None if pending.
    resolution: str | None = None


class ProductDesignIssue(BaseModel):
    """A concrete gap in the current ProductSpec, surfaced without auto-editing.

    Only raised when the spec is missing a necessary decision, internally
    inconsistent, unsupported, or conflicts with the research brief — never
    merely because a different design is possible.
    """

    id: str
    title: str
    description: str
    affected_sections: list[str] = Field(default_factory=list)
    severity: str
    reason: str
    blocks_readiness: bool = False
    # Populated at read time: addressed / dismissed, or None while open.
    resolution: str | None = None


class ProductQuestionAnswer(BaseModel):
    id: str
    question_id: str
    product_id: str
    product_version: str
    category: QuestionCategory
    answer_mode: AnswerMode = AnswerMode.EXPLANATION
    direct_answer: str
    claims: list[ProductAnswerClaim] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    affected_sections: list[str] = Field(default_factory=list)
    design_issue: ProductDesignIssue | None = None
    suggested_changes: list[ProductSuggestedChange] = Field(default_factory=list)
    # Transparency about backend citation repair/degradation, so the user can
    # see when evidence was insufficient rather than silently trusting a claim.
    integrity_notes: list[str] = Field(default_factory=list)
    # The exact evidence/competitor IDs the model was allowed to cite; lets the
    # frontend resolve titles and show what context the answer was grounded in.
    context_evidence_ids: list[str] = Field(default_factory=list)
    context_competitor_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProductQuestionRecord(BaseModel):
    """A question paired with its structured answer (persisted together)."""

    question: ProductQuestion
    answer: ProductQuestionAnswer


class ProductAnswerDraftClaim(BaseModel):
    text: str
    epistemic_status: EpistemicStatus
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Only EV-* IDs from the supplied evidence digest.",
    )
    competitor_evidence_ids: list[str] = Field(
        default_factory=list,
        description="Only COMP-* IDs from the supplied competitor digest.",
    )


class ProductAnswerDraftChange(BaseModel):
    section: str
    current_summary: str
    proposed_change: str
    rationale: str


class ValidationHypothesisDraft(BaseModel):
    """A falsifiable validation candidate proposed alongside a Copilot answer."""

    assumption: str
    metric: str
    proposed_method: str
    pass_condition: str
    kill_condition: str


class ProductDesignIssueDraft(BaseModel):
    title: str
    description: str
    affected_sections: list[str] = Field(default_factory=list)
    severity: str
    reason: str
    blocks_readiness: bool = False


class ProductAnswerDraft(BaseModel):
    """LLM-authored answer body before the backend assigns IDs and validates."""

    answer_mode: AnswerMode = AnswerMode.EXPLANATION
    direct_answer: str
    claims: list[ProductAnswerDraftClaim] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    affected_sections: list[str] = Field(default_factory=list)
    design_issue: ProductDesignIssueDraft | None = None
    suggested_changes: list[ProductAnswerDraftChange] = Field(default_factory=list)
    validation_proposal: ValidationHypothesisDraft | None = None


class ProductAnswerEnvelope(BaseModel):
    answer: ProductAnswerDraft


class ProductProposalEnvelope(BaseModel):
    """Suggested changes generated on demand from a detected design issue."""

    suggested_changes: list[ProductAnswerDraftChange] = Field(default_factory=list)


class ProductRevisionDecision(BaseModel):
    suggestion_id: str
    disposition: SuggestionDisposition = SuggestionDisposition.APPLY

    @model_validator(mode="after")
    def reject_dismiss(self) -> ProductRevisionDecision:
        if self.disposition == SuggestionDisposition.DISMISS:
            raise ValueError("dismiss is not a revision; use the resolve endpoint")
        return self


class ProductRevisionRequest(BaseModel):
    decisions: list[ProductRevisionDecision] = Field(min_length=1)
    change_reason: str | None = Field(default=None, max_length=1_000)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class ProductRevisionChange(BaseModel):
    suggestion_id: str
    section: str
    proposed_change: str
    disposition: SuggestionDisposition


class ProductRevision(BaseModel):
    id: str
    product_id: str
    from_version: str
    to_version: str
    source_answer_ids: list[str] = Field(default_factory=list)
    accepted_changes: list[ProductRevisionChange] = Field(default_factory=list)
    change_reason: str
    before_snapshot: ProductSpec
    after_snapshot: ProductSpec
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SuggestionDismissRequest(BaseModel):
    suggestion_ids: list[str] = Field(min_length=1)


class IssueDismissRequest(BaseModel):
    issue_ids: list[str] = Field(min_length=1)


class SuggestionResolution(BaseModel):
    suggestion_id: str
    product_id: str
    resolution: str
    revision_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReadinessItem(BaseModel):
    id: str
    label: str
    ok: bool
    detail: str | None = None


class ProductDefinitionReadiness(BaseModel):
    product_id: str
    version: str
    definition_status: DefinitionStatus
    ready: bool
    score: int = Field(ge=0, le=100)
    completed_items: list[ReadinessItem] = Field(default_factory=list)
    blocking_items: list[ReadinessItem] = Field(default_factory=list)
    warnings: list[ReadinessItem] = Field(default_factory=list)
    outstanding_suggestions: int = 0
    next_recommended_questions: list[str] = Field(default_factory=list)
