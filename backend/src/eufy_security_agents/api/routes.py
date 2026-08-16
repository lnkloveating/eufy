"""HTTP and SSE API for product forecasting and human selection."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from eufy_security_agents.application.validation_insights import (
    SurveyAnswerError,
    SurveyClosedError,
    SurveyNotReadyError,
)
from eufy_security_agents.application.validation_reporting import ValidationReportNotReadyError
from eufy_security_agents.core.config import get_settings
from eufy_security_agents.domain.models import (
    AgentEvent,
    Artifact,
    ForecastRequest,
    ForecastResult,
    ForecastRun,
    ForecastRunListResponse,
    IssueDismissRequest,
    KnowledgeCoverage,
    ProductDefinitionReadiness,
    ProductQuestionRecord,
    ProductQuestionRequest,
    ProductRevision,
    ProductRevisionRequest,
    ProductSelectionRequest,
    ProductSpec,
    RankedCandidate,
    RetrievalPreview,
    RunProductDefinitionState,
    RunStatus,
    SuggestionDismissRequest,
)
from eufy_security_agents.domain.reporting import FeishuSyncResult
from eufy_security_agents.domain.strategy import strategy_presets
from eufy_security_agents.domain.validation import (
    SendBackResponse,
    ValidationEvent,
    ValidationProject,
    ValidationProjectCreateRequest,
    ValidationProjectStatus,
)
from eufy_security_agents.domain.validation_insights import (
    SurveyAccess,
    SurveyResults,
    SurveySubmissionRequest,
    SurveySubmissionResult,
    ValidationVisualSummary,
)
from eufy_security_agents.infrastructure.feishu import FeishuAPIError, FeishuConfigurationError
from eufy_security_agents.orchestration.validation_workflow import ValidationNotReadyError
from eufy_security_agents.orchestration.workflow import DefinitionNotReadyError

from .dependencies import (
    competitor_store,
    evidence_store,
    repository,
    validation_insights_service,
    validation_report_service,
    validation_workflow,
    workflow,
)

router = APIRouter()


@router.get("/health", tags=["system"])
async def health() -> dict[str, object]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "llm_model": settings.llm_model,
        "llm_configured": bool(settings.llm_api_key),
        "feishu_configured": bool(
            settings.feishu_app_id
            and settings.feishu_app_secret
            and (settings.feishu_bitable_app_token or settings.feishu_wiki_node_token)
        ),
        "local_evidence_count": len(evidence_store.load()),
        "competitor_evidence_count": len(competitor_store.load()),
        "knowledge_layers": evidence_store.coverage().records_by_layer,
    }


@router.get("/knowledge/coverage", response_model=KnowledgeCoverage, tags=["knowledge"])
async def knowledge_coverage(
    regions: Annotated[list[str] | None, Query()] = None,
) -> KnowledgeCoverage:
    return evidence_store.coverage(regions)


@router.post(
    "/knowledge/retrieval-preview",
    response_model=RetrievalPreview,
    tags=["knowledge"],
)
async def retrieval_preview(request: ForecastRequest) -> RetrievalPreview:
    plan, evidence = evidence_store.retrieve(request)
    return RetrievalPreview(plan=plan, evidence=evidence)


@router.get("/forecast-options", tags=["forecasting"])
async def forecast_options() -> dict[str, object]:
    return {
        "regions": [
            "China",
            "United States",
            "Canada",
            "United Kingdom",
            "Germany",
            "France",
            "European Union",
            "Japan",
            "Australia",
            "Global",
        ],
        "custom_regions_allowed": True,
        "research_context_options": {
            "housing_types": ["城市公寓", "独栋住宅", "联排住宅", "租赁住房", "多代同堂住宅"],
            "household_members": ["独居者", "双职工家庭", "有儿童家庭", "有老人家庭", "有宠物家庭"],
            "security_scenarios": [
                "入侵与周界",
                "包裹与门前",
                "室内异常",
                "老人儿童照护",
                "火灾水浸等环境风险",
                "车辆与车库",
            ],
            "current_devices": [
                "尚未使用安防设备",
                "摄像头或门铃",
                "HomeBase 或本地存储",
                "门窗或运动传感器",
                "智能锁",
                "第三方智能家居设备",
            ],
            "pain_points": [
                "误报过多",
                "告警太晚",
                "室内摄像头隐私顾虑",
                "设备孤岛",
                "安装维护复杂",
                "电池与断网问题",
                "订阅费用",
            ],
            "allowed_sensors": [
                "摄像头",
                "毫米波雷达",
                "PIR 运动传感器",
                "门窗磁",
                "声学传感器",
                "环境传感器",
                "可穿戴或手机协同",
            ],
            "privacy_preferences": [
                "优先端侧 AI",
                "优先本地存储",
                "敏感数据不出户",
                "允许可撤回的云端增强",
            ],
            "installation_constraints": [
                "纯无线免布线",
                "租房可移除",
                "用户自行安装",
                "低维护长续航",
                "不改变家装",
            ],
            "connectivity_constraints": [
                "断网仍可工作",
                "弱网环境",
                "兼容 Matter",
                "不依赖单一中枢",
                "支持家庭局域网",
            ],
            "business_preferences": [
                "一次性硬件收入",
                "不依赖强制订阅",
                "可选增值服务",
                "家庭套装",
                "与现有 eufy 设备协同",
            ],
            "desired_outcomes": [
                "更早预防风险",
                "降低误报",
                "缩短处置时间",
                "保护隐私",
                "减少安装学习成本",
                "提升家庭成员安心感",
            ],
            "validation_priorities": [
                "用户愿付价格",
                "误报与漏报",
                "安装完成率",
                "隐私接受度",
                "技术可实现性",
                "三年量产成本",
                "竞品差异化",
            ],
            "innovation_posture": ["近三年可量产", "平衡创新与落地", "探索激进的新形态"],
        },
        "forecast_horizon_years": {"minimum": 1, "maximum": 10, "default": 3},
        "candidate_count": {"minimum": 3, "maximum": 10, "default": 6},
        "default_weights": ForecastRequest(
            question="Predict future AI-native eufy Security product opportunities."
        ).weights.model_dump(),
        "default_strategy_profile": "balanced",
        "strategy_presets": strategy_presets(),
    }


@router.get("/forecast-runs/recent", response_model=ForecastRunListResponse, tags=["forecasting"])
async def list_forecast_runs(limit: int = Query(default=3, ge=1, le=20)) -> ForecastRunListResponse:
    items = repository.list_runs(limit=limit)
    return ForecastRunListResponse(
        items=items,
        total=repository.count_runs(),
        limit=limit,
    )


@router.post(
    "/forecast-runs",
    response_model=ForecastRun,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["forecasting"],
)
async def create_forecast_run(
    request: ForecastRequest,
    background_tasks: BackgroundTasks,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ForecastRun:
    # An optional client-supplied idempotency key makes a double-click or retry
    # return the same run instead of spawning a second background task. The
    # background execution is scheduled only when a run is genuinely created.
    if idempotency_key:
        run_id, created = workflow.create_idempotent(request, idempotency_key)
    else:
        run_id, created = workflow.create(request), True
    if created:
        background_tasks.add_task(workflow.execute, run_id)
    run = repository.get_run(run_id)
    if run is None:  # pragma: no cover - defensive persistence check
        raise HTTPException(status_code=500, detail="forecast run was not persisted")
    return run


@router.get("/forecast-runs/{run_id}", response_model=ForecastRun, tags=["forecasting"])
async def get_forecast_run(run_id: str) -> ForecastRun:
    run = repository.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="forecast run not found")
    return run


@router.get(
    "/forecast-runs/{run_id}/product-definition-state",
    response_model=RunProductDefinitionState,
    tags=["products"],
)
async def get_run_product_definition_state(run_id: str) -> RunProductDefinitionState:
    try:
        return workflow.product_definition_state(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="forecast run not found") from exc


@router.get(
    "/forecast-runs/{run_id}/result",
    response_model=ForecastResult,
    tags=["forecasting"],
)
async def get_forecast_result(run_id: str) -> ForecastResult:
    run = repository.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="forecast run not found")
    if run.status == RunStatus.FAILED:
        raise HTTPException(status_code=422, detail=run.error or "forecast failed")
    if run.status != RunStatus.COMPLETED:
        raise HTTPException(status_code=409, detail=f"forecast is currently {run.stage}")
    return workflow.get_result(run_id)


@router.get(
    "/forecast-runs/{run_id}/candidates",
    response_model=list[RankedCandidate],
    tags=["forecasting"],
)
async def get_candidates(run_id: str) -> list[RankedCandidate]:
    return (await get_forecast_result(run_id)).candidates


@router.get(
    "/forecast-runs/{run_id}/events",
    response_model=list[AgentEvent],
    tags=["observability"],
)
async def get_events(run_id: str, after_sequence: int = Query(default=0, ge=0)) -> list[AgentEvent]:
    if repository.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="forecast run not found")
    return repository.list_events(run_id, after_sequence)


@router.get(
    "/forecast-runs/{run_id}/artifacts",
    response_model=list[Artifact],
    tags=["observability"],
)
async def get_artifacts(run_id: str, kind: str | None = None) -> list[Artifact]:
    if repository.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="forecast run not found")
    artifacts = repository.list_artifacts(run_id)
    return [artifact for artifact in artifacts if kind is None or artifact.kind == kind]


@router.get("/forecast-runs/{run_id}/events/stream", tags=["observability"])
async def stream_events(
    run_id: str, after_sequence: int = Query(default=0, ge=0)
) -> StreamingResponse:
    if repository.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="forecast run not found")

    async def event_source() -> AsyncIterator[str]:
        cursor = after_sequence
        while True:
            events = repository.list_events(run_id, cursor)
            for event in events:
                cursor = event.sequence
                data = event.model_dump(mode="json")
                serialized = json.dumps(data, ensure_ascii=False)
                yield (f"id: {event.sequence}\nevent: {event.event_type}\ndata: {serialized}\n\n")
            run = repository.get_run(run_id)
            if (
                run is None or run.status in {RunStatus.COMPLETED, RunStatus.FAILED}
            ) and not events:
                break
            yield ": keep-alive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/forecast-runs/{run_id}/selections",
    response_model=ProductSpec,
    status_code=status.HTTP_201_CREATED,
    tags=["products"],
)
async def select_candidate(run_id: str, selection: ProductSelectionRequest) -> ProductSpec:
    try:
        return await workflow.define_selected_product(run_id, selection)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="forecast run not found") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/products/{product_id}", response_model=ProductSpec, tags=["products"])
async def get_product(product_id: str) -> ProductSpec:
    product = repository.get_product(product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="product not found")
    return product


@router.post(
    "/products/{product_id}/questions",
    response_model=ProductQuestionRecord,
    status_code=status.HTTP_201_CREATED,
    tags=["products"],
)
async def ask_product_question(
    product_id: str, request: ProductQuestionRequest
) -> ProductQuestionRecord:
    try:
        return await workflow.answer_product_question(product_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="product not found") from exc


@router.get(
    "/products/{product_id}/questions",
    response_model=list[ProductQuestionRecord],
    tags=["products"],
)
async def list_product_questions(product_id: str) -> list[ProductQuestionRecord]:
    try:
        return workflow.list_product_questions(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="product not found") from exc


@router.post(
    "/products/{product_id}/questions/{question_id}/proposal",
    response_model=ProductQuestionRecord,
    status_code=status.HTTP_201_CREATED,
    tags=["products"],
)
async def generate_issue_proposal(product_id: str, question_id: str) -> ProductQuestionRecord:
    try:
        return await workflow.generate_issue_proposal(product_id, question_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="product not found") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/products/{product_id}/issues/dismiss",
    response_model=ProductDefinitionReadiness,
    tags=["products"],
)
async def dismiss_design_issues(
    product_id: str, request: IssueDismissRequest
) -> ProductDefinitionReadiness:
    try:
        return workflow.resolve_design_issues(product_id, request.issue_ids)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="product not found") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/products/{product_id}/revisions",
    response_model=list[ProductRevision],
    tags=["products"],
)
async def list_product_revisions(product_id: str) -> list[ProductRevision]:
    try:
        return workflow.list_product_revisions(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="product not found") from exc


@router.post(
    "/products/{product_id}/revisions",
    response_model=ProductSpec,
    status_code=status.HTTP_201_CREATED,
    tags=["products"],
)
async def revise_product(product_id: str, request: ProductRevisionRequest) -> ProductSpec:
    try:
        return await workflow.revise_product(product_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="product not found") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/products/{product_id}/suggestions/dismiss",
    response_model=ProductDefinitionReadiness,
    tags=["products"],
)
async def dismiss_suggestions(
    product_id: str, request: SuggestionDismissRequest
) -> ProductDefinitionReadiness:
    try:
        return workflow.resolve_suggestions(product_id, request.suggestion_ids)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="product not found") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get(
    "/products/{product_id}/readiness",
    response_model=ProductDefinitionReadiness,
    tags=["products"],
)
async def get_product_readiness(product_id: str) -> ProductDefinitionReadiness:
    try:
        return workflow.product_readiness(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="product not found") from exc


@router.post(
    "/products/{product_id}/confirm",
    response_model=ProductSpec,
    tags=["products"],
)
async def confirm_product(product_id: str) -> ProductSpec:
    try:
        return workflow.confirm_product(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="product not found") from exc
    except DefinitionNotReadyError as exc:
        blocking = len(exc.readiness.blocking_items)
        raise HTTPException(
            status_code=409,
            detail=f"产品定义尚未满足验证准备度：还有 {blocking} 项阻塞项待处理",
        ) from exc


# --------------------------------------------------------------------------- #
# Pre-validation lab (预验证 / 模拟验证)                                          #
# --------------------------------------------------------------------------- #


@router.post(
    "/products/{product_id}/validation-projects",
    response_model=ValidationProject,
    status_code=status.HTTP_201_CREATED,
    tags=["validation"],
)
async def create_validation_project(
    product_id: str, request: ValidationProjectCreateRequest | None = None
) -> ValidationProject:
    try:
        return validation_workflow.create_project(
            product_id, request or ValidationProjectCreateRequest()
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="product not found") from exc
    except ValidationNotReadyError as exc:
        raise HTTPException(
            status_code=409,
            detail="产品尚未完成产品定义（validation_ready），请先在产品定义页确认。",
        ) from exc


@router.get(
    "/products/{product_id}/validation-projects/latest",
    response_model=ValidationProject,
    tags=["validation"],
)
async def get_latest_validation_project(product_id: str) -> ValidationProject:
    try:
        return validation_workflow.get_latest_project(product_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="product not found") from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=404, detail="该产品尚未创建预验证项目"
        ) from exc


@router.get(
    "/validation-projects/{project_id}",
    response_model=ValidationProject,
    tags=["validation"],
)
async def get_validation_project(project_id: str) -> ValidationProject:
    try:
        return validation_workflow.get_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="validation project not found") from exc


@router.get(
    "/validation-projects/{project_id}/visual-summary",
    response_model=ValidationVisualSummary,
    tags=["validation"],
)
async def get_validation_visual_summary(project_id: str) -> ValidationVisualSummary:
    try:
        return validation_insights_service.get_visual_summary(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="validation project not found") from exc


@router.post(
    "/validation-projects/{project_id}/survey",
    response_model=SurveyAccess,
    tags=["validation"],
)
async def create_validation_survey(project_id: str) -> SurveyAccess:
    try:
        return validation_insights_service.create_or_get_survey(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="validation project not found") from exc
    except SurveyNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/validation-projects/{project_id}/survey",
    response_model=SurveyAccess,
    tags=["validation"],
)
async def get_validation_survey(project_id: str) -> SurveyAccess:
    try:
        return validation_insights_service.get_survey_for_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="validation project not found") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="该项目尚未生成调查问卷") from exc


@router.get(
    "/validation-projects/{project_id}/survey-results",
    response_model=SurveyResults,
    tags=["validation"],
)
async def get_validation_survey_results(project_id: str) -> SurveyResults:
    try:
        return validation_insights_service.get_results_for_project(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="validation project not found") from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="该项目尚未生成调查问卷") from exc


@router.get(
    "/surveys/{token}",
    response_model=SurveyAccess,
    tags=["surveys"],
)
async def get_public_validation_survey(token: str) -> SurveyAccess:
    try:
        return validation_insights_service.get_public_survey(token)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="调查问卷不存在") from exc


@router.post(
    "/surveys/{token}/responses",
    response_model=SurveySubmissionResult,
    tags=["surveys"],
)
async def submit_public_validation_survey(
    token: str,
    submission: SurveySubmissionRequest,
) -> SurveySubmissionResult:
    try:
        return validation_insights_service.submit_response(token, submission)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="调查问卷不存在") from exc
    except SurveyClosedError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SurveyAnswerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/validation-projects/{project_id}/feishu-sync",
    response_model=FeishuSyncResult,
    tags=["validation"],
)
async def sync_validation_project_to_feishu(project_id: str) -> FeishuSyncResult:
    try:
        return await validation_report_service.sync_to_feishu(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="validation project not found") from exc
    except ValidationReportNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FeishuConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except FeishuAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post(
    "/validation-projects/{project_id}/run",
    response_model=ValidationProject,
    tags=["validation"],
)
async def run_validation_project(
    project_id: str, background_tasks: BackgroundTasks
) -> ValidationProject:
    try:
        project, scheduled = validation_workflow.request_run(project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="validation project not found") from exc
    if scheduled:
        background_tasks.add_task(validation_workflow.execute, project_id)
    return project


@router.get(
    "/validation-projects/{project_id}/events",
    response_model=list[ValidationEvent],
    tags=["validation"],
)
async def get_validation_events(
    project_id: str, after_sequence: int = Query(default=0, ge=0)
) -> list[ValidationEvent]:
    try:
        return validation_workflow.list_events(project_id, after_sequence)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="validation project not found") from exc


@router.get("/validation-projects/{project_id}/events/stream", tags=["validation"])
async def stream_validation_events(
    project_id: str, after_sequence: int = Query(default=0, ge=0)
) -> StreamingResponse:
    if repository.get_validation_project(project_id) is None:
        raise HTTPException(status_code=404, detail="validation project not found")

    async def event_source() -> AsyncIterator[str]:
        cursor = after_sequence
        while True:
            events = repository.list_validation_events(project_id, cursor)
            for event in events:
                cursor = event.sequence
                data = event.model_dump(mode="json")
                serialized = json.dumps(data, ensure_ascii=False)
                yield (f"id: {event.sequence}\nevent: {event.event_type}\ndata: {serialized}\n\n")
            project = repository.get_validation_project(project_id)
            terminal = project is None or project.status in {
                ValidationProjectStatus.COMPLETED,
                ValidationProjectStatus.FAILED,
            }
            if terminal and not events:
                break
            yield ": keep-alive\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post(
    "/validation-findings/{finding_id}/send-back",
    response_model=SendBackResponse,
    tags=["validation"],
)
async def send_back_validation_finding(finding_id: str) -> SendBackResponse:
    try:
        return validation_workflow.send_back_finding(finding_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="finding not found") from exc
