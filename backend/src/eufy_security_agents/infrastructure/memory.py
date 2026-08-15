"""In-memory repository used by isolated workflow tests."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

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
from eufy_security_agents.domain.validation import (
    ValidationEvent,
    ValidationProject,
    ValidationProjectStatus,
)


class InMemoryRunRepository:
    def __init__(self) -> None:
        self.runs: dict[str, ForecastRun] = {}
        self.events: dict[str, list[AgentEvent]] = {}
        self.artifacts: dict[tuple[str, str], Artifact] = {}
        self.products: dict[str, ProductSpec] = {}
        self.selections: dict[tuple[str, str], ProductSelectionState] = {}
        self.question_records: dict[str, list[ProductQuestionRecord]] = {}
        self.question_keys: dict[tuple[str, str], str] = {}
        self.revisions: dict[str, list[ProductRevision]] = {}
        self.revision_keys: dict[tuple[str, str], str] = {}
        self.suggestion_resolutions: dict[str, dict[str, SuggestionResolution]] = {}
        self.run_keys: dict[str, str] = {}
        self.validation_projects: dict[str, ValidationProject] = {}
        self.validation_events: dict[str, list[ValidationEvent]] = {}
        self.validation_finding_index: dict[str, str] = {}

    def create_run(self, request: ForecastRequest) -> ForecastRun:
        now = datetime.now(UTC)
        run = ForecastRun(
            id=f"forecast-{uuid4().hex[:12]}",
            status=RunStatus.PENDING,
            stage="queued",
            request=request,
            created_at=now,
            updated_at=now,
        )
        self.runs[run.id] = run
        self.events[run.id] = []
        return run

    def get_or_create_run(
        self, request: ForecastRequest, idempotency_key: str
    ) -> tuple[ForecastRun, bool]:
        existing_id = self.run_keys.get(idempotency_key)
        if existing_id is not None and existing_id in self.runs:
            return self.runs[existing_id], False
        run = self.create_run(request)
        self.run_keys[idempotency_key] = run.id
        return run, True

    def get_run(self, run_id: str) -> ForecastRun | None:
        return self.runs.get(run_id)

    def list_runs(self, *, limit: int = 20) -> list[ForecastRunSummary]:
        recent_runs = sorted(
            self.runs.values(),
            key=lambda run: run.created_at,
            reverse=True,
        )[:limit]
        return [
            ForecastRunSummary(
                id=run.id,
                status=run.status,
                stage=run.stage,
                question=run.request.question,
                category=run.request.category,
                regions=run.request.regions,
                created_at=run.created_at,
                updated_at=run.updated_at,
            )
            for run in recent_runs
        ]

    def count_runs(self) -> int:
        return len(self.runs)

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        stage: str | None = None,
        error: str | None = None,
    ) -> ForecastRun:
        run = self.runs[run_id]
        run = run.model_copy(
            update={
                "status": status or run.status,
                "stage": stage or run.stage,
                "error": error,
                "updated_at": datetime.now(UTC),
            }
        )
        self.runs[run_id] = run
        return run

    def add_event(self, event: AgentEvent) -> AgentEvent:
        persisted = event.model_copy(update={"id": len(self.events[event.run_id]) + 1})
        self.events[event.run_id].append(persisted)
        return persisted

    def list_events(self, run_id: str, after_sequence: int = 0) -> list[AgentEvent]:
        return [event for event in self.events.get(run_id, []) if event.sequence > after_sequence]

    def save_artifact(self, artifact: Artifact) -> None:
        self.artifacts[(artifact.run_id, artifact.kind)] = artifact

    def get_artifact(self, run_id: str, kind: str) -> Artifact | None:
        return self.artifacts.get((run_id, kind))

    def list_artifacts(self, run_id: str) -> list[Artifact]:
        return sorted(
            [
                artifact
                for (stored_run_id, _), artifact in self.artifacts.items()
                if stored_run_id == run_id
            ],
            key=lambda artifact: artifact.created_at,
        )

    def save_product(self, product: ProductSpec) -> None:
        self.products[product.id] = product

    def get_product(self, product_id: str) -> ProductSpec | None:
        return self.products.get(product_id)

    def save_question_record(
        self, record: ProductQuestionRecord, *, idempotency_key: str | None
    ) -> None:
        self.question_records.setdefault(record.question.product_id, []).append(record)
        if idempotency_key is not None:
            self.question_keys[(record.question.product_id, idempotency_key)] = (
                record.answer.question_id
            )

    def get_question_record(
        self, product_id: str, question_id: str
    ) -> ProductQuestionRecord | None:
        for record in self.question_records.get(product_id, []):
            if record.answer.question_id == question_id:
                return record
        return None

    def update_question_record(self, record: ProductQuestionRecord) -> None:
        records = self.question_records.setdefault(record.question.product_id, [])
        for index, existing in enumerate(records):
            if existing.answer.question_id == record.answer.question_id:
                records[index] = record
                return
        raise KeyError(record.answer.question_id)

    def list_question_records(self, product_id: str) -> list[ProductQuestionRecord]:
        return list(self.question_records.get(product_id, []))

    def find_question_record_by_key(
        self, product_id: str, idempotency_key: str
    ) -> ProductQuestionRecord | None:
        question_id = self.question_keys.get((product_id, idempotency_key))
        if question_id is None:
            return None
        for record in self.question_records.get(product_id, []):
            if record.answer.question_id == question_id:
                return record
        return None

    def save_revision(self, revision: ProductRevision, *, idempotency_key: str | None) -> None:
        self.revisions.setdefault(revision.product_id, []).append(revision)
        if idempotency_key is not None:
            self.revision_keys[(revision.product_id, idempotency_key)] = revision.id

    def list_revisions(self, product_id: str) -> list[ProductRevision]:
        return list(self.revisions.get(product_id, []))

    def find_revision_by_key(
        self, product_id: str, idempotency_key: str
    ) -> ProductRevision | None:
        revision_id = self.revision_keys.get((product_id, idempotency_key))
        if revision_id is None:
            return None
        for revision in self.revisions.get(product_id, []):
            if revision.id == revision_id:
                return revision
        return None

    def save_suggestion_resolution(self, resolution: SuggestionResolution) -> None:
        self.suggestion_resolutions.setdefault(resolution.product_id, {})[
            resolution.suggestion_id
        ] = resolution

    def list_suggestion_resolutions(self, product_id: str) -> list[SuggestionResolution]:
        return list(self.suggestion_resolutions.get(product_id, {}).values())

    def get_selection(self, run_id: str, idempotency_key: str) -> ProductSelectionState | None:
        return self.selections.get((run_id, idempotency_key))

    def get_latest_selection(self, run_id: str) -> ProductSelectionState | None:
        for (stored_run_id, _), selection in reversed(self.selections.items()):
            if stored_run_id == run_id:
                return selection
        return None

    def reserve_selection(self, run_id: str, idempotency_key: str, candidate_id: str) -> bool:
        key = (run_id, idempotency_key)
        existing = self.selections.get(key)
        if existing is not None:
            if existing.candidate_id != candidate_id:
                raise ValueError("idempotency key is already bound to another candidate")
            if existing.status != SelectionStatus.FAILED:
                return False
        self.selections[key] = ProductSelectionState(
            run_id=run_id,
            idempotency_key=idempotency_key,
            candidate_id=candidate_id,
            status=SelectionStatus.IN_PROGRESS,
        )
        return True

    def complete_selection(self, run_id: str, idempotency_key: str, product_id: str) -> None:
        key = (run_id, idempotency_key)
        self.selections[key] = self.selections[key].model_copy(
            update={"status": SelectionStatus.COMPLETED, "product_id": product_id, "error": None}
        )

    def fail_selection(self, run_id: str, idempotency_key: str, error: str) -> None:
        key = (run_id, idempotency_key)
        self.selections[key] = self.selections[key].model_copy(
            update={"status": SelectionStatus.FAILED, "product_id": None, "error": error}
        )

    def recover_interrupted_runs(self) -> int:
        interrupted = [run for run in self.runs.values() if run.status == RunStatus.RUNNING]
        for run in interrupted:
            self.update_run(
                run.id,
                status=RunStatus.FAILED,
                stage="interrupted",
                error="server restarted while the forecast was running; create a new run",
            )
        return len(interrupted)

    # ------------------------------------------------------------------ #
    # Pre-validation lab                                                  #
    # ------------------------------------------------------------------ #

    def save_validation_project(
        self, project: ValidationProject, *, idempotency_key: str | None = None
    ) -> None:
        del idempotency_key
        self.validation_projects[project.id] = project
        self.validation_events.setdefault(project.id, [])
        for experiment in project.experiments:
            for finding in experiment.findings:
                self.validation_finding_index[finding.id] = project.id

    def get_validation_project(self, project_id: str) -> ValidationProject | None:
        return self.validation_projects.get(project_id)

    def get_latest_validation_project(self, product_id: str) -> ValidationProject | None:
        projects = [
            project
            for project in self.validation_projects.values()
            if project.product_id == product_id
        ]
        if not projects:
            return None
        return max(projects, key=lambda project: project.created_at)

    def find_validation_project_by_version(
        self, product_id: str, product_version: str
    ) -> ValidationProject | None:
        for project in self.validation_projects.values():
            if project.product_id == product_id and project.product_version == product_version:
                return project
        return None

    def add_validation_event(self, event: ValidationEvent) -> ValidationEvent:
        events = self.validation_events.setdefault(event.project_id, [])
        persisted = event.model_copy(update={"id": len(events) + 1})
        events.append(persisted)
        return persisted

    def list_validation_events(
        self, project_id: str, after_sequence: int = 0
    ) -> list[ValidationEvent]:
        return [
            event
            for event in self.validation_events.get(project_id, [])
            if event.sequence > after_sequence
        ]

    def get_project_id_for_finding(self, finding_id: str) -> str | None:
        return self.validation_finding_index.get(finding_id)

    def recover_interrupted_validation_projects(self) -> int:
        interrupted = [
            project
            for project in self.validation_projects.values()
            if project.status == ValidationProjectStatus.RUNNING
        ]
        for project in interrupted:
            self.validation_projects[project.id] = project.model_copy(
                update={
                    "status": ValidationProjectStatus.PLANNED,
                    "error": "服务重启，预验证运行已中断，请重新开始预验证。",
                }
            )
        return len(interrupted)
