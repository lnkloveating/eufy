"""Auditable multi-agent workflow for future product generation."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any
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
)
from eufy_security_agents.agents.base import AgentOutput
from eufy_security_agents.domain.models import (
    AgentEvent,
    Artifact,
    CandidateNoveltyAssessment,
    CandidateReview,
    CompetitiveAnalysis,
    CompetitorRecord,
    CurrentCapabilityBaseline,
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
    ProductCandidate,
    ProductSelectionRequest,
    ProductSpec,
    RankedCandidate,
    RetrievalPlan,
    RunStatus,
    SelectionStatus,
)
from eufy_security_agents.domain.ports import RunRepository, StructuredLLM
from eufy_security_agents.domain.strategy import (
    dominant_dimensions as strategy_dominant_dimensions,
)
from eufy_security_agents.domain.strategy import (
    preset_label as strategy_preset_label,
)
from eufy_security_agents.infrastructure.competitors import LocalCompetitorStore
from eufy_security_agents.infrastructure.evidence import LocalEvidenceStore
from eufy_security_agents.infrastructure.llm import LLMGenerationError

FORECAST_LENSES = ["user_trends", "technology_trends", "security_futures", "market_futures"]
REVIEW_DIMENSIONS = [
    "innovation",
    "user_value",
    "business_value",
    "cost_effectiveness",
    "feasibility",
    "eufy_synergy",
]


class ForecastWorkflow:
    def __init__(
        self,
        *,
        repository: RunRepository,
        evidence_store: LocalEvidenceStore,
        competitor_store: LocalCompetitorStore,
        llm: StructuredLLM,
        timeout_seconds: float = 900,
    ) -> None:
        self._repository = repository
        self._evidence_store = evidence_store
        self._competitor_store = competitor_store
        self._llm = llm
        self._timeout_seconds = timeout_seconds

    def create(self, request: ForecastRequest) -> str:
        run = self._repository.create_run(request)
        self._emit(run.id, "run_queued", None, "预测任务已创建")
        return run.id

    async def execute(self, run_id: str) -> None:
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
                {"error": f"forecast exceeded {self._timeout_seconds:g} seconds"},
            )

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
            forecasts = await self._run_futures_panel(run_id, run.request, evidence)
            self._validate_forecasts(forecasts, evidence)
            self._save(run_id, "lens_forecasts", "futures-panel", forecasts)

            self._repository.update_run(run_id, stage="forecast_deliberation")
            deliberation_evidence = self._referenced_evidence(forecasts, evidence)
            deliberations = await self._run_deliberation_panel(
                run_id, run.request, forecasts, deliberation_evidence
            )
            self._validate_deliberations(deliberations, evidence)
            self._save(
                run_id,
                "lens_deliberations",
                "deliberation-panel",
                deliberations,
            )

            self._repository.update_run(run_id, stage="consensus_formation")
            consensus = await self._run_consensus(
                run_id,
                run.request,
                forecasts,
                deliberations,
                deliberation_evidence,
            )
            self._validate_consensus(consensus, evidence)
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
                },
            )

            self._repository.update_run(run_id, stage="opportunity_synthesis")
            opportunities = await self._run_opportunity_synthesis(
                run_id,
                run.request,
                evidence,
                forecasts,
                deliberations,
                consensus,
            )
            self._validate_opportunities(opportunities, evidence)
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
            competitive_analysis = await self._run_competitor_analysis(
                run_id, run.request, opportunities, competitor_evidence
            )
            self._validate_competitive_analysis(
                competitive_analysis, opportunities, competitor_evidence
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
                f"已分析 {len(competitor_evidence)} 条竞品资料并形成竞争空白",
                {
                    "evidence_count": len(competitor_evidence),
                    "gap_count": len(competitive_analysis.gaps),
                    "brands": sorted({item.brand for item in competitor_evidence}),
                },
            )

            self._repository.update_run(run_id, stage="current_capability_audit")
            current_baseline = await self._run_current_capability_baseline(
                run_id, run.request
            )
            self._save(
                run_id,
                "current_capability_baseline",
                "current-product-auditor",
                current_baseline,
            )

            self._repository.update_run(run_id, stage="candidate_generation")
            candidates = await self._run_product_architect(
                run_id,
                run.request,
                evidence,
                opportunities,
                competitive_analysis,
                competitor_evidence,
                current_baseline,
            )

            self._repository.update_run(run_id, stage="novelty_audit")
            candidates, novelty_audit = await self._run_novelty_gate(
                run_id,
                run.request,
                evidence,
                opportunities,
                competitive_analysis,
                competitor_evidence,
                current_baseline,
                candidates,
            )
            self._repository.update_run(run_id, stage="portfolio_diversity_audit")
            candidates, novelty_audit, portfolio_diversity_audit = (
                await self._run_portfolio_diversity_gate(
                    run_id,
                    run.request,
                    evidence,
                    opportunities,
                    competitive_analysis,
                    competitor_evidence,
                    current_baseline,
                    candidates,
                    novelty_audit,
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
            reviews = await self._run_review_panel(
                run_id, run.request, evidence, candidates, competitor_evidence
            )
            ranked = self._rank_candidates(run.request, candidates, reviews)
            self._save(run_id, "ranked_candidates", "blind-review-panel", ranked)
            self._emit(
                run_id,
                "reviews_completed",
                "blind-review-panel",
                "六个独立评审维度已完成，候选产品可由用户自由选择",
                {"candidate_count": len(ranked), "dimensions": REVIEW_DIMENSIONS},
            )

            self._repository.update_run(
                run_id, status=RunStatus.COMPLETED, stage="awaiting_product_selection"
            )
            self._emit(
                run_id,
                "run_completed",
                None,
                "未来产品预测完成，等待用户选择候选产品",
            )
        except Exception as exc:
            self._repository.update_run(
                run_id,
                status=RunStatus.FAILED,
                stage="failed",
                error=str(exc),
            )
            self._emit(run_id, "run_failed", None, "预测任务失败", {"error": str(exc)})

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
            output = await agent.run(
                run_id=run_id,
                request=result.run.request,
                evidence=result.evidence,
                ranked_candidate=ranked,
                selection=selection,
                competitive_analysis=result.competitive_analysis,
                competitor_evidence=result.competitor_evidence,
            )
            product = output.value.product
            self._validate_product(product, result.evidence, result.competitor_evidence)
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

    async def _run_futures_panel(
        self,
        run_id: str,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
    ) -> list[LensForecast]:
        agents = [FuturesLensAgent(self._llm, lens) for lens in FORECAST_LENSES]
        for agent in agents:
            self._emit(run_id, "agent_started", agent.name, "独立预测角色开始分析")
        outputs = await asyncio.gather(*(agent.run(request, evidence) for agent in agents))
        forecasts: list[LensForecast] = []
        for agent, output in zip(agents, outputs, strict=True):
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
                final_audit = PortfolioDiversityAudit(
                    pair_assessments=[],
                    regeneration_rounds=attempt,
                    regenerated_candidate_ids=list(dict.fromkeys(regenerated_ids)),
                    degraded=True,
                )
                self._emit(
                    run_id,
                    "portfolio_diversity_degraded",
                    auditor.name,
                    "合格候选不足两个，已停止继续查重并保留现有结果",
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
                final_audit = audit.model_copy(
                    update={
                        "regeneration_rounds": attempt,
                        "regenerated_candidate_ids": list(dict.fromkeys(regenerated_ids)),
                        "degraded": True,
                        "dropped_candidate_ids": dropped_ids,
                        "unresolved_duplicate_pairs": unresolved_pairs,
                    }
                )
                self._emit(
                    run_id,
                    "portfolio_diversity_degraded",
                    auditor.name,
                    "组合去重达到上限，已保留最强候选并继续后续评审",
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
        agents = [LensDeliberationAgent(self._llm, lens) for lens in FORECAST_LENSES]
        for agent in agents:
            self._emit(run_id, "agent_started", agent.name, "开始交叉审核其他视角")
        by_lens = {forecast.lens: forecast for forecast in forecasts}
        outputs = await asyncio.gather(
            *(
                agent.run(
                    request,
                    by_lens[agent.lens],
                    [item for item in forecasts if item.lens != agent.lens],
                    evidence,
                )
                for agent in agents
            )
        )
        deliberations: list[LensDeliberation] = []
        for agent, output in zip(agents, outputs, strict=True):
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
        self._save(
            run_id,
            "forecast_consensus_call",
            agent.name,
            output.value.consensus,
            output=output,
            prompt_version=agent.prompt_version,
        )
        self._emit(run_id, "agent_completed", agent.name, "共识裁决完成")
        return output.value.consensus

    async def _run_competitor_analysis(
        self,
        run_id: str,
        request: ForecastRequest,
        opportunities: list[Opportunity],
        competitor_evidence: list[CompetitorRecord],
    ) -> CompetitiveAnalysis:
        agent = CompetitorAnalysisAgent(self._llm)
        self._emit(run_id, "agent_started", agent.name, "开始分析竞品能力与竞争空白")
        output = await agent.run(request, opportunities, competitor_evidence)
        self._emit(run_id, "agent_completed", agent.name, "竞品分析完成")
        return output.value.analysis

    async def _run_review_panel(
        self,
        run_id: str,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        candidates: list[ProductCandidate],
        competitor_evidence: list[CompetitorRecord],
    ) -> list[CandidateReview]:
        agents = [CandidateReviewerAgent(self._llm, dimension) for dimension in REVIEW_DIMENSIONS]
        for agent in agents:
            self._emit(run_id, "agent_started", agent.name, "盲评角色开始评审")
        outputs = await asyncio.gather(
            *(agent.run(request, evidence, candidates, competitor_evidence) for agent in agents)
        )
        reviews: list[CandidateReview] = []
        valid_candidate_ids = {candidate.id for candidate in candidates}
        for agent, output in zip(agents, outputs, strict=True):
            normalized = [
                review.model_copy(update={"dimension": agent.dimension})
                for review in output.value.reviews
                if review.candidate_id in valid_candidate_ids
            ]
            if {review.candidate_id for review in normalized} != valid_candidate_ids:
                raise ValueError(f"{agent.name} did not review every candidate")
            reviews.extend(normalized)
            self._save(
                run_id,
                f"reviews:{agent.dimension}",
                agent.name,
                normalized,
                output=output,
                prompt_version=agent.prompt_version,
            )
            self._emit(run_id, "agent_completed", agent.name, "盲评完成")
        return reviews

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
        ranked: list[RankedCandidate] = []
        for candidate in candidates:
            candidate_reviews = grouped[candidate.id]
            scores = {review.dimension: review.score for review in candidate_reviews}
            weighted_score = round(
                sum(scores.get(dimension, 0) * weight for dimension, weight in weights.items()),
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
        if returned_lenses != expected_lenses:
            raise ValueError(f"forecast panel returned invalid lenses: {sorted(returned_lenses)}")
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
        if returned_lenses != set(FORECAST_LENSES):
            raise ValueError(
                f"deliberation panel returned invalid lenses: {sorted(returned_lenses)}"
            )
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
        candidate_ids = [item.id for item in candidates]
        expected_pairs = [
            (left, right)
            for index, left in enumerate(candidate_ids)
            for right in candidate_ids[index + 1 :]
        ]
        returned_pair_keys = [
            frozenset((item.candidate_a_id, item.candidate_b_id))
            for item in audit.pair_assessments
        ]
        expected_pair_keys = [frozenset(pair) for pair in expected_pairs]
        if (
            len(returned_pair_keys) != len(set(returned_pair_keys))
            or set(returned_pair_keys) != set(expected_pair_keys)
        ):
            raise ValueError(
                "portfolio diversity auditor must assess every unordered candidate pair "
                "exactly once"
            )

        by_pair = {
            frozenset((item.candidate_a_id, item.candidate_b_id)): item
            for item in audit.pair_assessments
        }
        normalized = []
        for left, right in expected_pairs:
            assessment = by_pair[frozenset((left, right))]
            pair_ids = {assessment.candidate_a_id, assessment.candidate_b_id}
            if assessment.preferred_candidate_id not in pair_ids:
                raise ValueError("portfolio audit preferred_candidate_id must belong to its pair")
            if assessment.regenerate_candidate_id not in pair_ids:
                raise ValueError("portfolio audit regenerate_candidate_id must belong to its pair")
            if assessment.preferred_candidate_id == assessment.regenerate_candidate_id:
                raise ValueError(
                    "portfolio audit pair choices must identify two different candidates"
                )
            # The model explains overlap; the backend owns the hard threshold.
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
                    }
                )
            )
        return audit.model_copy(update={"pair_assessments": normalized})

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
        if not 3 <= len(analysis.gaps) <= 6:
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
