"""SQLite persistence for runs, artifacts, events, and selected products."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, create_engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from eufy_security_agents.core.config import BACKEND_ROOT
from eufy_security_agents.domain.models import (
    AgentEvent,
    Artifact,
    ForecastRequest,
    ForecastRun,
    ForecastRunSummary,
    ProductQuestionRecord,
    ProductRevision,
    ProductSelectionState,
    ProductSpec,
    RunStatus,
    SelectionStatus,
    SuggestionResolution,
)


class Base(DeclarativeBase):
    pass


class ForecastRunRow(Base):
    __tablename__ = "forecast_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    stage: Mapped[str] = mapped_column(String(80))
    request_json: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ForecastRunKeyRow(Base):
    """Maps a client idempotency key to a run so a double-click / retry creates
    at most one forecast run. Kept in its own table so adding it needs no
    migration of the existing forecast_runs table."""

    __tablename__ = "forecast_run_keys"

    idempotency_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(80), index=True)
    producer: Mapped[str] = mapped_column(String(100))
    payload_json: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AgentEventRow(Base):
    __tablename__ = "agent_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(80))
    agent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProductRow(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    candidate_id: Mapped[str] = mapped_column(String(100), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProductQuestionRow(Base):
    __tablename__ = "product_questions"
    __table_args__ = (UniqueConstraint("product_id", "idempotency_key"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProductRevisionRow(Base):
    __tablename__ = "product_revisions"
    __table_args__ = (UniqueConstraint("product_id", "idempotency_key"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SuggestionResolutionRow(Base):
    __tablename__ = "product_suggestion_resolutions"
    __table_args__ = (UniqueConstraint("product_id", "suggestion_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    suggestion_id: Mapped[str] = mapped_column(String(64), index=True)
    resolution: Mapped[str] = mapped_column(String(40))
    revision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ProductSelectionRow(Base):
    __tablename__ = "product_selections"
    __table_args__ = (UniqueConstraint("run_id", "idempotency_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    candidate_id: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20))
    product_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        raw_path = database_url.removeprefix("sqlite:///")
        path = Path(raw_path)
        if not path.is_absolute():
            path = BACKEND_ROOT / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{path.as_posix()}"
    return database_url


class SqlAlchemyRunRepository:
    def __init__(self, database_url: str) -> None:
        url = normalize_database_url(database_url)
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self._engine = create_engine(url, connect_args=connect_args)
        self._sessions = sessionmaker(self._engine, expire_on_commit=False)
        Base.metadata.create_all(self._engine)

    def create_run(self, request: ForecastRequest) -> ForecastRun:
        now = datetime.now(UTC)
        row = ForecastRunRow(
            id=f"forecast-{uuid4().hex[:12]}",
            status=RunStatus.PENDING.value,
            stage="queued",
            request_json=request.model_dump_json(),
            error=None,
            created_at=now,
            updated_at=now,
        )
        with self._sessions.begin() as session:
            session.add(row)
        return self._run_model(row)

    def get_or_create_run(
        self, request: ForecastRequest, idempotency_key: str
    ) -> tuple[ForecastRun, bool]:
        existing_id = self._run_id_for_key(idempotency_key)
        if existing_id is not None:
            run = self.get_run(existing_id)
            if run is not None:
                return run, False
        now = datetime.now(UTC)
        new_id = f"forecast-{uuid4().hex[:12]}"
        try:
            with self._sessions.begin() as session:
                # Both rows commit atomically; a concurrent duplicate loses the
                # primary-key race on forecast_run_keys and is caught below.
                session.add(
                    ForecastRunKeyRow(
                        idempotency_key=idempotency_key,
                        run_id=new_id,
                        created_at=now,
                    )
                )
                session.add(
                    ForecastRunRow(
                        id=new_id,
                        status=RunStatus.PENDING.value,
                        stage="queued",
                        request_json=request.model_dump_json(),
                        error=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
        except IntegrityError:
            existing_id = self._run_id_for_key(idempotency_key)
            run = self.get_run(existing_id) if existing_id else None
            if run is None:  # pragma: no cover - unexpected race resolution
                raise
            return run, False
        run = self.get_run(new_id)
        if run is None:  # pragma: no cover - defensive persistence check
            raise RuntimeError("forecast run was not persisted")
        return run, True

    def _run_id_for_key(self, idempotency_key: str) -> str | None:
        with self._sessions() as session:
            row = session.get(ForecastRunKeyRow, idempotency_key)
            return row.run_id if row else None

    def get_run(self, run_id: str) -> ForecastRun | None:
        with self._sessions() as session:
            row = session.get(ForecastRunRow, run_id)
            return self._run_model(row) if row else None

    def list_runs(self, *, limit: int = 20) -> list[ForecastRunSummary]:
        statement = (
            select(ForecastRunRow)
            .order_by(ForecastRunRow.created_at.desc(), ForecastRunRow.id.desc())
            .limit(limit)
        )
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        return [self._run_summary_model(row) for row in rows]

    def count_runs(self) -> int:
        statement = select(func.count()).select_from(ForecastRunRow)
        with self._sessions() as session:
            return session.scalar(statement) or 0

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        stage: str | None = None,
        error: str | None = None,
    ) -> ForecastRun:
        with self._sessions.begin() as session:
            row = session.get(ForecastRunRow, run_id)
            if row is None:
                raise KeyError(run_id)
            if status is not None:
                row.status = status.value
            if stage is not None:
                row.stage = stage
            row.error = error
            row.updated_at = datetime.now(UTC)
        return self._run_model(row)

    def add_event(self, event: AgentEvent) -> AgentEvent:
        row = AgentEventRow(
            run_id=event.run_id,
            sequence=event.sequence,
            event_type=event.event_type,
            agent=event.agent,
            message=event.message,
            payload_json=json.dumps(event.payload, ensure_ascii=False),
            created_at=event.created_at,
        )
        with self._sessions.begin() as session:
            session.add(row)
        return event.model_copy(update={"id": row.id})

    def list_events(self, run_id: str, after_sequence: int = 0) -> list[AgentEvent]:
        statement = (
            select(AgentEventRow)
            .where(
                AgentEventRow.run_id == run_id,
                AgentEventRow.sequence > after_sequence,
            )
            .order_by(AgentEventRow.sequence)
        )
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        return [
            AgentEvent(
                id=row.id,
                run_id=row.run_id,
                sequence=row.sequence,
                event_type=row.event_type,
                agent=row.agent,
                message=row.message,
                payload=json.loads(row.payload_json),
                created_at=row.created_at,
            )
            for row in rows
        ]

    def save_artifact(self, artifact: Artifact) -> None:
        row = ArtifactRow(
            id=artifact.id,
            run_id=artifact.run_id,
            kind=artifact.kind,
            producer=artifact.producer,
            payload_json=json.dumps(artifact.payload, ensure_ascii=False, default=str),
            model_name=artifact.model_name,
            prompt_version=artifact.prompt_version,
            duration_ms=artifact.duration_ms,
            input_tokens=artifact.input_tokens,
            output_tokens=artifact.output_tokens,
            created_at=artifact.created_at,
        )
        with self._sessions.begin() as session:
            existing = session.get(ArtifactRow, artifact.id)
            if existing is not None:
                session.delete(existing)
                session.flush()
            session.add(row)

    def get_artifact(self, run_id: str, kind: str) -> Artifact | None:
        statement = (
            select(ArtifactRow)
            .where(ArtifactRow.run_id == run_id, ArtifactRow.kind == kind)
            .order_by(ArtifactRow.created_at.desc())
        )
        with self._sessions() as session:
            row = session.scalars(statement).first()
        if row is None:
            return None
        return Artifact(
            id=row.id,
            run_id=row.run_id,
            kind=row.kind,
            producer=row.producer,
            payload=json.loads(row.payload_json),
            model_name=row.model_name,
            prompt_version=row.prompt_version,
            duration_ms=row.duration_ms,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            created_at=row.created_at,
        )

    def list_artifacts(self, run_id: str) -> list[Artifact]:
        statement = (
            select(ArtifactRow).where(ArtifactRow.run_id == run_id).order_by(ArtifactRow.created_at)
        )
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        return [
            Artifact(
                id=row.id,
                run_id=row.run_id,
                kind=row.kind,
                producer=row.producer,
                payload=json.loads(row.payload_json),
                model_name=row.model_name,
                prompt_version=row.prompt_version,
                duration_ms=row.duration_ms,
                input_tokens=row.input_tokens,
                output_tokens=row.output_tokens,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def save_product(self, product: ProductSpec) -> None:
        # Upsert: the first selection inserts, later revisions update in place so
        # the product_id stays stable while payload_json carries the latest spec.
        with self._sessions.begin() as session:
            existing = session.get(ProductRow, product.id)
            if existing is not None:
                existing.run_id = product.source_run_id
                existing.candidate_id = product.source_candidate_id
                existing.payload_json = product.model_dump_json()
            else:
                session.add(
                    ProductRow(
                        id=product.id,
                        run_id=product.source_run_id,
                        candidate_id=product.source_candidate_id,
                        payload_json=product.model_dump_json(),
                        created_at=product.created_at,
                    )
                )

    def get_product(self, product_id: str) -> ProductSpec | None:
        with self._sessions() as session:
            row = session.get(ProductRow, product_id)
            return ProductSpec.model_validate_json(row.payload_json) if row else None

    def save_question_record(
        self, record: ProductQuestionRecord, *, idempotency_key: str | None
    ) -> None:
        with self._sessions.begin() as session:
            session.add(
                ProductQuestionRow(
                    id=record.answer.question_id,
                    product_id=record.question.product_id,
                    idempotency_key=idempotency_key,
                    payload_json=record.model_dump_json(),
                    created_at=record.question.created_at,
                )
            )

    def get_question_record(
        self, product_id: str, question_id: str
    ) -> ProductQuestionRecord | None:
        with self._sessions() as session:
            row = session.get(ProductQuestionRow, question_id)
        if row is None or row.product_id != product_id:
            return None
        return ProductQuestionRecord.model_validate_json(row.payload_json)

    def update_question_record(self, record: ProductQuestionRecord) -> None:
        with self._sessions.begin() as session:
            row = session.get(ProductQuestionRow, record.answer.question_id)
            if row is None:
                raise KeyError(record.answer.question_id)
            row.payload_json = record.model_dump_json()

    def list_question_records(self, product_id: str) -> list[ProductQuestionRecord]:
        statement = (
            select(ProductQuestionRow)
            .where(ProductQuestionRow.product_id == product_id)
            .order_by(ProductQuestionRow.created_at)
        )
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        return [ProductQuestionRecord.model_validate_json(row.payload_json) for row in rows]

    def find_question_record_by_key(
        self, product_id: str, idempotency_key: str
    ) -> ProductQuestionRecord | None:
        statement = select(ProductQuestionRow).where(
            ProductQuestionRow.product_id == product_id,
            ProductQuestionRow.idempotency_key == idempotency_key,
        )
        with self._sessions() as session:
            row = session.scalars(statement).first()
        return ProductQuestionRecord.model_validate_json(row.payload_json) if row else None

    def save_revision(self, revision: ProductRevision, *, idempotency_key: str | None) -> None:
        with self._sessions.begin() as session:
            session.add(
                ProductRevisionRow(
                    id=revision.id,
                    product_id=revision.product_id,
                    idempotency_key=idempotency_key,
                    payload_json=revision.model_dump_json(),
                    created_at=revision.created_at,
                )
            )

    def list_revisions(self, product_id: str) -> list[ProductRevision]:
        statement = (
            select(ProductRevisionRow)
            .where(ProductRevisionRow.product_id == product_id)
            .order_by(ProductRevisionRow.created_at)
        )
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        return [ProductRevision.model_validate_json(row.payload_json) for row in rows]

    def find_revision_by_key(
        self, product_id: str, idempotency_key: str
    ) -> ProductRevision | None:
        statement = select(ProductRevisionRow).where(
            ProductRevisionRow.product_id == product_id,
            ProductRevisionRow.idempotency_key == idempotency_key,
        )
        with self._sessions() as session:
            row = session.scalars(statement).first()
        return ProductRevision.model_validate_json(row.payload_json) if row else None

    def save_suggestion_resolution(self, resolution: SuggestionResolution) -> None:
        with self._sessions.begin() as session:
            existing = session.scalars(
                select(SuggestionResolutionRow).where(
                    SuggestionResolutionRow.product_id == resolution.product_id,
                    SuggestionResolutionRow.suggestion_id == resolution.suggestion_id,
                )
            ).first()
            if existing is not None:
                existing.resolution = resolution.resolution
                existing.revision_id = resolution.revision_id
                existing.created_at = resolution.created_at
            else:
                session.add(
                    SuggestionResolutionRow(
                        product_id=resolution.product_id,
                        suggestion_id=resolution.suggestion_id,
                        resolution=resolution.resolution,
                        revision_id=resolution.revision_id,
                        created_at=resolution.created_at,
                    )
                )

    def list_suggestion_resolutions(self, product_id: str) -> list[SuggestionResolution]:
        statement = (
            select(SuggestionResolutionRow)
            .where(SuggestionResolutionRow.product_id == product_id)
            .order_by(SuggestionResolutionRow.created_at)
        )
        with self._sessions() as session:
            rows = session.scalars(statement).all()
        return [
            SuggestionResolution(
                suggestion_id=row.suggestion_id,
                product_id=row.product_id,
                resolution=row.resolution,
                revision_id=row.revision_id,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def get_selection(self, run_id: str, idempotency_key: str) -> ProductSelectionState | None:
        statement = select(ProductSelectionRow).where(
            ProductSelectionRow.run_id == run_id,
            ProductSelectionRow.idempotency_key == idempotency_key,
        )
        with self._sessions() as session:
            row = session.scalars(statement).first()
        if row is None:
            return None
        return ProductSelectionState(
            run_id=row.run_id,
            idempotency_key=row.idempotency_key,
            candidate_id=row.candidate_id,
            status=SelectionStatus(row.status),
            product_id=row.product_id,
            error=row.error,
        )

    def reserve_selection(self, run_id: str, idempotency_key: str, candidate_id: str) -> bool:
        now = datetime.now(UTC)
        existing = self.get_selection(run_id, idempotency_key)
        if existing is not None:
            if existing.candidate_id != candidate_id:
                raise ValueError("idempotency key is already bound to another candidate")
            if existing.status != SelectionStatus.FAILED:
                return False
            with self._sessions.begin() as session:
                row = session.scalars(
                    select(ProductSelectionRow).where(
                        ProductSelectionRow.run_id == run_id,
                        ProductSelectionRow.idempotency_key == idempotency_key,
                    )
                ).one()
                row.status = SelectionStatus.IN_PROGRESS.value
                row.error = None
                row.updated_at = now
            return True
        try:
            with self._sessions.begin() as session:
                session.add(
                    ProductSelectionRow(
                        run_id=run_id,
                        idempotency_key=idempotency_key,
                        candidate_id=candidate_id,
                        status=SelectionStatus.IN_PROGRESS.value,
                        product_id=None,
                        error=None,
                        created_at=now,
                        updated_at=now,
                    )
                )
            return True
        except IntegrityError:
            return False

    def complete_selection(self, run_id: str, idempotency_key: str, product_id: str) -> None:
        self._update_selection(
            run_id,
            idempotency_key,
            status=SelectionStatus.COMPLETED,
            product_id=product_id,
            error=None,
        )

    def fail_selection(self, run_id: str, idempotency_key: str, error: str) -> None:
        self._update_selection(
            run_id,
            idempotency_key,
            status=SelectionStatus.FAILED,
            product_id=None,
            error=error,
        )

    def recover_interrupted_runs(self) -> int:
        with self._sessions.begin() as session:
            rows = session.scalars(
                select(ForecastRunRow).where(ForecastRunRow.status == RunStatus.RUNNING.value)
            ).all()
            now = datetime.now(UTC)
            for row in rows:
                row.status = RunStatus.FAILED.value
                row.stage = "interrupted"
                row.error = "server restarted while the forecast was running; create a new run"
                row.updated_at = now
        return len(rows)

    def _update_selection(
        self,
        run_id: str,
        idempotency_key: str,
        *,
        status: SelectionStatus,
        product_id: str | None,
        error: str | None,
    ) -> None:
        with self._sessions.begin() as session:
            row = session.scalars(
                select(ProductSelectionRow).where(
                    ProductSelectionRow.run_id == run_id,
                    ProductSelectionRow.idempotency_key == idempotency_key,
                )
            ).one()
            row.status = status.value
            row.product_id = product_id
            row.error = error
            row.updated_at = datetime.now(UTC)

    @staticmethod
    def _run_model(row: ForecastRunRow) -> ForecastRun:
        return ForecastRun(
            id=row.id,
            status=RunStatus(row.status),
            stage=row.stage,
            request=ForecastRequest.model_validate_json(row.request_json),
            error=row.error,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @staticmethod
    def _run_summary_model(row: ForecastRunRow) -> ForecastRunSummary:
        request = ForecastRequest.model_validate_json(row.request_json)
        return ForecastRunSummary(
            id=row.id,
            status=RunStatus(row.status),
            stage=row.stage,
            question=request.question,
            category=request.category,
            regions=request.regions,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
