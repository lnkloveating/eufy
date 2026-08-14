"""Reliability / anti-hang tests for the multi-agent research pipeline.

Every test drives the workflow with a controllable fake LLM (never the real
provider). They assert the four reliability guarantees:

    bounded retry -> deterministic repair -> explainable degradation -> terminal.

The base ``FakeStructuredLLM`` and ``_candidate`` helper are reused from
``test_workflow`` (same tests/unit directory, importable in pytest's default
prepend import mode).
"""

from __future__ import annotations

import asyncio
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel
from test_workflow import FakeStructuredLLM

from eufy_security_agents.domain.models import (
    CandidateEnvelope,
    CandidatePairSimilarity,
    CompetitiveAnalysisEnvelope,
    CompetitiveGapsEnvelope,
    CompetitiveLandscapeEnvelope,
    ForecastRequest,
    LensDeliberationEnvelope,
    LensForecastEnvelope,
    PortfolioDiversityAudit,
    PortfolioDiversityAuditEnvelope,
    ProductSelectionRequest,
    ReviewEnvelope,
    RunStatus,
)
from eufy_security_agents.domain.ports import RunRepository
from eufy_security_agents.infrastructure.competitors import LocalCompetitorStore
from eufy_security_agents.infrastructure.evidence import LocalEvidenceStore
from eufy_security_agents.infrastructure.llm import LLMGenerationError
from eufy_security_agents.infrastructure.memory import InMemoryRunRepository
from eufy_security_agents.orchestration.workflow import ForecastWorkflow

T = TypeVar("T", bound=BaseModel)

_DATA = Path(__file__).resolve().parents[2] / "data"
_META: dict[str, int | str | None] = {
    "model_name": "fake-model",
    "input_tokens": 900,
    "output_tokens": 600,
    "duration_ms": 30,
}


def _truncation_error() -> LLMGenerationError:
    return LLMGenerationError(
        "structured LLM generation failed after 3 attempts (truncated)",
        failure_kind="truncated",
        attempts=3,
        detail="provider stopped at the 6000-token output limit",
        metadata=dict(_META),
    )


def _make_workflow(llm: FakeStructuredLLM, **kwargs: float) -> ForecastWorkflow:
    return ForecastWorkflow(
        repository=InMemoryRunRepository(),
        evidence_store=LocalEvidenceStore(_DATA / "evidence"),
        competitor_store=LocalCompetitorStore(_DATA / "competitors"),
        llm=llm,
        **kwargs,
    )


def _request(candidate_count: int = 3) -> ForecastRequest:
    return ForecastRequest(
        question="预测未来三年美国eufy Security的差异化AI原生产品机会与竞争空白",
        regions=["United States"],
        target_users=["Households"],
        candidate_count=candidate_count,
    )


def _event_types(repo: RunRepository, run_id: str) -> list[str]:
    return [event.event_type for event in repo.list_events(run_id)]


def _completed_event_payload(repo: RunRepository, run_id: str) -> dict[str, object]:
    for event in repo.list_events(run_id):
        if event.event_type == "run_completed":
            return event.payload
    return {}


