"""SQLite persistence for the Product Definition Workbench tables."""

from __future__ import annotations

from pathlib import Path

from test_workflow import _product_spec

from eufy_security_agents.domain.models import (
    DefinitionStatus,
    ProductQuestion,
    ProductQuestionAnswer,
    ProductQuestionRecord,
    ProductRevision,
    ProductSpec,
    QuestionCategory,
    SuggestionResolution,
)
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
