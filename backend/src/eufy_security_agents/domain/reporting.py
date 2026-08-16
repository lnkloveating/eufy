"""Pure contracts and deterministic formatting for external research reports."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from .validation import (
    ExperimentVerdict,
    FindingSeverity,
    ValidationExperiment,
    ValidationProject,
)


class ResearchConclusionType(StrEnum):
    RESEARCH_REQUIRED = "research_required"
    REAL_VALIDATION_REQUIRED = "real_validation_required"
    UNQUALIFIED = "unqualified"
    SIMULATION_SUPPORTED = "simulation_supported"

    @property
    def label(self) -> str:
        return {
            ResearchConclusionType.RESEARCH_REQUIRED: "待真实调研",
            ResearchConclusionType.REAL_VALIDATION_REQUIRED: "待真实验证",
            ResearchConclusionType.UNQUALIFIED: "不合格",
            ResearchConclusionType.SIMULATION_SUPPORTED: "模拟支持",
        }[self]


class ResearchReportRow(BaseModel):
    product_name: str
    conclusion_type: ResearchConclusionType
    conclusion: str
    reason: str
    evidence_summary: str
    recommended_action: str
    priority: str
    project_id: str
    generated_at: datetime


class ValidationResearchReport(BaseModel):
    project_id: str
    product_id: str
    product_name: str
    product_version: str
    survey_url: str | None = None
    survey_response_count: int = Field(default=0, ge=0)
    rows: list[ResearchReportRow] = Field(min_length=1)


class FeishuSyncResult(BaseModel):
    project_id: str
    table_id: str
    table_name: str
    records_created: int = Field(ge=0)
    category_counts: dict[str, int] = Field(default_factory=dict)
    table_url: str | None = None
    overview_table_url: str | None = None
    synced_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def conclusion_type_for(experiment: ValidationExperiment) -> ResearchConclusionType:
    if experiment.verdict == ExperimentVerdict.CONTRADICTED:
        return ResearchConclusionType.UNQUALIFIED
    if experiment.verdict == ExperimentVerdict.REQUIRES_REAL_WORLD_TEST:
        return ResearchConclusionType.REAL_VALIDATION_REQUIRED
    if experiment.verdict == ExperimentVerdict.SUPPORTED_IN_SIMULATION:
        return ResearchConclusionType.SIMULATION_SUPPORTED
    return ResearchConclusionType.RESEARCH_REQUIRED


def priority_for(experiment: ValidationExperiment) -> str:
    severities = {finding.severity for finding in experiment.findings}
    if (
        FindingSeverity.CRITICAL in severities
        or experiment.verdict == ExperimentVerdict.CONTRADICTED
    ):
        return "高"
    if (
        FindingSeverity.WARNING in severities
        or experiment.verdict == ExperimentVerdict.REQUIRES_REAL_WORLD_TEST
    ):
        return "中"
    return "低"


def _join_limited(values: list[str], *, fallback: str, limit: int = 3) -> str:
    selected = [value.strip() for value in values if value.strip()][:limit]
    return "；".join(selected) if selected else fallback


def _evidence_summary(experiment: ValidationExperiment) -> str:
    evidence = list(experiment.supporting_points)
    evidence.extend(observation.content for observation in experiment.observations)
    return _join_limited(evidence, fallback="当前仅有模拟分析，尚无可引用的真实测试证据。")


def _recommended_action(experiment: ValidationExperiment) -> str:
    if experiment.next_recommended_test.strip():
        return experiment.next_recommended_test.strip()
    changes = [finding.recommended_change for finding in experiment.findings]
    return _join_limited(changes, fallback="补充真实用户、硬件或市场证据后重新评估。", limit=2)


def build_validation_research_report(project: ValidationProject) -> ValidationResearchReport:
    """Convert one completed validation project into a compact, auditable report."""

    # Use persisted project state instead of wall-clock time so repeated exports of
    # the same completed project produce an identical payload for Feishu idempotency.
    generated_at = project.updated_at
    rows = [
        ResearchReportRow(
            product_name=project.product_snapshot.name,
            conclusion_type=conclusion_type_for(experiment),
            conclusion=experiment.assumption,
            reason=(
                experiment.verdict_reason.strip()
                or experiment.summary.strip()
                or "当前证据不足，需补充验证后再判断。"
            ),
            evidence_summary=_evidence_summary(experiment),
            recommended_action=_recommended_action(experiment),
            priority=priority_for(experiment),
            project_id=project.id,
            generated_at=generated_at,
        )
        for experiment in project.experiments
    ]
    return ValidationResearchReport(
        project_id=project.id,
        product_id=project.product_id,
        product_name=project.product_snapshot.name,
        product_version=project.product_version,
        rows=rows,
    )


def category_counts(report: ValidationResearchReport) -> dict[str, int]:
    counts = Counter(row.conclusion_type.label for row in report.rows)
    return dict(counts)
