"""Auditable multi-agent workflow for future product generation."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from contextlib import suppress
from time import monotonic
from typing import Any, TypeVar
from uuid import uuid4

from eufy_security_agents.agents import (
    CandidateNoveltyAuditorAgent,
    CandidateReviewerAgent,
    CompetitorAnalysisAgent,
    CurrentProductAuditorAgent,
    ForecastConsensusAgent,
    FuturesLensAgent,
    LensDeliberationAgent,
    OpportunitySynthesizerAgent,
    PortfolioDiversityAuditorAgent,
    ProductArchitectAgent,
    ProductDefinitionAgent,
    ProductSpecAnalystAgent,
    ProductSpecReviserAgent,
)
from eufy_security_agents.agents.base import AgentOutput
from eufy_security_agents.agents.forecasting import COMPETITIVE_OUTPUT_CAPS
from eufy_security_agents.core.serialization import compact_json
from eufy_security_agents.domain.models import (
    AgentEvent,
    AnswerMode,
    Artifact,
    BusinessModel,
    CandidateNoveltyAssessment,
    CandidatePairSimilarity,
    CandidateReview,
    CapabilityDelta,
    CompetitiveAnalysis,
    CompetitiveGap,
    CompetitivePositioning,
    CompetitorRecord,
    ConsensusClaim,
    CrossLensChallenge,
    CurrentCapability,
    CurrentCapabilityBaseline,
    DefinitionStatus,
    EpistemicStatus,
    EvidenceRecord,
    ForecastConsensus,
    ForecastRequest,
    ForecastResult,
    InnovationVector,
    KnowledgeLayer,
    LensDeliberation,
    LensForecast,
    NoveltyAudit,
    NoveltyClassification,
    Opportunity,
    PortfolioDiversityAudit,
    ProductAnswerClaim,
    ProductAnswerDraft,
    ProductCandidate,
    ProductDefinitionReadiness,
    ProductDesignIssue,
    ProductQuestion,
    ProductQuestionAnswer,
    ProductQuestionRecord,
    ProductQuestionRequest,
    ProductRevision,
    ProductRevisionChange,
    ProductRevisionRequest,
    ProductSelectionRequest,
    ProductSpec,
    ProductSuggestedChange,
    QuestionCategory,
    RankedCandidate,
    RegionalFit,
    RetrievalPlan,
    RiskItem,
    RunStatus,
    SelectionStatus,
    StageDegradation,
    StrategyAlignment,
    SuggestionDisposition,
    SuggestionResolution,
    TrendSignal,
    ValidationHypothesis,
)
from eufy_security_agents.domain.ports import RunRepository, StructuredLLM
from eufy_security_agents.domain.product_workbench import (
    CATEGORIES_WITH_BASELINE,
    CATEGORIES_WITH_COMPETITORS,
    CATEGORIES_WITH_CONSENSUS,
    CATEGORIES_WITH_NOVELTY,
    CATEGORY_LAYERS,
    CATEGORY_LENSES,
    CATEGORY_REVIEW_DIMENSIONS,
    SPEC_SECTIONS,
    classify_question,
    evaluate_readiness,
    question_tokens,
)
from eufy_security_agents.domain.strategy import (
    dominant_dimensions as strategy_dominant_dimensions,
)
from eufy_security_agents.domain.strategy import (
    preset_label as strategy_preset_label,
)
from eufy_security_agents.infrastructure.competitors import LocalCompetitorStore
from eufy_security_agents.infrastructure.evidence import LocalEvidenceStore
from eufy_security_agents.infrastructure.llm import LLMConfigurationError, LLMGenerationError

TStage = TypeVar("TStage")


class DefinitionNotReadyError(RuntimeError):
    """Raised when a product cannot be confirmed because readiness is incomplete."""

    def __init__(self, readiness: ProductDefinitionReadiness) -> None:
        super().__init__("product definition is not ready for validation")
        self.readiness = readiness


# How many context records to hand the analyst; small enough to avoid prompt bloat.
QUESTION_EVIDENCE_LIMIT = 8
QUESTION_COMPETITOR_LIMIT = 6

FORECAST_LENSES = ["user_trends", "technology_trends", "security_futures", "market_futures"]
REVIEW_DIMENSIONS = [
    "innovation",
    "user_value",
    "business_value",
    "cost_effectiveness",
    "feasibility",
    "eufy_synergy",
]

# LLM failure kinds that must abort the whole run rather than degrade. Only a
# credential/authentication failure is fatal at a per-stage boundary: it will
# break every downstream model call too, so failing fast is correct. Everything
# else (truncation, empty content, malformed JSON, schema drift, transient
# provider errors) is recoverable via retry / repair / normalize / degrade.
FATAL_LLM_FAILURE_KINDS = frozenset({"authentication"})

# A forecasting run needs at least this many independent lens forecasts to form a
# defensible consensus. Losing one or two lenses degrades transparently; losing
# more than that is a genuine failure of the core forecasting stage.
MIN_VALID_LENSES = 2


def _is_fatal_llm_error(exc: LLMGenerationError) -> bool:
    return exc.failure_kind in FATAL_LLM_FAILURE_KINDS


def _llm_failure_payload(exc: BaseException) -> dict[str, Any]:
    """Safe, structured description of a per-agent failure for an SSE event.

    Never includes prompts, responses, API keys or headers — only a failure
    category and (for LLM errors) token/duration counts.
    """
    if isinstance(exc, LLMGenerationError):
        return exc.diagnostic_payload()
    return {"failure_kind": type(exc).__name__, "detail": str(exc)[:200]}


class ForecastWorkflow:
    def __init__(
        self,
        *,
        repository: RunRepository,
        evidence_store: LocalEvidenceStore,
        competitor_store: LocalCompetitorStore,
        llm: StructuredLLM,
        timeout_seconds: float = 900,
        stage_timeout_seconds: float = 75,
        heartbeat_seconds: float = 10,
    ) -> None:
        self._repository = repository
        self._evidence_store = evidence_store
        self._competitor_store = competitor_store
        self._llm = llm
        self._timeout_seconds = timeout_seconds
        self._stage_timeout_seconds = stage_timeout_seconds
        self._heartbeat_seconds = heartbeat_seconds

    def create(self, request: ForecastRequest) -> str:
        run = self._repository.create_run(request)
        self._emit(run.id, "run_queued", None, "预测任务已创建")
        return run.id

    def create_idempotent(
        self, request: ForecastRequest, idempotency_key: str
    ) -> tuple[str, bool]:
        """Create a run, or return the existing one bound to this key.

        Returns (run_id, created). ``created`` is False when a prior request with
        the same key already created the run, so the caller must NOT schedule a
        second background execution — the fix for a double-click spawning two
        runs / two background tasks.
        """
        run, created = self._repository.get_or_create_run(request, idempotency_key)
        if created:
            self._emit(run.id, "run_queued", None, "预测任务已创建")
        return run.id, created

    async def execute(self, run_id: str) -> None:
        # A single heartbeat task proves the run is alive during long model
        # calls. It reports the real current stage and elapsed time only — never
        # a fabricated progress percentage — and is always cancelled on exit.
        heartbeat = asyncio.create_task(self._heartbeat_loop(run_id))
        try:
            await asyncio.wait_for(self._execute_pipeline(run_id), timeout=self._timeout_seconds)
        except TimeoutError:
            self._repository.update_run(
                run_id,
                status=RunStatus.FAILED,
                stage="timed_out",
                error=f"forecast exceeded {self._timeout_seconds:g} seconds",
            )
            self._emit(
                run_id,
                "run_failed",
                None,
                "预测任务超时",
                {
                    "error": f"forecast exceeded {self._timeout_seconds:g} seconds",
                    "error_kind": "workflow_timeout",
                },
            )
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat

    async def _heartbeat_loop(self, run_id: str) -> None:
        started = monotonic()
        while True:
            await asyncio.sleep(self._heartbeat_seconds)
            run = self._repository.get_run(run_id)
            if run is None or run.status in {RunStatus.COMPLETED, RunStatus.FAILED}:
                return
            if run.status != RunStatus.RUNNING:
                continue
            self._emit(
                run_id,
                "llm_call_heartbeat",
                None,
                "模型仍在处理，请稍候…",
                {
                    "stage": run.stage,
                    "elapsed_seconds": round(monotonic() - started, 1),
                },
            )

    async def _run_stage_with_fallback(
        self,
        run_id: str,
        stage: str,
        operation: Callable[[], Awaitable[TStage]],
        fallback: Callable[[BaseException], TStage],
        *,
        validate: Callable[[TStage], None] | None = None,
    ) -> TStage:
        """Run one stage inside a hard budget and recover from model-output failures.

        The stage owns the deadline. Nested provider and semantic retries may use
        the budget, but can never extend it. Only known external/model-output
        failures are degraded; programming and persistence errors still surface.
        """

        try:
            async with asyncio.timeout(self._stage_timeout_seconds):
                value = await operation()
                if validate is not None:
                    validate(value)
                return value
        except Exception as exc:
            if not self._is_recoverable_stage_error(exc):
                raise
            value = fallback(exc)
            if validate is not None:
                validate(value)
            self._record_stage_degradation(run_id, stage, exc)
            return value

    @staticmethod
    def _is_recoverable_stage_error(exc: BaseException) -> bool:
        if isinstance(
            exc,
            (TimeoutError, LLMConfigurationError, LLMGenerationError, ValueError),
        ):
            return True
        return isinstance(exc, RuntimeError) and "exhausted" in str(exc).casefold()

    def _record_stage_degradation(
        self, run_id: str, stage: str, exc: BaseException
    ) -> None:
        if isinstance(exc, TimeoutError):
            failure_kind = "stage_timeout"
            reason = (
                f"{stage} 超过 {self._stage_timeout_seconds:g} 秒阶段预算，"
                "已切换到本地确定性降级结果"
            )
        elif isinstance(exc, LLMGenerationError):
            failure_kind = exc.failure_kind
            reason = f"{stage} 模型调用不可用（{failure_kind}），已使用本地确定性降级结果"
        elif isinstance(exc, LLMConfigurationError):
            failure_kind = "llm_configuration"
            reason = f"{stage} 模型配置不可用，已使用本地确定性降级结果"
        else:
            failure_kind = type(exc).__name__
            detail = str(exc).strip()[:120]
            reason = f"{stage} 输出未通过校验，已使用本地确定性降级结果"
            if detail:
                reason = f"{reason}：{detail}"
        degradation = StageDegradation(
            stage=stage,
            reason=reason,
            failure_kind=failure_kind,
        )
        self._emit(
            run_id,
            "stage_degraded",
            None,
            reason,
            degradation.model_dump(mode="json"),
        )

    def _recorded_stage_degradations(self, run_id: str) -> list[dict[str, str]]:
        records: list[dict[str, str]] = []
        for event in self._repository.list_events(run_id):
            if event.event_type != "stage_degraded":
                continue
            stage = event.payload.get("stage")
            reason = event.payload.get("reason")
            if isinstance(stage, str) and isinstance(reason, str):
                records.append({"stage": stage, "reason": reason})
        return records

    async def _execute_pipeline(self, run_id: str) -> None:
        run = self._repository.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        try:
            self._repository.update_run(
                run_id, status=RunStatus.RUNNING, stage="evidence_selection"
            )
            retrieval_plan, evidence = self._evidence_store.retrieve(run.request)
            self._save(
                run_id,
                "retrieval_plan",
                "layered-retrieval-planner",
                retrieval_plan,
            )
            self._save(run_id, "evidence", "local-evidence-store", evidence)
            self._emit(
                run_id,
                "evidence_selected",
                "local-evidence-store",
                f"已从本地证据库选择 {len(evidence)} 条相关证据",
                {
                    "count": len(evidence),
                    "evidence_ids": [item.id for item in evidence],
                    "layers": sorted({item.layer.value for item in evidence if item.layer}),
                    "coverage": [item.model_dump(mode="json") for item in retrieval_plan.coverage],
                    "fallback_used": retrieval_plan.fallback_used,
                    "artifact_kinds": ["retrieval_plan", "evidence"],
                },
            )
            self._emit(
                run_id,
                "strategy_applied",
                "layered-retrieval-planner",
                f"研究策略已应用：{strategy_preset_label(run.request.strategy_profile)}",
                {
                    "strategy_profile": run.request.strategy_profile.value,
                    "weights": run.request.weights.model_dump(),
                    "dominant_dimensions": strategy_dominant_dimensions(run.request.weights),
                    "retrieval_adjustments": retrieval_plan.strategy_adjustments,
                    "strategy_explanation": retrieval_plan.strategy_explanation,
                },
            )

            self._repository.update_run(run_id, stage="future_forecasting")
            forecasts = await self._run_stage_with_fallback(
                run_id,
                "future_forecasting",
                lambda: self._run_futures_panel(run_id, run.request, evidence),
                lambda _exc: self._fallback_forecasts(run.request, evidence),
                validate=lambda value: self._validate_forecasts(value, evidence),
            )
            self._save(run_id, "lens_forecasts", "futures-panel", forecasts)

            self._repository.update_run(run_id, stage="forecast_deliberation")
            deliberation_evidence = self._referenced_evidence(forecasts, evidence)
            deliberations = await self._run_stage_with_fallback(
                run_id,
                "forecast_deliberation",
                lambda: self._run_deliberation_panel(
                    run_id, run.request, forecasts, deliberation_evidence
                ),
                lambda _exc: self._fallback_deliberations(forecasts, deliberation_evidence),
                validate=lambda value: self._validate_deliberations(value, evidence),
            )
            self._save(
                run_id,
                "lens_deliberations",
                "deliberation-panel",
                deliberations,
            )

            self._repository.update_run(run_id, stage="consensus_formation")
            consensus = await self._run_stage_with_fallback(
                run_id,
                "consensus_formation",
                lambda: self._run_consensus(
                    run_id,
                    run.request,
                    forecasts,
                    deliberations,
                    deliberation_evidence,
                ),
                lambda _exc: self._fallback_consensus(forecasts, evidence),
                validate=lambda value: self._validate_consensus(value, evidence),
            )
            self._save(run_id, "forecast_consensus", "forecast-consensus", consensus)
            self._emit(
                run_id,
                "consensus_completed",
                "forecast-consensus",
                "已形成证据加权共识，并保留少数意见与未解决分歧",
                {
                    "consensus_claims": len(consensus.consensus_claims),
                    "unresolved_disagreements": len(consensus.unresolved_disagreements),
                    "evidence_gaps": len(consensus.evidence_gaps),
                    "missing_lenses": consensus.missing_lenses,
                },
            )

            self._repository.update_run(run_id, stage="opportunity_synthesis")
            opportunities = await self._run_stage_with_fallback(
                run_id,
                "opportunity_synthesis",
                lambda: self._run_opportunity_synthesis(
                    run_id,
                    run.request,
                    evidence,
                    forecasts,
                    deliberations,
                    consensus,
                ),
                lambda _exc: self._fallback_opportunities(run.request, evidence, consensus),
                validate=lambda value: self._validate_opportunities(value, evidence),
            )
            self._save(run_id, "opportunities", "opportunity-synthesizer", opportunities)
            self._emit(
                run_id,
                "opportunities_created",
                "opportunity-synthesizer",
                f"已形成 {len(opportunities)} 个未来机会方向",
                {"count": len(opportunities)},
            )

            self._repository.update_run(run_id, stage="competitor_analysis")
            competitor_evidence = self._competitor_store.retrieve(run.request)
            self._save(
                run_id,
                "competitor_evidence",
                "local-competitor-store",
                competitor_evidence,
            )
            competitive_analysis = await self._run_stage_with_fallback(
                run_id,
                "competitor_analysis",
                lambda: self._run_competitor_analysis(
                    run_id, run.request, opportunities, competitor_evidence
                ),
                lambda exc: self._fallback_competitive_analysis(
                    run.request, opportunities, competitor_evidence, exc
                ),
                validate=lambda value: self._validate_competitive_analysis(
                    value, opportunities, competitor_evidence
                ),
            )
            self._save(
                run_id,
                "competitive_analysis",
                "competitor-analysis",
                competitive_analysis,
            )
            self._emit(
                run_id,
                "competitive_analysis_completed",
                "competitor-analysis",
                (
                    "竞品分析已降级完成（基于现有官方竞品资料）"
                    if competitive_analysis.degraded
                    else f"已分析 {len(competitor_evidence)} 条竞品资料并形成竞争空白"
                ),
                {
                    "evidence_count": len(competitor_evidence),
                    "gap_count": len(competitive_analysis.gaps),
                    "brands": sorted({item.brand for item in competitor_evidence}),
                    "degraded": competitive_analysis.degraded,
                },
            )

            self._repository.update_run(run_id, stage="current_capability_audit")
            current_capability_evidence = self._current_capability_evidence()
            current_baseline = await self._run_stage_with_fallback(
                run_id,
                "current_capability_audit",
                lambda: self._run_current_capability_baseline(run_id, run.request),
                lambda _exc: self._fallback_current_baseline(current_capability_evidence),
                validate=lambda value: self._validate_current_baseline(
                    value, current_capability_evidence
                ),
            )
            if self._repository.get_artifact(run_id, "current_capability_evidence") is None:
                self._save(
                    run_id,
                    "current_capability_evidence",
                    "local-evidence-store",
                    current_capability_evidence,
                )
            self._save(
                run_id,
                "current_capability_baseline",
                "current-product-auditor",
                current_baseline,
            )

            self._repository.update_run(run_id, stage="candidate_generation")
            candidates = await self._run_stage_with_fallback(
                run_id,
                "candidate_generation",
                lambda: self._run_product_architect(
                    run_id,
                    run.request,
                    evidence,
                    opportunities,
                    competitive_analysis,
                    competitor_evidence,
                    current_baseline,
                ),
                lambda _exc: self._fallback_candidates(
                    run.request, evidence, opportunities, competitor_evidence
                ),
                validate=lambda value: self._validate_candidates(
                    value,
                    opportunities,
                    evidence,
                    run.request.candidate_count,
                    competitor_evidence,
                ),
            )

            self._repository.update_run(run_id, stage="novelty_audit")
            candidates, novelty_audit = await self._run_stage_with_fallback(
                run_id,
                "novelty_audit",
                lambda: self._run_novelty_gate(
                    run_id,
                    run.request,
                    evidence,
                    opportunities,
                    competitive_analysis,
                    competitor_evidence,
                    current_baseline,
                    candidates,
                ),
                lambda _exc: (
                    candidates,
                    self._fallback_novelty_audit(candidates, current_baseline),
                ),
            )
            self._repository.update_run(run_id, stage="portfolio_diversity_audit")
            candidates, novelty_audit, portfolio_diversity_audit = (
                await self._run_stage_with_fallback(
                    run_id,
                    "portfolio_diversity_audit",
                    lambda: self._run_portfolio_diversity_gate(
                        run_id,
                        run.request,
                        evidence,
                        opportunities,
                        competitive_analysis,
                        competitor_evidence,
                        current_baseline,
                        candidates,
                        novelty_audit,
                    ),
                    lambda exc: (
                        candidates,
                        novelty_audit,
                        self._fallback_portfolio_audit(candidates, exc),
                    ),
                )
            )
            self._save(
                run_id,
                "novelty_audit",
                "current-product-auditor",
                novelty_audit,
            )
            self._save(
                run_id,
                "portfolio_diversity_audit",
                "portfolio-diversity-auditor",
                portfolio_diversity_audit,
            )
            self._save(run_id, "raw_candidates", "product-architect", candidates)
            self._emit(
                run_id,
                "candidates_created",
                "product-architect",
                f"已生成 {len(candidates)} 个差异化消费电子产品候选",
                {"count": len(candidates)},
            )

            self._repository.update_run(run_id, stage="candidate_review")
            reviews, available_dimensions = await self._run_stage_with_fallback(
                run_id,
                "candidate_review",
                lambda: self._run_review_panel(
                    run_id, run.request, evidence, candidates, competitor_evidence
                ),
                lambda _exc: (
                    self._fallback_reviews(candidates),
                    list(REVIEW_DIMENSIONS),
                ),
            )
            ranked = self._rank_candidates(run.request, candidates, reviews)
            self._save(run_id, "ranked_candidates", "blind-review-panel", ranked)
            missing_dimensions = [
                dimension
                for dimension in REVIEW_DIMENSIONS
                if dimension not in available_dimensions
            ]
            self._emit(
                run_id,
                "reviews_completed",
                "blind-review-panel",
                (
                    "独立评审完成，候选产品可由用户自由选择"
                    if not missing_dimensions
                    else "部分评审维度缺失，已按剩余维度归一化后完成评审"
                ),
                {
                    "candidate_count": len(ranked),
                    "dimensions": available_dimensions,
                    "missing_dimensions": missing_dimensions,
                },
            )

            degradations = self._collect_degradations(
                competitive_analysis=competitive_analysis,
                consensus=consensus,
                novelty_audit=novelty_audit,
                portfolio_diversity_audit=portfolio_diversity_audit,
                missing_dimensions=missing_dimensions,
            )
            degradations = self._merge_degradations(
                degradations, self._recorded_stage_degradations(run_id)
            )
            self._repository.update_run(
                run_id, status=RunStatus.COMPLETED, stage="awaiting_product_selection"
            )
            # Terminal state carries degraded metadata rather than a new enum
            # value, so a partially-degraded run is COMPLETED (never FAILED) but
            # is never presented as a fully-verified analysis.
            self._emit(
                run_id,
                "run_completed",
                None,
                (
                    "未来产品预测已降级完成，等待用户选择候选产品"
                    if degradations
                    else "未来产品预测完成，等待用户选择候选产品"
                ),
                {
                    "degraded": bool(degradations),
                    "degradation_count": len(degradations),
                    "degradations": degradations,
                },
            )
        except Exception as exc:
            # The exception is never swallowed: the run is moved to a terminal
            # FAILED state, a safe error category is persisted, and a terminal SSE
            # event is emitted. No prompt, response, API key or header is logged —
            # only our own messages and (for LLM errors) the failure category.
            error_kind = (
                exc.failure_kind if isinstance(exc, LLMGenerationError) else type(exc).__name__
            )
            self._repository.update_run(
                run_id,
                status=RunStatus.FAILED,
                stage="failed",
                error=str(exc),
            )
            self._emit(
                run_id,
                "run_failed",
                None,
                "预测任务失败",
                {"error": str(exc), "error_kind": error_kind},
            )

    def get_result(self, run_id: str) -> ForecastResult:
        run = self._repository.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        evidence = self._artifact_models(run_id, "evidence", EvidenceRecord)
        retrieval_plan = self._artifact_model(run_id, "retrieval_plan", RetrievalPlan)
        forecasts = self._artifact_models(run_id, "lens_forecasts", LensForecast)
        deliberations = self._artifact_models(run_id, "lens_deliberations", LensDeliberation)
        consensus = self._artifact_model(run_id, "forecast_consensus", ForecastConsensus)
        opportunities = self._artifact_models(run_id, "opportunities", Opportunity)
        competitor_evidence = self._artifact_models(run_id, "competitor_evidence", CompetitorRecord)
        competitive_analysis = self._artifact_model(
            run_id, "competitive_analysis", CompetitiveAnalysis
        )
        current_capability_baseline = self._artifact_model(
            run_id, "current_capability_baseline", CurrentCapabilityBaseline
        )
        current_capability_evidence = self._artifact_models(
            run_id, "current_capability_evidence", EvidenceRecord
        )
        novelty_audit = self._artifact_model(run_id, "novelty_audit", NoveltyAudit)
        portfolio_diversity_audit = self._artifact_model(
            run_id, "portfolio_diversity_audit", PortfolioDiversityAudit
        )
        ranked = self._artifact_models(run_id, "ranked_candidates", RankedCandidate)
        return ForecastResult(
            run=run,
            retrieval_plan=retrieval_plan,
            evidence=evidence,
            lens_forecasts=forecasts,
            lens_deliberations=deliberations,
            forecast_consensus=consensus,
            opportunities=opportunities,
            competitor_evidence=competitor_evidence,
            competitive_analysis=competitive_analysis,
            current_capability_evidence=current_capability_evidence,
            current_capability_baseline=current_capability_baseline,
            novelty_audit=novelty_audit,
            portfolio_diversity_audit=portfolio_diversity_audit,
            candidates=ranked,
        )

    async def define_selected_product(
        self, run_id: str, selection: ProductSelectionRequest
    ) -> ProductSpec:
        result = self.get_result(run_id)
        if result.run.status != RunStatus.COMPLETED:
            raise ValueError("forecast run has not completed")
        ranked = next(
            (item for item in result.candidates if item.candidate.id == selection.candidate_id),
            None,
        )
        if ranked is None:
            raise LookupError(f"candidate not found: {selection.candidate_id}")

        idempotency_key = selection.idempotency_key or f"candidate:{selection.candidate_id}"
        state = self._repository.get_selection(run_id, idempotency_key)
        if state is not None:
            if state.candidate_id != selection.candidate_id:
                raise ValueError("idempotency key is already bound to another candidate")
            if state.status == SelectionStatus.COMPLETED and state.product_id:
                existing = self._repository.get_product(state.product_id)
                if existing is not None:
                    return existing
            if state.status == SelectionStatus.IN_PROGRESS:
                raise ValueError("this product definition is already being generated")
        if not self._repository.reserve_selection(run_id, idempotency_key, selection.candidate_id):
            raise ValueError("this product definition is already being generated")

        self._emit(
            run_id,
            "product_definition_started",
            "product-definition",
            f"正在将用户选择的 {ranked.candidate.name} 转换为标准产品定义",
        )
        agent = ProductDefinitionAgent(self._llm)
        try:
            async def generate_product() -> tuple[ProductSpec, AgentOutput[Any] | None]:
                generated = await agent.run(
                    run_id=run_id,
                    request=result.run.request,
                    evidence=result.evidence,
                    ranked_candidate=ranked,
                    selection=selection,
                    competitive_analysis=result.competitive_analysis,
                    competitor_evidence=result.competitor_evidence,
                )
                return generated.value.product, generated

            product, output = await self._run_stage_with_fallback(
                run_id,
                "product_definition",
                generate_product,
                lambda _exc: (
                    self._fallback_product_spec(
                        run_id, result.run.request, ranked, selection
                    ),
                    None,
                ),
                validate=lambda value: self._validate_product(
                    value[0], result.evidence, result.competitor_evidence
                ),
            )
            self._repository.save_product(product)
            self._save(
                run_id,
                f"product_spec:{product.id}",
                agent.name,
                product,
                output=output,
                prompt_version=agent.prompt_version,
            )
            self._repository.complete_selection(run_id, idempotency_key, product.id)
        except Exception as exc:
            self._repository.fail_selection(run_id, idempotency_key, str(exc))
            raise
        self._emit(
            run_id,
            "product_definition_completed",
            agent.name,
            "标准ProductSpec已生成，验证假设已准备但尚未执行",
            {
                "product_id": product.id,
                "candidate_id": selection.candidate_id,
                "idempotency_key": idempotency_key,
            },
        )
        return product

    # ------------------------------------------------------------------ #
    # Product Definition Workbench                                        #
    # ------------------------------------------------------------------ #

    async def answer_product_question(
        self, product_id: str, request: ProductQuestionRequest
    ) -> ProductQuestionRecord:
        """Answer a user question about a ProductSpec with grounded, labeled claims.

        The answer never mutates the ProductSpec; it may only surface structured
        suggested changes for the user to accept later.
        """

        product = self._load_product(product_id)
        if request.idempotency_key:
            existing = self._repository.find_question_record_by_key(
                product_id, request.idempotency_key
            )
            if existing is not None:
                return existing

        category = classify_question(request.question)
        context_prompt, allowed_ev, allowed_comp = self._build_question_context(
            product, category, request.question
        )
        agent = ProductSpecAnalystAgent(self._llm)
        output = await agent.answer(
            question=request.question,
            category=category,
            context_prompt=context_prompt,
            allowed_evidence_ids=allowed_ev,
            allowed_competitor_ids=allowed_comp,
            sections=list(SPEC_SECTIONS),
        )
        draft = output.value.answer
        illegal = self._illegal_reference_ids(draft, allowed_ev, allowed_comp)
        if illegal:
            repaired = await agent.repair(
                question=request.question,
                category=category,
                context_prompt=context_prompt,
                previous=draft,
                invalid_ids=sorted(illegal),
                allowed_evidence_ids=allowed_ev,
                allowed_competitor_ids=allowed_comp,
                sections=list(SPEC_SECTIONS),
            )
            draft = repaired.value.answer
        claims, integrity_notes = self._reconcile_claims(draft, allowed_ev, allowed_comp)

        question_id = f"pq-{uuid4().hex[:12]}"
        answer_id = f"pa-{uuid4().hex[:12]}"
        affected_sections = [
            section for section in draft.affected_sections if section in set(SPEC_SECTIONS)
        ]

        # Enforce the mode contract regardless of what the model returned:
        # explanation never proposes; issue_detected surfaces an issue but no
        # changes; only change_request may carry suggested changes.
        mode = draft.answer_mode
        design_issue: ProductDesignIssue | None = None
        suggestions: list[ProductSuggestedChange] = []
        if mode == AnswerMode.ISSUE_DETECTED and draft.design_issue is not None:
            design_issue = ProductDesignIssue(
                id=f"di-{uuid4().hex[:10]}",
                title=draft.design_issue.title,
                description=draft.design_issue.description,
                affected_sections=[
                    section
                    for section in draft.design_issue.affected_sections
                    if section in set(SPEC_SECTIONS)
                ],
                severity=draft.design_issue.severity,
                reason=draft.design_issue.reason,
                blocks_readiness=draft.design_issue.blocks_readiness,
            )
        elif mode == AnswerMode.CHANGE_REQUEST:
            suggestions = [
                ProductSuggestedChange(
                    id=f"sc-{uuid4().hex[:10]}",
                    section=change.section,
                    current_summary=change.current_summary,
                    proposed_change=change.proposed_change,
                    rationale=change.rationale,
                    source_question_id=question_id,
                )
                for change in draft.suggested_changes
            ]
        # A claimed issue with no structured payload is just an explanation.
        if mode == AnswerMode.ISSUE_DETECTED and design_issue is None:
            mode = AnswerMode.EXPLANATION

        question = ProductQuestion(
            id=question_id,
            product_id=product.id,
            product_version=product.version,
            question=request.question,
            category=category,
        )
        answer = ProductQuestionAnswer(
            id=answer_id,
            question_id=question_id,
            product_id=product.id,
            product_version=product.version,
            category=category,
            answer_mode=mode,
            direct_answer=draft.direct_answer,
            claims=claims,
            assumptions=draft.assumptions,
            unknowns=draft.unknowns,
            affected_sections=affected_sections,
            design_issue=design_issue,
            suggested_changes=suggestions,
            integrity_notes=integrity_notes,
            context_evidence_ids=allowed_ev,
            context_competitor_ids=allowed_comp,
        )
        record = ProductQuestionRecord(question=question, answer=answer)
        self._repository.save_question_record(record, idempotency_key=request.idempotency_key)

        # A pure explanation changes nothing. Only surfacing an issue or a change
        # request moves a fresh draft into review; a confirmed product is reverted
        # only by an accepted revision, never by asking a question.
        if (
            product.definition_status == DefinitionStatus.DRAFT
            and answer.answer_mode != AnswerMode.EXPLANATION
        ):
            self._repository.save_product(
                product.model_copy(update={"definition_status": DefinitionStatus.UNDER_REVIEW})
            )
        return record

    def list_product_questions(self, product_id: str) -> list[ProductQuestionRecord]:
        self._load_product(product_id)
        records = self._repository.list_question_records(product_id)
        resolutions = {
            resolution.suggestion_id: resolution.resolution
            for resolution in self._repository.list_suggestion_resolutions(product_id)
        }
        if not resolutions:
            return records
        annotated: list[ProductQuestionRecord] = []
        for record in records:
            changes = [
                suggestion.model_copy(update={"resolution": resolutions.get(suggestion.id)})
                for suggestion in record.answer.suggested_changes
            ]
            issue = record.answer.design_issue
            if issue is not None:
                issue = issue.model_copy(update={"resolution": resolutions.get(issue.id)})
            answer = record.answer.model_copy(
                update={"suggested_changes": changes, "design_issue": issue}
            )
            annotated.append(record.model_copy(update={"answer": answer}))
        return annotated

    async def generate_issue_proposal(
        self, product_id: str, question_id: str
    ) -> ProductQuestionRecord:
        """Turn a previously detected design issue into concrete suggested changes.

        Only runs when the user explicitly asks; the issue's answer carried no
        suggestions until now.
        """

        product = self._load_product(product_id)
        record = self._repository.get_question_record(product_id, question_id)
        if record is None:
            raise LookupError(f"question not found: {question_id}")
        answer = record.answer
        if answer.answer_mode != AnswerMode.ISSUE_DETECTED or answer.design_issue is None:
            raise ValueError("this answer has no design issue to turn into a proposal")
        if answer.suggested_changes:
            return record  # already generated — idempotent

        context_prompt, _ev, _comp = self._build_question_context(
            product, answer.category, record.question.question
        )
        agent = ProductSpecAnalystAgent(self._llm)
        output = await agent.propose(
            design_issue=answer.design_issue,
            context_prompt=context_prompt,
            sections=list(SPEC_SECTIONS),
        )
        drafts = [
            change
            for change in output.value.suggested_changes
            if change.section in set(SPEC_SECTIONS)
        ]
        if not drafts:
            raise ValueError("proposal generation returned no applicable changes")
        suggestions = [
            ProductSuggestedChange(
                id=f"sc-{uuid4().hex[:10]}",
                section=change.section,
                current_summary=change.current_summary,
                proposed_change=change.proposed_change,
                rationale=change.rationale,
                source_question_id=question_id,
                source_issue_id=answer.design_issue.id,
            )
            for change in drafts
        ]
        updated_answer = answer.model_copy(update={"suggested_changes": suggestions})
        updated_record = record.model_copy(update={"answer": updated_answer})
        self._repository.update_question_record(updated_record)
        return updated_record

    def resolve_design_issues(
        self, product_id: str, issue_ids: list[str]
    ) -> ProductDefinitionReadiness:
        """Dismiss detected design issues ("暂不处理") without changing the spec."""

        self._load_product(product_id)
        valid_ids = {
            record.answer.design_issue.id
            for record in self._repository.list_question_records(product_id)
            if record.answer.design_issue is not None
        }
        unknown = [issue_id for issue_id in issue_ids if issue_id not in valid_ids]
        if unknown:
            raise LookupError(f"design issue not found: {sorted(unknown)}")
        for issue_id in dict.fromkeys(issue_ids):
            self._repository.save_suggestion_resolution(
                SuggestionResolution(
                    suggestion_id=issue_id,
                    product_id=product_id,
                    resolution="dismissed",
                )
            )
        return self.product_readiness(product_id)

    def list_product_revisions(self, product_id: str) -> list[ProductRevision]:
        self._load_product(product_id)
        return self._repository.list_revisions(product_id)

    async def revise_product(
        self, product_id: str, request: ProductRevisionRequest
    ) -> ProductSpec:
        """Apply only the user-accepted suggested changes into a new spec version."""

        product = self._load_product(product_id)
        if request.idempotency_key:
            existing = self._repository.find_revision_by_key(product_id, request.idempotency_key)
            if existing is not None:
                return self._load_product(product_id)

        suggestion_map: dict[str, tuple[ProductSuggestedChange, str]] = {}
        for record in self._repository.list_question_records(product_id):
            for suggestion in record.answer.suggested_changes:
                suggestion_map[suggestion.id] = (suggestion, record.answer.id)

        accepted: list[tuple[ProductSuggestedChange, SuggestionDisposition]] = []
        source_answer_ids: list[str] = []
        for decision in request.decisions:
            entry = suggestion_map.get(decision.suggestion_id)
            if entry is None:
                raise LookupError(f"suggestion not found: {decision.suggestion_id}")
            suggestion, answer_id = entry
            accepted.append((suggestion, decision.disposition))
            if answer_id not in source_answer_ids:
                source_answer_ids.append(answer_id)

        result = self._result_for_product(product)
        evidence = result.evidence if result else []
        competitor_evidence = result.competitor_evidence if result else []
        change_reason = request.change_reason or self._default_change_reason(accepted)
        change_dicts = [
            {
                "section": suggestion.section,
                "current_summary": suggestion.current_summary,
                "proposed_change": suggestion.proposed_change,
                "rationale": suggestion.rationale,
                "disposition": disposition.value,
            }
            for suggestion, disposition in accepted
        ]

        agent = ProductSpecReviserAgent(self._llm)
        output = await agent.run(
            product=product,
            accepted_changes=change_dicts,
            evidence=evidence,
            competitor_evidence=competitor_evidence,
            change_reason=change_reason,
        )
        to_version = self._bump_version(product.version)
        revised = self._sanitize_revised_product(
            output.value.product,
            previous=product,
            evidence=evidence,
            competitor_evidence=competitor_evidence,
            to_version=to_version,
            change_reason=change_reason,
        )
        # Safety net: identity and citation invariants are already enforced above.
        self._validate_product(revised, evidence, competitor_evidence)
        self._repository.save_product(revised)

        revision = ProductRevision(
            id=f"rev-{uuid4().hex[:12]}",
            product_id=product.id,
            from_version=product.version,
            to_version=to_version,
            source_answer_ids=source_answer_ids,
            accepted_changes=[
                ProductRevisionChange(
                    suggestion_id=suggestion.id,
                    section=suggestion.section,
                    proposed_change=suggestion.proposed_change,
                    disposition=disposition,
                )
                for suggestion, disposition in accepted
            ],
            change_reason=change_reason,
            before_snapshot=product,
            after_snapshot=revised,
        )
        self._repository.save_revision(revision, idempotency_key=request.idempotency_key)

        resolution_labels = {
            SuggestionDisposition.APPLY: "accepted",
            SuggestionDisposition.AS_RISK: "converted_to_risk",
            SuggestionDisposition.AS_HYPOTHESIS: "converted_to_hypothesis",
        }
        for suggestion, disposition in accepted:
            self._repository.save_suggestion_resolution(
                SuggestionResolution(
                    suggestion_id=suggestion.id,
                    product_id=product.id,
                    resolution=resolution_labels[disposition],
                    revision_id=revision.id,
                )
            )
            # Accepting a proposal also resolves the design issue it came from.
            if suggestion.source_issue_id:
                self._repository.save_suggestion_resolution(
                    SuggestionResolution(
                        suggestion_id=suggestion.source_issue_id,
                        product_id=product.id,
                        resolution="addressed",
                        revision_id=revision.id,
                    )
                )
        return revised

    def resolve_suggestions(
        self, product_id: str, suggestion_ids: list[str]
    ) -> ProductDefinitionReadiness:
        """Dismiss suggestions without changing the spec (marks them resolved)."""

        self._load_product(product_id)
        valid_ids = {
            suggestion.id
            for record in self._repository.list_question_records(product_id)
            for suggestion in record.answer.suggested_changes
        }
        unknown = [sid for sid in suggestion_ids if sid not in valid_ids]
        if unknown:
            raise LookupError(f"suggestion not found: {sorted(unknown)}")
        for suggestion_id in dict.fromkeys(suggestion_ids):
            self._repository.save_suggestion_resolution(
                SuggestionResolution(
                    suggestion_id=suggestion_id,
                    product_id=product_id,
                    resolution="dismissed",
                )
            )
        return self.product_readiness(product_id)

    def product_readiness(self, product_id: str) -> ProductDefinitionReadiness:
        product = self._load_product(product_id)
        return evaluate_readiness(
            product,
            outstanding_suggestions=self._outstanding_suggestion_count(product_id),
            outstanding_issues=self._outstanding_blocking_issue_count(product_id),
        )

    def confirm_product(self, product_id: str) -> ProductSpec:
        """Run readiness and, only if it passes, mark the product validation_ready."""

        product = self._load_product(product_id)
        readiness = self.product_readiness(product_id)
        if not readiness.ready:
            raise DefinitionNotReadyError(readiness)
        if product.definition_status != DefinitionStatus.VALIDATION_READY:
            product = product.model_copy(
                update={"definition_status": DefinitionStatus.VALIDATION_READY}
            )
            self._repository.save_product(product)
        return product

    def _load_product(self, product_id: str) -> ProductSpec:
        product = self._repository.get_product(product_id)
        if product is None:
            raise KeyError(product_id)
        return product

    def _result_for_product(self, product: ProductSpec) -> ForecastResult | None:
        try:
            return self.get_result(product.source_run_id)
        except KeyError:
            return None

    def _outstanding_suggestion_count(self, product_id: str) -> int:
        records = self._repository.list_question_records(product_id)
        all_ids = {
            suggestion.id
            for record in records
            for suggestion in record.answer.suggested_changes
        }
        resolved = {
            resolution.suggestion_id
            for resolution in self._repository.list_suggestion_resolutions(product_id)
        }
        return len(all_ids - resolved)

    def _outstanding_blocking_issue_count(self, product_id: str) -> int:
        records = self._repository.list_question_records(product_id)
        blocking_ids = {
            record.answer.design_issue.id
            for record in records
            if record.answer.design_issue is not None
            and record.answer.design_issue.blocks_readiness
        }
        resolved = {
            resolution.suggestion_id
            for resolution in self._repository.list_suggestion_resolutions(product_id)
        }
        return len(blocking_ids - resolved)

    def _build_question_context(
        self, product: ProductSpec, category: QuestionCategory, question: str
    ) -> tuple[str, list[str], list[str]]:
        result = self._result_for_product(product)
        tokens = question_tokens(question)
        layers = set(CATEGORY_LAYERS[category])
        evidence_pool = result.evidence if result else []
        layered = [item for item in evidence_pool if item.layer in layers]
        if not layered:
            layered = evidence_pool
        selected_evidence = self._rank_evidence(layered, tokens)[:QUESTION_EVIDENCE_LIMIT]
        allowed_evidence_ids = [item.id for item in selected_evidence]

        selected_competitors: list[CompetitorRecord] = []
        if result and category in CATEGORIES_WITH_COMPETITORS:
            selected_competitors = self._rank_competitors(result.competitor_evidence, tokens)[
                :QUESTION_COMPETITOR_LIMIT
            ]
        allowed_competitor_ids = [item.id for item in selected_competitors]

        context: dict[str, Any] = {
            "product_spec": product.model_dump(mode="json"),
            "question_category": category.value,
            "evidence_digest": self._evidence_context_digest(selected_evidence),
        }
        if selected_competitors:
            context["competitor_digest"] = self._competitor_context_digest(selected_competitors)
        if result:
            if category in CATEGORIES_WITH_BASELINE and result.current_capability_baseline:
                context["current_capability_baseline"] = (
                    result.current_capability_baseline.model_dump(mode="json")
                )
            if category in CATEGORIES_WITH_NOVELTY and result.novelty_audit:
                assessment = next(
                    (
                        item
                        for item in result.novelty_audit.assessments
                        if item.candidate_id == product.source_candidate_id
                    ),
                    None,
                )
                if assessment:
                    context["novelty_assessment"] = assessment.model_dump(mode="json")
            lenses = CATEGORY_LENSES[category]
            if lenses:
                relevant_forecasts = [
                    item.model_dump(mode="json")
                    for item in result.lens_forecasts
                    if item.lens in lenses
                ]
                if relevant_forecasts:
                    context["trend_forecasts"] = relevant_forecasts
            if category in CATEGORIES_WITH_CONSENSUS and result.forecast_consensus:
                consensus = result.forecast_consensus
                context["forecast_consensus"] = {
                    "consensus_claims": [
                        item.model_dump(mode="json") for item in consensus.consensus_claims
                    ],
                    "evidence_gaps": consensus.evidence_gaps,
                }
            dimensions = CATEGORY_REVIEW_DIMENSIONS[category]
            ranked = next(
                (
                    item
                    for item in result.candidates
                    if item.candidate.id == product.source_candidate_id
                ),
                None,
            )
            if ranked and dimensions:
                reviews = [
                    review.model_dump(mode="json")
                    for review in ranked.reviews
                    if review.dimension in dimensions
                ]
                if reviews:
                    context["reviewer_opinions"] = reviews

        revisions = self._repository.list_revisions(product.id)
        if revisions:
            context["revision_history"] = [
                {
                    "from_version": revision.from_version,
                    "to_version": revision.to_version,
                    "change_reason": revision.change_reason,
                    "sections": sorted({change.section for change in revision.accepted_changes}),
                }
                for revision in revisions
            ]

        prompt = (
            "以下是回答本问题可用的全部上下文；只能引用这里出现的 EV-* 与 COMP-* 编号：\n"
            f"{compact_json(context)}"
        )
        return prompt, allowed_evidence_ids, allowed_competitor_ids

    @staticmethod
    def _rank_evidence(
        records: list[EvidenceRecord], tokens: set[str]
    ) -> list[EvidenceRecord]:
        def key(record: EvidenceRecord) -> tuple[int, float]:
            haystack = question_tokens(
                " ".join([record.title, record.content[:400], *record.topics, *record.tags])
            )
            return (len(tokens & haystack), record.credibility)

        return sorted(records, key=key, reverse=True)

    @staticmethod
    def _rank_competitors(
        records: list[CompetitorRecord], tokens: set[str]
    ) -> list[CompetitorRecord]:
        def key(record: CompetitorRecord) -> tuple[int, float]:
            haystack = question_tokens(
                " ".join(
                    [
                        record.brand,
                        record.product_name,
                        *record.verified_capabilities,
                        *record.documented_constraints,
                        *record.tags,
                    ]
                )
            )
            return (len(tokens & haystack), record.credibility)

        return sorted(records, key=key, reverse=True)

    @staticmethod
    def _evidence_context_digest(records: list[EvidenceRecord]) -> list[dict[str, Any]]:
        return [
            {
                "id": record.id,
                "title": record.title,
                "summary": record.content[:500],
                "regions": record.regions,
                "layer": record.layer.value if record.layer else None,
                "claim_status": record.claim_status.value if record.claim_status else None,
                "source_name": record.source_name,
                "credibility": record.credibility,
            }
            for record in records
        ]

    @staticmethod
    def _competitor_context_digest(records: list[CompetitorRecord]) -> list[dict[str, Any]]:
        return [
            {
                "id": record.id,
                "brand": record.brand,
                "product_name": record.product_name,
                "verified_capabilities": record.verified_capabilities,
                "documented_constraints": record.documented_constraints,
                "business_model": record.business_model,
                "privacy_and_storage": record.privacy_and_storage,
            }
            for record in records
        ]

    @staticmethod
    def _illegal_reference_ids(
        draft: ProductAnswerDraft, allowed_ev: list[str], allowed_comp: list[str]
    ) -> set[str]:
        ev_set = set(allowed_ev)
        comp_set = set(allowed_comp)
        illegal: set[str] = set()
        for claim in draft.claims:
            illegal |= set(claim.evidence_ids) - ev_set
            illegal |= set(claim.competitor_evidence_ids) - comp_set
        return illegal

    @staticmethod
    def _reconcile_claims(
        draft: ProductAnswerDraft, allowed_ev: list[str], allowed_comp: list[str]
    ) -> tuple[list[ProductAnswerClaim], list[str]]:
        ev_set = set(allowed_ev)
        comp_set = set(allowed_comp)
        claims: list[ProductAnswerClaim] = []
        notes: list[str] = []
        for claim in draft.claims:
            legal_ev = [item for item in dict.fromkeys(claim.evidence_ids) if item in ev_set]
            legal_comp = [
                item for item in dict.fromkeys(claim.competitor_evidence_ids) if item in comp_set
            ]
            removed = (set(claim.evidence_ids) - ev_set) | (
                set(claim.competitor_evidence_ids) - comp_set
            )
            status = claim.epistemic_status
            if removed:
                notes.append(f"已移除无法核对的引用：{', '.join(sorted(removed))}")
            has_support = bool(legal_ev) or bool(legal_comp)
            if status == EpistemicStatus.EVIDENCE_SUPPORTED and not has_support:
                status = EpistemicStatus.INSUFFICIENT_EVIDENCE
                notes.append("某条结论标注为『证据支持』但缺乏有效引用，已降级为『证据不足』")
            claims.append(
                ProductAnswerClaim(
                    text=claim.text,
                    epistemic_status=status,
                    evidence_ids=legal_ev,
                    competitor_evidence_ids=legal_comp,
                )
            )
        return claims, notes

    def _sanitize_revised_product(
        self,
        revised: ProductSpec,
        *,
        previous: ProductSpec,
        evidence: list[EvidenceRecord],
        competitor_evidence: list[CompetitorRecord],
        to_version: str,
        change_reason: str,
    ) -> ProductSpec:
        evidence_ids = {item.id for item in evidence}
        competitor_ids = {item.id for item in competitor_evidence}

        delta = revised.capability_delta
        if not (delta.new_capabilities and delta.hardware_or_system_delta.strip()):
            delta = previous.capability_delta

        positioning = revised.competitive_positioning
        if not (
            positioning.closest_alternatives
            and positioning.defensible_differences
            and positioning.validation_questions
        ):
            positioning = previous.competitive_positioning
        positioning = positioning.model_copy(
            update={
                "competitor_evidence_ids": [
                    item
                    for item in positioning.competitor_evidence_ids
                    if item in competitor_ids
                ]
            }
        )

        regional_fit = [
            fit.model_copy(
                update={
                    "evidence_ids": [item for item in fit.evidence_ids if item in evidence_ids]
                }
            )
            for fit in revised.regional_fit
        ]
        return revised.model_copy(
            update={
                "id": previous.id,
                "source_run_id": previous.source_run_id,
                "source_candidate_id": previous.source_candidate_id,
                "version": to_version,
                "created_at": previous.created_at,
                "human_selection_reason": previous.human_selection_reason,
                "capability_delta": delta,
                "competitive_positioning": positioning,
                "evidence_ids": [item for item in revised.evidence_ids if item in evidence_ids],
                "regional_fit": regional_fit,
                "definition_status": DefinitionStatus.UNDER_REVIEW,
                "last_change_reason": change_reason,
            }
        )

    @staticmethod
    def _bump_version(version: str) -> str:
        parts = version.split(".")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"{parts[0]}.{int(parts[1]) + 1}"
        return f"{version}.1"

    @staticmethod
    def _default_change_reason(
        accepted: list[tuple[ProductSuggestedChange, SuggestionDisposition]],
    ) -> str:
        sections = sorted({suggestion.section for suggestion, _ in accepted})
        return f"应用用户接受的修改建议（章节：{', '.join(sections)}）"

    async def _resilient_gather(
        self,
        run_id: str,
        stage: str,
        agents: list[Any],
        invoke: Any,
        key: Any,
    ) -> tuple[list[tuple[Any, Any]], dict[str, BaseException]]:
        """Run a panel of per-item agents concurrently, tolerating single failures.

        Each agent runs with ``return_exceptions=True`` so one bad output can
        never abort the whole panel. Every failed agent is retried exactly once
        (only the failures — successful agents are never re-run). Whatever still
        fails is dropped and returned so the caller can mark it unavailable and
        renormalize. Returns (successes as ordered (agent, output) pairs, and a
        mapping of still-failed agent label → its error).
        """
        successes: dict[int, Any] = {}
        errors: dict[int, BaseException] = {}
        outcomes = await asyncio.gather(
            *(invoke(agent) for agent in agents), return_exceptions=True
        )
        for index, outcome in enumerate(outcomes):
            if isinstance(outcome, Exception):
                errors[index] = outcome
            else:
                successes[index] = outcome
        if errors:
            for index in errors:
                self._emit(
                    run_id,
                    "llm_call_retrying",
                    key(agents[index]),
                    "该角色首次失败，正在单独重试，其它已成功角色不受影响",
                    {"stage": stage, **_llm_failure_payload(errors[index])},
                )
            retry_indices = list(errors)
            retry_outcomes = await asyncio.gather(
                *(invoke(agents[index]) for index in retry_indices),
                return_exceptions=True,
            )
            for index, outcome in zip(retry_indices, retry_outcomes, strict=True):
                if isinstance(outcome, Exception):
                    errors[index] = outcome
                else:
                    successes[index] = outcome
                    del errors[index]
        ordered = [
            (agents[index], successes[index])
            for index in range(len(agents))
            if index in successes
        ]
        failures = {key(agents[index]): errors[index] for index in errors}
        return ordered, failures

    async def _run_futures_panel(
        self,
        run_id: str,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
    ) -> list[LensForecast]:
        agents = [FuturesLensAgent(self._llm, lens) for lens in FORECAST_LENSES]
        for agent in agents:
            self._emit(run_id, "agent_started", agent.name, "独立预测角色开始分析")
        successes, failures = await self._resilient_gather(
            run_id,
            "future_forecasting",
            agents,
            lambda agent: agent.run(request, evidence),
            lambda agent: agent.name,
        )
        forecasts: list[LensForecast] = []
        for agent, output in successes:
            forecast = output.value.forecast.model_copy(update={"lens": agent.lens})
            forecasts.append(forecast)
            self._save(
                run_id,
                f"lens_forecast:{agent.lens}",
                agent.name,
                forecast,
                output=output,
                prompt_version=agent.prompt_version,
            )
            self._emit(run_id, "agent_completed", agent.name, "独立预测分析完成")
        for agent_name in failures:
            self._emit(
                run_id,
                "agent_unavailable",
                agent_name,
                "该预测视角在重试后仍失败，已跳过并在共识中标注缺失",
                {"stage": "future_forecasting", **_llm_failure_payload(failures[agent_name])},
            )
        if len(forecasts) < MIN_VALID_LENSES:
            raise ValueError(
                "future forecasting produced too few valid lenses: "
                f"{sorted(forecast.lens for forecast in forecasts)}"
            )
        return forecasts

    async def _run_opportunity_synthesis(
        self,
        run_id: str,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        forecasts: list[LensForecast],
        deliberations: list[LensDeliberation],
        consensus: ForecastConsensus,
    ) -> list[Opportunity]:
        agent = OpportunitySynthesizerAgent(self._llm)
        self._emit(run_id, "agent_started", agent.name, "开始合并并去重未来机会")
        output = await agent.run(request, evidence, forecasts, deliberations, consensus)
        self._emit(run_id, "agent_completed", agent.name, "未来机会聚合完成")
        return output.value.opportunities

    async def _run_current_capability_baseline(
        self,
        run_id: str,
        request: ForecastRequest,
    ) -> CurrentCapabilityBaseline:
        current_eufy_evidence = [
            item
            for item in self._evidence_store.load()
            if item.layer == KnowledgeLayer.EUFY_FOUNDATION
            or item.evidence_type in {"current_product", "current_capability", "brand_strategy"}
        ]
        if len(current_eufy_evidence) < 3:
            raise ValueError(
                "current-product audit requires at least three eufy capability records"
            )
        agent = CurrentProductAuditorAgent(self._llm)
        self._save(
            run_id,
            "current_capability_evidence",
            "local-evidence-store",
            current_eufy_evidence,
        )
        self._emit(
            run_id,
            "agent_started",
            agent.name,
            "开始建立 eufy 当前产品与能力基线",
        )
        output = await agent.build_baseline(request, current_eufy_evidence)
        baseline = output.value.baseline
        self._validate_current_baseline(baseline, current_eufy_evidence)
        self._save(
            run_id,
            "current_capability_baseline_call",
            agent.name,
            baseline,
            output=output,
            prompt_version=agent.prompt_version,
        )
        self._emit(
            run_id,
            "current_capability_baseline_completed",
            agent.name,
            f"已建立 {len(baseline.capabilities)} 项当前能力基线",
            {"capability_count": len(baseline.capabilities)},
        )
        self._emit(run_id, "agent_completed", agent.name, "当前产品能力基线审计完成")
        return baseline

    async def _run_novelty_gate(
        self,
        run_id: str,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        opportunities: list[Opportunity],
        competitive_analysis: CompetitiveAnalysis,
        competitor_evidence: list[CompetitorRecord],
        current_baseline: CurrentCapabilityBaseline,
        candidates: list[ProductCandidate],
        *,
        minimum_valid_candidates: int = 1,
        standard_regeneration_attempts: int = 2,
        rescue_regeneration_attempts: int = 1,
    ) -> tuple[list[ProductCandidate], NoveltyAudit]:
        auditor = CandidateNoveltyAuditorAgent(self._llm)
        architect = ProductArchitectAgent(self._llm)
        max_regeneration_attempts = (
            standard_regeneration_attempts + rescue_regeneration_attempts
        )
        requested_candidate_count = len(candidates)
        pending_ids = {item.id for item in candidates}
        accepted_assessments: dict[str, CandidateNoveltyAssessment] = {}
        rejected_candidate_history: dict[str, list[ProductCandidate]] = defaultdict(list)
        novelty_feedback_history: dict[str, list[CandidateNoveltyAssessment]] = defaultdict(list)
        for attempt in range(max_regeneration_attempts + 1):
            pending_candidates = [item for item in candidates if item.id in pending_ids]
            self._emit(
                run_id,
                "agent_started",
                auditor.name,
                "开始对照现有能力审计候选产品新颖性",
                {"attempt": attempt + 1},
            )
            self._emit(
                run_id,
                "novelty_audit_started",
                auditor.name,
                "当前产品查重与创新门槛审计运行中",
                {"attempt": attempt + 1},
            )
            output = await auditor.audit(request, current_baseline, pending_candidates)
            partial_audit = self._normalize_novelty_audit(
                output.value.audit, pending_candidates, current_baseline
            )
            for assessment in partial_audit.assessments:
                novelty_feedback_history[assessment.candidate_id].append(assessment)
            self._emit(run_id, "agent_completed", auditor.name, "候选新颖性审计完成")
            self._save(
                run_id,
                f"novelty_audit_attempt:{attempt + 1}",
                auditor.name,
                partial_audit,
                output=output,
                prompt_version=auditor.prompt_version,
            )
            failed_ids = {
                assessment.candidate_id
                for assessment in partial_audit.assessments
                if not assessment.passes_gate
            }
            accepted_assessments.update(
                {
                    assessment.candidate_id: assessment
                    for assessment in partial_audit.assessments
                    if assessment.passes_gate
                }
            )
            if not failed_ids:
                final_audit = NoveltyAudit(
                    assessments=[accepted_assessments[item.id] for item in candidates],
                    requested_candidate_count=requested_candidate_count,
                    returned_candidate_count=len(candidates),
                    regeneration_rounds=min(attempt, standard_regeneration_attempts),
                    rescue_rounds=max(0, attempt - standard_regeneration_attempts),
                )
                self._emit(
                    run_id,
                    "novelty_audit_completed",
                    auditor.name,
                    "全部候选已通过当前产品查重与创新门槛",
                    {"attempts": attempt + 1, "passed": len(candidates), "rejected": 0},
                )
                return candidates, final_audit
            if attempt >= max_regeneration_attempts:
                accepted_candidates = [item for item in candidates if item.id not in failed_ids]
                if len(accepted_candidates) < minimum_valid_candidates:
                    raise ValueError(
                        "novelty gate left too few valid candidates after rescue: "
                        f"{sorted(failed_ids)}"
                    )
                final_audit = NoveltyAudit(
                    assessments=[accepted_assessments[item.id] for item in accepted_candidates],
                    requested_candidate_count=requested_candidate_count,
                    returned_candidate_count=len(accepted_candidates),
                    regeneration_rounds=standard_regeneration_attempts,
                    rescue_rounds=rescue_regeneration_attempts,
                    dropped_candidate_ids=sorted(failed_ids),
                )
                self._emit(
                    run_id,
                    "novelty_gate_degraded",
                    auditor.name,
                    "个别方向在救援后仍未通过，已丢弃并继续交付其余合格候选",
                    {
                        "requested_count": requested_candidate_count,
                        "returned_count": len(accepted_candidates),
                        "dropped_candidate_ids": sorted(failed_ids),
                    },
                )
                self._emit(
                    run_id,
                    "novelty_audit_completed",
                    auditor.name,
                    "新颖性审计完成，未通过的方向已安全降级移除",
                    {
                        "attempts": attempt + 1,
                        "passed": len(accepted_candidates),
                        "rejected": len(failed_ids),
                    },
                )
                return accepted_candidates, final_audit

            rescue_mode = attempt >= standard_regeneration_attempts
            self._emit(
                run_id,
                "novelty_rescue_started" if rescue_mode else "novelty_gate_failed",
                auditor.name,
                (
                    "常规定向重生已耗尽，正在切换创新向量并生成备用方向"
                    if rescue_mode
                    else "发现与当前产品高度重合的候选，正在保留需求并替换产品机制"
                ),
                {
                    "attempt": attempt + 1,
                    "rejected_candidate_ids": sorted(failed_ids),
                    "accepted_count": len(accepted_assessments),
                    "rescue_mode": rescue_mode,
                },
            )
            failed = [item for item in candidates if item.id in failed_ids]
            accepted = [item for item in candidates if item.id not in failed_ids]
            for item in failed:
                rejected_candidate_history[item.id].append(item)
            vector_overrides = (
                self._rescue_vector_overrides(
                    failed,
                    accepted,
                    rejected_candidate_history,
                )
                if rescue_mode
                else None
            )
            regeneration = await architect.regenerate_novelty_failures(
                request=request,
                failed_candidates=failed,
                assessments=partial_audit.assessments,
                accepted_candidates=accepted,
                evidence=evidence,
                opportunities=opportunities,
                competitive_analysis=competitive_analysis,
                competitor_evidence=competitor_evidence,
                current_baseline=current_baseline,
                rejected_candidate_history=rejected_candidate_history,
                novelty_feedback_history=novelty_feedback_history,
                innovation_vector_overrides=vector_overrides,
            )
            replacements = {item.id: item for item in regeneration.value.candidates}
            candidates = [replacements.get(item.id, item) for item in candidates]
            pending_ids = failed_ids
            self._validate_candidates(
                candidates,
                opportunities,
                evidence,
                requested_candidate_count,
                competitor_evidence,
            )
            self._save(
                run_id,
                (
                    f"novelty_rescue_attempt:{attempt - standard_regeneration_attempts + 1}"
                    if rescue_mode
                    else f"novelty_regeneration_attempt:{attempt + 1}"
                ),
                architect.name,
                regeneration.value.candidates,
                output=regeneration,
                prompt_version=architect.prompt_version,
            )
        raise RuntimeError("novelty gate exhausted without a validated portfolio")

    async def _run_portfolio_diversity_gate(
        self,
        run_id: str,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        opportunities: list[Opportunity],
        competitive_analysis: CompetitiveAnalysis,
        competitor_evidence: list[CompetitorRecord],
        current_baseline: CurrentCapabilityBaseline,
        candidates: list[ProductCandidate],
        novelty_audit: NoveltyAudit,
    ) -> tuple[list[ProductCandidate], NoveltyAudit, PortfolioDiversityAudit]:
        auditor = PortfolioDiversityAuditorAgent(self._llm)
        architect = ProductArchitectAgent(self._llm)
        # One semantic rewrite is enough for a demo run. If the portfolio still
        # converges, degrade transparently instead of multiplying nested LLM loops.
        max_regeneration_attempts = 1
        regenerated_ids: list[str] = []

        for attempt in range(max_regeneration_attempts + 1):
            if len(candidates) < 2:
                reason = "合格候选不足两个，已停止继续查重并保留现有结果"
                final_audit = PortfolioDiversityAudit(
                    pair_assessments=[],
                    regeneration_rounds=attempt,
                    regenerated_candidate_ids=list(dict.fromkeys(regenerated_ids)),
                    degraded=True,
                    degradation_reason=reason,
                )
                self._emit(
                    run_id,
                    "portfolio_diversity_degraded",
                    auditor.name,
                    reason,
                    {"returned_count": len(candidates)},
                )
                return candidates, novelty_audit, final_audit
            self._emit(
                run_id,
                "agent_started",
                auditor.name,
                "开始两两审计候选产品的用户任务与底层机制",
                {"attempt": attempt + 1},
            )
            self._emit(
                run_id,
                "portfolio_diversity_audit_started",
                auditor.name,
                "候选组合语义查重运行中",
                {
                    "attempt": attempt + 1,
                    "pair_count": len(candidates) * (len(candidates) - 1) // 2,
                },
            )
            output = await auditor.audit(request, candidates, novelty_audit)
            audit = self._normalize_portfolio_diversity_audit(output.value.audit, candidates)
            # A malformed pairwise audit (reordered/duplicate/missing/unknown/illegal
            # pair choices) is already self-healed above. Give the model exactly one
            # targeted correction pass before falling back to the deterministic fix,
            # then keep whichever needed fewer repairs — never fail the run for it.
            if audit.normalization_notes:
                self._emit(
                    run_id,
                    "portfolio_diversity_repaired",
                    auditor.name,
                    "组合查重返回不合法，已定向重试并由后端归一化",
                    {"attempt": attempt + 1, "notes": audit.normalization_notes},
                )
                repair_output = await auditor.repair(
                    request, candidates, novelty_audit, audit.normalization_notes
                )
                repaired = self._normalize_portfolio_diversity_audit(
                    repair_output.value.audit, candidates
                )
                if len(repaired.normalization_notes) < len(audit.normalization_notes):
                    audit, output = repaired, repair_output
            self._save(
                run_id,
                f"portfolio_diversity_audit_attempt:{attempt + 1}",
                auditor.name,
                audit,
                output=output,
                prompt_version=auditor.prompt_version,
            )
            duplicate_ids = self._duplicate_candidate_ids(audit, candidates, novelty_audit)
            self._emit(run_id, "agent_completed", auditor.name, "候选组合语义查重完成")

            if not duplicate_ids:
                final_audit = audit.model_copy(
                    update={
                        "regeneration_rounds": attempt,
                        "regenerated_candidate_ids": list(dict.fromkeys(regenerated_ids)),
                    }
                )
                self._emit(
                    run_id,
                    "portfolio_diversity_audit_completed",
                    auditor.name,
                    "全部候选已通过组合差异化门槛",
                    {
                        "attempts": attempt + 1,
                        "pair_count": len(audit.pair_assessments),
                        "regenerated_candidate_ids": final_audit.regenerated_candidate_ids,
                    },
                )
                return candidates, novelty_audit, final_audit

            if attempt >= max_regeneration_attempts:
                minimum_survivors = min(2, len(candidates))
                survivor_ids = {item.id for item in candidates if item.id not in duplicate_ids}
                if len(survivor_ids) < minimum_survivors:
                    ranked_ids = sorted(
                        (item.id for item in candidates),
                        key=lambda candidate_id: self._novelty_quality_key(
                            candidate_id, candidates, novelty_audit
                        ),
                        reverse=True,
                    )
                    for candidate_id in ranked_ids:
                        survivor_ids.add(candidate_id)
                        if len(survivor_ids) >= minimum_survivors:
                            break
                survivors = [item for item in candidates if item.id in survivor_ids]
                dropped_ids = [item.id for item in candidates if item.id not in survivor_ids]
                survivor_assessments = {
                    item.candidate_id: item for item in novelty_audit.assessments
                }
                novelty_audit = novelty_audit.model_copy(
                    update={
                        "assessments": [
                            survivor_assessments[item.id] for item in survivors
                        ],
                        "returned_candidate_count": len(survivors),
                        "dropped_candidate_ids": list(
                            dict.fromkeys(
                                [*novelty_audit.dropped_candidate_ids, *dropped_ids]
                            )
                        ),
                    }
                )
                unresolved_pairs = [
                    [pair.candidate_a_id, pair.candidate_b_id]
                    for pair in audit.pair_assessments
                    if pair.duplicate
                    and pair.candidate_a_id in survivor_ids
                    and pair.candidate_b_id in survivor_ids
                ]
                reason = "组合去重达到上限，已保留最强候选并继续后续评审"
                final_audit = audit.model_copy(
                    update={
                        "regeneration_rounds": attempt,
                        "regenerated_candidate_ids": list(dict.fromkeys(regenerated_ids)),
                        "degraded": True,
                        "degradation_reason": reason,
                        "dropped_candidate_ids": dropped_ids,
                        "unresolved_duplicate_pairs": unresolved_pairs,
                    }
                )
                self._emit(
                    run_id,
                    "portfolio_diversity_degraded",
                    auditor.name,
                    reason,
                    {
                        "returned_count": len(survivors),
                        "dropped_candidate_ids": dropped_ids,
                        "unresolved_duplicate_pairs": unresolved_pairs,
                    },
                )
                return survivors, novelty_audit, final_audit

            regenerated_ids.extend(sorted(duplicate_ids))
            self._emit(
                run_id,
                "portfolio_duplicate_found",
                auditor.name,
                "发现候选产品底层方案重复，正在保留较强方向并定向重生其余候选",
                {
                    "attempt": attempt + 1,
                    "regenerate_candidate_ids": sorted(duplicate_ids),
                    "kept_count": len(candidates) - len(duplicate_ids),
                },
            )
            duplicate_candidates = [item for item in candidates if item.id in duplicate_ids]
            kept_candidates = [item for item in candidates if item.id not in duplicate_ids]
            regeneration = await architect.regenerate_portfolio_duplicates(
                request=request,
                duplicate_candidates=duplicate_candidates,
                kept_candidates=kept_candidates,
                pair_feedback=audit.pair_assessments,
                evidence=evidence,
                opportunities=opportunities,
                competitive_analysis=competitive_analysis,
                competitor_evidence=competitor_evidence,
                current_baseline=current_baseline,
            )
            replacements = {item.id: item for item in regeneration.value.candidates}
            if set(replacements) != duplicate_ids:
                raise ValueError(
                    "portfolio regeneration must replace every duplicate ID exactly once"
                )
            replacement_candidates = [replacements[item.id] for item in duplicate_candidates]
            self._validate_candidates(
                replacement_candidates,
                opportunities,
                evidence,
                len(replacement_candidates),
                competitor_evidence,
            )
            self._save(
                run_id,
                f"portfolio_diversity_regeneration_attempt:{attempt + 1}",
                architect.name,
                regeneration.value.candidates,
                output=regeneration,
                prompt_version=architect.prompt_version,
            )

            # Audit only replacements. Re-auditing locked survivors caused model
            # judgment drift and multiplied the full retry loop.
            valid_replacements, replacement_audit = await self._run_novelty_gate(
                run_id,
                request,
                evidence,
                opportunities,
                competitive_analysis,
                competitor_evidence,
                current_baseline,
                replacement_candidates,
                minimum_valid_candidates=0,
                standard_regeneration_attempts=1,
                rescue_regeneration_attempts=1,
            )
            valid_replacement_by_id = {item.id: item for item in valid_replacements}
            previous_candidate_order = [item.id for item in candidates]
            kept_by_id = {item.id: item for item in kept_candidates}
            candidates = [
                kept_by_id.get(candidate_id) or valid_replacement_by_id[candidate_id]
                for candidate_id in previous_candidate_order
                if candidate_id in kept_by_id or candidate_id in valid_replacement_by_id
            ]
            existing_assessments = {
                item.candidate_id: item for item in novelty_audit.assessments
            }
            replacement_assessments = {
                item.candidate_id: item for item in replacement_audit.assessments
            }
            combined_assessments = {**existing_assessments, **replacement_assessments}
            novelty_audit = novelty_audit.model_copy(
                update={
                    "assessments": [combined_assessments[item.id] for item in candidates],
                    "returned_candidate_count": len(candidates),
                    "regeneration_rounds": (
                        novelty_audit.regeneration_rounds
                        + replacement_audit.regeneration_rounds
                    ),
                    "rescue_rounds": (
                        novelty_audit.rescue_rounds + replacement_audit.rescue_rounds
                    ),
                    "dropped_candidate_ids": list(
                        dict.fromkeys(
                            [
                                *novelty_audit.dropped_candidate_ids,
                                *replacement_audit.dropped_candidate_ids,
                            ]
                        )
                    ),
                }
            )

        raise RuntimeError("portfolio diversity gate exhausted without a diverse portfolio")

    async def _run_product_architect(
        self,
        run_id: str,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        opportunities: list[Opportunity],
        competitive_analysis: CompetitiveAnalysis,
        competitor_evidence: list[CompetitorRecord],
        current_baseline: CurrentCapabilityBaseline,
    ) -> list[ProductCandidate]:
        agent = ProductArchitectAgent(self._llm)
        self._emit(run_id, "agent_started", agent.name, "开始生成差异化硬件产品组合")
        try:
            output = await agent.run(
                request,
                evidence,
                opportunities,
                competitive_analysis,
                competitor_evidence,
                current_baseline,
            )
        except LLMGenerationError as exc:
            self._save(
                run_id,
                "candidate_generation_failure",
                agent.name,
                exc.diagnostic_payload(),
                metadata=exc.metadata,
                prompt_version=agent.prompt_version,
            )
            self._emit(
                run_id,
                "structured_generation_failed",
                agent.name,
                "候选产品结构化生成失败，已记录模型重试诊断",
                exc.diagnostic_payload(),
            )
            raise
        max_repair_attempts = 2
        for attempt in range(max_repair_attempts + 1):
            candidates = output.value.candidates
            self._save(
                run_id,
                f"candidate_generation_attempt:{attempt + 1}",
                agent.name,
                candidates,
                output=output,
                prompt_version=agent.prompt_version,
            )
            try:
                self._validate_candidates(
                    candidates,
                    opportunities,
                    evidence,
                    request.candidate_count,
                    competitor_evidence,
                )
            except ValueError as exc:
                if attempt >= max_repair_attempts:
                    raise
                self._emit(
                    run_id,
                    "candidate_validation_failed",
                    agent.name,
                    "候选引用或结构校验失败，正在定向修复",
                    {"attempt": attempt + 1, "error": str(exc)},
                )
                output = await agent.repair(
                    request=request,
                    invalid_candidates=candidates,
                    validation_error=str(exc),
                    opportunities=opportunities,
                    evidence=evidence,
                    competitor_evidence=competitor_evidence,
                    current_baseline=current_baseline,
                )
                continue
            self._emit(
                run_id,
                "agent_completed",
                agent.name,
                "候选产品生成并通过引用校验",
                {"attempts": attempt + 1},
            )
            return candidates
        raise RuntimeError("candidate generation exhausted without a validated portfolio")

    async def _run_deliberation_panel(
        self,
        run_id: str,
        request: ForecastRequest,
        forecasts: list[LensForecast],
        evidence: list[EvidenceRecord],
    ) -> list[LensDeliberation]:
        # Only lenses that produced a forecast can deliberate; a lens dropped in
        # the futures panel is simply absent here too.
        by_lens = {forecast.lens: forecast for forecast in forecasts}
        agents = [LensDeliberationAgent(self._llm, lens) for lens in by_lens]
        for agent in agents:
            self._emit(run_id, "agent_started", agent.name, "开始交叉审核其他视角")
        successes, failures = await self._resilient_gather(
            run_id,
            "forecast_deliberation",
            agents,
            lambda agent: agent.run(
                request,
                by_lens[agent.lens],
                [item for item in forecasts if item.lens != agent.lens],
                evidence,
            ),
            lambda agent: agent.name,
        )
        deliberations: list[LensDeliberation] = []
        for agent, output in successes:
            deliberation = output.value.deliberation.model_copy(
                update={"reviewer_lens": agent.lens}
            )
            deliberations.append(deliberation)
            self._save(
                run_id,
                f"lens_deliberation:{agent.lens}",
                agent.name,
                deliberation,
                output=output,
                prompt_version=agent.prompt_version,
            )
            self._emit(
                run_id,
                "agent_completed",
                agent.name,
                "交叉审核完成，已记录接受、质疑与观点修正",
                {
                    "challenge_count": len(deliberation.challenges),
                    "revised_confidence": deliberation.revised_confidence,
                },
            )
        for agent_name in failures:
            self._emit(
                run_id,
                "agent_unavailable",
                agent_name,
                "该交叉审议视角在重试后仍失败，已跳过并继续形成共识",
                {"stage": "forecast_deliberation", **_llm_failure_payload(failures[agent_name])},
            )
        return deliberations

    async def _run_consensus(
        self,
        run_id: str,
        request: ForecastRequest,
        forecasts: list[LensForecast],
        deliberations: list[LensDeliberation],
        evidence: list[EvidenceRecord],
    ) -> ForecastConsensus:
        agent = ForecastConsensusAgent(self._llm)
        self._emit(run_id, "agent_started", agent.name, "开始裁决共识、分歧与证据缺口")
        output = await agent.run(request, forecasts, deliberations, evidence)
        # The backend, not the model, records which lenses are missing so a
        # degraded panel can never be presented as a complete consensus.
        available_lenses = {forecast.lens for forecast in forecasts}
        missing_lenses = [lens for lens in FORECAST_LENSES if lens not in available_lenses]
        consensus = output.value.consensus.model_copy(update={"missing_lenses": missing_lenses})
        self._save(
            run_id,
            "forecast_consensus_call",
            agent.name,
            consensus,
            output=output,
            prompt_version=agent.prompt_version,
        )
        self._emit(run_id, "agent_completed", agent.name, "共识裁决完成")
        return consensus

    async def _run_competitor_analysis(
        self,
        run_id: str,
        request: ForecastRequest,
        opportunities: list[Opportunity],
        competitor_evidence: list[CompetitorRecord],
    ) -> CompetitiveAnalysis:
        """Bounded, self-healing competitive analysis.

        normal call → compact retry (fewer records, tighter caps) → split into
        landscape + gaps → evidence-derived degraded fallback. Truncation (and
        any non-auth model failure) can never fail the whole run: the worst case
        is a clearly-labelled degraded analysis built only from real competitor
        records. This is the fix for the production 6000-token truncation.
        """
        agent = CompetitorAnalysisAgent(self._llm)
        self._emit(run_id, "agent_started", agent.name, "开始分析竞品能力与竞争空白")
        relevant = self._select_relevant_competitors(
            request, opportunities, competitor_evidence, limit=8
        )

        # 1. Normal call on the relevance-filtered, compact-projected set.
        try:
            output = await agent.run(request, opportunities, relevant)
            analysis = self._cap_competitive_analysis(output.value.analysis)
            self._emit(run_id, "agent_completed", agent.name, "竞品分析完成")
            return analysis
        except LLMGenerationError as exc:
            if _is_fatal_llm_error(exc):
                raise
            self._emit(
                run_id,
                "llm_call_retrying",
                agent.name,
                "竞品分析输出超过模型上限，正在压缩输入与输出后重试",
                {**exc.diagnostic_payload(), "strategy": "compact_retry"},
            )

        # 2. Compact retry: fewer competitors + stricter output caps.
        narrower = relevant[:5]
        try:
            output = await agent.run(request, opportunities, narrower, compact=True)
            analysis = self._cap_competitive_analysis(output.value.analysis)
            self._emit(run_id, "agent_completed", agent.name, "竞品分析在压缩重试后完成")
            return analysis
        except LLMGenerationError as exc:
            if _is_fatal_llm_error(exc):
                raise
            self._emit(
                run_id,
                "llm_call_retrying",
                agent.name,
                "压缩重试仍超限，拆分为竞品概览与竞争空白两次较小调用",
                {**exc.diagnostic_payload(), "strategy": "split"},
            )

        # 3. Split into two smaller calls (landscape + gaps), merged in the backend.
        try:
            analysis = await self._competitive_split(agent, request, opportunities, narrower)
            analysis = self._cap_competitive_analysis(analysis)
            self._emit(run_id, "agent_completed", agent.name, "竞品分析通过拆分调用完成")
            return analysis
        except LLMGenerationError as exc:
            if _is_fatal_llm_error(exc):
                raise
            # 4. Explainable, evidence-derived degradation. Never fabricate gaps.
            reason = (
                f"竞品分析连续超出模型输出上限（{exc.failure_kind}），"
                "已改用现有官方竞品资料生成降级竞争上下文"
            )
            analysis = self._degraded_competitive_analysis(
                request, opportunities, relevant, reason
            )
            self._save(
                run_id,
                "competitive_analysis_failure",
                agent.name,
                exc.diagnostic_payload(),
                metadata=exc.metadata,
            )
            self._emit(
                run_id,
                "competitive_analysis_degraded",
                agent.name,
                reason,
                {
                    **exc.diagnostic_payload(),
                    "gap_count": len(analysis.gaps),
                    "brands": sorted({item.brand for item in relevant}),
                },
            )
            self._emit(run_id, "agent_completed", agent.name, "竞品分析已降级完成")
            return analysis

    async def _competitive_split(
        self,
        agent: CompetitorAnalysisAgent,
        request: ForecastRequest,
        opportunities: list[Opportunity],
        competitors: list[CompetitorRecord],
    ) -> CompetitiveAnalysis:
        landscape_output = await agent.summarize_landscape(request, opportunities, competitors)
        gaps_output = await agent.identify_gaps(request, opportunities, competitors)
        landscape = landscape_output.value.landscape
        gaps = self._sanitize_competitive_gaps(
            gaps_output.value.gaps, opportunities, competitors
        )
        if not gaps:
            raise LLMGenerationError(
                "competitive split produced no citable gaps",
                failure_kind="insufficient_gaps",
                attempts=1,
                detail="both split calls returned but no gap survived citation filtering",
            )
        return CompetitiveAnalysis(
            market_patterns=landscape.market_patterns,
            established_capabilities=landscape.established_capabilities,
            competitor_strengths=landscape.competitor_strengths,
            competitor_limitations=landscape.competitor_limitations,
            underserved_needs=landscape.underserved_needs,
            subscription_or_lock_in_gaps=landscape.subscription_or_lock_in_gaps,
            privacy_and_interoperability_gaps=landscape.privacy_and_interoperability_gaps,
            regional_differences=landscape.regional_differences,
            gaps=gaps,
        )

    @staticmethod
    def _sanitize_competitive_gaps(
        gaps: list[CompetitiveGap],
        opportunities: list[Opportunity],
        competitors: list[CompetitorRecord],
    ) -> list[CompetitiveGap]:
        opportunity_ids = {item.id for item in opportunities}
        competitor_ids = {item.id for item in competitors}
        cleaned: list[CompetitiveGap] = []
        for index, gap in enumerate(gaps[: COMPETITIVE_OUTPUT_CAPS["gaps"]], 1):
            legal_opportunities = [
                item for item in gap.affected_opportunity_ids if item in opportunity_ids
            ]
            legal_competitors = [
                item for item in gap.competitor_evidence_ids if item in competitor_ids
            ]
            if not legal_competitors:
                continue
            cleaned.append(
                gap.model_copy(
                    update={
                        "id": f"GAP-{index:03d}",
                        "affected_opportunity_ids": legal_opportunities,
                        "competitor_evidence_ids": legal_competitors,
                    }
                )
            )
        return cleaned

    @staticmethod
    def _select_relevant_competitors(
        request: ForecastRequest,
        opportunities: list[Opportunity],
        competitor_evidence: list[CompetitorRecord],
        *,
        limit: int,
    ) -> list[CompetitorRecord]:
        """Pick the most relevant competitors so the prompt stays bounded."""
        if len(competitor_evidence) <= limit:
            return competitor_evidence
        tokens = question_tokens(
            " ".join(
                [
                    request.question,
                    request.category,
                    *request.regions,
                    *request.target_users,
                    *request.constraints,
                    *(item.title for item in opportunities),
                    *(item.unmet_job for item in opportunities),
                ]
            )
        )
        request_regions = {region.casefold() for region in request.regions}

        def key(record: CompetitorRecord) -> tuple[int, int, float]:
            record_regions = {region.casefold() for region in record.regions}
            region_match = (
                1 if request_regions & record_regions or "global" in record_regions else 0
            )
            haystack = question_tokens(
                " ".join(
                    [
                        record.brand,
                        record.product_name,
                        *record.verified_capabilities,
                        *record.documented_constraints,
                        *record.tags,
                    ]
                )
            )
            return (region_match, len(tokens & haystack), record.credibility)

        return sorted(competitor_evidence, key=key, reverse=True)[:limit]

    @staticmethod
    def _cap_competitive_analysis(analysis: CompetitiveAnalysis) -> CompetitiveAnalysis:
        """Deterministically enforce the output caps the prompt asked for."""
        caps = COMPETITIVE_OUTPUT_CAPS
        return analysis.model_copy(
            update={
                "market_patterns": analysis.market_patterns[: caps["market_patterns"]],
                "established_capabilities": analysis.established_capabilities[
                    : caps["established_capabilities"]
                ],
                "competitor_strengths": {
                    brand: items[: caps["per_brand"]]
                    for brand, items in analysis.competitor_strengths.items()
                },
                "competitor_limitations": {
                    brand: items[: caps["per_brand"]]
                    for brand, items in analysis.competitor_limitations.items()
                },
                "underserved_needs": analysis.underserved_needs[: caps["underserved_needs"]],
                "subscription_or_lock_in_gaps": analysis.subscription_or_lock_in_gaps[
                    : caps["subscription_or_lock_in_gaps"]
                ],
                "privacy_and_interoperability_gaps": analysis.privacy_and_interoperability_gaps[
                    : caps["privacy_and_interoperability_gaps"]
                ],
                "regional_differences": {
                    region: items[: caps["per_region"]]
                    for region, items in analysis.regional_differences.items()
                },
                "gaps": [
                    gap.model_copy(
                        update={
                            "design_implications": gap.design_implications[
                                : caps["design_implications"]
                            ]
                        }
                    )
                    for gap in analysis.gaps[: caps["gaps"]]
                ],
            }
        )

    @staticmethod
    def _degraded_competitive_analysis(
        request: ForecastRequest,
        opportunities: list[Opportunity],
        competitors: list[CompetitorRecord],
        reason: str,
    ) -> CompetitiveAnalysis:
        """Build a minimal competitive context from real records only.

        Every field is derived from actual CompetitorRecord data. Nothing is
        fabricated: gaps come from documented constraints, strengths from
        verified capabilities. Fields that cannot be established from evidence
        are left empty rather than invented.
        """
        caps = COMPETITIVE_OUTPUT_CAPS
        strengths = {
            record.brand: record.verified_capabilities[: caps["per_brand"]]
            for record in competitors
            if record.verified_capabilities
        }
        limitations = {
            record.brand: record.documented_constraints[: caps["per_brand"]]
            for record in competitors
            if record.documented_constraints
        }
        established = list(
            dict.fromkeys(
                capability
                for record in competitors
                for capability in record.verified_capabilities
            )
        )[: caps["established_capabilities"]]
        regional: dict[str, list[str]] = {}
        for region in request.regions:
            in_region = [
                record.brand
                for record in competitors
                if region in record.regions or "Global" in record.regions
            ]
            if in_region:
                regional[region] = list(dict.fromkeys(in_region))[: caps["per_region"]]

        gaps: list[CompetitiveGap] = []
        for record in competitors:
            if not record.documented_constraints:
                continue
            constraint = record.documented_constraints[0]
            gaps.append(
                CompetitiveGap(
                    id=f"GAP-{len(gaps) + 1:03d}",
                    title=f"{record.brand}：{constraint[:60]}",
                    description=constraint,
                    # Opportunity links cannot be established without the model;
                    # left empty rather than fabricated.
                    affected_opportunity_ids=[],
                    competitor_brands=[record.brand],
                    competitor_evidence_ids=[record.id],
                    white_space=constraint,
                    design_implications=[],
                    imitation_risk="unavailable",
                    validation_question="需人工确认该记录中的约束是否构成真实的市场空白。",
                    confidence=0.3,
                )
            )
            if len(gaps) >= caps["gaps"]:
                break

        return CompetitiveAnalysis(
            market_patterns=[],
            established_capabilities=established,
            competitor_strengths=strengths,
            competitor_limitations=limitations,
            underserved_needs=[],
            subscription_or_lock_in_gaps=[],
            privacy_and_interoperability_gaps=[],
            regional_differences=regional,
            gaps=gaps,
            degraded=True,
            degradation_reason=reason,
        )

    async def _run_review_panel(
        self,
        run_id: str,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        candidates: list[ProductCandidate],
        competitor_evidence: list[CompetitorRecord],
    ) -> tuple[list[CandidateReview], list[str]]:
        agents = [CandidateReviewerAgent(self._llm, dimension) for dimension in REVIEW_DIMENSIONS]
        for agent in agents:
            self._emit(run_id, "agent_started", agent.name, "盲评角色开始评审")
        valid_candidate_ids = {candidate.id for candidate in candidates}

        async def review(
            agent: CandidateReviewerAgent,
        ) -> tuple[AgentOutput[Any], list[CandidateReview]]:
            output = await agent.run(request, evidence, candidates, competitor_evidence)
            normalized = [
                item.model_copy(update={"dimension": agent.dimension})
                for item in output.value.reviews
                if item.candidate_id in valid_candidate_ids
            ]
            if {item.candidate_id for item in normalized} != valid_candidate_ids:
                raise ValueError(f"{agent.name} did not review every candidate")
            return output, normalized

        successes, failures = await self._resilient_gather(
            run_id,
            "candidate_review",
            agents,
            review,
            lambda agent: agent.name,
        )
        reviews: list[CandidateReview] = []
        available_dimensions: list[str] = []
        for agent, (output, normalized) in successes:
            reviews.extend(normalized)
            available_dimensions.append(agent.dimension)
            self._save(
                run_id,
                f"reviews:{agent.dimension}",
                agent.name,
                normalized,
                output=output,
                prompt_version=agent.prompt_version,
            )
            self._emit(run_id, "agent_completed", agent.name, "盲评完成")
        for agent_name in failures:
            self._emit(
                run_id,
                "review_dimension_unavailable",
                agent_name,
                "该评审维度在重试后仍失败，已跳过；综合评分按剩余维度重新归一化",
                {"stage": "candidate_review", **_llm_failure_payload(failures[agent_name])},
            )
        if not available_dimensions:
            raise ValueError("all review dimensions failed after retry")
        ordered_dimensions = [
            dimension for dimension in REVIEW_DIMENSIONS if dimension in available_dimensions
        ]
        return reviews, ordered_dimensions

    @staticmethod
    def _rank_candidates(
        request: ForecastRequest,
        candidates: list[ProductCandidate],
        reviews: list[CandidateReview],
    ) -> list[RankedCandidate]:
        grouped: dict[str, list[CandidateReview]] = defaultdict(list)
        for review in reviews:
            grouped[review.candidate_id].append(review)
        weights = request.weights.model_dump()
        # Renormalize weights over the dimensions that actually produced reviews,
        # so a dropped reviewer never contributes a fabricated 0 (or 50) score.
        present_dimensions = {review.dimension for review in reviews}
        weight_total = sum(
            weight for dimension, weight in weights.items() if dimension in present_dimensions
        )
        if weight_total <= 0:
            weight_total = 1.0
        ranked: list[RankedCandidate] = []
        for candidate in candidates:
            candidate_reviews = grouped[candidate.id]
            scores = {review.dimension: review.score for review in candidate_reviews}
            weighted_score = round(
                sum(
                    scores.get(dimension, 0) * weight
                    for dimension, weight in weights.items()
                    if dimension in present_dimensions
                )
                / weight_total,
                2,
            )
            ranked.append(
                RankedCandidate(
                    candidate=candidate,
                    reviews=candidate_reviews,
                    dimension_scores=scores,
                    weighted_score=weighted_score,
                    rank=0,
                )
            )
        ranked.sort(key=lambda item: item.weighted_score, reverse=True)
        return [item.model_copy(update={"rank": index}) for index, item in enumerate(ranked, 1)]

    @staticmethod
    def _fallback_forecasts(
        request: ForecastRequest, evidence: list[EvidenceRecord]
    ) -> list[LensForecast]:
        records = evidence[:2]
        lens_labels = {
            "user_trends": "用户需求",
            "technology_trends": "技术演进",
            "security_futures": "安全风险",
            "market_futures": "市场变化",
        }
        forecasts: list[LensForecast] = []
        for lens in FORECAST_LENSES:
            signals: list[TrendSignal] = []
            for index in range(2):
                record = records[index] if index < len(records) else None
                signals.append(
                    TrendSignal(
                        title=(record.title if record else f"{lens_labels[lens]}信号 {index + 1}"),
                        description=(
                            record.content[:280]
                            if record
                            else "本地资料不足，需在后续用户研究中验证该趋势。"
                        ),
                        impact_horizon=f"1-{request.forecast_horizon_years} years",
                        evidence_ids=[record.id] if record else [],
                        confidence=0.55 if record else 0.3,
                        uncertainty="该结论来自本地证据归纳，尚未经过本轮模型交叉验证。",
                    )
                )
            forecasts.append(
                LensForecast(
                    lens=lens,
                    thesis=f"从{lens_labels[lens]}视角看，{request.question.strip()}",
                    signals=signals,
                    implications=[
                        "优先验证真实家庭场景中的可感知用户价值。",
                        "在进入量产决策前验证隐私、可靠性与成本边界。",
                    ],
                )
            )
        return forecasts

    @staticmethod
    def _fallback_deliberations(
        forecasts: list[LensForecast], evidence: list[EvidenceRecord]
    ) -> list[LensDeliberation]:
        evidence_ids = [item.id for item in evidence[:1]]
        deliberations: list[LensDeliberation] = []
        for index, forecast in enumerate(forecasts):
            target = forecasts[(index + 1) % len(forecasts)].lens
            deliberations.append(
                LensDeliberation(
                    reviewer_lens=forecast.lens,
                    original_thesis=forecast.thesis,
                    challenges=[
                        CrossLensChallenge(
                            id=f"CH-{index + 1:03d}",
                            target_lens=target,
                            challenged_claim="趋势能直接转化为稳定的消费者采用。",
                            challenge_reason="本地证据能说明方向，但不能替代采用率实测。",
                            evidence_ids=evidence_ids,
                            severity="medium",
                        )
                    ],
                    revisions_to_own_view=["降低未经实测的采用率与效果置信度。"],
                    unchanged_positions=["保留隐私、本地处理和可靠性优先原则。"],
                    unresolved_questions=["目标用户是否愿意为该结果改变现有行为？"],
                    revised_thesis=forecast.thesis,
                    revised_confidence=0.5,
                )
            )
        return deliberations

    @staticmethod
    def _fallback_consensus(
        forecasts: list[LensForecast], evidence: list[EvidenceRecord]
    ) -> ForecastConsensus:
        claims: list[ConsensusClaim] = []
        for index in range(2):
            forecast = forecasts[index % len(forecasts)]
            signal = forecast.signals[index % len(forecast.signals)]
            claims.append(
                ConsensusClaim(
                    claim=signal.description,
                    supporting_lenses=list(dict.fromkeys([forecast.lens, forecasts[-1].lens])),
                    evidence_ids=signal.evidence_ids,
                    confidence=min(signal.confidence, 0.55),
                )
            )
        return ForecastConsensus(
            consensus_claims=claims,
            minority_views=["模型交叉审议不可用，本结论仅代表本地证据的保守归纳。"],
            evidence_gaps=["缺少本轮独立模型共识，需要通过用户研究和原型测试复核。"],
            opportunity_implications=[
                "围绕可验证的家庭安全任务构建最小产品实验。",
                "优先验证误报、隐私接受度、安装成本和付费意愿。",
            ],
            missing_lenses=[],
        )

    @staticmethod
    def _fallback_opportunities(
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        consensus: ForecastConsensus,
    ) -> list[Opportunity]:
        names = [
            "更早识别家庭风险",
            "弱网与断网持续防护",
            "隐私优先的室内理解",
            "跨设备协同处置",
            "低维护的家庭安全服务",
        ]
        records: list[EvidenceRecord | None] = [*evidence] or [None]
        opportunities: list[Opportunity] = []
        for index, name in enumerate(names, 1):
            record = records[(index - 1) % len(records)]
            evidence_ids = [record.id] if record is not None else []
            implication = consensus.opportunity_implications[
                (index - 1) % len(consensus.opportunity_implications)
            ]
            opportunities.append(
                Opportunity(
                    id=f"OPP-{index:03d}",
                    title=name,
                    unmet_job=f"家庭希望在不增加持续操作负担的情况下实现{name}。",
                    target_users=request.target_users,
                    target_regions=request.regions,
                    why_now=implication,
                    opportunity_window=f"1-{request.forecast_horizon_years} years",
                    enabling_trends=["端侧 AI", "多传感器融合", "低功耗连接"],
                    evidence_ids=evidence_ids,
                    counter_evidence=["实际效果、安装摩擦和付费意愿仍需验证。"],
                    confidence=0.5 if evidence_ids else 0.3,
                    regional_differences={
                        region: ["需进行本地法规与家庭场景验证"]
                        for region in request.regions
                    },
                )
            )
        return opportunities

    def _current_capability_evidence(self) -> list[EvidenceRecord]:
        return [
            item
            for item in self._evidence_store.load()
            if item.layer == KnowledgeLayer.EUFY_FOUNDATION
            or item.evidence_type in {"current_product", "current_capability", "brand_strategy"}
        ]

    @staticmethod
    def _fallback_current_baseline(
        evidence: list[EvidenceRecord],
    ) -> CurrentCapabilityBaseline:
        capabilities: list[CurrentCapability] = []
        for index in range(3):
            record = evidence[index] if index < len(evidence) else None
            capabilities.append(
                CurrentCapability(
                    id=f"CAP-{index + 1:03d}",
                    capability=(record.title if record else f"当前能力基线 {index + 1}"),
                    existing_products=[record.source_name] if record else ["现有 eufy 产品组合"],
                    form_factors=["camera", "sensor", "hub"][index : index + 1],
                    evidence_ids=[record.id] if record else [],
                )
            )
        return CurrentCapabilityBaseline(
            summary="基于本地 eufy 资料建立的保守能力基线。",
            capabilities=capabilities,
            combination_warning_signs=["仅重组现有摄像、传感和通知能力，不构成独立创新。"],
        )

    def _fallback_competitive_analysis(
        self,
        request: ForecastRequest,
        opportunities: list[Opportunity],
        competitor_evidence: list[CompetitorRecord],
        exc: BaseException,
    ) -> CompetitiveAnalysis:
        relevant = self._select_relevant_competitors(
            request, opportunities, competitor_evidence, limit=8
        )
        reason = f"模型竞品分析不可用（{type(exc).__name__}），已改用官方竞品资料归纳"
        return self._degraded_competitive_analysis(request, opportunities, relevant, reason)

    @staticmethod
    def _fallback_candidates(
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        opportunities: list[Opportunity],
        competitor_evidence: list[CompetitorRecord],
    ) -> list[ProductCandidate]:
        product_names = [
            "Edge Sentinel",
            "SafePath Beacon",
            "Resilience Mesh",
            "Privacy Guardian",
            "Care Signal Hub",
            "Home Response Node",
            "Trust Access Kit",
            "Boundary Sense",
            "QuietWatch Relay",
            "Family Safety Link",
        ]
        form_factors = [
            "wall-mounted ambient sensor",
            "portable safety beacon",
            "distributed resilience nodes",
            "privacy-first indoor hub",
            "tabletop care signal hub",
            "home response controller",
            "modular access kit",
            "outdoor boundary sensor",
            "low-power relay node",
            "wearable and home bridge",
        ]
        evidence_ids = [item.id for item in evidence[:2]]
        alternatives = [item.product_name for item in competitor_evidence[:2]] or [
            "current camera and alarm systems"
        ]
        competitor_ids = [item.id for item in competitor_evidence[:2]]
        vectors = list(InnovationVector)
        candidates: list[ProductCandidate] = []
        for index in range(request.candidate_count):
            opportunity = opportunities[index % len(opportunities)]
            vector = vectors[index % len(vectors)]
            name = f"eufy {product_names[index % len(product_names)]} {index + 1}"
            regional_fit = [
                RegionalFit(
                    region=region,
                    fit_reasons=["面向该地区的家庭安全与低维护需求"],
                    required_adaptations=["验证当地法规、住宅结构和通知偏好"],
                    evidence_ids=evidence_ids,
                    confidence=0.45,
                )
                for region in request.regions
            ]
            candidates.append(
                ProductCandidate(
                    id=f"CAND-{index + 1:03d}",
                    name=name,
                    tagline=f"面向{opportunity.title}的可验证 AI 原生硬件概念",
                    opportunity_ids=[opportunity.id],
                    target_users=opportunity.target_users,
                    target_regions=opportunity.target_regions,
                    core_problem=opportunity.unmet_job,
                    value_proposition="以端侧多信号理解降低操作负担，并把高影响动作保留给用户确认。",
                    form_factor=form_factors[index % len(form_factors)],
                    hardware_components=["low-power sensor", "edge processor", "secure radio"],
                    ai_native_mechanism="端侧模型融合环境、设备和用户上下文，输出可解释的风险判断。",
                    key_scenarios=[opportunity.title, "断网条件下的本地安全响应"],
                    differentiators=["本地优先", "跨传感器上下文", "无强制订阅的核心能力"],
                    estimated_price_range="$99-$249",
                    technical_dependencies=["低功耗端侧 AI", "安全设备协同协议"],
                    key_assumptions=["用户能感知该任务相对现有通知的增量价值"],
                    kill_criteria=["实测不能显著降低误报或处置时间"],
                    evidence_ids=evidence_ids,
                    regional_fit=regional_fit,
                    competitive_positioning=CompetitivePositioning(
                        closest_alternatives=alternatives,
                        borrowed_patterns=["本地中枢与模块化传感器"],
                        defensible_differences=["围绕不同用户任务设计的端侧多信号决策闭环"],
                        non_copycat_rationale="产品以可验证的用户结果为起点，不是为现有设备增加单一功能。",
                        copycat_risks=["成熟厂商可能复制其中的软件编排能力"],
                        competitor_evidence_ids=competitor_ids,
                        validation_questions=["相较最佳现有替代方案，是否显著改善目标任务？"],
                    ),
                    strategy_alignment=StrategyAlignment(
                        aligned_dimensions=strategy_dominant_dimensions(request.weights),
                        rationale="按用户选择的策略权重优先验证价值、可行性与差异化。",
                        tradeoffs=["概念完整度来自本地回退，需补充模型与人工复核。"],
                    ),
                    capability_delta=CapabilityDelta(
                        today_equivalents=alternatives,
                        new_capabilities=[f"以 {vector.value} 机制完成{opportunity.title}"],
                        why_not_available_today="所需端侧模型、低功耗传感与跨设备可靠协同尚未共同成熟。",
                        enabling_changes=["模型压缩", "传感器成本下降", "设备协议标准化"],
                        proof_needed=["现场准确率", "误报改善", "安装完成率"],
                        hardware_or_system_delta=f"采用 {vector.value} 的专用硬件与系统闭环。",
                        innovation_vector=vector,
                    ),
                )
            )
        return candidates

    @staticmethod
    def _fallback_novelty_audit(
        candidates: list[ProductCandidate], baseline: CurrentCapabilityBaseline
    ) -> NoveltyAudit:
        capability_ids = [item.id for item in baseline.capabilities[:1]]
        return NoveltyAudit(
            assessments=[
                CandidateNoveltyAssessment(
                    candidate_id=candidate.id,
                    classification=NoveltyClassification.ADJACENT_INNOVATION,
                    overlap_ratio=0.5,
                    overlapping_capability_ids=capability_ids,
                    genuinely_new_capabilities=(
                        candidate.capability_delta.new_capabilities
                        or [candidate.capability_delta.hardware_or_system_delta]
                    ),
                    why_not_available_today_is_credible=True,
                    hardware_or_system_delta_is_meaningful=True,
                    innovation_vector_is_credible=True,
                    reasons=["模型审计不可用；候选具备明确的新能力、使能变化和验证要求。"],
                    regeneration_brief="需在人工评审中复核与现有产品的语义重合。",
                    passes_gate=True,
                )
                for candidate in candidates
            ],
            requested_candidate_count=len(candidates),
            returned_candidate_count=len(candidates),
        )

    @staticmethod
    def _fallback_portfolio_audit(
        candidates: list[ProductCandidate], exc: BaseException
    ) -> PortfolioDiversityAudit:
        pairs = [
            CandidatePairSimilarity(
                candidate_a_id=left.id,
                candidate_b_id=right.id,
                similarity_score=0.35,
                shared_user_jobs=[],
                shared_product_mechanisms=[],
                meaningful_differences=[
                    f"{left.form_factor} 与 {right.form_factor} 的形态和主要机会不同"
                ],
                duplicate=False,
                regeneration_brief="需在人工组合评审中复核。",
            )
            for index, left in enumerate(candidates)
            for right in candidates[index + 1 :]
        ]
        return PortfolioDiversityAudit(
            pair_assessments=pairs,
            degraded=True,
            degradation_reason=f"组合语义审计不可用（{type(exc).__name__}），已保留结构差异明确的候选",
        )

    @staticmethod
    def _fallback_reviews(candidates: list[ProductCandidate]) -> list[CandidateReview]:
        reviews: list[CandidateReview] = []
        for dimension_index, dimension in enumerate(REVIEW_DIMENSIONS):
            for candidate_index, candidate in enumerate(candidates):
                score = max(55.0, 82.0 - candidate_index * 2 + dimension_index % 3)
                reviews.append(
                    CandidateReview(
                        candidate_id=candidate.id,
                        dimension=dimension,
                        score=score,
                        strengths=["问题、系统差异和验证边界均有结构化描述。"],
                        concerns=["该分数来自确定性回退，需要人工和用户研究复核。"],
                        decisive_question="目标用户是否认可相对现有替代方案的增量价值？",
                    )
                )
        return reviews

    @staticmethod
    def _fallback_product_spec(
        run_id: str,
        request: ForecastRequest,
        ranked: RankedCandidate,
        selection: ProductSelectionRequest,
    ) -> ProductSpec:
        candidate = ranked.candidate
        assumptions = list(candidate.key_assumptions)
        assumptions.extend(
            f"用户要求：{change}" for change in selection.requested_changes if change.strip()
        )
        hypotheses = [
            ValidationHypothesis(
                id="H-001",
                assumption="目标用户能感知该产品相对现有替代方案的增量价值。",
                metric="concept preference and willingness to pay",
                proposed_method="moderated concept test",
                pass_condition="目标用户偏好和付费意愿达到项目预设门槛",
                kill_condition="多数目标用户认为现有方案已经足够",
            ),
            ValidationHypothesis(
                id="H-002",
                assumption="端侧多信号判断可以降低误报并缩短处置时间。",
                metric="false-positive rate and time-to-action",
                proposed_method="scenario simulation and instrumented prototype",
                pass_condition="相较基线显著降低误报或处置时间",
                kill_condition="改善不足以抵消新增硬件与安装成本",
            ),
            ValidationHypothesis(
                id="H-003",
                assumption="隐私边界和安装流程能被家庭成员接受。",
                metric="installation completion and privacy acceptance",
                proposed_method="in-home pilot",
                pass_condition="完成率与接受度达到项目预设门槛",
                kill_condition="持续出现无法缓解的隐私或安装阻力",
            ),
        ]
        return ProductSpec(
            id=f"product-{uuid4().hex[:12]}",
            source_run_id=run_id,
            source_candidate_id=candidate.id,
            name=candidate.name,
            one_sentence_definition=candidate.tagline,
            category=request.category,
            target_users=candidate.target_users,
            target_regions=candidate.target_regions,
            core_problem=candidate.core_problem,
            value_proposition=candidate.value_proposition,
            form_factor=candidate.form_factor,
            hardware_architecture=candidate.hardware_components,
            ai_capabilities=[candidate.ai_native_mechanism],
            ai_decision_boundary="模型仅提供风险判断和低影响自动化；高影响设备动作必须经过明确策略或用户确认。",
            user_journeys=[
                f"安装并完成 {candidate.form_factor} 的隐私与区域配置",
                *candidate.key_scenarios,
                "收到可解释提醒并确认或调整系统响应",
            ],
            ecosystem_relationships=["HomeBase", "eufy Security app", "local device mesh"],
            privacy_principles=["数据最小化", "默认本地处理", "敏感动作可审计且可撤销"],
            business_model=BusinessModel(
                hardware_revenue=f"{candidate.estimated_price_range} 的一次性硬件销售",
                recurring_revenue="仅提供可选增值服务，不锁定核心安全能力",
                ecosystem_pull_through=["HomeBase", "兼容的 eufy 传感与执行设备"],
                cost_drivers=candidate.hardware_components,
            ),
            risks=[
                RiskItem(
                    category="technical",
                    risk="多信号模型在真实家庭中的准确性不足",
                    mitigation="通过分阶段原型和现场数据验证，并保留人工确认边界",
                    severity="high",
                ),
                RiskItem(
                    category="privacy",
                    risk="家庭成员不接受持续环境理解",
                    mitigation="端侧处理、可见状态、区域屏蔽和数据最小化",
                    severity="high",
                ),
            ],
            key_assumptions=assumptions,
            kill_criteria=candidate.kill_criteria,
            evidence_ids=candidate.evidence_ids,
            validation_readiness=hypotheses,
            regional_fit=candidate.regional_fit,
            competitive_positioning=candidate.competitive_positioning,
            capability_delta=candidate.capability_delta,
            human_selection_reason=selection.selection_reason,
        )

    @staticmethod
    def _merge_degradations(
        *groups: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        merged: list[dict[str, str]] = []
        seen: set[str] = set()
        for group in groups:
            for item in group:
                stage = item["stage"]
                if stage in seen:
                    continue
                seen.add(stage)
                merged.append(item)
        return merged

    @staticmethod
    def _collect_degradations(
        *,
        competitive_analysis: CompetitiveAnalysis | None,
        consensus: ForecastConsensus | None,
        novelty_audit: NoveltyAudit | None,
        portfolio_diversity_audit: PortfolioDiversityAudit | None,
        missing_dimensions: list[str],
    ) -> list[dict[str, str]]:
        """Summarize every stage that finished in a degraded state.

        Used only for the terminal ``run_completed`` metadata so the frontend can
        show an honest "completed with degradation" state. It never changes an
        artifact — it only reports what already happened.
        """
        degradations: list[dict[str, str]] = []
        if competitive_analysis is not None and competitive_analysis.degraded:
            degradations.append(
                {
                    "stage": "competitor_analysis",
                    "reason": competitive_analysis.degradation_reason or "竞品分析已降级",
                }
            )
        if consensus is not None and consensus.missing_lenses:
            degradations.append(
                {
                    "stage": "future_forecasting",
                    "reason": f"缺失预测视角：{', '.join(consensus.missing_lenses)}",
                }
            )
        if novelty_audit is not None and novelty_audit.dropped_candidate_ids:
            degradations.append(
                {
                    "stage": "novelty_audit",
                    "reason": (
                        "已丢弃未通过查重的候选："
                        f"{', '.join(novelty_audit.dropped_candidate_ids)}"
                    ),
                }
            )
        if portfolio_diversity_audit is not None and portfolio_diversity_audit.degraded:
            degradations.append(
                {
                    "stage": "portfolio_diversity_audit",
                    "reason": portfolio_diversity_audit.degradation_reason or "组合去重已降级",
                }
            )
        if missing_dimensions:
            degradations.append(
                {
                    "stage": "candidate_review",
                    "reason": f"缺失评审维度：{', '.join(missing_dimensions)}",
                }
            )
        return degradations

    @staticmethod
    def _referenced_evidence(
        forecasts: list[LensForecast], evidence: list[EvidenceRecord]
    ) -> list[EvidenceRecord]:
        referenced_ids = {
            evidence_id
            for forecast in forecasts
            for signal in forecast.signals
            for evidence_id in signal.evidence_ids
        }
        return [record for record in evidence if record.id in referenced_ids]

    @staticmethod
    def _validate_forecasts(forecasts: list[LensForecast], evidence: list[EvidenceRecord]) -> None:
        expected_lenses = set(FORECAST_LENSES)
        returned_lenses = {forecast.lens for forecast in forecasts}
        # A subset is allowed: unavailable lenses are dropped and surfaced in the
        # consensus. Only unknown/duplicate lenses or an empty panel are invalid.
        if not returned_lenses <= expected_lenses:
            raise ValueError(f"forecast panel returned invalid lenses: {sorted(returned_lenses)}")
        if len(returned_lenses) != len(forecasts):
            raise ValueError("forecast panel returned duplicate lenses")
        if not returned_lenses:
            raise ValueError("forecast panel returned no lenses")
        evidence_ids = {item.id for item in evidence}
        unknown = {
            evidence_id
            for forecast in forecasts
            for signal in forecast.signals
            for evidence_id in signal.evidence_ids
            if evidence_id not in evidence_ids
        }
        if unknown:
            raise ValueError(f"lens forecasts cite unknown evidence IDs: {sorted(unknown)}")

    @staticmethod
    def _validate_deliberations(
        deliberations: list[LensDeliberation], evidence: list[EvidenceRecord]
    ) -> None:
        returned_lenses = {item.reviewer_lens for item in deliberations}
        # Deliberations only run for lenses that produced a forecast; a subset is
        # expected. Unknown or duplicate reviewer lenses are still invalid.
        if not returned_lenses <= set(FORECAST_LENSES):
            raise ValueError(
                f"deliberation panel returned invalid lenses: {sorted(returned_lenses)}"
            )
        if len(returned_lenses) != len(deliberations):
            raise ValueError("deliberation panel returned duplicate lenses")
        if not returned_lenses:
            raise ValueError("deliberation panel returned no valid reviews")
        evidence_ids = {item.id for item in evidence}
        cited = {
            evidence_id
            for deliberation in deliberations
            for point in deliberation.accepted_points
            for evidence_id in point.evidence_ids
        }
        cited.update(
            evidence_id
            for deliberation in deliberations
            for challenge in deliberation.challenges
            for evidence_id in challenge.evidence_ids
        )
        unknown = cited - evidence_ids
        if unknown:
            raise ValueError(f"deliberations cite unknown evidence IDs: {sorted(unknown)}")

    @staticmethod
    def _validate_consensus(consensus: ForecastConsensus, evidence: list[EvidenceRecord]) -> None:
        evidence_ids = {item.id for item in evidence}
        unknown = {
            evidence_id
            for claim in consensus.consensus_claims
            for evidence_id in claim.evidence_ids
            if evidence_id not in evidence_ids
        }
        if unknown:
            raise ValueError(f"forecast consensus cites unknown evidence IDs: {sorted(unknown)}")

    @staticmethod
    def _validate_opportunities(
        opportunities: list[Opportunity], evidence: list[EvidenceRecord]
    ) -> None:
        if not 5 <= len(opportunities) <= 9:
            raise ValueError("opportunity synthesizer must return 5-9 opportunities")
        if len({item.id for item in opportunities}) != len(opportunities):
            raise ValueError("opportunity IDs must be unique")
        evidence_ids = {item.id for item in evidence}
        unknown = {
            evidence_id
            for opportunity in opportunities
            for evidence_id in opportunity.evidence_ids
            if evidence_id not in evidence_ids
        }
        if unknown:
            raise ValueError(f"opportunities cite unknown evidence IDs: {sorted(unknown)}")

    @staticmethod
    def _validate_current_baseline(
        baseline: CurrentCapabilityBaseline,
        evidence: list[EvidenceRecord],
    ) -> None:
        capability_ids = [item.id for item in baseline.capabilities]
        if len(capability_ids) != len(set(capability_ids)):
            raise ValueError("current capability baseline IDs must be unique")
        evidence_ids = {item.id for item in evidence}
        unknown = {
            evidence_id
            for capability in baseline.capabilities
            for evidence_id in capability.evidence_ids
            if evidence_id not in evidence_ids
        }
        if unknown:
            raise ValueError(
                "current capability baseline cites unknown evidence IDs: "
                f"{sorted(unknown)}"
            )

    @staticmethod
    def _novelty_quality_key(
        candidate_id: str,
        candidates: list[ProductCandidate],
        novelty_audit: NoveltyAudit,
    ) -> tuple[int, float, int, int, str]:
        assessment = next(
            item for item in novelty_audit.assessments if item.candidate_id == candidate_id
        )
        candidate = next(item for item in candidates if item.id == candidate_id)
        classification_score = {
            NoveltyClassification.EXISTING_EQUIVALENT: 0,
            NoveltyClassification.FEATURE_EXTENSION: 1,
            NoveltyClassification.ADJACENT_INNOVATION: 2,
            NoveltyClassification.NEW_PRODUCT_CATEGORY: 3,
        }
        return (
            classification_score[assessment.classification],
            -assessment.overlap_ratio,
            len(candidate.capability_delta.new_capabilities),
            len(candidate.capability_delta.proof_needed),
            candidate_id,
        )

    @staticmethod
    def _rescue_vector_overrides(
        failed_candidates: list[ProductCandidate],
        accepted_candidates: list[ProductCandidate],
        rejected_candidate_history: dict[str, list[ProductCandidate]],
    ) -> dict[str, InnovationVector]:
        """Move exhausted candidates to the least-used, not-yet-tried innovation vectors."""

        used_vectors = {
            item.capability_delta.innovation_vector for item in accepted_candidates
        }
        overrides: dict[str, InnovationVector] = {}
        for candidate in sorted(failed_candidates, key=lambda item: item.id):
            tried_vectors = {
                item.capability_delta.innovation_vector
                for item in rejected_candidate_history.get(candidate.id, [])
            }
            choices = [
                vector
                for vector in InnovationVector
                if vector not in used_vectors and vector not in tried_vectors
            ]
            if not choices:
                choices = [vector for vector in InnovationVector if vector not in tried_vectors]
            if not choices:
                choices = [
                    vector
                    for vector in InnovationVector
                    if vector != candidate.capability_delta.innovation_vector
                ]
            selected = choices[0]
            overrides[candidate.id] = selected
            used_vectors.add(selected)
        return overrides

    @staticmethod
    def _normalize_portfolio_diversity_audit(
        audit: PortfolioDiversityAudit,
        candidates: list[ProductCandidate],
    ) -> PortfolioDiversityAudit:
        """Repair a possibly-malformed auditor response instead of failing the run.

        The auditor is an LLM: it may reorder pairs, duplicate a pair, omit one,
        emit an unknown candidate ID, or pick an illegal preferred/regenerate
        choice (e.g. the same candidate twice). None of that is allowed to abort
        the workflow. The backend owns identity and the duplicate threshold; the
        model only supplies the semantic description. Every repair is recorded in
        ``normalization_notes`` so the degradation stays auditable, never hidden.
        """

        candidate_ids = [item.id for item in candidates]
        candidate_id_set = set(candidate_ids)
        expected_pairs = [
            (left, right)
            for index, left in enumerate(candidate_ids)
            for right in candidate_ids[index + 1 :]
        ]

        notes: list[str] = []
        by_pair: dict[frozenset[str], CandidatePairSimilarity] = {}
        for item in audit.pair_assessments:
            pair_ids = {item.candidate_a_id, item.candidate_b_id}
            if (
                len(pair_ids) != 2
                or not pair_ids <= candidate_id_set
            ):
                notes.append(
                    "已忽略无法对应现有候选的 pair："
                    f"{item.candidate_a_id}/{item.candidate_b_id}"
                )
                continue
            key = frozenset(pair_ids)
            if key in by_pair:
                notes.append(
                    "已合并重复出现的 pair："
                    f"{sorted(pair_ids)}"
                )
                continue
            by_pair[key] = item

        normalized: list[CandidatePairSimilarity] = []
        for left, right in expected_pairs:
            assessment = by_pair.get(frozenset((left, right)))
            if assessment is None:
                notes.append(f"已为缺失的 pair 生成中性评估：{left}/{right}")
                assessment = CandidatePairSimilarity(
                    candidate_a_id=left,
                    candidate_b_id=right,
                    similarity_score=0.0,
                    duplicate=False,
                    regeneration_brief="",
                )
            # The model explains overlap; the backend owns the hard threshold and
            # the deterministic candidate order. preferred/regenerate are cleared
            # because the backend, not the model, decides which candidate survives.
            duplicate = (
                assessment.duplicate
                or assessment.similarity_score >= 0.70
                or (
                    bool(assessment.shared_user_jobs)
                    and len(assessment.shared_product_mechanisms) >= 2
                    and len(assessment.meaningful_differences) <= 1
                )
            )
            normalized.append(
                assessment.model_copy(
                    update={
                        "candidate_a_id": left,
                        "candidate_b_id": right,
                        "duplicate": duplicate,
                        "preferred_candidate_id": "",
                        "regenerate_candidate_id": "",
                    }
                )
            )
        return audit.model_copy(
            update={
                "pair_assessments": normalized,
                "normalization_notes": [*audit.normalization_notes, *notes],
            }
        )

    @staticmethod
    def _duplicate_candidate_ids(
        audit: PortfolioDiversityAudit,
        candidates: list[ProductCandidate],
        novelty_audit: NoveltyAudit,
    ) -> set[str]:
        """Keep one strongest member from each connected duplicate cluster."""

        graph: dict[str, set[str]] = defaultdict(set)
        for pair in audit.pair_assessments:
            if not pair.duplicate:
                continue
            graph[pair.candidate_a_id].add(pair.candidate_b_id)
            graph[pair.candidate_b_id].add(pair.candidate_a_id)
        if not graph:
            return set()

        assessment_by_id = {item.candidate_id: item for item in novelty_audit.assessments}
        candidate_by_id = {item.id: item for item in candidates}
        classification_score = {
            NoveltyClassification.EXISTING_EQUIVALENT: 0,
            NoveltyClassification.FEATURE_EXTENSION: 1,
            NoveltyClassification.ADJACENT_INNOVATION: 2,
            NoveltyClassification.NEW_PRODUCT_CATEGORY: 3,
        }

        def quality(candidate_id: str) -> tuple[int, float, int, int, str]:
            novelty = assessment_by_id[candidate_id]
            candidate = candidate_by_id[candidate_id]
            delta = candidate.capability_delta
            return (
                classification_score[novelty.classification],
                -novelty.overlap_ratio,
                len(delta.new_capabilities),
                len(delta.proof_needed),
                candidate_id,
            )

        regenerate: set[str] = set()
        visited: set[str] = set()
        for root in sorted(graph):
            if root in visited:
                continue
            stack = [root]
            component: set[str] = set()
            while stack:
                current = stack.pop()
                if current in component:
                    continue
                component.add(current)
                stack.extend(graph[current] - component)
            visited.update(component)
            keeper = max(component, key=quality)
            regenerate.update(component - {keeper})
        return regenerate

    @staticmethod
    def _normalize_novelty_audit(
        audit: NoveltyAudit,
        candidates: list[ProductCandidate],
        baseline: CurrentCapabilityBaseline,
    ) -> NoveltyAudit:
        candidate_ids = {item.id for item in candidates}
        returned_ids = [item.candidate_id for item in audit.assessments]
        if set(returned_ids) != candidate_ids or len(returned_ids) != len(candidate_ids):
            raise ValueError("novelty auditor must assess every candidate exactly once")
        capability_ids = {item.id for item in baseline.capabilities}
        unknown = {
            capability_id
            for assessment in audit.assessments
            for capability_id in assessment.overlapping_capability_ids
            if capability_id not in capability_ids
        }
        if unknown:
            raise ValueError(f"novelty audit cites unknown capability IDs: {sorted(unknown)}")

        by_id = {item.id: item for item in candidates}
        passing_classifications = {
            NoveltyClassification.ADJACENT_INNOVATION,
            NoveltyClassification.NEW_PRODUCT_CATEGORY,
        }
        normalized = []
        for assessment in audit.assessments:
            delta = by_id[assessment.candidate_id].capability_delta
            passes_gate = (
                assessment.classification in passing_classifications
                and assessment.overlap_ratio <= 0.65
                and assessment.why_not_available_today_is_credible
                and assessment.hardware_or_system_delta_is_meaningful
                and assessment.innovation_vector_is_credible
                and bool(delta.new_capabilities)
                and bool(delta.why_not_available_today.strip())
                and bool(delta.enabling_changes)
                and bool(delta.proof_needed)
                and bool(delta.hardware_or_system_delta.strip())
            )
            normalized.append(assessment.model_copy(update={"passes_gate": passes_gate}))
        return audit.model_copy(update={"assessments": normalized})

    @staticmethod
    def _validate_candidates(
        candidates: list[ProductCandidate],
        opportunities: list[Opportunity],
        evidence: list[EvidenceRecord],
        expected_count: int,
        competitor_evidence: list[CompetitorRecord],
    ) -> None:
        if len(candidates) != expected_count:
            raise ValueError(f"product architect must return exactly {expected_count} candidates")
        if len({item.id for item in candidates}) != len(candidates):
            raise ValueError("candidate IDs must be unique")
        normalized_names = {item.name.strip().casefold() for item in candidates}
        if len(normalized_names) != len(candidates):
            raise ValueError("candidate product names must be unique")
        represented_vectors = {
            candidate.capability_delta.innovation_vector for candidate in candidates
        }
        required_vector_count = min(len(candidates), 4)
        if len(represented_vectors) < required_vector_count:
            raise ValueError(
                "candidate portfolio lacks innovation-vector diversity: "
                f"expected at least {required_vector_count}, got {len(represented_vectors)}"
            )
        opportunity_ids = {item.id for item in opportunities}
        evidence_ids = {item.id for item in evidence}
        unknown_opportunities = {
            opportunity_id
            for candidate in candidates
            for opportunity_id in candidate.opportunity_ids
            if opportunity_id not in opportunity_ids
        }
        unknown_evidence = {
            evidence_id
            for candidate in candidates
            for evidence_id in candidate.evidence_ids
            if evidence_id not in evidence_ids
        }
        unknown_evidence.update(
            evidence_id
            for candidate in candidates
            for regional_fit in candidate.regional_fit
            for evidence_id in regional_fit.evidence_ids
            if evidence_id not in evidence_ids
        )
        if unknown_opportunities:
            raise ValueError(
                f"candidates cite unknown opportunity IDs: {sorted(unknown_opportunities)}"
            )
        if unknown_evidence:
            raise ValueError(f"candidates cite unknown evidence IDs: {sorted(unknown_evidence)}")
        incomplete_positioning = [
            candidate.id
            for candidate in candidates
            if not candidate.competitive_positioning.closest_alternatives
            or not candidate.competitive_positioning.defensible_differences
            or not candidate.competitive_positioning.validation_questions
        ]
        if incomplete_positioning:
            raise ValueError(
                "candidates must include complete competitive positioning: "
                f"{incomplete_positioning}"
            )
        competitor_ids = {item.id for item in competitor_evidence}
        unknown_competitors = {
            evidence_id
            for candidate in candidates
            for evidence_id in candidate.competitive_positioning.competitor_evidence_ids
            if evidence_id not in competitor_ids
        }
        if unknown_competitors:
            raise ValueError(
                f"candidates cite unknown competitor evidence IDs: {sorted(unknown_competitors)}"
            )

    @staticmethod
    def _validate_competitive_analysis(
        analysis: CompetitiveAnalysis,
        opportunities: list[Opportunity],
        competitor_evidence: list[CompetitorRecord],
    ) -> None:
        # A degraded, evidence-derived analysis is allowed to carry fewer gaps
        # (it never fabricates white space). The strict 3-6 rule applies only to
        # a full model-authored analysis. Citation integrity is enforced in both.
        if not analysis.degraded and not 3 <= len(analysis.gaps) <= 6:
            raise ValueError("competitor analysis must return 3-6 gaps")
        opportunity_ids = {item.id for item in opportunities}
        competitor_ids = {item.id for item in competitor_evidence}
        unknown_opportunities = {
            item_id
            for gap in analysis.gaps
            for item_id in gap.affected_opportunity_ids
            if item_id not in opportunity_ids
        }
        unknown_competitors = {
            item_id
            for gap in analysis.gaps
            for item_id in gap.competitor_evidence_ids
            if item_id not in competitor_ids
        }
        if unknown_opportunities:
            raise ValueError(
                f"competitive gaps cite unknown opportunities: {sorted(unknown_opportunities)}"
            )
        if unknown_competitors:
            raise ValueError(
                f"competitive gaps cite unknown evidence: {sorted(unknown_competitors)}"
            )

    @staticmethod
    def _validate_product(
        product: ProductSpec,
        evidence: list[EvidenceRecord],
        competitor_evidence: list[CompetitorRecord],
    ) -> None:
        evidence_ids = {item.id for item in evidence}
        cited = set(product.evidence_ids)
        cited.update(
            evidence_id
            for regional_fit in product.regional_fit
            for evidence_id in regional_fit.evidence_ids
        )
        unknown = cited - evidence_ids
        if unknown:
            raise ValueError(f"product definition cites unknown evidence IDs: {sorted(unknown)}")
        if (
            not product.competitive_positioning.closest_alternatives
            or not product.competitive_positioning.defensible_differences
            or not product.competitive_positioning.validation_questions
        ):
            raise ValueError("product definition must preserve competitive positioning")
        competitor_ids = {item.id for item in competitor_evidence}
        unknown_competitors = (
            set(product.competitive_positioning.competitor_evidence_ids) - competitor_ids
        )
        if unknown_competitors:
            raise ValueError(
                "product definition cites unknown competitor evidence IDs: "
                f"{sorted(unknown_competitors)}"
            )

    def _emit(
        self,
        run_id: str,
        event_type: str,
        agent: str | None,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        sequence = len(self._repository.list_events(run_id)) + 1
        self._repository.add_event(
            AgentEvent(
                run_id=run_id,
                sequence=sequence,
                event_type=event_type,
                agent=agent,
                message=message,
                payload=payload or {},
            )
        )

    def _save(
        self,
        run_id: str,
        kind: str,
        producer: str,
        value: Any,
        *,
        output: AgentOutput[Any] | None = None,
        metadata: dict[str, int | str | None] | None = None,
        prompt_version: str | None = None,
    ) -> None:
        if isinstance(value, list):
            payload = [
                item.model_dump(mode="json") if hasattr(item, "model_dump") else item
                for item in value
            ]
        elif hasattr(value, "model_dump"):
            payload = value.model_dump(mode="json")
        else:
            payload = value
        artifact_metadata = output.metadata if output else (metadata or {})
        artifact = Artifact(
            id=f"artifact-{uuid4().hex[:12]}",
            run_id=run_id,
            kind=kind,
            producer=producer,
            payload=payload,
            model_name=(
                str(artifact_metadata.get("model_name"))
                if artifact_metadata.get("model_name")
                else None
            ),
            prompt_version=prompt_version,
            duration_ms=_as_int(artifact_metadata.get("duration_ms")),
            input_tokens=_as_int(artifact_metadata.get("input_tokens")),
            output_tokens=_as_int(artifact_metadata.get("output_tokens")),
        )
        self._repository.save_artifact(artifact)
        self._emit(
            run_id,
            "artifact_ready",
            producer,
            f"中间产物已就绪：{kind}",
            {"artifact_id": artifact.id, "artifact_kind": kind, "producer": producer},
        )

    def _artifact_models(self, run_id: str, kind: str, model: type[Any]) -> list[Any]:
        artifact = self._repository.get_artifact(run_id, kind)
        if artifact is None:
            return []
        return [model.model_validate(item) for item in artifact.payload]

    def _artifact_model(self, run_id: str, kind: str, model: type[Any]) -> Any | None:
        artifact = self._repository.get_artifact(run_id, kind)
        if artifact is None:
            return None
        return model.model_validate(artifact.payload)


def _as_int(value: object) -> int | None:
    return int(value) if isinstance(value, int | float) else None