# --------------------------------------------------------------------------- #
# LLM boundary error classification                                           #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_authentication_failure_is_classified() -> None:
    import httpx

    from eufy_security_agents.infrastructure.llm import OpenAICompatibleLLM

    class _R(BaseModel):
        status: str

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, request=request, json={"error": "bad key"})

    client = OpenAICompatibleLLM(
        api_key="wrong-key",
        base_url="https://provider.invalid",
        model_name="test-model",
        max_retries=0,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(LLMGenerationError) as caught:
        await client.generate(
            system_prompt="s", user_prompt="u", response_model=_R, temperature=0
        )
    assert caught.value.failure_kind == "authentication"


@pytest.mark.asyncio
async def test_empty_content_then_valid_recovers() -> None:
    import httpx

    from eufy_security_agents.infrastructure.llm import OpenAICompatibleLLM

    class _R(BaseModel):
        status: str

    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        content = "" if calls == 1 else '{"status":"ok"}'
        return httpx.Response(
            200,
            request=request,
            json={
                "model": "test-model",
                "choices": [{"finish_reason": "stop", "message": {"content": content}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    client = OpenAICompatibleLLM(
        api_key="k",
        base_url="https://provider.invalid",
        model_name="test-model",
        max_retries=1,
        transport=httpx.MockTransport(handler),
    )
    result, _ = await client.generate(
        system_prompt="s", user_prompt="u", response_model=_R, temperature=0
    )
    assert result.status == "ok"
    assert calls == 2


# --------------------------------------------------------------------------- #
# 故障一 — Competitive analysis truncation                                     #
# --------------------------------------------------------------------------- #


class CompetitiveTruncationLLM(FakeStructuredLLM):
    """Truncates the competitive analysis according to the configured plan."""

    def __init__(
        self,
        *,
        fail_normal: bool = True,
        fail_compact: bool = False,
        fail_split: bool = False,
    ) -> None:
        super().__init__()
        self.fail_normal = fail_normal
        self.fail_compact = fail_compact
        self.fail_split = fail_split
        self.competitive_calls = 0
        self.split_calls = 0

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
    ) -> tuple[T, dict[str, int | str | None]]:
        if response_model is CompetitiveAnalysisEnvelope:
            self.competitive_calls += 1
            is_compact = "size-reduced retry" in user_prompt
            if is_compact and self.fail_compact:
                raise _truncation_error()
            if not is_compact and self.fail_normal:
                raise _truncation_error()
        if response_model is CompetitiveLandscapeEnvelope:
            self.split_calls += 1
            if self.fail_split:
                raise _truncation_error()
        if response_model is CompetitiveGapsEnvelope:
            self.split_calls += 1
            if self.fail_split:
                raise _truncation_error()
        return await super().generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            temperature=temperature,
        )


@pytest.mark.asyncio
async def test_competitive_truncation_recovers_on_compact_retry() -> None:
    llm = CompetitiveTruncationLLM(fail_normal=True, fail_compact=False)
    workflow = _make_workflow(llm)
    repo = workflow._repository
    run_id = workflow.create(_request())

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    assert result.competitive_analysis is not None
    assert result.competitive_analysis.degraded is False
    assert llm.competitive_calls == 2  # normal (truncated) + compact (ok)
    assert "llm_call_retrying" in _event_types(repo, run_id)


@pytest.mark.asyncio
async def test_competitive_persistent_truncation_degrades_not_fails() -> None:
    llm = CompetitiveTruncationLLM(fail_normal=True, fail_compact=True, fail_split=True)
    workflow = _make_workflow(llm)
    repo = workflow._repository
    run_id = workflow.create(_request())

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    assert result.competitive_analysis is not None
    assert result.competitive_analysis.degraded is True
    assert result.competitive_analysis.degradation_reason
    # Degraded analysis is built only from real competitor records.
    real_ids = {record.id for record in result.competitor_evidence}
    for gap in result.competitive_analysis.gaps:
        assert set(gap.competitor_evidence_ids) <= real_ids
    events = _event_types(repo, run_id)
    assert "competitive_analysis_degraded" in events
    payload = _completed_event_payload(repo, run_id)
    assert payload.get("degraded") is True


# --------------------------------------------------------------------------- #
# 故障二 — Portfolio diversity illegal IDs                                     #
# --------------------------------------------------------------------------- #


def _portfolio_pairs(
    candidate_ids: list[str], mode: str
) -> list[CandidatePairSimilarity]:
    pairs = [
        (left, right)
        for index, left in enumerate(candidate_ids)
        for right in candidate_ids[index + 1 :]
    ]

    def base(left: str, right: str, **overrides: object) -> CandidatePairSimilarity:
        data: dict[str, object] = {
            "candidate_a_id": left,
            "candidate_b_id": right,
            "similarity_score": 0.2,
            "duplicate": False,
            "preferred_candidate_id": left,
            "regenerate_candidate_id": right,
            "regeneration_brief": "",
        }
        data.update(overrides)
        return CandidatePairSimilarity(**data)  # type: ignore[arg-type]

    if mode == "preferred_equals_regenerate":
        return [
            base(left, right, preferred_candidate_id=left, regenerate_candidate_id=left)
            for left, right in pairs
        ]
    if mode == "unknown_id":
        # Corrupt the first pair with a candidate that does not exist.
        result = [base(left, right) for left, right in pairs]
        result[0] = base("CAND-999", pairs[0][1])
        return result
    if mode == "missing_pair":
        return [base(left, right) for left, right in pairs[:-1]]
    if mode == "duplicate_pair":
        return [base(pairs[0][0], pairs[0][1]), *(base(left, right) for left, right in pairs)]
    raise AssertionError(mode)


class MalformedPortfolioLLM(FakeStructuredLLM):
    def __init__(self, *, mode: str, persist: bool = True) -> None:
        super().__init__()
        self.mode = mode
        self.persist = persist

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
    ) -> tuple[T, dict[str, int | str | None]]:
        if response_model is PortfolioDiversityAuditEnvelope:
            candidate_ids = sorted(set(re.findall(r"CAND-\d{3}", user_prompt)))
            is_repair = "was malformed" in user_prompt
            if is_repair and not self.persist:
                pairs = _portfolio_pairs(candidate_ids, "missing_pair")
                # Clean, complete set on repair.
                pairs = [
                    CandidatePairSimilarity(
                        candidate_a_id=left,
                        candidate_b_id=right,
                        similarity_score=0.2,
                        duplicate=False,
                        preferred_candidate_id=left,
                        regenerate_candidate_id=right,
                        regeneration_brief="",
                    )
                    for index, left in enumerate(candidate_ids)
                    for right in candidate_ids[index + 1 :]
                ]
            else:
                pairs = _portfolio_pairs(candidate_ids, self.mode)
            value = PortfolioDiversityAuditEnvelope(
                audit=PortfolioDiversityAudit(pair_assessments=pairs)
            )
            return value, dict(_META)  # type: ignore[return-value]
        return await super().generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            temperature=temperature,
        )


@pytest.mark.parametrize(
    "mode",
    ["preferred_equals_regenerate", "unknown_id", "missing_pair", "duplicate_pair"],
)
@pytest.mark.asyncio
async def test_portfolio_illegal_ids_never_fail_the_run(mode: str) -> None:
    llm = MalformedPortfolioLLM(mode=mode, persist=True)
    workflow = _make_workflow(llm)
    run_id = workflow.create(_request())

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    assert result.portfolio_diversity_audit is not None
    # At least two candidates always survive to the review panel.
    assert len(result.candidates) >= 2
    # A malformed response is repaired, never fatal.
    if mode in {"unknown_id", "missing_pair", "duplicate_pair"}:
        assert result.portfolio_diversity_audit.normalization_notes


@pytest.mark.asyncio
async def test_portfolio_malformed_then_repaired_emits_event() -> None:
    llm = MalformedPortfolioLLM(mode="missing_pair", persist=False)
    workflow = _make_workflow(llm)
    repo = workflow._repository
    run_id = workflow.create(_request())

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    assert "portfolio_diversity_repaired" in _event_types(repo, run_id)


# --------------------------------------------------------------------------- #
# 故障三 — Panel resilience (one agent failing must not fail the run)          #
# --------------------------------------------------------------------------- #


class PanelFailureLLM(FakeStructuredLLM):
    def __init__(
        self,
        *,
        fail_lens: str | None = None,
        fail_deliberator: str | None = None,
        fail_reviewer: str | None = None,
        transient: bool = False,
    ) -> None:
        super().__init__()
        self.fail_lens = fail_lens
        self.fail_deliberator = fail_deliberator
        self.fail_reviewer = fail_reviewer
        self.transient = transient
        self.attempts: dict[str, int] = defaultdict(int)

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
    ) -> tuple[T, dict[str, int | str | None]]:
        if response_model is LensForecastEnvelope and self.fail_lens:
            match = re.search(r"lens identifier is '([^']+)'", user_prompt)
            if match and match.group(1) == self.fail_lens:
                self.attempts[self.fail_lens] += 1
                if not self.transient or self.attempts[self.fail_lens] == 1:
                    raise _truncation_error()
        if response_model is LensDeliberationEnvelope and self.fail_deliberator:
            match = re.search(r"Review from the '([^']+)' perspective", user_prompt)
            if match and match.group(1) == self.fail_deliberator:
                raise _truncation_error()
        if response_model is ReviewEnvelope and self.fail_reviewer:
            match = re.search(r"only on '([^']+)'", user_prompt)
            if match and match.group(1) == self.fail_reviewer:
                raise _truncation_error()
        return await super().generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            temperature=temperature,
        )


