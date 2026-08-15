"""Pre-validation lab workflow (预验证 / 模拟验证).

Orchestrates: snapshot a validation-ready ProductSpec → build one experiment per
validation hypothesis → run deterministic pre-validation roles and a scenario
simulation for each → adjudicate an honest verdict → feed a finding back to the
Product Definition Copilot as a reviewable suggestion.

Design rules encoded here:

* The verdict and every structural finding are deterministic; the LLM only adds
  supplemental narrative and can never change an outcome.
* A single role/LLM failure degrades that step only — the project still completes.
* Nothing claims a real hardware test, a real user study, or a real market
  result. Positive pure-simulation results are ``supported_in_simulation`` at
  most; inherently empirical claims become ``requires_real_world_test``.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from eufy_security_agents.agents.validation import ValidationAnalysisAgent
from eufy_security_agents.domain.digital_twin import build_product_digital_twin
from eufy_security_agents.domain.models import (
    AnswerMode,
    DefinitionStatus,
    ProductQuestion,
    ProductQuestionAnswer,
    ProductQuestionRecord,
    ProductSpec,
    ProductSuggestedChange,
    QuestionCategory,
    ValidationHypothesis,
)
from eufy_security_agents.domain.ports import FullRepository, StructuredLLM
from eufy_security_agents.domain.product_workbench import SPEC_SECTIONS
from eufy_security_agents.domain.scenario_simulation import (
    detect_capabilities,
    simulate_all_scenarios,
)
from eufy_security_agents.domain.validation import (
    ExperimentStatus,
    ExperimentVerdict,
    FindingFeedbackStatus,
    ObservationSourceType,
    ScenarioSimulation,
    ScenarioTemplate,
    SendBackResponse,
    ValidationAnalysisActor,
    ValidationAnalysisStep,
    ValidationEvent,
    ValidationExperiment,
    ValidationFinding,
    ValidationObservation,
    ValidationProject,
    ValidationProjectCreateRequest,
    ValidationProjectStatus,
    ValidationRole,
    experiment_from_hypothesis,
)
from eufy_security_agents.domain.validation_roles import (
    FindingDraft,
    RoleReport,
    Stance,
    adjudicate,
    analyze_adversarial,
    analyze_business,
    analyze_privacy_security,
    analyze_technology,
    analyze_user_scenario,
    overall_verdict,
    plan_experiment_type,
    plan_scenario_template,
)

_ROLE_LABELS = {
    ValidationRole.TECHNOLOGY: "技术验证",
    ValidationRole.PRIVACY_SECURITY: "隐私安全",
    ValidationRole.USER_SCENARIO: "用户场景",
    ValidationRole.BUSINESS: "商业验证",
    ValidationRole.ADVERSARIAL: "反方审查",
    ValidationRole.ADJUDICATOR: "最终裁决器",
}

_VERDICT_LABELS = {
    ExperimentVerdict.NOT_RUN: "未运行",
    ExperimentVerdict.SUPPORTED_IN_SIMULATION: "模拟支持",
    ExperimentVerdict.INCONCLUSIVE: "证据不足",
    ExperimentVerdict.CONTRADICTED: "出现反例",
    ExperimentVerdict.REQUIRES_REAL_WORLD_TEST: "需真实测试",
}

_STANCE_LABELS = {
    Stance.SUPPORTIVE: "支持",
    Stance.CONCERN: "存在顾虑",
    Stance.BLOCKING: "发现阻断项",
    Stance.NEEDS_REAL_WORLD: "需要真实测试",
    Stance.NEUTRAL: "信息不足",
}

_ACTOR_FOR_ROLE = {
    ValidationRole.TECHNOLOGY: ValidationAnalysisActor.TECHNOLOGY,
    ValidationRole.PRIVACY_SECURITY: ValidationAnalysisActor.PRIVACY_SECURITY,
    ValidationRole.USER_SCENARIO: ValidationAnalysisActor.USER_SCENARIO,
    ValidationRole.BUSINESS: ValidationAnalysisActor.BUSINESS,
    ValidationRole.ADVERSARIAL: ValidationAnalysisActor.ADVERSARIAL,
    ValidationRole.ADJUDICATOR: ValidationAnalysisActor.ADJUDICATOR,
}

_CATEGORY_FOR_FINDING = {
    "technology": QuestionCategory.TECHNOLOGY,
    "privacy": QuestionCategory.PRIVACY,
    "business": QuestionCategory.BUSINESS,
    "user_scenario": QuestionCategory.USER_EXPERIENCE,
}


class ValidationNotReadyError(RuntimeError):
    """Raised when a project cannot be created because the product is not ready."""

    def __init__(self, product_id: str, status: DefinitionStatus) -> None:
        super().__init__("product definition is not validation_ready")
        self.product_id = product_id
        self.status = status


class ValidationWorkflow:
    def __init__(
        self,
        *,
        repository: FullRepository,
        llm: StructuredLLM,
        run_timeout_seconds: float = 240,
        experiment_timeout_seconds: float = 40,
    ) -> None:
        self._repository = repository
        self._llm = llm
        self._run_timeout_seconds = run_timeout_seconds
        self._experiment_timeout_seconds = experiment_timeout_seconds

    # ------------------------------------------------------------------ #
    # Project lifecycle                                                   #
    # ------------------------------------------------------------------ #

    def create_project(
        self, product_id: str, request: ValidationProjectCreateRequest
    ) -> ValidationProject:
        product = self._repository.get_product(product_id)
        if product is None:
            raise KeyError(product_id)
        if product.definition_status != DefinitionStatus.VALIDATION_READY:
            raise ValidationNotReadyError(product_id, product.definition_status)

        # Idempotency: one project per (product_id, product_version). A repeated
        # create for the same snapshot returns the existing project instead of a
        # duplicate, so a double-click never spawns two projects.
        existing = self._repository.find_validation_project_by_version(product_id, product.version)
        if existing is not None:
            return existing

        project_id = f"vproj-{uuid4().hex[:12]}"
        experiments = self._plan_experiments(project_id, product)
        scenarios = simulate_all_scenarios(product)
        project = ValidationProject(
            id=project_id,
            product_id=product.id,
            product_version=product.version,
            product_snapshot=product,
            status=ValidationProjectStatus.PLANNED,
            experiments=experiments,
            scenario_simulations=scenarios,
            digital_twin=build_product_digital_twin(product),
            summary=(
                f"已根据 {len(experiments)} 条验证假设生成预验证实验计划，"
                "尚未运行。所有结果均为预验证 / 模拟。"
            ),
        )
        self._repository.save_validation_project(
            project, idempotency_key=request.idempotency_key
        )
        self._emit(
            project_id,
            "project_created",
            None,
            f"已为产品 {product.name} V{product.version} 创建预验证项目",
            {"experiment_count": len(experiments), "product_version": product.version},
        )
        return project

    @staticmethod
    def _plan_experiments(project_id: str, product: ProductSpec) -> list[ValidationExperiment]:
        experiments: list[ValidationExperiment] = []
        for hypothesis in product.validation_readiness:
            experiment_type = plan_experiment_type(hypothesis)
            template = plan_scenario_template(hypothesis)
            experiments.append(
                experiment_from_hypothesis(project_id, hypothesis, experiment_type, template)
            )
        return experiments

    def get_project(self, project_id: str) -> ValidationProject:
        project = self._repository.get_validation_project(project_id)
        if project is None:
            raise KeyError(project_id)
        return self._hydrate_project_explanations(project)

    def get_latest_project(self, product_id: str) -> ValidationProject:
        if self._repository.get_product(product_id) is None:
            raise KeyError(product_id)
        project = self._repository.get_latest_validation_project(product_id)
        if project is None:
            raise LookupError(product_id)
        return self._hydrate_project_explanations(project)

    def list_events(self, project_id: str, after_sequence: int = 0) -> list[ValidationEvent]:
        self.get_project(project_id)
        return self._repository.list_validation_events(project_id, after_sequence)

    def request_run(self, project_id: str) -> tuple[ValidationProject, bool]:
        """Flip a planned/failed project to running; returns (project, scheduled).

        ``scheduled`` is True only when this call caused the transition — so a
        double-click can never schedule two background runs.
        """

        project = self.get_project(project_id)
        if project.status in {ValidationProjectStatus.RUNNING, ValidationProjectStatus.COMPLETED}:
            return project, False
        running = project.model_copy(
            update={"status": ValidationProjectStatus.RUNNING, "error": None}
        )
        self._repository.save_validation_project(running)
        self._emit(project_id, "run_scheduled", None, "预验证已排队，开始多角色模拟…")
        return running, True

    async def execute(self, project_id: str) -> None:
        try:
            await asyncio.wait_for(
                self._run_all(project_id), timeout=self._run_timeout_seconds
            )
        except TimeoutError:
            project = self._repository.get_validation_project(project_id)
            if project is not None:
                self._repository.save_validation_project(
                    project.model_copy(
                        update={
                            "status": ValidationProjectStatus.FAILED,
                            "error": "预验证运行超时，请重试。",
                        }
                    )
                )
            self._emit(project_id, "run_failed", None, "预验证运行超时")
        except Exception as exc:  # pragma: no cover - defensive terminal guard
            project = self._repository.get_validation_project(project_id)
            if project is not None:
                self._repository.save_validation_project(
                    project.model_copy(
                        update={
                            "status": ValidationProjectStatus.FAILED,
                            "error": str(exc)[:200],
                        }
                    )
                )
            self._emit(project_id, "run_failed", None, "预验证运行失败", {"detail": str(exc)[:200]})

    async def _run_all(self, project_id: str) -> None:
        project = self.get_project(project_id)
        spec = project.product_snapshot
        caps = detect_capabilities(spec)
        scenarios = {scenario.template: scenario for scenario in simulate_all_scenarios(spec)}

        # Fresh run: reset experiment state and refresh the scenario simulations.
        experiments = [
            experiment.model_copy(
                update={
                    "status": ExperimentStatus.NOT_RUN,
                    "verdict": ExperimentVerdict.NOT_RUN,
                    "observations": [],
                    "findings": [],
                    "summary": "",
                    "verdict_reason": "",
                    "supporting_points": [],
                    "counter_points": [],
                    "uncertainties": [],
                    "next_recommended_test": "",
                    "analysis_trace": [],
                }
            )
            for experiment in project.experiments
        ]
        project = project.model_copy(
            update={
                "status": ValidationProjectStatus.RUNNING,
                "experiments": experiments,
                "scenario_simulations": list(scenarios.values()),
                "error": None,
            }
        )
        self._repository.save_validation_project(project)
        self._emit(
            project_id,
            "run_started",
            None,
            f"开始预验证：{len(experiments)} 个实验、4 个确定性场景推演",
            {"experiment_count": len(experiments)},
        )

        for index, experiment in enumerate(experiments):
            try:
                completed = await self._run_experiment(
                    project_id, spec, caps, experiment, scenarios
                )
            except Exception as exc:  # a single experiment failing never fails the run
                completed = experiment.model_copy(
                    update={
                        "status": ExperimentStatus.FAILED,
                        "verdict": ExperimentVerdict.INCONCLUSIVE,
                        "summary": f"实验执行失败：{str(exc)[:120]}",
                        "verdict_reason": "实验链路未完整执行，因此不能形成可靠裁决。",
                        "uncertainties": [f"执行异常：{str(exc)[:120]}"],
                        "next_recommended_test": "排除执行异常后重新运行该预验证实验。",
                    }
                )
                self._emit(
                    project_id,
                    "experiment_failed",
                    None,
                    f"实验失败：{experiment.title}",
                    {"experiment_id": experiment.id, "detail": str(exc)[:120]},
                )
            experiments[index] = completed
            project = project.model_copy(update={"experiments": list(experiments)})
            self._repository.save_validation_project(project)

        verdicts = [
            experiment.verdict
            for experiment in experiments
            if experiment.status == ExperimentStatus.COMPLETED
        ]
        rollup = overall_verdict(verdicts)
        summary = self._summarize(experiments, rollup)
        project = project.model_copy(
            update={
                "status": ValidationProjectStatus.COMPLETED,
                "overall_verdict": rollup,
                "summary": summary,
            }
        )
        self._repository.save_validation_project(project)
        self._emit(
            project_id,
            "run_completed",
            None,
            f"预验证完成（模拟）：整体裁决 {_VERDICT_LABELS[rollup]}",
            {"overall_verdict": rollup.value, "summary": summary},
        )

    async def _run_experiment(
        self,
        project_id: str,
        spec: ProductSpec,
        caps: Any,
        experiment: ValidationExperiment,
        scenarios: dict[ScenarioTemplate, ScenarioSimulation],
    ) -> ValidationExperiment:
        template = experiment.scenario_template or ScenarioTemplate.URBAN_APARTMENT_INTRUSION
        scenario = scenarios[template]
        hypothesis = self._hypothesis_of(experiment)

        self._emit(
            project_id,
            "experiment_started",
            None,
            f"开始实验：{experiment.title}",
            {
                "experiment_id": experiment.id,
                "experiment_type": experiment.experiment_type.value,
                "scenario_template": template.value,
            },
        )

        reports: list[RoleReport] = []
        tech = analyze_technology(spec, hypothesis, caps)
        privacy = analyze_privacy_security(spec, hypothesis, caps)
        user = analyze_user_scenario(spec, hypothesis, scenario)
        business = analyze_business(spec, hypothesis, caps)
        for report in (tech, privacy, user, business):
            reports.append(report)
            self._emit_role(project_id, experiment.id, report)
        adversarial = analyze_adversarial(spec, hypothesis, reports, scenario)
        reports.append(adversarial)
        self._emit_role(project_id, experiment.id, adversarial)

        report_observations = [self._observation_from_report(report) for report in reports]
        scenario_observation = self._scenario_observation(scenario)
        observations = [*report_observations, scenario_observation]
        findings = self._findings_from_reports(experiment.id, reports)

        # Optional, isolated LLM enrichment — additive narrative only.
        ai_observation = await self._maybe_llm_observation(
            project_id, experiment, scenario, reports
        )
        if ai_observation is not None:
            observations.append(ai_observation)

        verdict, rationale, summary = adjudicate(hypothesis, reports, scenario)
        supporting_points, counter_points, uncertainties = self._explanation_points(
            reports, scenario
        )
        next_test = self._next_recommended_test(hypothesis, verdict, findings)
        analysis_trace = self._build_analysis_trace(
            experiment=experiment,
            spec=spec,
            scenario=scenario,
            reports=reports,
            report_observations=report_observations,
            scenario_observation=scenario_observation,
            ai_observation=ai_observation,
            verdict=verdict,
            rationale=rationale,
        )
        self._emit(
            project_id,
            "experiment_completed",
            _ROLE_LABELS[ValidationRole.ADJUDICATOR],
            f"实验裁决：{experiment.title} → {_VERDICT_LABELS[verdict]}",
            {
                "experiment_id": experiment.id,
                "verdict": verdict.value,
                "rationale": rationale,
                "finding_count": len(findings),
            },
        )
        return experiment.model_copy(
            update={
                "status": ExperimentStatus.COMPLETED,
                "verdict": verdict,
                "observations": observations,
                "findings": findings,
                "summary": summary,
                "verdict_reason": rationale,
                "supporting_points": supporting_points,
                "counter_points": counter_points,
                "uncertainties": uncertainties,
                "next_recommended_test": next_test,
                "analysis_trace": analysis_trace,
            }
        )

    async def _maybe_llm_observation(
        self,
        project_id: str,
        experiment: ValidationExperiment,
        scenario: ScenarioSimulation,
        reports: list[RoleReport],
    ) -> ValidationObservation | None:
        agent = ValidationAnalysisAgent(self._llm)
        deterministic_summary = "；".join(report.headline for report in reports)[:600]
        try:
            output = await asyncio.wait_for(
                agent.analyze(
                    experiment=experiment,
                    deterministic_summary=deterministic_summary,
                    scenario_summary=f"{scenario.title}：{scenario.verdict_rationale}",
                ),
                timeout=self._experiment_timeout_seconds,
            )
        except Exception as exc:
            # Enrichment is optional — log and continue on any failure.
            self._emit(
                project_id,
                "role_degraded",
                "AI 分析",
                f"AI 补充分析不可用（{type(exc).__name__}），已仅使用确定性结果",
                {"experiment_id": experiment.id},
            )
            return None
        draft = output.value.analysis
        content = draft.headline.strip() or draft.rationale.strip()
        if not content:
            return None
        detail = f"{draft.headline}\n{draft.rationale}".strip()
        if draft.open_questions:
            detail += "\n仍需真实测试：" + "；".join(draft.open_questions[:3])
        self._emit(
            project_id,
            "role_analyzed",
            "AI 分析",
            f"AI 补充分析已加入：{experiment.title}",
            {"experiment_id": experiment.id, "source_type": "ai_analysis"},
        )
        return ValidationObservation(
            id=f"vo-{uuid4().hex[:10]}",
            source_type=ObservationSourceType.AI_ANALYSIS,
            source_label="AI 补充分析 (deepseek-chat)",
            content=detail,
            supports_hypothesis=None,
        )

    # ------------------------------------------------------------------ #
    # Send a finding back to the Product Definition Copilot               #
    # ------------------------------------------------------------------ #

    def send_back_finding(self, finding_id: str) -> SendBackResponse:
        project_id = self._repository.get_project_id_for_finding(finding_id)
        if project_id is None:
            raise KeyError(finding_id)
        project = self._repository.get_validation_project(project_id)
        if project is None:  # pragma: no cover - index/payload drift guard
            raise KeyError(finding_id)
        finding = project.find_finding(finding_id)
        if finding is None:  # pragma: no cover - index/payload drift guard
            raise KeyError(finding_id)
        product = self._repository.get_product(project.product_id)
        if product is None:
            raise KeyError(project.product_id)

        idempotency_key = f"validation-finding:{finding_id}"
        existing = self._repository.find_question_record_by_key(product.id, idempotency_key)
        if existing is not None:
            suggestion_id = (
                existing.answer.suggested_changes[0].id
                if existing.answer.suggested_changes
                else ""
            )
            return SendBackResponse(
                finding=self._mark_sent(project, finding_id),
                product_id=product.id,
                question_id=existing.answer.question_id,
                suggestion_id=suggestion_id,
                message="该发现已发送回产品定义 Copilot，等待用户审查。",
            )

        section = (
            finding.target_section
            if finding.target_section in set(SPEC_SECTIONS)
            else "risks"
        )
        category = _CATEGORY_FOR_FINDING.get(finding.category, QuestionCategory.GENERAL)
        question_id = f"pq-val-{uuid4().hex[:10]}"
        suggestion_id = f"sc-{uuid4().hex[:10]}"
        question = ProductQuestion(
            id=question_id,
            product_id=product.id,
            product_version=product.version,
            question=f"[预验证发现] {finding.title}",
            category=category,
        )
        suggestion = ProductSuggestedChange(
            id=suggestion_id,
            section=section,
            current_summary="来自预验证 / 模拟实验的改进建议（尚未修改产品定义）。",
            proposed_change=finding.recommended_change,
            rationale=finding.detail,
            source_question_id=question_id,
        )
        answer = ProductQuestionAnswer(
            id=f"pa-val-{uuid4().hex[:10]}",
            question_id=question_id,
            product_id=product.id,
            product_version=product.version,
            category=category,
            answer_mode=AnswerMode.CHANGE_REQUEST,
            direct_answer=(
                f"预验证实验产生了一条改进建议：{finding.title}。"
                "这是模拟结论，非真实验证；请在下方审查后自行决定是否修改产品定义。"
            ),
            assumptions=[],
            unknowns=[],
            affected_sections=[section],
            suggested_changes=[suggestion],
            integrity_notes=["该建议来源于预验证 / 模拟实验，未经过真实硬件或真实用户测试。"],
        )
        record = ProductQuestionRecord(question=question, answer=answer)
        self._repository.save_question_record(record, idempotency_key=idempotency_key)
        if product.definition_status == DefinitionStatus.DRAFT:
            self._repository.save_product(
                product.model_copy(update={"definition_status": DefinitionStatus.UNDER_REVIEW})
            )

        updated_finding = self._mark_sent(project, finding_id)
        self._emit(
            project_id,
            "finding_sent_back",
            None,
            f"已将发现发送回产品定义：{finding.title}",
            {
                "finding_id": finding_id,
                "product_id": product.id,
                "question_id": question_id,
                "suggestion_id": suggestion_id,
            },
        )
        return SendBackResponse(
            finding=updated_finding,
            product_id=product.id,
            question_id=question_id,
            suggestion_id=suggestion_id,
            message="已发送回产品定义 Copilot，请在产品定义页审查并决定是否采纳。",
        )

    def _mark_sent(self, project: ValidationProject, finding_id: str) -> ValidationFinding:
        updated: ValidationFinding | None = None
        experiments = []
        for experiment in project.experiments:
            findings = []
            for finding in experiment.findings:
                if finding.id == finding_id:
                    finding = finding.model_copy(
                        update={"feedback_status": FindingFeedbackStatus.SENT_TO_DEFINITION}
                    )
                    updated = finding
                findings.append(finding)
            experiments.append(experiment.model_copy(update={"findings": findings}))
        self._repository.save_validation_project(
            project.model_copy(update={"experiments": experiments})
        )
        assert updated is not None
        return updated

    # ------------------------------------------------------------------ #
    # Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _hydrate_project_explanations(self, project: ValidationProject) -> ValidationProject:
        """Backfill explainability for projects saved before the trace contract.

        This is intentionally deterministic and only consumes the saved product
        snapshot, scenario results and observations. It never calls the LLM and
        never changes an experiment's stored verdict.
        """

        twin_changed = project.digital_twin is None
        if twin_changed:
            project = project.model_copy(
                update={"digital_twin": build_product_digital_twin(project.product_snapshot)}
            )

        if project.status != ValidationProjectStatus.COMPLETED or all(
            experiment.analysis_trace and experiment.verdict_reason
            for experiment in project.experiments
        ):
            if twin_changed:
                self._repository.save_validation_project(project)
            return project

        spec = project.product_snapshot
        caps = detect_capabilities(spec)
        scenarios = {scenario.template: scenario for scenario in project.scenario_simulations}
        changed = False
        hydrated: list[ValidationExperiment] = []
        for experiment in project.experiments:
            if experiment.status != ExperimentStatus.COMPLETED or (
                experiment.analysis_trace and experiment.verdict_reason
            ):
                hydrated.append(experiment)
                continue
            template = experiment.scenario_template or ScenarioTemplate.URBAN_APARTMENT_INTRUSION
            scenario = scenarios.get(template)
            if scenario is None:
                hydrated.append(experiment)
                continue
            hypothesis = self._hypothesis_of(experiment)
            reports = [
                analyze_technology(spec, hypothesis, caps),
                analyze_privacy_security(spec, hypothesis, caps),
                analyze_user_scenario(spec, hypothesis, scenario),
                analyze_business(spec, hypothesis, caps),
            ]
            reports.append(analyze_adversarial(spec, hypothesis, reports, scenario))

            available = list(experiment.observations)
            report_observations: list[ValidationObservation] = []
            for report in reports:
                label = _ROLE_LABELS[report.role]
                observation = next(
                    (item for item in available if item.source_label == label), None
                )
                if observation is None:
                    observation = self._observation_from_report(report)
                report_observations.append(observation)
            scenario_observation = next(
                (
                    item
                    for item in available
                    if item.source_label.startswith("场景推演")
                ),
                self._scenario_observation(scenario),
            )
            ai_observation = next(
                (
                    item
                    for item in available
                    if item.source_type == ObservationSourceType.AI_ANALYSIS
                ),
                None,
            )
            _recomputed_verdict, rationale, _summary = adjudicate(
                hypothesis, reports, scenario
            )
            supporting, counter, uncertainties = self._explanation_points(
                reports, scenario
            )
            trace = self._build_analysis_trace(
                experiment=experiment,
                spec=spec,
                scenario=scenario,
                reports=reports,
                report_observations=report_observations,
                scenario_observation=scenario_observation,
                ai_observation=ai_observation,
                verdict=experiment.verdict,
                rationale=rationale,
            )
            hydrated.append(
                experiment.model_copy(
                    update={
                        "verdict_reason": rationale,
                        "supporting_points": supporting,
                        "counter_points": counter,
                        "uncertainties": uncertainties,
                        "next_recommended_test": self._next_recommended_test(
                            hypothesis, experiment.verdict, experiment.findings
                        ),
                        "analysis_trace": trace,
                    }
                )
            )
            changed = True

        if not changed:
            if twin_changed:
                self._repository.save_validation_project(project)
            return project
        project = project.model_copy(update={"experiments": hydrated})
        self._repository.save_validation_project(project)
        return project

    @staticmethod
    def _explanation_points(
        reports: list[RoleReport], scenario: ScenarioSimulation
    ) -> tuple[list[str], list[str], list[str]]:
        supporting = [report.headline for report in reports if report.stance == Stance.SUPPORTIVE]
        counter = [
            report.headline
            for report in reports
            if report.stance in {Stance.CONCERN, Stance.BLOCKING}
        ]
        uncertainties = [
            report.headline
            for report in reports
            if report.stance in {Stance.NEEDS_REAL_WORLD, Stance.NEUTRAL}
        ]
        if scenario.verdict == ExperimentVerdict.SUPPORTED_IN_SIMULATION:
            supporting.append(f"场景推演「{scenario.title}」：{scenario.verdict_rationale}")
        elif scenario.verdict == ExperimentVerdict.CONTRADICTED:
            counter.append(f"场景推演「{scenario.title}」：{scenario.verdict_rationale}")
        else:
            uncertainties.append(f"场景推演「{scenario.title}」：{scenario.verdict_rationale}")
        return supporting, counter, uncertainties

    @staticmethod
    def _next_recommended_test(
        hypothesis: ValidationHypothesis,
        verdict: ExperimentVerdict,
        findings: list[ValidationFinding],
    ) -> str:
        text = f"{hypothesis.assumption} {hypothesis.metric}".casefold()
        if verdict == ExperimentVerdict.REQUIRES_REAL_WORLD_TEST:
            if any(token in text for token in ("付费", "愿意", "价格", "订阅", "price", "pay")):
                return (
                    "开展小样本价格敏感度访谈或联合分析，并用可撤回预订/购买选择验证真实付费行为；"
                    f"以「{hypothesis.pass_condition}」作为预先约定的判断条件。"
                )
            if any(token in text for token in ("准确", "误报", "漏报", "accuracy", "false alarm")):
                return (
                    "在代表性真实家庭环境开展受控现场测试，记录误报、漏报及失败样本；"
                    f"以「{hypothesis.pass_condition}」作为预先约定的判断条件。"
                )
            return (
                f"按「{hypothesis.proposed_method}」开展真实硬件、用户或市场测试，"
                f"并以「{hypothesis.pass_condition}」作为预先约定的判断条件。"
            )
        if verdict == ExperimentVerdict.CONTRADICTED:
            first_fix = findings[0].recommended_change if findings else "补齐当前反例暴露的能力缺口"
            return f"先{first_fix}，再复跑相同场景并补充真实环境边界测试。"
        if verdict == ExperimentVerdict.INCONCLUSIVE:
            return (
                f"先补齐当前不确定信息，再按「{hypothesis.proposed_method}」验证；"
                f"判断条件保持为「{hypothesis.pass_condition}」。"
            )
        if verdict == ExperimentVerdict.SUPPORTED_IN_SIMULATION:
            return (
                f"进入小规模真实环境验证，按「{hypothesis.proposed_method}」检查模拟结论能否复现；"
                "在获得真实观测前不要将其表述为已验证。"
            )
        return "运行预验证后再生成下一步测试建议。"

    @staticmethod
    def _build_analysis_trace(
        *,
        experiment: ValidationExperiment,
        spec: ProductSpec,
        scenario: ScenarioSimulation,
        reports: list[RoleReport],
        report_observations: list[ValidationObservation],
        scenario_observation: ValidationObservation,
        ai_observation: ValidationObservation | None,
        verdict: ExperimentVerdict,
        rationale: str,
    ) -> list[ValidationAnalysisStep]:
        steps: list[ValidationAnalysisStep] = []

        def add(
            actor: ValidationAnalysisActor,
            action: str,
            reasoning: str,
            evidence_ids: list[str],
            outcome: str,
            source_type: ObservationSourceType,
        ) -> None:
            sequence = len(steps) + 1
            steps.append(
                ValidationAnalysisStep(
                    id=f"vas-{experiment.id}-{sequence}",
                    sequence=sequence,
                    actor=actor,
                    action=action,
                    reasoning=reasoning,
                    evidence_ids=evidence_ids,
                    outcome=outcome,
                    source_type=source_type,
                )
            )

        add(
            ValidationAnalysisActor.HYPOTHESIS_PARSER,
            "解析验证问题",
            f"将假设拆为度量「{experiment.metric}」、通过条件「{experiment.pass_condition}」与终止条件「{experiment.kill_condition}」。",
            [],
            f"已规划为{experiment.experiment_type.value}实验",
            ObservationSourceType.EXISTING_EVIDENCE,
        )
        add(
            ValidationAnalysisActor.EVIDENCE_RETRIEVAL,
            "检索产品定义与已有证据",
            "只读取当前 ProductSpec 快照及其证据引用，未把模拟内容伪装成外部事实。",
            list(spec.evidence_ids),
            f"读取 {len(spec.evidence_ids)} 条证据引用",
            ObservationSourceType.EXISTING_EVIDENCE,
        )
        add(
            ValidationAnalysisActor.DETERMINISTIC_SIMULATION,
            f"运行 场景推演：{scenario.title}",
            scenario.verdict_rationale,
            [scenario_observation.id],
            _VERDICT_LABELS[scenario.verdict],
            ObservationSourceType.DETERMINISTIC_SIMULATION,
        )
        for report, observation in zip(reports, report_observations, strict=True):
            add(
                _ACTOR_FOR_ROLE[report.role],
                f"{_ROLE_LABELS[report.role]}审查",
                f"{report.headline}。{report.rationale}",
                [observation.id],
                _STANCE_LABELS[report.stance],
                report.source_type,
            )
        if ai_observation is not None:
            add(
                ValidationAnalysisActor.AI_ANALYSIS,
                "AI 补充分析",
                ai_observation.content,
                [ai_observation.id],
                "仅补充开放问题，不改变确定性裁决",
                ObservationSourceType.AI_ANALYSIS,
            )
        add(
            ValidationAnalysisActor.ADJUDICATOR,
            "汇总支持、反例与不确定性",
            rationale,
            [observation.id for observation in [*report_observations, scenario_observation]],
            _VERDICT_LABELS[verdict],
            ObservationSourceType.DETERMINISTIC_SIMULATION,
        )
        return steps

    @staticmethod
    def _hypothesis_of(experiment: ValidationExperiment) -> ValidationHypothesis:
        return ValidationHypothesis(
            id=experiment.hypothesis_id,
            assumption=experiment.assumption,
            metric=experiment.metric,
            proposed_method=experiment.proposed_method,
            pass_condition=experiment.pass_condition,
            kill_condition=experiment.kill_condition,
        )

    @staticmethod
    def _observation_from_report(report: RoleReport) -> ValidationObservation:
        return ValidationObservation(
            id=f"vo-{uuid4().hex[:10]}",
            source_type=report.source_type,
            source_label=_ROLE_LABELS[report.role],
            content=f"{report.headline}｜{report.rationale}",
            supports_hypothesis=report.supports_hypothesis,
        )

    @staticmethod
    def _scenario_observation(scenario: ScenarioSimulation) -> ValidationObservation:
        supports = None
        if scenario.verdict == ExperimentVerdict.SUPPORTED_IN_SIMULATION:
            supports = True
        elif scenario.verdict == ExperimentVerdict.CONTRADICTED:
            supports = False
        return ValidationObservation(
            id=f"vo-{uuid4().hex[:10]}",
            source_type=ObservationSourceType.DETERMINISTIC_SIMULATION,
            source_label=f"场景推演 · {scenario.title}",
            content=f"{_VERDICT_LABELS[scenario.verdict]}：{scenario.verdict_rationale}",
            supports_hypothesis=supports,
        )

    @staticmethod
    def _findings_from_reports(
        experiment_id: str, reports: list[RoleReport]
    ) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        for report in reports:
            for draft in report.findings:
                findings.append(_finding_from_draft(experiment_id, draft))
        return findings

    @staticmethod
    def _summarize(experiments: list[ValidationExperiment], rollup: ExperimentVerdict) -> str:
        counts: dict[ExperimentVerdict, int] = {}
        for experiment in experiments:
            if experiment.status != ExperimentStatus.COMPLETED:
                continue
            counts[experiment.verdict] = counts.get(experiment.verdict, 0) + 1
        parts = [
            f"{_VERDICT_LABELS[verdict]} {count}"
            for verdict, count in counts.items()
        ]
        distribution = "、".join(parts) if parts else "无已完成实验"
        return (
            f"预验证 / 模拟完成：整体裁决 {_VERDICT_LABELS[rollup]}（{distribution}）。"
            "所有结论均为模拟推演，不代表真实硬件或真实用户测试。"
        )

    def _emit_role(self, project_id: str, experiment_id: str, report: RoleReport) -> None:
        self._emit(
            project_id,
            "role_analyzed",
            _ROLE_LABELS[report.role],
            f"{_ROLE_LABELS[report.role]}：{report.headline}",
            {
                "experiment_id": experiment_id,
                "role": report.role.value,
                "stance": report.stance.value,
                "source_type": report.source_type.value,
                "finding_count": len(report.findings),
                "rationale": report.rationale,
            },
        )

    def _emit(
        self,
        project_id: str,
        event_type: str,
        validator_name: str | None,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        sequence = len(self._repository.list_validation_events(project_id)) + 1
        self._repository.add_validation_event(
            ValidationEvent(
                project_id=project_id,
                sequence=sequence,
                event_type=event_type,
                validator_name=validator_name,
                message=message,
                payload=payload or {},
            )
        )


def _finding_from_draft(experiment_id: str, draft: FindingDraft) -> ValidationFinding:
    section = draft.target_section if draft.target_section in set(SPEC_SECTIONS) else "risks"
    return ValidationFinding(
        id=f"vf-{uuid4().hex[:10]}",
        experiment_id=experiment_id,
        category=draft.category,
        title=draft.title,
        detail=draft.detail,
        severity=draft.severity,
        recommended_change=draft.recommended_change,
        source_type=draft.source_type,
        target_section=section,
    )
