"""Application composition root."""

from eufy_security_agents.core.config import get_settings
from eufy_security_agents.infrastructure.competitors import LocalCompetitorStore
from eufy_security_agents.infrastructure.evidence import LocalEvidenceStore
from eufy_security_agents.infrastructure.llm import OpenAICompatibleLLM
from eufy_security_agents.infrastructure.repositories import SqlAlchemyRunRepository
from eufy_security_agents.orchestration import ForecastWorkflow

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
)
workflow = ForecastWorkflow(
    repository=repository,
    evidence_store=evidence_store,
    competitor_store=competitor_store,
    llm=llm,
    timeout_seconds=settings.workflow_timeout_seconds,
)
