"""Tests for the local chart, survey and result-feedback loop."""

from __future__ import annotations

import pytest

from eufy_security_agents.application.validation_insights import (
    SurveyAnswerError,
    ValidationInsightsService,
)
from eufy_security_agents.domain.models import ProductSpec
from eufy_security_agents.domain.validation import (
    ExperimentStatus,
    ExperimentType,
    ExperimentVerdict,
    ValidationExperiment,
    ValidationProject,
    ValidationProjectStatus,
)
from eufy_security_agents.domain.validation_insights import (
    SurveyQuestionType,
    SurveySubmissionRequest,
)
from eufy_security_agents.infrastructure.memory import InMemoryRunRepository


def _experiment(identifier: str, experiment_type: ExperimentType) -> ValidationExperiment:
    return ValidationExperiment(
        id=f"experiment-{identifier}",
        project_id="vproj-insights",
        hypothesis_id=f"VAL-{identifier}",
        title=f"假设 {identifier}",
        assumption=f"{identifier} 假设能够成立",
        experiment_type=experiment_type,
        metric="接受度",
        proposed_method="模拟与真实用户调研",
        pass_condition="达到预期",
        kill_condition="出现阻断项",
        status=ExperimentStatus.COMPLETED,
        verdict=(
            ExperimentVerdict.REQUIRES_REAL_WORLD_TEST
            if experiment_type == ExperimentType.TECHNOLOGY
            else ExperimentVerdict.INCONCLUSIVE
        ),
        verdict_reason="仍需补充真实证据",
    )


def _service() -> tuple[ValidationInsightsService, InMemoryRunRepository]:
    repository = InMemoryRunRepository()
    project = ValidationProject.model_construct(
        id="vproj-insights",
        product_id="product-insights",
        product_version="1.0",
        product_snapshot=ProductSpec.model_construct(name="eufy Beacon", version="1.0"),
        status=ValidationProjectStatus.COMPLETED,
        experiments=[
            _experiment("user", ExperimentType.USER_SCENARIO),
            _experiment("business", ExperimentType.BUSINESS),
            _experiment("technology", ExperimentType.TECHNOLOGY),
        ],
    )
    repository.save_validation_project(project)
    return (
        ValidationInsightsService(
            repository=repository,
            public_app_url="https://demo.example.com/",
        ),
        repository,
    )


def test_dynamic_survey_is_idempotent_and_separates_real_test_tasks() -> None:
    service, _ = _service()

    first = service.create_or_get_survey("vproj-insights")
    second = service.create_or_get_survey("vproj-insights")
    summary = service.get_visual_summary("vproj-insights")

    assert first.survey.id == second.survey.id
    assert first.public_url.startswith("https://demo.example.com/survey/")
    assert len(first.survey.linked_experiment_ids) == 2
    assert summary.survey_eligible_experiments == 2
    assert summary.real_experiment_tasks == 1


def test_survey_submission_aggregates_and_flows_back_into_summary() -> None:
    service, _ = _service()
    access = service.create_or_get_survey("vproj-insights")
    answers: dict[str, str | int | list[str]] = {}
    for question in access.survey.questions:
        if not question.required:
            continue
        if question.question_type == SurveyQuestionType.RATING:
            answers[question.id] = 4
        elif question.question_type == SurveyQuestionType.MULTIPLE_CHOICE:
            answers[question.id] = question.options[:2]
        else:
            answers[question.id] = question.options[0]

    submitted = service.submit_response(
        access.survey.token,
        SurveySubmissionRequest(answers=answers),
    )
    results = service.get_results_for_project("vproj-insights")
    summary = service.get_visual_summary("vproj-insights")

    assert submitted.total_responses == 1
    assert results.total_responses == 1
    assert summary.survey_response_count == 1
    purchase_intent = next(
        item for item in results.questions if item.question_id == "purchase-intent"
    )
    assert purchase_intent.average_rating == 4


def test_survey_rejects_missing_required_answers() -> None:
    service, _ = _service()
    access = service.create_or_get_survey("vproj-insights")

    with pytest.raises(SurveyAnswerError, match="请回答"):
        service.submit_response(
            access.survey.token,
            SurveySubmissionRequest(answers={}),
        )
