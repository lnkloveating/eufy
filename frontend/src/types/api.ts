/**
 * TypeScript contracts mirrored 1:1 from the backend Pydantic models in
 * `backend/src/eufy_security_agents/domain/models.py`.
 *
 * These types are the single source of truth on the frontend. They must not
 * drift from the backend; when the backend models change, update this file.
 */

export type RunStatus = "pending" | "running" | "completed" | "failed";

export type KnowledgeLayer =
  | "eufy_foundation"
  | "regional_market"
  | "user_needs"
  | "technology"
  | "privacy_regulation"
  | "business"
  | "risk_counterevidence";

export type ClaimStatus =
  | "verified"
  | "official_claim"
  | "research_synthesis"
  | "hypothesis";

export const SCORE_DIMENSIONS = [
  "innovation",
  "user_value",
  "business_value",
  "cost_effectiveness",
  "feasibility",
  "eufy_synergy",
] as const;

export type ScoreDimension = (typeof SCORE_DIMENSIONS)[number];

export type ScoreWeights = Record<ScoreDimension, number>;

/** Named strategy the user chose; `custom` means hand-tuned sliders. */
export type StrategyProfile =
  | "balanced"
  | "breakthrough"
  | "value"
  | "ecosystem"
  | "custom";

/** Backend-authored preset (weights are never re-derived on the frontend). */
export interface StrategyPreset {
  id: Exclude<StrategyProfile, "custom">;
  label: string;
  description: string;
  weights: ScoreWeights;
}

export interface ResearchContext {
  housing_types: string[];
  household_members: string[];
  security_scenarios: string[];
  current_devices: string[];
  pain_points: string[];
  allowed_sensors: string[];
  privacy_preferences: string[];
  installation_constraints: string[];
  connectivity_constraints: string[];
  business_preferences: string[];
  desired_outcomes: string[];
  validation_priorities: string[];
  innovation_posture: string | null;
}

export interface ForecastRequest {
  question: string;
  category: string;
  forecast_horizon_years: number;
  regions: string[];
  target_users: string[];
  price_segment: string | null;
  constraints: string[];
  research_context: ResearchContext;
  candidate_count: number;
  strategy_profile: StrategyProfile;
  weights: ScoreWeights;
}

export interface EvidenceRecord {
  id: string;
  title: string;
  content: string;
  evidence_type: string;
  regions: string[];
  category: string;
  source_name: string;
  source_url: string;
  published_at: string | null;
  retrieved_at: string;
  credibility: number;
  tags: string[];
  layer: KnowledgeLayer;
  scope: string;
  topics: string[];
  claim_status: ClaimStatus;
  language: string;
  supports: string[];
  contradicts: string[];
  valid_until: string | null;
}

export interface RegionCoverage {
  region: string;
  total_records: number;
  verified_records: number;
  hypothesis_records: number;
  represented_layers: KnowledgeLayer[];
  missing_layers: KnowledgeLayer[];
  level: "strong" | "moderate" | "limited";
}

export interface KnowledgeCoverage {
  total_records: number;
  records_by_layer: Record<string, number>;
  regions: RegionCoverage[];
}

export interface RetrievalPlan {
  requested_regions: string[];
  query_topics: string[];
  required_layers: KnowledgeLayer[];
  excluded_topics: string[];
  layer_quotas: Record<string, number>;
  coverage: RegionCoverage[];
  fallback_used: boolean;
  selected_evidence_ids: string[];
  selection_reasons: Record<string, string[]>;
  explanation: string;
  /** Strategy explainability. Optional so pre-strategy plans still parse. */
  strategy_profile?: StrategyProfile;
  strategy_adjustments?: Record<string, number>;
  strategy_topics?: string[];
  strategy_explanation?: string;
}

export interface RetrievalPreview {
  plan: RetrievalPlan;
  evidence: EvidenceRecord[];
}

export interface TrendSignal {
  title: string;
  description: string;
  impact_horizon: string;
  evidence_ids: string[];
  confidence: number;
  uncertainty: string;
}

export interface LensForecast {
  lens: string;
  thesis: string;
  signals: TrendSignal[];
  implications: string[];
}

export interface AcceptedCrossLensPoint {
  source_lens: string;
  claim: string;
  acceptance_reason: string;
  evidence_ids: string[];
}

export interface CrossLensChallenge {
  id: string;
  target_lens: string;
  challenged_claim: string;
  challenge_reason: string;
  evidence_ids: string[];
  severity: string;
}

export interface LensDeliberation {
  reviewer_lens: string;
  original_thesis: string;
  accepted_points: AcceptedCrossLensPoint[];
  challenges: CrossLensChallenge[];
  revisions_to_own_view: string[];
  unchanged_positions: string[];
  unresolved_questions: string[];
  revised_thesis: string;
  revised_confidence: number;
}

