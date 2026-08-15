"""Tests for the pre-validation lab (预验证 / 模拟验证)."""

from __future__ import annotations

from typing import TypeVar

import pytest
from pydantic import BaseModel

from eufy_security_agents.domain.models import (
    BusinessModel,
    CompetitivePositioning,
    DefinitionStatus,
    ProductSpec,
    RiskItem,
    ValidationHypothesis,
)
from eufy_security_agents.domain.scenario_simulation import (
    detect_capabilities,
    simulate_all_scenarios,
)
from eufy_security_agents.domain.validation import (
    ExperimentStatus,
    ExperimentVerdict,
    FindingFeedbackStatus,
    ObservationSourceType,
    RoleAnalysisDraft,
    RoleAnalysisEnvelope,
    ScenarioTemplate,
    ValidationAnalysisActor,
    ValidationProjectCreateRequest,
    ValidationProjectStatus,
)
from eufy_security_agents.domain.validation_roles import analyze_business
from eufy_security_agents.infrastructure.llm import LLMGenerationError
from eufy_security_agents.infrastructure.memory import InMemoryRunRepository
from eufy_security_agents.infrastructure.repositories import SqlAlchemyRunRepository
from eufy_security_agents.orchestration.validation_workflow import (
    ValidationNotReadyError,
    ValidationWorkflow,
)

T = TypeVar("T", bound=BaseModel)


class FakeValidationLLM:
    model_name = "fake-validation"

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
    ) -> tuple[T, dict[str, int | str | None]]:
        del system_prompt, user_prompt, temperature
        self.calls += 1
        if self.fail:
            raise LLMGenerationError(
                "structured LLM generation failed",
                failure_kind="provider_timeout",
                attempts=1,
            )
        assert response_model is RoleAnalysisEnvelope
        value = RoleAnalysisEnvelope(
            analysis=RoleAnalysisDraft(
                headline="补充解读：结论仅为模拟",
                rationale="需要真实测试才能确认经验指标。",
                open_questions=["真实误报率是多少？"],
            )
        )
        return value, {  # type: ignore[return-value]
            "model_name": self.model_name,
            "input_tokens": 10,
            "output_tokens": 20,
            "duration_ms": 5,
        }


def _hypothesis(hid: str, assumption: str, metric: str) -> ValidationHypothesis:
    return ValidationHypothesis(
        id=hid,
        assumption=assumption,
        metric=metric,
        proposed_method="确定性场景模拟",
        pass_condition="达到预设门槛",
        kill_condition="出现不可接受风险",
    )


def _base_spec(
    *,
    product_id: str,
    hardware: list[str],
    ai_capabilities: list[str],
    decision_boundary: str,
    privacy: list[str],
    ecosystem: list[str],
    hypotheses: list[ValidationHypothesis],
    status: DefinitionStatus = DefinitionStatus.VALIDATION_READY,
) -> ProductSpec:
    return ProductSpec(
        id=product_id,
        source_run_id="run-x",
        source_candidate_id="CAND-001",
        name="预验证测试产品",
        one_sentence_definition="用于验证实验室测试的产品定义。",
        category="eufy Security",
        target_users=["Households"],
        target_regions=["United States"],
        core_problem="家庭安防问题",
        value_proposition="更早发现风险",
        form_factor="定制硬件",
        hardware_architecture=hardware,
        ai_capabilities=ai_capabilities,
        ai_decision_boundary=decision_boundary,
        user_journeys=["安装并配置"],
        ecosystem_relationships=ecosystem,
        privacy_principles=privacy,
        business_model=BusinessModel(
            hardware_revenue="一次性硬件销售",
            ecosystem_pull_through=["HomeBase"],
            cost_drivers=["传感器"],
        ),
        risks=[RiskItem(category="technical", risk="准确性", mitigation="验证", severity="high")],
        key_assumptions=["用户重视结果"],
        kill_criteria=["采用率过低"],
        evidence_ids=["EV-EUFY-001"],
        validation_readiness=hypotheses,
        competitive_positioning=CompetitivePositioning(
            closest_alternatives=["Ring"],
            defensible_differences=["本地预测"],
            validation_questions=["预测是否降低事件？"],
        ),
        definition_status=status,
    )


