"""Application service for exporting completed validation results."""

from eufy_security_agents.domain.ports import FullRepository, ValidationReportPublisher
from eufy_security_agents.domain.reporting import (
    FeishuSyncResult,
    build_validation_research_report,
)
from eufy_security_agents.domain.validation import ValidationProjectStatus


class ValidationReportNotReadyError(RuntimeError):
    pass


class ValidationReportService:
    def __init__(
        self,
        *,
        repository: FullRepository,
        publisher: ValidationReportPublisher,
        public_app_url: str,
    ) -> None:
        self._repository = repository
        self._publisher = publisher
        self._public_app_url = public_app_url.rstrip("/")

    async def sync_to_feishu(self, project_id: str) -> FeishuSyncResult:
        project = self._repository.get_validation_project(project_id)
        if project is None:
            raise KeyError(project_id)
        if project.status != ValidationProjectStatus.COMPLETED:
            raise ValidationReportNotReadyError("预验证尚未完成，暂不能同步研究报告。")
        if not project.experiments:
            raise ValidationReportNotReadyError("当前项目没有可同步的验证结论。")
        report = build_validation_research_report(project)
        survey = self._repository.get_validation_survey_for_project(project_id)
        if survey is not None:
            report = report.model_copy(
                update={
                    "survey_url": f"{self._public_app_url}/survey/{survey.token}",
                    "survey_response_count": len(
                        self._repository.list_survey_responses(survey.id)
                    ),
                }
            )
        return await self._publisher.publish(report)