@pytest.mark.asyncio
async def test_one_futures_lens_failure_continues_and_is_marked_missing() -> None:
    llm = PanelFailureLLM(fail_lens="market_futures")
    workflow = _make_workflow(llm)
    repo = workflow._repository
    run_id = workflow.create(_request())

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    assert {f.lens for f in result.lens_forecasts} == {
        "user_trends",
        "technology_trends",
        "security_futures",
    }
    assert result.forecast_consensus is not None
    assert result.forecast_consensus.missing_lenses == ["market_futures"]
    assert "agent_unavailable" in _event_types(repo, run_id)


@pytest.mark.asyncio
async def test_transient_lens_failure_recovers_on_retry() -> None:
    llm = PanelFailureLLM(fail_lens="market_futures", transient=True)
    workflow = _make_workflow(llm)
    run_id = workflow.create(_request())

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    assert len(result.lens_forecasts) == 4
    assert result.forecast_consensus is not None
    assert result.forecast_consensus.missing_lenses == []


@pytest.mark.asyncio
async def test_one_deliberation_failure_continues() -> None:
    llm = PanelFailureLLM(fail_deliberator="security_futures")
    workflow = _make_workflow(llm)
    run_id = workflow.create(_request())

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    assert len(result.lens_forecasts) == 4  # forecasts unaffected
    assert {d.reviewer_lens for d in result.lens_deliberations} == {
        "user_trends",
        "technology_trends",
        "market_futures",
    }