def _ready_spec() -> ProductSpec:
    return _base_spec(
        product_id="product-ready",
        hardware=["摄像头模组", "毫米波雷达", "PIR 运动传感", "端侧 AI 芯片", "本地存储"],
        ai_capabilities=["多信号融合识别人形与宠物"],
        decision_boundary="高影响动作需用户确认，模型仅本地推理",
        privacy=["默认本地处理", "数据最小化"],
        ecosystem=["HomeBase", "eufy app"],
        hypotheses=[
            _hypothesis("H-001", "断网后产品仍能在本地继续侦测与告警", "离线连续性"),
            _hypothesis("H-002", "用户愿意为该产品一次性付费", "付费意愿"),
        ],
    )


def _cloud_only_spec() -> ProductSpec:
    return _base_spec(
        product_id="product-cloud",
        hardware=["摄像头模组", "云端 AI 分析"],
        ai_capabilities=["云端识别"],
        decision_boundary="自动执行响应",
        privacy=["加密传输"],
        ecosystem=["eufy app"],
        hypotheses=[
            _hypothesis("H-101", "断网后产品仍能在本地继续侦测与告警", "离线连续性"),
        ],
    )


def _workflow(repository: object) -> ValidationWorkflow:
    return ValidationWorkflow(repository=repository, llm=FakeValidationLLM())  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Creation, readiness gate, idempotency, planning                              #
# --------------------------------------------------------------------------- #


def test_non_ready_product_cannot_create_project() -> None:
    repository = InMemoryRunRepository()
    spec = _base_spec(
        product_id="product-draft",
        hardware=["摄像头"],
        ai_capabilities=["识别"],
        decision_boundary="用户确认",
        privacy=["本地处理"],
        ecosystem=["HomeBase"],
        hypotheses=[_hypothesis("H-1", "断网后仍工作", "离线连续性")],
        status=DefinitionStatus.DRAFT,
    )
    repository.save_product(spec)
    workflow = _workflow(repository)

    with pytest.raises(ValidationNotReadyError):
        workflow.create_project("product-draft", ValidationProjectCreateRequest())


def test_ready_product_creates_project_with_experiments_from_hypotheses() -> None:
    repository = InMemoryRunRepository()
    spec = _ready_spec()
    repository.save_product(spec)
    workflow = _workflow(repository)

    project = workflow.create_project("product-ready", ValidationProjectCreateRequest())

    assert project.status == ValidationProjectStatus.PLANNED
    assert project.product_version == spec.version
    assert len(project.experiments) == len(spec.validation_readiness)
    assert [experiment.hypothesis_id for experiment in project.experiments] == ["H-001", "H-002"]
    assert project.experiments[0].assumption == spec.validation_readiness[0].assumption
    # Four fixed scenarios are always available for the 2D view.
    assert {sim.template for sim in project.scenario_simulations} == set(ScenarioTemplate)
    assert "预验证" in project.disclaimer


def test_create_project_is_idempotent_per_product_version() -> None:
    repository = InMemoryRunRepository()
    repository.save_product(_ready_spec())
    workflow = _workflow(repository)

    first = workflow.create_project("product-ready", ValidationProjectCreateRequest())
    second = workflow.create_project(
        "product-ready", ValidationProjectCreateRequest(idempotency_key="abc12345")
    )

    assert first.id == second.id
    assert len(repository.validation_projects) == 1


# --------------------------------------------------------------------------- #
# Deterministic scenario engine                                                #
# --------------------------------------------------------------------------- #


def test_business_role_does_not_flag_negated_lock_in() -> None:
    # "不锁定核心安全能力" must NOT be read as forced subscription (negation bug).
    spec = _ready_spec().model_copy(
        update={
            "business_model": BusinessModel(
                hardware_revenue="一次性硬件销售",
                recurring_revenue="仅提供可选增值服务，不锁定核心安全能力",
                ecosystem_pull_through=[],
                cost_drivers=[],
            )
        }
    )
    caps = detect_capabilities(spec)
    report = analyze_business(spec, _hypothesis("H", "多信号可区分宠物与人形", "区分逻辑"), caps)
    assert report.findings == []


