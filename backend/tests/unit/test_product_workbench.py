"""Tests for the Product Definition Workbench (Q&A, revisions, readiness).

These reuse the full forecast pipeline fake from ``test_workflow`` to build a
real ProductSpec from real local artifacts, then exercise the workbench. No LLM
API key is ever required — everything runs against ``FakeStructuredLLM``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel
from test_workflow import FakeStructuredLLM, _product_spec

from eufy_security_agents.domain.models import (
    AnswerMode,
    CapabilityDelta,
    DefinitionStatus,
    EpistemicStatus,
    ForecastRequest,
    ProductAnswerDraft,
    ProductAnswerDraftChange,
    ProductAnswerDraftClaim,
    ProductAnswerEnvelope,
    ProductDesignIssueDraft,
    ProductProposalEnvelope,
    ProductQuestionRequest,
    ProductRevisionDecision,
    ProductRevisionRequest,
    ProductSelectionRequest,
    ProductSpec,
    ProductSpecEnvelope,
    QuestionCategory,
    RunStatus,
)
from eufy_security_agents.domain.product_workbench import classify_question, evaluate_readiness
from eufy_security_agents.infrastructure.competitors import LocalCompetitorStore
from eufy_security_agents.infrastructure.evidence import LocalEvidenceStore
from eufy_security_agents.infrastructure.memory import InMemoryRunRepository
from eufy_security_agents.orchestration.workflow import DefinitionNotReadyError, ForecastWorkflow

T = TypeVar("T", bound=BaseModel)

DATA = Path(__file__).resolve().parents[2] / "data"


class WorkbenchFakeLLM(FakeStructuredLLM):
    """Adds analyst answers and reviser output on top of the full-pipeline fake."""

    def __init__(
        self,
        *,
        mode: AnswerMode = AnswerMode.EXPLANATION,
        cite_illegal: bool = False,
    ) -> None:
        super().__init__()
        self.mode = mode
        self.cite_illegal = cite_illegal
        self.answer_prompts: list[str] = []

    @staticmethod
    def _privacy_change() -> ProductAnswerDraftChange:
        return ProductAnswerDraftChange(
            section="privacy",
            current_summary="当前隐私原则未定义访客数据保留时间。",
            proposed_change="补充访客数据保留与删除策略。",
            rationale="缺失会带来合规与信任风险。",
        )

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        temperature: float = 0.4,
    ) -> tuple[T, dict[str, int | str | None]]:
        if response_model is ProductSpecEnvelope and "用户已接受的修改建议" in user_prompt:
            revised = _product_spec().model_copy(
                update={
                    "privacy_principles": [
                        "Data minimization",
                        "访客数据默认 24 小时后本地删除",
                    ]
                }
            )
            return ProductSpecEnvelope(product=revised), self._metadata()  # type: ignore[return-value]

        if response_model is ProductProposalEnvelope:
            return (
                ProductProposalEnvelope(suggested_changes=[self._privacy_change()]),
                self._metadata(),
            )  # type: ignore[return-value]

        if response_model is ProductAnswerEnvelope:
            self.answer_prompts.append(user_prompt)
            allowed_ev, allowed_comp = self._allowed_ids(user_prompt)
            claims = [
                ProductAnswerDraftClaim(
                    text="该产品的本地推理能力有据可循。",
                    epistemic_status=EpistemicStatus.EVIDENCE_SUPPORTED,
                    evidence_ids=[allowed_ev[0]] if allowed_ev else [],
                ),
                ProductAnswerDraftClaim(
                    text="断网续航时长目前仍是产品设计假设。",
                    epistemic_status=EpistemicStatus.DESIGN_ASSUMPTION,
                ),
            ]
            if allowed_comp:
                claims.append(
                    ProductAnswerDraftClaim(
                        text="与主流竞品相比存在可防御差异。",
                        epistemic_status=EpistemicStatus.EVIDENCE_SUPPORTED,
                        competitor_evidence_ids=[allowed_comp[0]],
                    )
                )
            if self.cite_illegal:
                claims.append(
                    ProductAnswerDraftClaim(
                        text="这条结论引用了不存在的证据。",
                        epistemic_status=EpistemicStatus.EVIDENCE_SUPPORTED,
                        evidence_ids=["EV-FAKE-999", "OPP-001"],
                    )
                )
            design_issue = None
            suggestions: list[ProductAnswerDraftChange] = []
            if self.mode == AnswerMode.ISSUE_DETECTED:
                design_issue = ProductDesignIssueDraft(
                    title="访客数据保留周期未定义",
                    description="隐私原则没有说明访客数据保留多久、如何删除。",
                    affected_sections=["privacy", "not_a_real_section"],
                    severity="medium",
                    reason="必要的隐私决策缺失。",
                    blocks_readiness=True,
                )
            elif self.mode == AnswerMode.CHANGE_REQUEST:
                suggestions = [self._privacy_change()]
            answer = ProductAnswerDraft(
                answer_mode=self.mode,
                direct_answer="产品定义审查 Agent 的直接回答。",
                claims=claims,
                assumptions=["用户愿意在断网时依赖本地能力。"],
                unknowns=["不同地区的数据保留法规差异尚不明确。"],
                affected_sections=["privacy", "not_a_real_section"],
                design_issue=design_issue,
                suggested_changes=suggestions,
            )
            return ProductAnswerEnvelope(answer=answer), self._metadata()  # type: ignore[return-value]

        return await super().generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=response_model,
            temperature=temperature,
        )

    @staticmethod
    def _allowed_ids(prompt: str) -> tuple[list[str], list[str]]:
        ev_match = re.search(r"只能来自 (\[[^\]]*\])；涉及竞品", prompt)
        comp_match = re.search(r"competitor_evidence_ids 只能来自 (\[[^\]]*\])", prompt)
        allowed_ev = re.findall(r"EV-[A-Z0-9-]+", ev_match.group(1)) if ev_match else []
        allowed_comp = re.findall(r"COMP-[A-Z0-9-]+", comp_match.group(1)) if comp_match else []
        return allowed_ev, allowed_comp

    @staticmethod
    def _metadata() -> dict[str, int | str | None]:
        return {
            "model_name": "fake-model",
            "input_tokens": 100,
            "output_tokens": 200,
            "duration_ms": 10,
        }


async def _defined_product(
    llm: WorkbenchFakeLLM,
) -> tuple[ForecastWorkflow, InMemoryRunRepository, ProductSpec, str, str]:
    repository = InMemoryRunRepository()
    workflow = ForecastWorkflow(
        repository=repository,
        evidence_store=LocalEvidenceStore(DATA / "evidence"),
        competitor_store=LocalCompetitorStore(DATA / "competitors"),
        llm=llm,
    )
    run_id = workflow.create(
        ForecastRequest(
            question="预测未来三年美国eufy Security的AI原生消费电子产品机会",
            regions=["United States"],
            target_users=["Households"],
            candidate_count=3,
        )
    )
    await workflow.execute(run_id)
    result = workflow.get_result(run_id)
    assert result.run.status == RunStatus.COMPLETED, result.run.error
    chosen = result.candidates[0].candidate
    product = await workflow.define_selected_product(
        run_id,
        ProductSelectionRequest(candidate_id=chosen.id, selection_reason="测试选择"),
    )
    return workflow, repository, product, run_id, chosen.id


# --------------------------------------------------------------------------- #
# Pure helpers                                                                #
# --------------------------------------------------------------------------- #


def test_classify_question_routes_by_topic() -> None:
    assert classify_question("断网后还能工作吗？哪些能力可以在端侧运行？") == (
        QuestionCategory.TECHNOLOGY
    )
    assert classify_question("最接近的竞品是什么？与 Ring 有什么本质区别？") == (
        QuestionCategory.COMPETITION
    )
    assert classify_question("如何保护儿童、老人和访客的隐私？") == QuestionCategory.PRIVACY
    assert classify_question("如果不采用订阅模式，商业上如何成立？") == QuestionCategory.BUSINESS
    assert classify_question("它与 HomeBase 3 有什么关系？") == QuestionCategory.ECOSYSTEM
    assert classify_question("讲个笑话") == QuestionCategory.GENERAL


def _complete_spec() -> ProductSpec:
    """A ProductSpec that satisfies every deterministic readiness blocker."""

    return _product_spec().model_copy(
        update={
            "capability_delta": CapabilityDelta(
                new_capabilities=["new sensing outcome"],
                hardware_or_system_delta="A new distributed sensing architecture.",
            )
        }
    )


def test_readiness_blocks_on_outstanding_suggestions() -> None:
    product = _complete_spec()
    ready = evaluate_readiness(product, outstanding_suggestions=0)
    assert ready.ready is True
    assert ready.score == 100
    blocked = evaluate_readiness(product, outstanding_suggestions=2)
    assert blocked.ready is False
    assert any(item.id == "no_outstanding_suggestions" for item in blocked.blocking_items)
    assert blocked.outstanding_suggestions == 2


def test_readiness_flags_missing_sections() -> None:
    incomplete = _complete_spec().model_copy(update={"privacy_principles": [], "kill_criteria": []})
    readiness = evaluate_readiness(incomplete, outstanding_suggestions=0)
    assert readiness.ready is False
    blocking_ids = {item.id for item in readiness.blocking_items}
    assert {"privacy", "kill_criteria"} <= blocking_ids
    assert readiness.next_recommended_questions


def test_legacy_product_spec_without_workbench_fields_still_parses() -> None:
    legacy = {
        "id": "product-legacy",
        "source_run_id": "forecast-legacy",
        "source_candidate_id": "CAND-001",
        "name": "Legacy Product",
        "one_sentence_definition": "A previously defined product.",
        "category": "eufy Security",
        "target_users": ["Households"],
        "target_regions": ["United States"],
        "core_problem": "problem",
        "value_proposition": "value",
        "form_factor": "hardware",
        "hardware_architecture": ["sensor"],
        "ai_capabilities": ["local inference"],
        "ai_decision_boundary": "approval required",
        "user_journeys": ["install"],
        "ecosystem_relationships": ["HomeBase"],
        "privacy_principles": ["data minimization"],
        "business_model": {
            "hardware_revenue": "sale",
            "ecosystem_pull_through": ["HomeBase"],
            "cost_drivers": ["sensors"],
        },
        "risks": [],
        "key_assumptions": ["assumption"],
        "kill_criteria": ["kill"],
        "evidence_ids": ["EV-EUFY-001"],
        "validation_readiness": [],
    }
    product = ProductSpec.model_validate(legacy)
    assert product.definition_status == DefinitionStatus.DRAFT
    assert product.last_change_reason is None
    assert product.version == "1.0"


# --------------------------------------------------------------------------- #
# Q&A                                                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_question_reads_real_artifacts_and_labels_claims() -> None:
    workflow, _, product, run_id, _ = await _defined_product(WorkbenchFakeLLM())
    record = await workflow.answer_product_question(
        product.id,
        ProductQuestionRequest(question="哪些能力可以在端侧运行，哪些必须依赖云端？"),
    )
    answer = record.answer
    assert record.question.category == QuestionCategory.TECHNOLOGY
    # A plain understanding question defaults to explanation and proposes nothing.
    assert answer.answer_mode == AnswerMode.EXPLANATION
    assert answer.design_issue is None
    assert answer.suggested_changes == []
    # Grounded on real retrieved evidence from the source run.
    assert answer.context_evidence_ids
    assert all(evidence_id.startswith("EV-") for evidence_id in answer.context_evidence_ids)
    statuses = {claim.epistemic_status for claim in answer.claims}
    assert EpistemicStatus.EVIDENCE_SUPPORTED in statuses
    assert EpistemicStatus.DESIGN_ASSUMPTION in statuses
    assert answer.assumptions and answer.unknowns
    # affected_sections is filtered to the canonical vocabulary.
    assert "not_a_real_section" not in answer.affected_sections
    assert "privacy" in answer.affected_sections


@pytest.mark.asyncio
async def test_technology_and_competition_questions_get_different_context() -> None:
    llm = WorkbenchFakeLLM()
    workflow, _, product, _, _ = await _defined_product(llm)
    await workflow.answer_product_question(
        product.id, ProductQuestionRequest(question="哪些能力可以在端侧运行？断网后如何工作？")
    )
    await workflow.answer_product_question(
        product.id, ProductQuestionRequest(question="最接近的竞品是什么？与 Ring 有何差异？")
    )
    technology_prompt, competition_prompt = llm.answer_prompts[-2], llm.answer_prompts[-1]
    assert technology_prompt != competition_prompt
    # Competition questions receive competitor records; technology questions do not.
    assert "competitor_digest" in competition_prompt
    assert "COMP-" in competition_prompt
    assert "competitor_digest" not in technology_prompt


@pytest.mark.asyncio
async def test_illegal_evidence_ids_are_repaired_and_downgraded() -> None:
    workflow, _, product, _, _ = await _defined_product(WorkbenchFakeLLM(cite_illegal=True))
    record = await workflow.answer_product_question(
        product.id, ProductQuestionRequest(question="这个产品的隐私方案如何？")
    )
    answer = record.answer
    allowed = set(answer.context_evidence_ids) | set(answer.context_competitor_ids)
    for claim in answer.claims:
        for reference in [*claim.evidence_ids, *claim.competitor_evidence_ids]:
            assert reference in allowed
            assert not reference.startswith("OPP-")
    # The fabricated claim must have been downgraded, not trusted.
    assert answer.integrity_notes
    assert any(
        claim.epistemic_status == EpistemicStatus.INSUFFICIENT_EVIDENCE
        and not claim.evidence_ids
        and not claim.competitor_evidence_ids
        for claim in answer.claims
    )


@pytest.mark.asyncio
async def test_asking_a_question_does_not_mutate_the_spec() -> None:
    workflow, repository, product, _, _ = await _defined_product(WorkbenchFakeLLM())
    await workflow.answer_product_question(
        product.id, ProductQuestionRequest(question="断网后还能工作吗？")
    )
    stored = repository.get_product(product.id)
    assert stored is not None
    assert stored.version == "1.0"
    assert stored.name == product.name
    assert stored.privacy_principles == product.privacy_principles
    # A pure explanation question must not change anything, including status.
    assert stored.definition_status == DefinitionStatus.DRAFT


@pytest.mark.asyncio
async def test_question_idempotency_key_returns_same_record() -> None:
    workflow, _, product, _, _ = await _defined_product(WorkbenchFakeLLM())
    first = await workflow.answer_product_question(
        product.id,
        ProductQuestionRequest(question="断网后还能工作吗？", idempotency_key="dup-question-1"),
    )
    second = await workflow.answer_product_question(
        product.id,
        ProductQuestionRequest(question="断网后还能工作吗？", idempotency_key="dup-question-1"),
    )
    assert first.answer.id == second.answer.id
    assert len(workflow.list_product_questions(product.id)) == 1


# --------------------------------------------------------------------------- #
# Revisions                                                                    #
# --------------------------------------------------------------------------- #


async def _ask_and_get_suggestion(workflow: ForecastWorkflow, product_id: str) -> str:
    record = await workflow.answer_product_question(
        product_id, ProductQuestionRequest(question="访客数据保留多久？")
    )
    assert record.answer.suggested_changes
    return record.answer.suggested_changes[0].id


@pytest.mark.asyncio
async def test_accepting_a_suggestion_bumps_version_and_records_revision() -> None:
    workflow, _, product, run_id, candidate_id = await _defined_product(
        WorkbenchFakeLLM(mode=AnswerMode.CHANGE_REQUEST)
    )
    suggestion_id = await _ask_and_get_suggestion(workflow, product.id)

    revised = await workflow.revise_product(
        product.id,
        ProductRevisionRequest(decisions=[ProductRevisionDecision(suggestion_id=suggestion_id)]),
    )
    assert revised.version == "1.1"
    assert revised.source_run_id == run_id
    assert revised.source_candidate_id == candidate_id
    assert "访客数据默认 24 小时后本地删除" in revised.privacy_principles
    assert revised.definition_status == DefinitionStatus.UNDER_REVIEW
    assert revised.last_change_reason

    revisions = workflow.list_product_revisions(product.id)
    assert len(revisions) == 1
    assert revisions[0].from_version == "1.0"
    assert revisions[0].to_version == "1.1"
    assert revisions[0].before_snapshot.version == "1.0"
    assert revisions[0].after_snapshot.version == "1.1"


@pytest.mark.asyncio
async def test_dismissing_a_suggestion_does_not_change_the_spec() -> None:
    workflow, repository, product, _, _ = await _defined_product(
        WorkbenchFakeLLM(mode=AnswerMode.CHANGE_REQUEST)
    )
    suggestion_id = await _ask_and_get_suggestion(workflow, product.id)

    readiness = workflow.resolve_suggestions(product.id, [suggestion_id])
    stored = repository.get_product(product.id)
    assert stored is not None
    assert stored.version == "1.0"
    assert stored.privacy_principles == product.privacy_principles
    assert workflow.list_product_revisions(product.id) == []
    assert readiness.outstanding_suggestions == 0


@pytest.mark.asyncio
async def test_revision_is_idempotent() -> None:
    workflow, _, product, _, _ = await _defined_product(
        WorkbenchFakeLLM(mode=AnswerMode.CHANGE_REQUEST)
    )
    suggestion_id = await _ask_and_get_suggestion(workflow, product.id)
    request = ProductRevisionRequest(
        decisions=[ProductRevisionDecision(suggestion_id=suggestion_id)],
        idempotency_key="revision-key-1",
    )
    first = await workflow.revise_product(product.id, request)
    second = await workflow.revise_product(product.id, request)
    assert first.version == "1.1"
    assert second.version == "1.1"
    assert len(workflow.list_product_revisions(product.id)) == 1


# --------------------------------------------------------------------------- #
# Readiness & confirmation                                                     #
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_confirm_is_blocked_while_a_suggestion_is_outstanding() -> None:
    workflow, _, product, _, _ = await _defined_product(
        WorkbenchFakeLLM(mode=AnswerMode.CHANGE_REQUEST)
    )
    await _ask_and_get_suggestion(workflow, product.id)

    readiness = workflow.product_readiness(product.id)
    assert readiness.ready is False
    with pytest.raises(DefinitionNotReadyError):
        workflow.confirm_product(product.id)


@pytest.mark.asyncio
async def test_confirm_sets_validation_ready_when_ready() -> None:
    workflow, _, product, _, _ = await _defined_product(
        WorkbenchFakeLLM(mode=AnswerMode.CHANGE_REQUEST)
    )
    suggestion_id = await _ask_and_get_suggestion(workflow, product.id)
    workflow.resolve_suggestions(product.id, [suggestion_id])

    confirmed = workflow.confirm_product(product.id)
    assert confirmed.definition_status == DefinitionStatus.VALIDATION_READY


@pytest.mark.asyncio
async def test_revising_a_validation_ready_product_reverts_to_under_review() -> None:
    workflow, _, product, _, _ = await _defined_product(
        WorkbenchFakeLLM(mode=AnswerMode.CHANGE_REQUEST)
    )
    first_suggestion = await _ask_and_get_suggestion(workflow, product.id)
    workflow.resolve_suggestions(product.id, [first_suggestion])
    confirmed = workflow.confirm_product(product.id)
    assert confirmed.definition_status == DefinitionStatus.VALIDATION_READY

    second_suggestion = await _ask_and_get_suggestion(workflow, product.id)
    revised = await workflow.revise_product(
        product.id,
        ProductRevisionRequest(
            decisions=[ProductRevisionDecision(suggestion_id=second_suggestion)]
        ),
    )
    assert revised.definition_status == DefinitionStatus.UNDER_REVIEW
    assert revised.version == "1.1"


# --------------------------------------------------------------------------- #
# Answer modes                                                                 #
# --------------------------------------------------------------------------- #


def test_readiness_blocks_on_open_design_issues() -> None:
    product = _complete_spec()
    blocked = evaluate_readiness(product, outstanding_issues=1)
    assert blocked.ready is False
    assert any(item.id == "no_open_issues" for item in blocked.blocking_items)


@pytest.mark.asyncio
async def test_change_request_returns_suggestions_directly() -> None:
    workflow, _, product, _, _ = await _defined_product(
        WorkbenchFakeLLM(mode=AnswerMode.CHANGE_REQUEST)
    )
    record = await workflow.answer_product_question(
        product.id, ProductQuestionRequest(question="把访客人脸特征改成 24 小时后自动删除。")
    )
    assert record.answer.answer_mode == AnswerMode.CHANGE_REQUEST
    assert record.answer.design_issue is None
    assert record.answer.suggested_changes


@pytest.mark.asyncio
async def test_issue_detected_defers_proposal_and_blocks_readiness() -> None:
    workflow, _, product, _, _ = await _defined_product(
        WorkbenchFakeLLM(mode=AnswerMode.ISSUE_DETECTED)
    )
    record = await workflow.answer_product_question(
        product.id, ProductQuestionRequest(question="访客人脸数据会保存多久？")
    )
    answer = record.answer
    assert answer.answer_mode == AnswerMode.ISSUE_DETECTED
    assert answer.design_issue is not None
    # An issue surfaces a gap but proposes no change until the user asks.
    assert answer.suggested_changes == []
    readiness = workflow.product_readiness(product.id)
    assert readiness.ready is False
    assert any(item.id == "no_open_issues" for item in readiness.blocking_items)


@pytest.mark.asyncio
async def test_generating_a_proposal_then_accepting_resolves_the_issue() -> None:
    workflow, _, product, _, _ = await _defined_product(
        WorkbenchFakeLLM(mode=AnswerMode.ISSUE_DETECTED)
    )
    record = await workflow.answer_product_question(
        product.id, ProductQuestionRequest(question="访客人脸数据会保存多久？")
    )
    assert record.answer.design_issue is not None
    issue_id = record.answer.design_issue.id

    updated = await workflow.generate_issue_proposal(product.id, record.question.id)
    assert updated.answer.suggested_changes
    suggestion = updated.answer.suggested_changes[0]
    assert suggestion.source_issue_id == issue_id

    revised = await workflow.revise_product(
        product.id,
        ProductRevisionRequest(decisions=[ProductRevisionDecision(suggestion_id=suggestion.id)]),
    )
    assert revised.version == "1.1"
    readiness = workflow.product_readiness(product.id)
    assert not any(item.id == "no_open_issues" for item in readiness.blocking_items)
    listed = workflow.list_product_questions(product.id)
    assert listed[0].answer.design_issue is not None
    assert listed[0].answer.design_issue.resolution == "addressed"


@pytest.mark.asyncio
async def test_generating_a_proposal_requires_a_detected_issue() -> None:
    workflow, _, product, _, _ = await _defined_product(WorkbenchFakeLLM())
    record = await workflow.answer_product_question(
        product.id, ProductQuestionRequest(question="断网后还能工作吗？")
    )
    # An explanation answer has no issue to turn into a proposal.
    with pytest.raises(ValueError):
        await workflow.generate_issue_proposal(product.id, record.question.id)


@pytest.mark.asyncio
async def test_dismissing_a_design_issue_clears_the_readiness_block() -> None:
    workflow, repository, product, _, _ = await _defined_product(
        WorkbenchFakeLLM(mode=AnswerMode.ISSUE_DETECTED)
    )
    record = await workflow.answer_product_question(
        product.id, ProductQuestionRequest(question="访客人脸数据会保存多久？")
    )
    assert record.answer.design_issue is not None
    issue_id = record.answer.design_issue.id
    assert any(
        item.id == "no_open_issues"
        for item in workflow.product_readiness(product.id).blocking_items
    )

    readiness = workflow.resolve_design_issues(product.id, [issue_id])
    assert not any(item.id == "no_open_issues" for item in readiness.blocking_items)
    # Dismissing an issue must not change the spec.
    stored = repository.get_product(product.id)
    assert stored is not None
    assert stored.version == "1.0"
