"""Dependency-inversion ports for model generation and persistence."""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

from .models import (
    AgentEvent,
    Artifact,
    ForecastRequest,
    ForecastRun,
    ProductSelectionState,
    ProductSpec,
    RunStatus,
)

TModel = TypeVar("TModel", bound=BaseModel)


class StructuredLLM(Protocol):
    model_name: str

    async def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[TModel],
        temperature: float = 0.4,
    ) -> tuple[TModel, dict[str, int | str | None]]: ...


class RunRepository(Protocol):
    def create_run(self, request: ForecastRequest) -> ForecastRun: ...

    def get_run(self, run_id: str) -> ForecastRun | None: ...

    def update_run(
        self,
        run_id: str,
        *,
        status: RunStatus | None = None,
        stage: str | None = None,
        error: str | None = None,
    ) -> ForecastRun: ...

    def add_event(self, event: AgentEvent) -> AgentEvent: ...

    def list_events(self, run_id: str, after_sequence: int = 0) -> list[AgentEvent]: ...

    def save_artifact(self, artifact: Artifact) -> None: ...

    def get_artifact(self, run_id: str, kind: str) -> Artifact | None: ...

    def list_artifacts(self, run_id: str) -> list[Artifact]: ...

    def save_product(self, product: ProductSpec) -> None: ...

    def get_product(self, product_id: str) -> ProductSpec | None: ...

    def get_selection(self, run_id: str, idempotency_key: str) -> ProductSelectionState | None: ...

    def reserve_selection(self, run_id: str, idempotency_key: str, candidate_id: str) -> bool: ...

    def complete_selection(self, run_id: str, idempotency_key: str, product_id: str) -> None: ...

    def fail_selection(self, run_id: str, idempotency_key: str, error: str) -> None: ...

    def recover_interrupted_runs(self) -> int: ...