def test_scenario_simulation_is_deterministic() -> None:
    spec = _ready_spec()
    first = [sim.model_dump() for sim in simulate_all_scenarios(spec)]
    second = [sim.model_dump() for sim in simulate_all_scenarios(spec)]
    assert first == second


def test_scenario_reflects_product_capabilities_not_hardcoded_success() -> None:
    ready = {sim.template: sim for sim in simulate_all_scenarios(_ready_spec())}
    cloud = {sim.template: sim for sim in simulate_all_scenarios(_cloud_only_spec())}

    # Local-first product survives the outage in simulation.
    assert (
        ready[ScenarioTemplate.HOME_NETWORK_OUTAGE].verdict
        == ExperimentVerdict.SUPPORTED_IN_SIMULATION
    )
    # Cloud-only product is contradicted by the same scenario — no hard-coded win.
    assert (
        cloud[ScenarioTemplate.HOME_NETWORK_OUTAGE].verdict == ExperimentVerdict.CONTRADICTED
    )


# --------------------------------------------------------------------------- #
# Running: verdict honesty, role isolation, event order                        #
# --------------------------------------------------------------------------- #


async def test_run_produces_honest_verdicts_never_faking_real_validation() -> None:
    repository = InMemoryRunRepository()
    repository.save_product(_ready_spec())
    workflow = _workflow(repository)
    project = workflow.create_project("product-ready", ValidationProjectCreateRequest())

    await workflow.execute(project.id)
    ran = workflow.get_project(project.id)

    assert ran.status == ValidationProjectStatus.COMPLETED
    verdicts = {experiment.hypothesis_id: experiment.verdict for experiment in ran.experiments}
    # A structurally simulatable claim can only be "supported in simulation".
    assert verdicts["H-001"] == ExperimentVerdict.SUPPORTED_IN_SIMULATION
    # An inherently empirical claim (willingness to pay) needs a real-world test.
    assert verdicts["H-002"] == ExperimentVerdict.REQUIRES_REAL_WORLD_TEST
    # Every verdict is one of the allowed enum values (never a "validated" state).
    assert all(experiment.verdict in set(ExperimentVerdict) for experiment in ran.experiments)
    assert ran.overall_verdict == ExperimentVerdict.REQUIRES_REAL_WORLD_TEST
    assert "模拟" in ran.summary


async def test_experiments_persist_explainable_verdict_and_replay_trace() -> None:
    repository = InMemoryRunRepository()
    repository.save_product(_ready_spec())
    workflow = _workflow(repository)
    project = workflow.create_project("product-ready", ValidationProjectCreateRequest())

    await workflow.execute(project.id)
    ran = workflow.get_project(project.id)
    offline = next(e for e in ran.experiments if e.hypothesis_id == "H-001")
    payment = next(e for e in ran.experiments if e.hypothesis_id == "H-002")

    assert offline.verdict_reason
    assert offline.supporting_points
    assert offline.next_recommended_test
    assert [step.sequence for step in offline.analysis_trace] == list(
        range(1, len(offline.analysis_trace) + 1)
    )
    actors = [step.actor for step in offline.analysis_trace]
    assert actors[:3] == [
        ValidationAnalysisActor.HYPOTHESIS_PARSER,
        ValidationAnalysisActor.EVIDENCE_RETRIEVAL,
        ValidationAnalysisActor.DETERMINISTIC_SIMULATION,
    ]
    assert ValidationAnalysisActor.TECHNOLOGY in actors
    assert ValidationAnalysisActor.ADVERSARIAL in actors
    assert actors[-1] == ValidationAnalysisActor.ADJUDICATOR
    assert all(step.reasoning and step.outcome for step in offline.analysis_trace)

    # The business hypothesis is explicitly bounded: the simulator explains
    # why it cannot prove willingness to pay and recommends a real behaviour test.
    assert payment.verdict == ExperimentVerdict.REQUIRES_REAL_WORLD_TEST
    assert "真实测试" in payment.verdict_reason
    assert "价格敏感度" in payment.next_recommended_test
    assert "预订" in payment.next_recommended_test


