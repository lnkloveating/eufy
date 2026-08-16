"""Deterministic visualization and real-user survey contracts.

Survey responses are real human observations, but they only measure perception,
intent and reported context. They never turn a simulated technical verdict into a
real hardware validation result.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from .reporting import conclusion_type_for, priority_for
from .validation import ExperimentType, ValidationProject


class SurveyQuestionType(StrEnum):
    SINGLE_CHOICE = "single_choice"
    MULTIPLE_CHOICE = "multiple_choice"
    RATING = "rating"
    LONG_TEXT = "long_text"


class SurveyStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class SurveySampleStatus(StrEnum):
    NO_RESPONSES = "no_responses"
    COLLECTING = "collecting"
    EARLY_SIGNAL = "early_signal"
    DIRECTIONAL = "directional"


SurveyAnswerValue = str | int | list[str]


class SurveyQuestion(BaseModel):
    id: str
    prompt: str
    question_type: SurveyQuestionType
    required: bool = True
    options: list[str] = Field(default_factory=list)
    rating_min: int = 1
    rating_max: int = 5
    linked_experiment_id: str | None = None
    evidence_boundary: str = "仅衡量用户态度或自述行为，不代表技术验证。"


class ValidationSurvey(BaseModel):
    id: str
    token: str
    project_id: str
    product_id: str
    product_name: str
    title: str
    description: str
    status: SurveyStatus = SurveyStatus.OPEN
    questions: list[SurveyQuestion] = Field(min_length=1)
    linked_experiment_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SurveyAccess(BaseModel):
    survey: ValidationSurvey
    public_url: str


class SurveySubmissionRequest(BaseModel):
    answers: dict[str, SurveyAnswerValue]


class SurveyResponse(BaseModel):
    id: str
    survey_id: str
    answers: dict[str, SurveyAnswerValue]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class SurveySubmissionResult(BaseModel):
    response_id: str
    total_responses: int = Field(ge=1)
    sample_status: SurveySampleStatus
    sample_status_label: str
    message: str = "感谢参与，回答已作为真实用户自述证据回流验证实验室。"


class SurveyQuestionResult(BaseModel):
    question_id: str
    prompt: str
    question_type: SurveyQuestionType
    response_count: int = Field(ge=0)
    option_counts: dict[str, int] = Field(default_factory=dict)
    average_rating: float | None = None
    text_samples: list[str] = Field(default_factory=list)
    linked_experiment_id: str | None = None


class SurveyResults(BaseModel):
    survey_id: str
    project_id: str
    total_responses: int = Field(ge=0)
    sample_status: SurveySampleStatus
    sample_status_label: str
    questions: list[SurveyQuestionResult]
    disclaimer: str = (
        "问卷结果属于真实用户自述证据，但当前样本不代表总体市场，"
        "也不能替代硬件、准确率、隐私安全或可靠性实验。"
    )


class ValidationVisualSummary(BaseModel):
    project_id: str
    total_experiments: int = Field(ge=0)
    conclusion_counts: dict[str, int]
    priority_counts: dict[str, int]
    simulation_support_rate: float = Field(ge=0, le=100)
    high_risk_count: int = Field(ge=0)
    survey_eligible_experiments: int = Field(ge=0)
    real_experiment_tasks: int = Field(ge=0)
    survey_response_count: int = Field(ge=0)
    survey_sample_status: SurveySampleStatus
    generated_at: datetime


SURVEY_ELIGIBLE_TYPES = {
    ExperimentType.USER_SCENARIO,
    ExperimentType.BUSINESS,
    ExperimentType.PRIVACY_SECURITY,
}


def survey_sample_status(response_count: int) -> SurveySampleStatus:
    if response_count == 0:
        return SurveySampleStatus.NO_RESPONSES
    if response_count < 5:
        return SurveySampleStatus.COLLECTING
    if response_count < 20:
        return SurveySampleStatus.EARLY_SIGNAL
    return SurveySampleStatus.DIRECTIONAL


def sample_status_label(status: SurveySampleStatus) -> str:
    return {
        SurveySampleStatus.NO_RESPONSES: "尚未收集样本",
        SurveySampleStatus.COLLECTING: "样本收集中",
        SurveySampleStatus.EARLY_SIGNAL: "初步信号",
        SurveySampleStatus.DIRECTIONAL: "方向性参考",
    }[status]


def build_visual_summary(
    project: ValidationProject,
    *,
    survey_response_count: int = 0,
) -> ValidationVisualSummary:
    conclusions = Counter(conclusion_type_for(item).value for item in project.experiments)
    priorities = Counter(priority_for(item) for item in project.experiments)
    total = len(project.experiments)
    supported = conclusions.get("simulation_supported", 0)
    survey_eligible = sum(
        item.experiment_type in SURVEY_ELIGIBLE_TYPES for item in project.experiments
    )
    real_tasks = total - survey_eligible
    status = survey_sample_status(survey_response_count)
    return ValidationVisualSummary(
        project_id=project.id,
        total_experiments=total,
        conclusion_counts={
            "research_required": conclusions.get("research_required", 0),
            "real_validation_required": conclusions.get("real_validation_required", 0),
            "unqualified": conclusions.get("unqualified", 0),
            "simulation_supported": supported,
        },
        priority_counts={
            "高": priorities.get("高", 0),
            "中": priorities.get("中", 0),
            "低": priorities.get("低", 0),
        },
        simulation_support_rate=round((supported / total * 100) if total else 0, 1),
        high_risk_count=priorities.get("高", 0),
        survey_eligible_experiments=survey_eligible,
        real_experiment_tasks=real_tasks,
        survey_response_count=survey_response_count,
        survey_sample_status=status,
        generated_at=project.updated_at,
    )


def build_survey(
    project: ValidationProject,
    *,
    survey_id: str,
    token: str,
    now: datetime | None = None,
) -> ValidationSurvey:
    generated_at = now or datetime.now(UTC)
    eligible = [
        item for item in project.experiments if item.experiment_type in SURVEY_ELIGIBLE_TYPES
    ]
    questions = [
        SurveyQuestion(
            id="usage-context",
            prompt="你目前与家庭安防产品的关系是？",
            question_type=SurveyQuestionType.SINGLE_CHOICE,
            options=[
                "正在使用家庭安防产品",
                "过去使用过",
                "正在考虑购买",
                "暂时没有购买计划",
            ],
        ),
        SurveyQuestion(
            id="purchase-intent",
            prompt=f"如果 {project.product_snapshot.name} 按描述实现，你的尝试或购买意愿有多高？",
            question_type=SurveyQuestionType.RATING,
        ),
        SurveyQuestion(
            id="main-concerns",
            prompt="决定是否采用这类产品时，你最关心哪些因素？",
            question_type=SurveyQuestionType.MULTIPLE_CHOICE,
            options=["隐私", "准确率", "误报", "价格", "安装难度", "可靠性", "售后与订阅"],
        ),
    ]
    for index, experiment in enumerate(eligible[:4], start=1):
        qualifier = (
            "从用户信任和接受度角度，"
            if experiment.experiment_type == ExperimentType.PRIVACY_SECURITY
            else ""
        )
        questions.append(
            SurveyQuestion(
                id=f"gap-{index}-{experiment.id[-8:]}",
                prompt=f"{qualifier}你对以下描述的认同程度如何：{experiment.assumption}",
                question_type=SurveyQuestionType.RATING,
                linked_experiment_id=experiment.id,
            )
        )
    questions.append(
        SurveyQuestion(
            id="open-feedback",
            prompt="还有哪些顾虑、使用场景或改进建议？",
            question_type=SurveyQuestionType.LONG_TEXT,
            required=False,
        )
    )
    return ValidationSurvey(
        id=survey_id,
        token=token,
        project_id=project.id,
        product_id=project.product_id,
        product_name=project.product_snapshot.name,
        title=f"{project.product_snapshot.name} 用户调研",
        description=(
            "本问卷用于补充用户需求、信任和购买意愿证据。"
            "不收集姓名、住址或设备标识，也不替代真实技术实验。"
        ),
        questions=questions,
        linked_experiment_ids=[item.id for item in eligible],
        created_at=generated_at,
        updated_at=generated_at,
    )


def aggregate_survey_results(
    survey: ValidationSurvey,
    responses: list[SurveyResponse],
) -> SurveyResults:
    question_results: list[SurveyQuestionResult] = []
    for question in survey.questions:
        values = [
            response.answers[question.id]
            for response in responses
            if question.id in response.answers
        ]
        counts: Counter[str] = Counter()
        ratings: list[int] = []
        texts: list[str] = []
        for value in values:
            if isinstance(value, list):
                counts.update(str(item) for item in value)
            elif isinstance(value, int):
                ratings.append(value)
                counts[str(value)] += 1
            elif value.strip():
                if question.question_type == SurveyQuestionType.LONG_TEXT:
                    texts.append(value.strip())
                else:
                    counts[value.strip()] += 1
        question_results.append(
            SurveyQuestionResult(
                question_id=question.id,
                prompt=question.prompt,
                question_type=question.question_type,
                response_count=len(values),
                option_counts=dict(counts),
                average_rating=(
                    round(sum(ratings) / len(ratings), 2) if ratings else None
                ),
                text_samples=texts[:5],
                linked_experiment_id=question.linked_experiment_id,
            )
        )
    status = survey_sample_status(len(responses))
    return SurveyResults(
        survey_id=survey.id,
        project_id=survey.project_id,
        total_responses=len(responses),
        sample_status=status,
        sample_status_label=sample_status_label(status),
        questions=question_results,
    )
