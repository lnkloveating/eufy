"""Domain contracts for the pre-validation lab (预验证 / 模拟验证).

Everything here is a pure Pydantic/enum contract with no framework or
infrastructure dependency, matching the repository's delivery order. The models
describe a *pre-validation* project: deterministic scenario simulation plus
multi-role analysis of a snapshotted :class:`ProductSpec`. None of it claims a
real hardware test, a real user study, or a real market result — every result
carries an explicit source type and the verdict enum never includes a
"validated for real" state.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from .digital_twin import ProductDigitalTwinSpec
from .models import ProductSpec, ValidationHypothesis

# A single, reusable disclaimer stamped onto every project so the boundary is
# never lost, in the API payload or the UI.
SIMULATION_DISCLAIMER = (
    "本实验室仅进行预验证 / 模拟验证：结论基于确定性场景推演与当前产品定义，"
    "不代表真实硬件测试、真实用户研究或真实市场数据。"
)


class ValidationProjectStatus(StrEnum):
    DRAFT = "draft"
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExperimentType(StrEnum):
    TECHNOLOGY = "technology"
    PRIVACY_SECURITY = "privacy_security"
    USER_SCENARIO = "user_scenario"
    BUSINESS = "business"
    DETERMINISTIC_SIMULATION = "deterministic_simulation"


class ExperimentStatus(StrEnum):
    NOT_RUN = "not_run"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExperimentVerdict(StrEnum):
    """The only verdicts an experiment (or the whole project) may carry.

    Deliberately excludes any "validated for real" value. A positive pure
    simulation result can at most be ``supported_in_simulation``; anything that
    genuinely needs real hardware, real users, or a real market becomes
    ``requires_real_world_test``.
    """

    NOT_RUN = "not_run"
    SUPPORTED_IN_SIMULATION = "supported_in_simulation"
    INCONCLUSIVE = "inconclusive"
    CONTRADICTED = "contradicted"
    REQUIRES_REAL_WORLD_TEST = "requires_real_world_test"


class ObservationSourceType(StrEnum):
    EXISTING_EVIDENCE = "existing_evidence"
    AI_ANALYSIS = "ai_analysis"
    DETERMINISTIC_SIMULATION = "deterministic_simulation"
    HUMAN_OBSERVATION = "human_observation"
    EXTERNAL_TEST = "external_test"


class FindingSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class FindingFeedbackStatus(StrEnum):
    NOT_SENT = "not_sent"
    SENT_TO_DEFINITION = "sent_to_definition"
    DISMISSED = "dismissed"


class ValidationRole(StrEnum):
    """The pre-validation roles that examine each experiment."""

    TECHNOLOGY = "technology"
    PRIVACY_SECURITY = "privacy_security"
    USER_SCENARIO = "user_scenario"
    BUSINESS = "business"
    ADVERSARIAL = "adversarial"
    ADJUDICATOR = "adjudicator"


class ValidationAnalysisActor(StrEnum):
    """Stable actors used by the persisted, replayable analysis trace."""

    HYPOTHESIS_PARSER = "hypothesis_parser"
    EVIDENCE_RETRIEVAL = "evidence_retrieval"
    DETERMINISTIC_SIMULATION = "deterministic_simulation"
    TECHNOLOGY = "technology"
    PRIVACY_SECURITY = "privacy_security"
    USER_SCENARIO = "user_scenario"
    BUSINESS = "business"
    ADVERSARIAL = "adversarial"
    AI_ANALYSIS = "ai_analysis"
    ADJUDICATOR = "adjudicator"


class ScenarioTemplate(StrEnum):
    URBAN_APARTMENT_INTRUSION = "urban_apartment_intrusion"
    ELDERLY_NIGHT_ANOMALY = "elderly_night_anomaly"
    PET_FALSE_ALARM = "pet_false_alarm"
    HOME_NETWORK_OUTAGE = "home_network_outage"


# --------------------------------------------------------------------------- #
# Observations, findings, scenario simulation                                  #
# --------------------------------------------------------------------------- #


class ValidationObservation(BaseModel):
    id: str
    source_type: ObservationSourceType
    source_label: str
    content: str
    # True/False when the observation clearly supports or contradicts the
    # experiment's assumption; None when it is context that does neither.
    supports_hypothesis: bool | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ValidationFinding(BaseModel):
    id: str
    experiment_id: str
    category: str
    title: str
    detail: str
    severity: FindingSeverity
    recommended_change: str
    source_type: ObservationSourceType
    # Which ProductSpec section a send-back should target (validated against the
    # canonical section list before a suggestion is created).
    target_section: str = "risks"
    feedback_status: FindingFeedbackStatus = FindingFeedbackStatus.NOT_SENT
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ScenarioZone(BaseModel):
    """A simple rectangle in a 0-100 SVG coordinate space for the floor plan."""

    id: str
    name: str
    x: float
    y: float
    width: float
    height: float


class ScenarioSensor(BaseModel):
    id: str
    label: str
    zone_id: str
    sensor_type: str
    # Whether the snapshotted ProductSpec actually provides this sensing
    # modality. Unavailable nodes are drawn dimmed so the gap is visible.
    available: bool
    x: float
    y: float


class ScenarioTimelineStep(BaseModel):
    order: int
    time_label: str
    zone_id: str
    title: str
    description: str
    expected_decision: str
    privacy_note: str | None = None
    is_failure_point: bool = False


class ScenarioSimulation(BaseModel):
    template: ScenarioTemplate
    title: str
    description: str
    floor_plan: list[ScenarioZone] = Field(default_factory=list)
    sensors: list[ScenarioSensor] = Field(default_factory=list)
    timeline: list[ScenarioTimelineStep] = Field(default_factory=list)
    expected_product_decisions: list[str] = Field(default_factory=list)
    privacy_boundaries: list[str] = Field(default_factory=list)
    failure_conditions: list[str] = Field(default_factory=list)
    observations: list[str] = Field(default_factory=list)
    coverage_notes: list[str] = Field(default_factory=list)
    verdict: ExperimentVerdict = ExperimentVerdict.NOT_RUN
    verdict_rationale: str = ""


class ValidationAnalysisStep(BaseModel):
    """One persisted step in an experiment's explainable analysis chain.

    The frontend replays these records locally. Replaying therefore never
    invokes an agent or LLM and always reproduces the reasoning that was used
    for the stored verdict.
    """

    id: str
    sequence: int = Field(ge=1)
    actor: ValidationAnalysisActor
    action: str
    reasoning: str
    evidence_ids: list[str] = Field(default_factory=list)
    outcome: str
    source_type: ObservationSourceType


class ValidationExperiment(BaseModel):
    id: str
    project_id: str
    hypothesis_id: str
    title: str
    assumption: str
    experiment_type: ExperimentType
    metric: str
    proposed_method: str
    pass_condition: str
    kill_condition: str
    status: ExperimentStatus = ExperimentStatus.NOT_RUN
    verdict: ExperimentVerdict = ExperimentVerdict.NOT_RUN
    findings: list[ValidationFinding] = Field(default_factory=list)
    observations: list[ValidationObservation] = Field(default_factory=list)
    scenario_template: ScenarioTemplate | None = None
    summary: str = ""
    verdict_reason: str = ""
    supporting_points: list[str] = Field(default_factory=list)
    counter_points: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    next_recommended_test: str = ""
    analysis_trace: list[ValidationAnalysisStep] = Field(default_factory=list)


class ValidationEvent(BaseModel):
    id: int | None = None
    project_id: str
    sequence: int
    event_type: str
    validator_name: str | None = None
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ValidationProject(BaseModel):
    id: str
    product_id: str
    product_version: str
    product_snapshot: ProductSpec
    status: ValidationProjectStatus = ValidationProjectStatus.PLANNED
    experiments: list[ValidationExperiment] = Field(default_factory=list)
    scenario_simulations: list[ScenarioSimulation] = Field(default_factory=list)
    digital_twin: ProductDigitalTwinSpec | None = None
    overall_verdict: ExperimentVerdict = ExperimentVerdict.NOT_RUN
    summary: str = ""
    disclaimer: str = SIMULATION_DISCLAIMER
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def find_finding(self, finding_id: str) -> ValidationFinding | None:
        for experiment in self.experiments:
            for finding in experiment.findings:
                if finding.id == finding_id:
                    return finding
        return None


# --------------------------------------------------------------------------- #
# Request / response envelopes                                                  #
# --------------------------------------------------------------------------- #


class ValidationProjectCreateRequest(BaseModel):
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=100)


class SendBackResponse(BaseModel):
    """Result of sending a finding back to the Product Definition Copilot.

    The ProductSpec is never mutated here; a reviewable suggested change is
    queued for the user to accept or reject in the definition workbench.
    """

    finding: ValidationFinding
    product_id: str
    question_id: str
    suggestion_id: str
    message: str


# --------------------------------------------------------------------------- #
# Optional LLM enrichment envelope (deepseek-chat) — deterministic-safe         #
# --------------------------------------------------------------------------- #


class RoleAnalysisDraft(BaseModel):
    """A short supplemental analysis the LLM may add for one experiment.

    Purely additive narrative context (``ai_analysis`` source). The verdict and
    every structural finding are decided deterministically, never by this draft,
    so a missing or malformed draft can never change an outcome.
    """

    headline: str = ""
    rationale: str = ""
    open_questions: list[str] = Field(default_factory=list)


class RoleAnalysisEnvelope(BaseModel):
    analysis: RoleAnalysisDraft


def experiment_from_hypothesis(
    project_id: str,
    hypothesis: ValidationHypothesis,
    experiment_type: ExperimentType,
    scenario_template: ScenarioTemplate | None,
) -> ValidationExperiment:
    """Deterministically turn one validation hypothesis into an experiment."""

    return ValidationExperiment(
        id=f"exp-{hypothesis.id}",
        project_id=project_id,
        hypothesis_id=hypothesis.id,
        title=hypothesis.assumption[:80],
        assumption=hypothesis.assumption,
        experiment_type=experiment_type,
        metric=hypothesis.metric,
        proposed_method=hypothesis.proposed_method,
        pass_condition=hypothesis.pass_condition,
        kill_condition=hypothesis.kill_condition,
        scenario_template=scenario_template,
    )