@pytest.mark.asyncio
async def test_one_reviewer_failure_renormalizes_weights() -> None:
    llm = PanelFailureLLM(fail_reviewer="feasibility")
    workflow = _make_workflow(llm)
    repo = workflow._repository
    run_id = workflow.create(_request())

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    for ranked in result.candidates:
        assert "feasibility" not in ranked.dimension_scores
        assert len(ranked.reviews) == 5
        # No fabricated fill: weighted score stays within the observed range.
        assert 0 <= ranked.weighted_score <= 100
    assert "review_dimension_unavailable" in _event_types(repo, run_id)


class DuplicateRegenerationLLM(FakeStructuredLLM):
    def __init__(self) -> None:
        super().__init__(novelty_failures_before_pass=1)

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
    ) -> tuple[T, dict[str, int | str | None]]:
        value, metadata = await super().generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            temperature=temperature,
        )
        if response_model is CandidateEnvelope and self.candidate_calls >= 3:
            candidates = value.candidates
            candidates[1] = candidates[1].model_copy(update={"name": candidates[0].name})
            value = CandidateEnvelope(candidates=candidates)  # type: ignore[assignment]
        return value, metadata


@pytest.mark.asyncio
async def test_invalid_novelty_regeneration_uses_last_valid_candidates() -> None:
    workflow = _make_workflow(DuplicateRegenerationLLM())
    repo = workflow._repository
    run_id = workflow.create(_request())

    await workflow.execute(run_id)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    names = [item.candidate.name for item in result.candidates]
    assert len(names) == len(set(names))
    assert any(
        event.event_type == "stage_degraded"
        and event.payload.get("stage") == "novelty_audit"
        for event in repo.list_events(run_id)
    )


# --------------------------------------------------------------------------- #
# Terminal-state guarantees                                                   #
# --------------------------------------------------------------------------- #


class SlowLLM(FakeStructuredLLM):
    def __init__(self, *, delay: float) -> None:
        super().__init__()
        self.delay = delay

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
    ) -> tuple[T, dict[str, int | str | None]]:
        import asyncio

        await asyncio.sleep(self.delay)
        return await super().generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            temperature=temperature,
        )


class NeverReturningLLM:
    """A provider call that only exits when cancellation reaches it."""

    model_name = "never-returning-model"

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
    ) -> tuple[T, dict[str, int | str | None]]:
        del system_prompt, user_prompt, response_model, temperature
        await asyncio.Event().wait()
        raise AssertionError("unreachable")


@pytest.mark.asyncio
async def test_never_returning_provider_completes_with_bounded_fallbacks() -> None:
    workflow = ForecastWorkflow(
        repository=InMemoryRunRepository(),
        evidence_store=LocalEvidenceStore(_DATA / "evidence"),
        competitor_store=LocalCompetitorStore(_DATA / "competitors"),
        llm=NeverReturningLLM(),
        stage_timeout_seconds=0.01,
        timeout_seconds=2,
    )
    repo = workflow._repository
    run_id = workflow.create(_request())

    await asyncio.wait_for(workflow.execute(run_id), timeout=1)
    result = workflow.get_result(run_id)

    assert result.run.status == RunStatus.COMPLETED, result.run.error
    assert len(result.lens_forecasts) == 4
    assert len(result.opportunities) == 5
    assert len(result.candidates) == 3
    completed = _completed_event_payload(repo, run_id)
    assert completed.get("degraded") is True
    degraded_stages = {
        event.payload.get("stage")
        for event in repo.list_events(run_id)
        if event.event_type == "stage_degraded"
    }
    assert {
        "future_forecasting",
        "forecast_deliberation",
        "consensus_formation",
        "opportunity_synthesis",
        "competitor_analysis",
        "current_capability_audit",
        "candidate_generation",
        "novelty_audit",
        "portfolio_diversity_audit",
        "candidate_review",
    } <= degraded_stages

    product = await asyncio.wait_for(
        workflow.define_selected_product(
            run_id,
            ProductSelectionRequest(candidate_id=result.candidates[0].candidate.id),
        ),
        timeout=1,
    )
    assert product.source_run_id == run_id
    assert product.source_candidate_id == result.candidates[0].candidate.id


