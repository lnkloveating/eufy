"""Auditable multi-agent workflow for future product generation."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any
from uuid import uuid4

from eufy_security_agents.agents import (
    CandidateReviewerAgent,
    CompetitorAnalysisAgent,
    ForecastConsensusAgent,
    FuturesLensAgent,
    LensDeliberationAgent,
    OpportunitySynthesizerAgent,
    ProductArchitectAgent,
    ProductDefinitionAgent,
)
from eufy_security_agents.agents.base import AgentOutput
from eufy_security_agents.domain.models import (
    AgentEvent,
    Artifact,
    CandidateReview,
    CompetitiveAnalysis,
    CompetitorRecord,
    EvidenceRecord,
    ForecastConsensus,
    ForecastRequest,
    ForecastResult,
    LensDeliberation,
    LensForecast,
    Opportunity,
    ProductCandidate,
    ProductSelectionRequest,
    ProductSpec,
    RankedCandidate,
    RetrievalPlan,
    RunStatus,
    SelectionStatus,
)
from eufy_security_agents.domain.ports import RunRepository, StructuredLLM
from eufy_security_agents.infrastructure.competitors import LocalCompetitorStore
from eufy_security_agents.infrastructure.evidence import LocalEvidenceStore

FORECAST_LENSES = ["user_trends", "technology_trends", "security_futures", "market_futures"]
REVIEW_DIMENSIONS = ["innovation", "user_value", "business_value", "feasibility", "eufy_synergy"]


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

            self._repository.update_run(run_id, stage="candidate_generation")
            candidates = await self._run_product_architect(
                run_id,
                run.request,
                evidence,
                opportunities,
                competitive_analysis,
                competitor_evidence,
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
                "五个独立评审维度已完成，候选产品可由用户自由选择",
                {"candidate_count": len(ranked)},
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

    async def _run_product_architect(
        self,
        run_id: str,
        request: ForecastRequest,
        evidence: list[EvidenceRecord],
        opportunities: list[Opportunity],
        competitive_analysis: CompetitiveAnalysis,
        competitor_evidence: list[CompetitorRecord],
    ) -> list[ProductCandidate]:
        agent = ProductArchitectAgent(self._llm)
        self._emit(run_id, "agent_started", agent.name, "开始生成差异化硬件产品组合")
        output = await agent.run(
            request, evidence, opportunities, competitive_analysis, competitor_evidence
        )
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
        metadata = output.metadata if output else {}
        artifact = Artifact(
            id=f"artifact-{uuid4().hex[:12]}",
            run_id=run_id,
            kind=kind,
            producer=producer,
            payload=payload,
            model_name=str(metadata.get("model_name")) if metadata.get("model_name") else None,
            prompt_version=prompt_version,
            duration_ms=_as_int(metadata.get("duration_ms")),
            input_tokens=_as_int(metadata.get("input_tokens")),
            output_tokens=_as_int(metadata.get("output_tokens")),
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