async def test_historical_completed_project_is_backfilled_without_llm_call() -> None:
    repository = InMemoryRunRepository()
    repository.save_product(_ready_spec())
    llm = FakeValidationLLM()
    workflow = ValidationWorkflow(repository=repository, llm=llm)
    project = workflow.create_project("product-ready", ValidationProjectCreateRequest())
    await workflow.execute(project.id)
    calls_after_original_run = llm.calls

    completed = repository.get_validation_project(project.id)
    assert completed is not None
    historical = completed.model_copy(
        update={
            "experiments": [
                experiment.model_copy(
                    update={
                        "verdict_reason": "",
                        "supporting_points": [],
                        "counter_points": [],
                        "uncertainties": [],
                        "next_recommended_test": "",
                        "analysis_trace": [],
                    }
                )
                for experiment in completed.experiments
            ]
        }
    )
    repository.save_validation_project(historical)

    recovered = workflow.get_project(project.id)

    assert all(experiment.verdict_reason for experiment in recovered.experiments)
    assert all(experiment.analysis_trace for experiment in recovered.experiments)
    assert llm.calls == calls_after_original_run


async def test_pure_simulation_positive_is_capped_at_supported_in_simulation() -> None:
    repository = InMemoryRunRepository()
    repository.save_product(_ready_spec())
    workflow = _workflow(repository)
    project = workflow.create_project("product-ready", ValidationProjectCreateRequest())

    await workflow.execute(project.id)
    ran = workflow.get_project(project.id)

    # No experiment is ever marked as a real "pass" — the strongest positive is
    # supported_in_simulation, and it must carry AI + deterministic sources.
    offline = next(e for e in ran.experiments if e.hypothesis_id == "H-001")
    sources = {obs.source_type for obs in offline.observations}
    assert ObservationSourceType.DETERMINISTIC_SIMULATION in sources
    assert ObservationSourceType.EXISTING_EVIDENCE in sources
    assert ObservationSourceType.AI_ANALYSIS in sources  # LLM enrichment succeeded
    assert ObservationSourceType.HUMAN_OBSERVATION not in sources  # never fabricated
    assert ObservationSourceType.EXTERNAL_TEST not in sources


async def test_single_role_failure_does_not_fail_the_project() -> None:
    repository = InMemoryRunRepository()
    repository.save_product(_ready_spec())
    # The LLM enrichment role always fails; the run must still complete.
    workflow = ValidationWorkflow(repository=repository, llm=FakeValidationLLM(fail=True))
    project = workflow.create_project("product-ready", ValidationProjectCreateRequest())

    await workflow.execute(project.id)
    ran = workflow.get_project(project.id)

    assert ran.status == ValidationProjectStatus.COMPLETED
    assert all(e.status == ExperimentStatus.COMPLETED for e in ran.experiments)
    events = repository.list_validation_events(project.id)
    assert any(event.event_type == "role_degraded" for event in events)
    # Deterministic verdicts are unaffected by the LLM failure.
    verdicts = {e.hypothesis_id: e.verdict for e in ran.experiments}
    assert verdicts["H-001"] == ExperimentVerdict.SUPPORTED_IN_SIMULATION


async def test_event_sequence_is_stable_and_ordered() -> None:
    repository = InMemoryRunRepository()
    repository.save_product(_ready_spec())
    workflow = _workflow(repository)
    project = workflow.create_project("product-ready", ValidationProjectCreateRequest())

    await workflow.execute(project.id)
    events = repository.list_validation_events(project.id)

    sequences = [event.sequence for event in events]
    assert sequences == list(range(1, len(events) + 1))
    types = [event.event_type for event in events]
    assert "run_started" in types
    assert types.index("run_started") < types.index("run_completed")
    assert "role_analyzed" in types


async def test_run_is_not_scheduled_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    repository = InMemoryRunRepository()
    repository.save_product(_ready_spec())
    workflow = _workflow(repository)
    project = workflow.create_project("product-ready", ValidationProjectCreateRequest())

    _, scheduled_first = workflow.request_run(project.id)
    _, scheduled_second = workflow.request_run(project.id)

    assert scheduled_first is True
    assert scheduled_second is False


# --------------------------------------------------------------------------- #
# Feedback to product definition (send-back)                                   #
# --------------------------------------------------------------------------- #


