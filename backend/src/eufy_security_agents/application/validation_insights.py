"""Application service for visual summaries and public validation surveys."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from uuid import uuid4

from eufy_security_agents.domain.ports import FullRepository
from eufy_security_agents.domain.validation import ValidationProject, ValidationProjectStatus
from eufy_security_agents.domain.validation_insights import (
    SurveyAccess,
    SurveyQuestion,
    SurveyQuestionType,
    SurveyResponse,
    SurveyResults,
    SurveyStatus,
    SurveySubmissionRequest,
    SurveySubmissionResult,
    ValidationSurvey,
    ValidationVisualSummary,
    aggregate_survey_results,
    build_survey,
    build_visual_summary,
    sample_status_label,
    survey_sample_status,
)


class SurveyNotReadyError(RuntimeError):
    pass


class SurveyClosedError(RuntimeError):
    pass


class SurveyAnswerError(ValueError):
    pass


class ValidationInsightsService:
    def __init__(self, *, repository: FullRepository, public_app_url: str) -> None:
        self._repository = repository
        self._public_app_url = public_app_url.rstrip("/")

    def get_visual_summary(self, project_id: str) -> ValidationVisualSummary:
        project = self._project(project_id)
        survey = self._repository.get_validation_survey_for_project(project_id)
        response_count = (
            len(self._repository.list_survey_responses(survey.id)) if survey else 0
        )
        return build_visual_summary(project, survey_response_count=response_count)

    def create_or_get_survey(self, project_id: str) -> SurveyAccess:
        project = self._project(project_id)
        if project.status != ValidationProjectStatus.COMPLETED:
            raise SurveyNotReadyError("预验证完成后才能根据证据缺口生成调查问卷。")
        survey = self._repository.get_validation_survey_for_project(project_id)
        if survey is None:
            survey = build_survey(
                project,
                survey_id=f"survey-{uuid4().hex[:12]}",
                token=secrets.token_urlsafe(24),
            )
            self._repository.save_validation_survey(survey)
        return self._access(survey)

    def get_survey_for_project(self, project_id: str) -> SurveyAccess:
        self._project(project_id)
        survey = self._repository.get_validation_survey_for_project(project_id)
        if survey is None:
            raise LookupError(project_id)
        return self._access(survey)

    def get_public_survey(self, token: str) -> SurveyAccess:
        return self._access(self._survey_by_token(token))

    def submit_response(
        self,
        token: str,
        submission: SurveySubmissionRequest,
    ) -> SurveySubmissionResult:
        survey = self._survey_by_token(token)
        if survey.status != SurveyStatus.OPEN:
            raise SurveyClosedError("该调查已停止收集。")
        answers = _validate_answers(survey.questions, submission.answers)
        response = SurveyResponse(
            id=f"sresp-{uuid4().hex[:12]}",
            survey_id=survey.id,
            answers=answers,
            created_at=datetime.now(UTC),
        )
        self._repository.save_survey_response(response)
        total = len(self._repository.list_survey_responses(survey.id))
        status = survey_sample_status(total)
        return SurveySubmissionResult(
            response_id=response.id,
            total_responses=total,
            sample_status=status,
            sample_status_label=sample_status_label(status),
        )

    def get_results_for_project(self, project_id: str) -> SurveyResults:
        self._project(project_id)
        survey = self._repository.get_validation_survey_for_project(project_id)
        if survey is None:
            raise LookupError(project_id)
        return aggregate_survey_results(
            survey,
            self._repository.list_survey_responses(survey.id),
        )

    def _project(self, project_id: str) -> ValidationProject:
        project = self._repository.get_validation_project(project_id)
        if project is None:
            raise KeyError(project_id)
        return project

    def _access(self, survey: ValidationSurvey) -> SurveyAccess:
        return SurveyAccess(
            survey=survey,
            public_url=f"{self._public_app_url}/survey/{survey.token}",
        )

    def _survey_by_token(self, token: str) -> ValidationSurvey:
        survey = self._repository.get_validation_survey_by_token(token)
        if survey is None:
            raise KeyError(token)
        return survey


def _validate_answers(
    questions: list[SurveyQuestion],
    supplied: dict[str, str | int | list[str]],
) -> dict[str, str | int | list[str]]:
    by_id = {question.id: question for question in questions}
    unknown = set(supplied) - set(by_id)
    if unknown:
        raise SurveyAnswerError("问卷包含无法识别的问题。")
    normalized: dict[str, str | int | list[str]] = {}
    for question in questions:
        value = supplied.get(question.id)
        if value is None or value == "" or value == []:
            if question.required:
                raise SurveyAnswerError(f"请回答：{question.prompt}")
            continue
        normalized[question.id] = _validate_answer(question, value)
    return normalized


def _validate_answer(
    question: SurveyQuestion,
    value: str | int | list[str],
) -> str | int | list[str]:
    if question.question_type == SurveyQuestionType.RATING:
        if isinstance(value, bool) or not isinstance(value, int):
            raise SurveyAnswerError(f"“{question.prompt}”需要选择评分。")
        if not question.rating_min <= value <= question.rating_max:
            raise SurveyAnswerError(f"“{question.prompt}”评分超出范围。")
        return value
    if question.question_type == SurveyQuestionType.MULTIPLE_CHOICE:
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise SurveyAnswerError(f"“{question.prompt}”需要选择一个或多个选项。")
        selected = list(dict.fromkeys(item for item in value if item in question.options))
        if len(selected) != len(value):
            raise SurveyAnswerError(f"“{question.prompt}”包含无效选项。")
        return selected
    if not isinstance(value, str):
        raise SurveyAnswerError(f"“{question.prompt}”回答格式错误。")
    clean = value.strip()
    if question.question_type == SurveyQuestionType.SINGLE_CHOICE:
        if clean not in question.options:
            raise SurveyAnswerError(f"“{question.prompt}”包含无效选项。")
        return clean
    if len(clean) > 2000:
        raise SurveyAnswerError(f"“{question.prompt}”回答不能超过 2000 个字符。")
    return clean