export interface ConsensusClaim {
  claim: string;
  supporting_lenses: string[];
  evidence_ids: string[];
  confidence: number;
}

export interface DisagreementResolution {
  topic: string;
  positions: Record<string, string>;
  resolution: string;
  rationale: string;
}

export interface UnresolvedDisagreement {
  topic: string;
  positions: Record<string, string>;
  why_unresolved: string;
  validation_need: string;
}

export interface ForecastConsensus {
  consensus_claims: ConsensusClaim[];
  resolved_disagreements: DisagreementResolution[];
  unresolved_disagreements: UnresolvedDisagreement[];
  rejected_claims: string[];
  minority_views: string[];
  evidence_gaps: string[];
  opportunity_implications: string[];
}

export interface Opportunity {
  id: string;
  title: string;
  unmet_job: string;
  target_users: string[];
  target_regions: string[];
  why_now: string;
  opportunity_window: string;
  enabling_trends: string[];
  evidence_ids: string[];
  counter_evidence: string[];
  confidence: number;
  regional_differences: Record<string, string[]>;
}

export interface CompetitorRecord {
  id: string;
  brand: string;
  product_name: string;
  product_family: string;
  regions: string[];
  verified_capabilities: string[];
  documented_constraints: string[];
  business_model: string;
  privacy_and_storage: string[];
  interoperability: string[];
  source_name: string;
  source_url: string;
  retrieved_at: string;
  credibility: number;
  claim_status: ClaimStatus;
  tags: string[];
}

export interface CompetitiveGap {
  id: string;
  title: string;
  description: string;
  affected_opportunity_ids: string[];
  competitor_brands: string[];
  competitor_evidence_ids: string[];
  white_space: string;
  design_implications: string[];
  imitation_risk: string;
  validation_question: string;
  confidence: number;
}

export interface CompetitiveAnalysis {
  market_patterns: string[];
  established_capabilities: string[];
  competitor_strengths: Record<string, string[]>;
  competitor_limitations: Record<string, string[]>;
  underserved_needs: string[];
  subscription_or_lock_in_gaps: string[];
  privacy_and_interoperability_gaps: string[];
  regional_differences: Record<string, string[]>;
  gaps: CompetitiveGap[];
}

export interface CompetitivePositioning {
  closest_alternatives: string[];
  borrowed_patterns: string[];
  defensible_differences: string[];
  non_copycat_rationale: string;
  copycat_risks: string[];
  competitor_evidence_ids: string[];
  validation_questions: string[];
}

export interface RegionalFit {
  region: string;
  fit_reasons: string[];
  required_adaptations: string[];
  evidence_ids: string[];
  confidence: number;
}

/** How a candidate answers the user's prediction strategy (explainable, no fabricated scores). */
export interface StrategyAlignment {
  aligned_dimensions: ScoreDimension[];
  rationale: string;
  tradeoffs: string[];
}

export type NoveltyClassification =
  | "existing_equivalent"
  | "feature_extension"
  | "adjacent_innovation"
  | "new_product_category";

export interface CapabilityDelta {
  today_equivalents: string[];
  new_capabilities: string[];
  why_not_available_today: string;
  enabling_changes: string[];
  proof_needed: string[];
  hardware_or_system_delta: string;
  innovation_vector:
    | "new_sensing"
    | "proactive_intervention"
    | "distributed_architecture"
    | "resilience_recovery"
    | "trust_privacy"
    | "human_ai_coordination"
    | "new_business_delivery";
}

export interface CurrentCapability {
  id: string;
  capability: string;
  existing_products: string[];
  form_factors: string[];
  evidence_ids: string[];
}

export interface CurrentCapabilityBaseline {
  summary: string;
  capabilities: CurrentCapability[];
  combination_warning_signs: string[];
}

export interface CandidateNoveltyAssessment {
  candidate_id: string;
  classification: NoveltyClassification;
  overlap_ratio: number;
  overlapping_capability_ids: string[];
  genuinely_new_capabilities: string[];
  why_not_available_today_is_credible: boolean;
  hardware_or_system_delta_is_meaningful: boolean;
  innovation_vector_is_credible: boolean;
  reasons: string[];
  regeneration_brief: string;
  passes_gate: boolean;
}

export interface NoveltyAudit {
  assessments: CandidateNoveltyAssessment[];
  requested_candidate_count?: number | null;
  returned_candidate_count?: number | null;
  regeneration_rounds?: number;
  rescue_rounds?: number;
  dropped_candidate_ids?: string[];
}

export interface CandidatePairSimilarity {
  candidate_a_id: string;
  candidate_b_id: string;
  similarity_score: number;
  shared_user_jobs: string[];
  shared_product_mechanisms: string[];
  meaningful_differences: string[];
  duplicate: boolean;
  preferred_candidate_id: string;
  regenerate_candidate_id: string;
  regeneration_brief: string;
}

