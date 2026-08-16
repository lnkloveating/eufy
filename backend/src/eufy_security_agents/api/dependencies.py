"""Application composition root."""

from eufy_security_agents.application.validation_insights import ValidationInsightsService
from eufy_security_agents.application.validation_reporting import ValidationReportService
from eufy_security_agents.core.config import get_settings
from eufy_security_agents.infrastructure.competitors import LocalCompetitorStore
from eufy_security_agents.infrastructure.evidence import LocalEvidenceStore
from eufy_security_agents.infrastructure.feishu import FeishuBitablePublisher
from eufy_security_agents.infrastructure.llm import OpenAICompatibleLLM
from eufy_security_agents.infrastructure.repositories import SqlAlchemyRunRepository
from eufy_security_agents.orchestration import ForecastWorkflow, ValidationWorkflow

settings = get_settings()
repository = SqlAlchemyRunRepository(settings.database_url)
evidence_store = LocalEvidenceStore(settings.evidence_path)
competitor_store = LocalCompetitorStore(settings.competitor_evidence_path)
llm = OpenAICompatibleLLM(
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
    model_name=settings.llm_model,
    timeout_seconds=settings.llm_timeout_seconds,
    max_retries=settings.llm_max_retries,
    max_output_tokens=settings.llm_max_output_tokens,
)
workflow = ForecastWorkflow(
    repository=repository,
    evidence_store=evidence_store,
    competitor_store=competitor_store,
    llm=llm,
    stage_timeout_seconds=settings.stage_timeout_seconds,
    timeout_seconds=settings.workflow_timeout_seconds,
)
validation_workflow = ValidationWorkflow(repository=repository, llm=llm)
feishu_publisher = FeishuBitablePublisher(
    app_id=settings.feishu_app_id,
    app_secret=settings.feishu_app_secret,
    app_token=settings.feishu_bitable_app_token,
    wiki_node_token=settings.feishu_wiki_node_token,
    table_id=settings.feishu_bitable_table_id,
    table_url=settings.feishu_bitable_url,
    api_base_url=settings.feishu_api_base_url,
    timeout_seconds=settings.feishu_timeout_seconds,
)
validation_report_service = ValidationReportService(
    repository=repository,
    publisher=feishu_publisher,
    public_app_url=settings.public_app_url,
)
validation_insights_service = ValidationInsightsService(
    repository=repository,
    public_app_url=settings.public_app_url,
)