@pytest.mark.asyncio
async def test_global_workflow_timeout_reaches_terminal_state() -> None:
    workflow = _make_workflow(SlowLLM(delay=0.05), timeout_seconds=0.01)
    repo = workflow._repository
    run_id = workflow.create(_request())

    await workflow.execute(run_id)

    run = repo.get_run(run_id)
    assert run is not None
    assert run.status == RunStatus.FAILED
    assert run.stage == "timed_out"
    assert "run_failed" in _event_types(repo, run_id)


@pytest.mark.asyncio
async def test_heartbeat_emitted_during_slow_stage() -> None:
    workflow = _make_workflow(
        SlowLLM(delay=0.05), timeout_seconds=30, heartbeat_seconds=0.02
    )
    repo = workflow._repository
    run_id = workflow.create(_request())

    await workflow.execute(run_id)

    run = repo.get_run(run_id)
    assert run is not None
    assert run.status == RunStatus.COMPLETED, run.error
    assert "llm_call_heartbeat" in _event_types(repo, run_id)


# --------------------------------------------------------------------------- #
# Run-create idempotency (double-click protection)                            #
# --------------------------------------------------------------------------- #


def test_repeated_create_with_same_key_returns_one_run() -> None:
    workflow = _make_workflow(FakeStructuredLLM())
    request = _request()

    run_id_1, created_1 = workflow.create_idempotent(request, "click-key-123456")
    run_id_2, created_2 = workflow.create_idempotent(request, "click-key-123456")

    assert created_1 is True
    assert created_2 is False
    assert run_id_1 == run_id_2


# --------------------------------------------------------------------------- #
# Chaos: random recoverable failures never leave a run hung or unbounded      #
# --------------------------------------------------------------------------- #


class ChaosLLM(FakeStructuredLLM):
    """Randomly injects recoverable failures across all agent calls."""

    _KINDS = ["truncated", "empty_response", "invalid_json", "provider_timeout"]

    def __init__(self, *, seed: int, failure_rate: float = 0.12) -> None:
        super().__init__()
        self._rng = random.Random(seed)
        self._failure_rate = failure_rate
        self.calls = 0

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
    ) -> tuple[T, dict[str, int | str | None]]:
        self.calls += 1
        if self._rng.random() < self._failure_rate:
            kind = self._rng.choice(self._KINDS)
            raise LLMGenerationError(
                f"chaos-injected {kind}",
                failure_kind=kind,
                attempts=3,
                detail="chaos",
                metadata=dict(_META),
            )
        return await super().generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            temperature=temperature,
        )


@pytest.mark.asyncio
async def test_chaos_runs_always_reach_terminal_state() -> None:
    terminal = {RunStatus.COMPLETED, RunStatus.FAILED}
    completed = 0
    call_ceiling = 400
    runs = 20

    for index in range(runs):
        llm = ChaosLLM(seed=1000 + index)
        workflow = _make_workflow(llm)
        repo = workflow._repository
        run_id = workflow.create(_request())

        await workflow.execute(run_id)

        run = repo.get_run(run_id)
        assert run is not None
        # No run is ever left pending/running: every run has a terminal state.
        assert run.status in terminal, f"run {index} stuck at {run.status}/{run.stage}"
        # Retries and total calls stay bounded — no infinite loops.
        assert llm.calls <= call_ceiling, f"run {index} made {llm.calls} calls"
        if run.status == RunStatus.COMPLETED:
            completed += 1

    # Recoverable failures do not terminate the whole chain: some runs still
    # complete despite injected truncation / empty / invalid_json / timeout.
    assert completed >= 1