export interface PortfolioDiversityAudit {
  pair_assessments: CandidatePairSimilarity[];
  regeneration_rounds: number;
  regenerated_candidate_ids: string[];
  degraded?: boolean;
  dropped_candidate_ids?: string[];
  unresolved_duplicate_pairs?: string[][];
}

export interface ProductCandidate {
  id: string;
  name: string;
  tagline: string;
  opportunity_ids: string[];
  target_users: string[];
  target_regions: string[];
  core_problem: string;
  value_proposition: string;
  form_factor: string;
  hardware_components: string[];
  ai_native_mechanism: string;
  key_scenarios: string[];
  differentiators: string[];
  estimated_price_range: string;
  technical_dependencies: string[];
  key_assumptions: string[];
  kill_criteria: string[];
  evidence_ids: string[];
  regional_fit: RegionalFit[];
  competitive_positioning: CompetitivePositioning;
  /** Optional so historical candidates without strategy alignment still parse. */
  strategy_alignment?: StrategyAlignment;
  /** Optional for historical result compatibility. */
  capability_delta?: CapabilityDelta;
}

export interface CandidateReview {
  candidate_id: string;
  dimension: string;
  score: number;
  strengths: string[];
  concerns: string[];
  decisive_question: string;
}

export interface RankedCandidate {
  candidate: ProductCandidate;
  reviews: CandidateReview[];
  dimension_scores: Record<string, number>;
  weighted_score: number;
  rank: number;
}

export interface BusinessModel {
  hardware_revenue: string;
  recurring_revenue: string | null;
  ecosystem_pull_through: string[];
  cost_drivers: string[];
}

export interface RiskItem {
  category: string;
  risk: string;
  mitigation: string;
  severity: string;
}

export interface ValidationHypothesis {
  id: string;
  assumption: string;
  metric: string;
  proposed_method: string;
  pass_condition: string;
  kill_condition: string;
}

export interface ProductSpec {
  id: string;
  source_run_id: string;
  source_candidate_id: string;
  version: string;
  name: string;
  one_sentence_definition: string;
  category: string;
  target_users: string[];
  target_regions: string[];
  core_problem: string;
  value_proposition: string;
  form_factor: string;
  hardware_architecture: string[];
  ai_capabilities: string[];
  ai_decision_boundary: string;
  user_journeys: string[];
  ecosystem_relationships: string[];
  privacy_principles: string[];
  business_model: BusinessModel;
  risks: RiskItem[];
  key_assumptions: string[];
  kill_criteria: string[];
  evidence_ids: string[];
  validation_readiness: ValidationHypothesis[];
  regional_fit: RegionalFit[];
  competitive_positioning: CompetitivePositioning;
  capability_delta?: CapabilityDelta;
  human_selection_reason: string | null;
  created_at: string;
}

export interface ProductSelectionRequest {
  candidate_id: string;
  selection_reason: string | null;
  requested_changes: string[];
  idempotency_key?: string;
}

export interface AgentEvent {
  id: number | null;
  run_id: string;
  sequence: number;
  event_type: string;
  agent: string | null;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface ForecastRun {
  id: string;
  status: RunStatus;
  stage: string;
  request: ForecastRequest;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ForecastResult {
  run: ForecastRun;
  retrieval_plan: RetrievalPlan | null;
  evidence: EvidenceRecord[];
  lens_forecasts: LensForecast[];
  lens_deliberations: LensDeliberation[];
  forecast_consensus: ForecastConsensus | null;
  opportunities: Opportunity[];
  competitor_evidence: CompetitorRecord[];
  competitive_analysis: CompetitiveAnalysis | null;
  current_capability_evidence: EvidenceRecord[];
  current_capability_baseline: CurrentCapabilityBaseline | null;
  novelty_audit: NoveltyAudit | null;
  portfolio_diversity_audit: PortfolioDiversityAudit | null;
  candidates: RankedCandidate[];
}

/** GET /health */
export interface HealthResponse {
  status: string;
  service: string;
  llm_model: string;
  llm_configured: boolean;
  local_evidence_count: number;
  competitor_evidence_count: number;
  knowledge_layers: Record<string, number>;
}

export interface Artifact {
  id: string;
  run_id: string;
  kind: string;
  producer: string;
  payload: unknown;
  model_name: string | null;
  prompt_version: string | null;
  duration_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  created_at: string;
}

/** GET /forecast-options */
export interface ForecastOptions {
  regions: string[];
  custom_regions_allowed: boolean;
  research_context_options: Record<keyof ResearchContext, string[]>;
  forecast_horizon_years: {
    minimum: number;
    maximum: number;
    default: number;
  };
  candidate_count: {
    minimum: number;
    maximum: number;
    default: number;
  };
  default_weights: ScoreWeights;
  default_strategy_profile: StrategyProfile;
  strategy_presets: StrategyPreset[];
}
