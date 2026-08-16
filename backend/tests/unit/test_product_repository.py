"""SQLite persistence for the Product Definition Workbench tables."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from test_workflow import _product_spec

from eufy_security_agents.domain.models import AgentEvent, Artifact, ForecastRequest
from eufy_security_agents.domain.models import (
    DefinitionStatus,
    ProductQuestion,
    ProductQuestionAnswer,
    ProductQuestionRecord,
    ProductRevision,
    ProductSpec,
    QuestionCategory,
    RunStatus,
    SuggestionResolution,
)
from eufy_security_agents.domain.validation import ValidationProject, ValidationProjectStatus
from eufy_security_agents.domain.validation_insights import SurveyResponse, ValidationSurvey
from eufy_security_agents.infrastructure.repositories import SqlAlchemyRunRepository


def _repository(tmp_path: Path) -> SqlAlchemyRunRepository:
    return SqlAlchemyRunRepository(f"sqlite:///{(tmp_path / 'app.db').as_posix()}")


def _question_record(product_id: str) -> ProductQuestionRecord:
    question = ProductQuestion(
        id="pq-1",
        product_id=product_id,
        product_version="1.0",
        question="访客数据保留多久？",
        category=QuestionCategory.PRIVACY,
    )
    answer = ProductQuestionAnswer(
        id="pa-1",
        question_id="pq-1",
        product_id=product_id,
        product_version="1.0",
        category=QuestionCategory.PRIVACY,
        direct_answer="当前资料不足。",
    )
    return ProductQuestionRecord(question=question, answer=answer)


def test_product_upsert_keeps_created_at_stable(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    product = _product_spec().model_copy(update={"id": "product-1", "source_run_id": "forecast-1"})
    repository.save_product(product)

    updated = product.model_copy(update={"version": "1.1", "name": "Renamed"})
    repository.save_product(updated)

    stored = repository.get_product("product-1")
    assert stored is not None
    assert stored.version == "1.1"
    assert stored.name == "Renamed"
    assert stored.created_at == product.created_at


def test_legacy_product_row_reads_with_defaulted_fields(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    # A ProductSpec whose payload predates the workbench fields still validates.
    legacy = _product_spec().model_copy(update={"id": "product-legacy"})
    payload = legacy.model_dump()
    payload.pop("definition_status", None)
    payload.pop("last_change_reason", None)
    repository.save_product(ProductSpec.model_validate(payload))

    stored = repository.get_product("product-legacy")
    assert stored is not None
    assert stored.definition_status == DefinitionStatus.DRAFT


def test_question_records_persist_and_dedupe_by_key(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    record = _question_record("product-1")
    repository.save_question_record(record, idempotency_key="key-1")

    assert len(repository.list_question_records("product-1")) == 1
    found = repository.find_question_record_by_key("product-1", "key-1")
    assert found is not None
    assert found.answer.question_id == "pa-1" or found.answer.id == "pa-1"
    assert repository.find_question_record_by_key("product-1", "missing") is None


def test_revisions_and_resolutions_round_trip(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    before = _product_spec().model_copy(update={"id": "product-1", "version": "1.0"})
    after = before.model_copy(update={"version": "1.1"})
    revision = ProductRevision(
        id="rev-1",
        product_id="product-1",
        from_version="1.0",
        to_version="1.1",
        change_reason="apply accepted change",
        before_snapshot=before,
        after_snapshot=after,
    )
    repository.save_revision(revision, idempotency_key="rev-key")

    revisions = repository.list_revisions("product-1")
    assert len(revisions) == 1
    assert revisions[0].to_version == "1.1"
    assert repository.find_revision_by_key("product-1", "rev-key") is not None

    repository.save_suggestion_resolution(
        SuggestionResolution(suggestion_id="sc-1", product_id="product-1", resolution="dismissed")
    )
    # Resolving the same suggestion again upserts rather than duplicating.
    repository.save_suggestion_resolution(
        SuggestionResolution(
            suggestion_id="sc-1", product_id="product-1", resolution="accepted", revision_id="rev-1"
        )
    )
    resolutions = repository.list_suggestion_resolutions("product-1")
    assert len(resolutions) == 1
    assert resolutions[0].resolution == "accepted"
    assert resolutions[0].revision_id == "rev-1"


def test_latest_selection_is_scoped_to_run(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    assert repository.get_latest_selection("forecast-1") is None

    repository.reserve_selection("forecast-1", "selection-one", "CAND-001")
    repository.reserve_selection("forecast-2", "selection-other", "CAND-009")
    repository.reserve_selection("forecast-1", "selection-two", "CAND-002")

    latest = repository.get_latest_selection("forecast-1")
    assert latest is not None
    assert latest.candidate_id == "CAND-002"


def test_delete_run_cascades_to_related_rows(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    request = ForecastRequest(question="Delete recent research run")
    run = repository.create_run(request)
    repository.update_run(run.id, status=RunStatus.COMPLETED, stage="done")

    product = _product_spec().model_copy(
        update={"id": "product-1", "source_run_id": run.id, "source_candidate_id": "CAND-001"}
    )
    repository.save_product(product)
    repository.save_question_record(_question_record(product.id), idempotency_key="q-key")
    repository.save_revision(
        ProductRevision(
            id="rev-1",
            product_id="product-1",
            from_version="1.0",
            to_version="1.1",
            change_reason="update",
            before_snapshot=product,
            after_snapshot=product.model_copy(update={"version": "1.1"}),
        ),
        idempotency_key="rev-key",
    )
    repository.save_suggestion_resolution(
        SuggestionResolution(suggestion_id="sc-1", product_id="product-1", resolution="accepted")
    )
    repository.reserve_selection(run.id, "selection-key", "CAND-001")
    repository.add_event(
        AgentEvent(
            run_id=run.id,
            sequence=1,
            event_type="agent_completed",
            message="done",
            payload={},
            created_at=datetime.now(UTC),
        )
    )
    repository.save_artifact(
        Artifact(
            id="artifact-1",
            run_id=run.id,
            kind="result",
            producer="forecast-consensus",
            payload={"ok": True},
            created_at=datetime.now(UTC),
        )
    )

    project = ValidationProject.model_construct(
        id="vproj-1",
        product_id=product.id,
        product_version=product.version,
        product_snapshot=product,
        status=ValidationProjectStatus.COMPLETED,
        experiments=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repository.save_validation_project(project)
    survey = ValidationSurvey.model_construct(
        id="survey-1",
        token="survey-token-1",
        project_id=project.id,
        product_id=product.id,
        product_name=product.name,
        title="survey",
        description="survey",
        questions=[],
        linked_experiment_ids=[],
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    repository.save_validation_survey(survey)
    repository.save_survey_response(
        SurveyResponse(id="resp-1", survey_id=survey.id, answers={}, created_at=datetime.now(UTC))
    )

    repository.delete_run(run.id)

    assert repository.get_run(run.id) is None
    assert repository.get_product(product.id) is None
    assert repository.list_question_records(product.id) == []
    assert repository.list_revisions(product.id) == []
    assert repository.list_suggestion_resolutions(product.id) == []
    assert repository.get_latest_selection(run.id) is None
    assert repository.list_events(run.id) == []
    assert repository.get_artifact(run.id, "result") is None
    assert repository.get_validation_project(project.id) is None
    assert repository.get_validation_survey_for_project(project.id) is None
    assert repository.list_survey_responses(survey.id) == []
    assert repository.count_runs() == 0