async def test_send_back_does_not_modify_product_spec() -> None:
    repository = InMemoryRunRepository()
    spec = _cloud_only_spec()
    repository.save_product(spec)
    workflow = _workflow(repository)
    project = workflow.create_project("product-cloud", ValidationProjectCreateRequest())
    await workflow.execute(project.id)
    ran = workflow.get_project(project.id)

    findings = [f for experiment in ran.experiments for f in experiment.findings]
    assert findings, "cloud-only product should surface at least one finding"
    finding = findings[0]

    response = workflow.send_back_finding(finding.id)

    # The ProductSpec itself is untouched.
    product_after = repository.get_product("product-cloud")
    assert product_after is not None
    assert product_after.definition_status == DefinitionStatus.VALIDATION_READY
    assert product_after.validation_readiness == spec.validation_readiness
    assert product_after.model_dump() == spec.model_dump()

    # A reviewable suggested change was queued in the Copilot instead.
    records = repository.list_question_records("product-cloud")
    assert len(records) == 1
    suggestion = records[0].answer.suggested_changes[0]
    assert suggestion.id == response.suggestion_id
    assert suggestion.proposed_change == finding.recommended_change

    # The finding is now marked sent, not applied.
    reloaded = workflow.get_project(project.id)
    reloaded_finding = reloaded.find_finding(finding.id)
    assert reloaded_finding is not None
    assert reloaded_finding.feedback_status == FindingFeedbackStatus.SENT_TO_DEFINITION


async def test_send_back_is_idempotent() -> None:
    repository = InMemoryRunRepository()
    repository.save_product(_cloud_only_spec())
    workflow = _workflow(repository)
    project = workflow.create_project("product-cloud", ValidationProjectCreateRequest())
    await workflow.execute(project.id)
    ran = workflow.get_project(project.id)
    finding = next(f for experiment in ran.experiments for f in experiment.findings)

    first = workflow.send_back_finding(finding.id)
    second = workflow.send_back_finding(finding.id)

    assert first.question_id == second.question_id
    assert len(repository.list_question_records("product-cloud")) == 1


# --------------------------------------------------------------------------- #
# Isolation and persistence                                                    #
# --------------------------------------------------------------------------- #


async def test_projects_and_events_are_isolated_by_product() -> None:
    repository = InMemoryRunRepository()
    repository.save_product(_ready_spec())
    repository.save_product(_cloud_only_spec())
    workflow = _workflow(repository)

    ready_project = workflow.create_project("product-ready", ValidationProjectCreateRequest())
    cloud_project = workflow.create_project("product-cloud", ValidationProjectCreateRequest())
    await workflow.execute(ready_project.id)
    await workflow.execute(cloud_project.id)

    assert workflow.get_latest_project("product-ready").id == ready_project.id
    assert workflow.get_latest_project("product-cloud").id == cloud_project.id
    ready_events = repository.list_validation_events(ready_project.id)
    cloud_events = repository.list_validation_events(cloud_project.id)
    assert all(event.project_id == ready_project.id for event in ready_events)
    assert all(event.project_id == cloud_project.id for event in cloud_events)


async def test_project_survives_a_backend_restart(tmp_path: object) -> None:
    database_url = f"sqlite:///{tmp_path}/validation.db"  # type: ignore[str-bytes-safe]
    repository = SqlAlchemyRunRepository(database_url)
    repository.save_product(_ready_spec())
    workflow = ValidationWorkflow(repository=repository, llm=FakeValidationLLM())
    project = workflow.create_project("product-ready", ValidationProjectCreateRequest())
    await workflow.execute(project.id)

    # Simulate a restart: a brand new repository over the same database file.
    restarted = SqlAlchemyRunRepository(database_url)
    recovered = restarted.get_validation_project(project.id)

    assert recovered is not None
    assert recovered.status == ValidationProjectStatus.COMPLETED
    assert len(recovered.experiments) == 2
    assert recovered.experiments[0].verdict_reason
    assert recovered.experiments[0].analysis_trace
    assert recovered.experiments[0].analysis_trace[-1].actor == ValidationAnalysisActor.ADJUDICATOR
    assert restarted.get_latest_validation_project("product-ready") is not None
    events = restarted.list_validation_events(project.id)
    assert events and [event.sequence for event in events] == list(
        range(1, len(events) + 1)
    )
