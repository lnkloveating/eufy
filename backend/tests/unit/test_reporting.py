"""Tests for deterministic report formatting and the Feishu adapter."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest

from eufy_security_agents.domain.models import ProductSpec
from eufy_security_agents.domain.reporting import (
    ResearchConclusionType,
    build_validation_research_report,
)
from eufy_security_agents.domain.validation import (
    ExperimentStatus,
    ExperimentType,
    ExperimentVerdict,
    ValidationExperiment,
    ValidationProject,
    ValidationProjectStatus,
)
from eufy_security_agents.infrastructure.feishu import (
    OVERVIEW_FIELD_DEFINITIONS,
    REPORT_FIELD_DEFINITIONS,
    FeishuBitablePublisher,
    FeishuConfigurationError,
)


def _experiment(identifier: str, verdict: ExperimentVerdict) -> ValidationExperiment:
    return ValidationExperiment(
        id=identifier,
        project_id="vproj-report",
        hypothesis_id=f"H-{identifier}",
        title=f"假设 {identifier}",
        assumption=f"需要判断的假设 {identifier}",
        experiment_type=ExperimentType.TECHNOLOGY,
        metric="可靠性",
        proposed_method="确定性模拟",
        pass_condition="满足门槛",
        kill_condition="出现阻断项",
        status=ExperimentStatus.COMPLETED,
        verdict=verdict,
        verdict_reason=f"{identifier} 的裁决理由",
        supporting_points=[f"{identifier} 的证据"],
        next_recommended_test=f"执行 {identifier} 的真实测试",
    )


def _project() -> ValidationProject:
    product = ProductSpec.model_construct(name="eufy Horizon", version="1.0")
    return ValidationProject.model_construct(
        id="vproj-report",
        product_id="product-report",
        product_version="1.0",
        product_snapshot=product,
        status=ValidationProjectStatus.COMPLETED,
        experiments=[
            _experiment("supported", ExperimentVerdict.SUPPORTED_IN_SIMULATION),
            _experiment("real", ExperimentVerdict.REQUIRES_REAL_WORLD_TEST),
            _experiment("failed", ExperimentVerdict.CONTRADICTED),
            _experiment("research", ExperimentVerdict.INCONCLUSIVE),
        ],
    )


def test_report_preserves_english_product_name_and_classifies_each_experiment() -> None:
    project = _project()
    report = build_validation_research_report(project)

    assert report.product_name == "eufy Horizon"
    assert [row.conclusion_type for row in report.rows] == [
        ResearchConclusionType.SIMULATION_SUPPORTED,
        ResearchConclusionType.REAL_VALIDATION_REQUIRED,
        ResearchConclusionType.UNQUALIFIED,
        ResearchConclusionType.RESEARCH_REQUIRED,
    ]
    assert all(row.project_id == "vproj-report" for row in report.rows)
    assert all(row.generated_at == project.updated_at for row in report.rows)
    assert report.rows[2].priority == "高"


@pytest.mark.asyncio
async def test_feishu_publisher_resolves_wiki_initializes_fields_and_writes_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[httpx.Request] = []
    write_attempts = 0
    created_tables: list[dict[str, str]] = []
    overview_records: list[dict[str, object]] = []
    overview_updates = 0

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("eufy_security_agents.infrastructure.feishu.asyncio.sleep", no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal overview_updates, write_attempts
        requests.append(request)
        path = request.url.path
        if path.endswith("/auth/v3/tenant_access_token/internal"):
            return httpx.Response(
                200,
                json={"code": 0, "tenant_access_token": "t-test", "expire": 7200},
            )
        if path.endswith("/wiki/v2/spaces/get_node"):
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {"node": {"obj_type": "bitable", "obj_token": "app-test"}},
                },
            )
        if path.endswith("/bitable/v1/apps/app-test/tables") and request.method == "GET":
            return httpx.Response(
                200,
                json={"code": 0, "data": {"items": created_tables, "has_more": False}},
            )
        if path.endswith("/bitable/v1/apps/app-test/tables") and request.method == "POST":
            payload = json.loads(request.content)
            table_name = payload["table"]["name"]
            if table_name == "研究总览":
                table_id = "tbl-overview"
                assert payload["table"]["default_view_name"] == "研究概览"
            else:
                table_id = "tbl-product"
                assert table_name.startswith("eufy Horizon · ")
                assert payload["table"]["default_view_name"] == "验证结论"
                definitions = payload["table"]["fields"]
                conclusion_field = next(
                    field for field in definitions if field["field_name"] == "结论分类"
                )
                assert conclusion_field["type"] == 3
                assert len(conclusion_field["property"]["options"]) == 4
            created_tables.append({"name": table_name, "table_id": table_id})
            return httpx.Response(
                200,
                json={"code": 0, "data": {"table_id": table_id}},
            )
        if path.endswith("/fields") and request.method == "GET":
            definitions = (
                OVERVIEW_FIELD_DEFINITIONS
                if "/tables/tbl-overview/" in path
                else REPORT_FIELD_DEFINITIONS
            )
            fields = [
                {
                    "field_id": f"fld-{index}",
                    **definition,
                    "is_primary": index == 0,
                }
                for index, definition in enumerate(definitions)
            ]
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {"items": fields},
                },
            )
        if path.endswith("/fields") and request.method == "POST":
            return httpx.Response(200, json={"code": 0, "data": {}})
        if path.endswith("/tables/tbl-overview/records") and request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {"items": overview_records, "has_more": False},
                },
            )
        if path.endswith("/records/batch_create"):
            payload = json.loads(request.content)
            records = payload["records"]
            if "/tables/tbl-overview/" in path:
                overview = records[0]["fields"]
                assert overview["产品名称"] == "eufy Horizon"
                assert overview["验证假设总数"] == 4
                assert overview["模拟支持"] == 1
                assert overview["调查样本"] == 0
                overview_records.append(
                    {"record_id": "rec-overview", "fields": overview}
                )
            else:
                write_attempts += 1
                if write_attempts > 1:
                    return httpx.Response(
                        400,
                        json={"code": 1254608, "msg": "duplicate client token"},
                    )
                assert records[0]["fields"]["验证假设"] == "需要判断的假设 supported"
                assert records[0]["fields"]["结论分类"] == "模拟支持"
                assert isinstance(records[0]["fields"]["同步时间"], int)
            client_token = request.url.params["client_token"]
            assert uuid.UUID(client_token).version == 4
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "data": {
                        "records": [
                            {"record_id": f"rec-{index}"} for index, _ in enumerate(records)
                        ]
                    },
                },
            )
        if path.endswith("/records/batch_update"):
            overview_updates += 1
            payload = json.loads(request.content)
            assert payload["records"][0]["record_id"] == "rec-overview"
            assert payload["records"][0]["fields"]["验证假设总数"] == 4
            return httpx.Response(
                200,
                json={"code": 0, "data": {"records": payload["records"]}},
            )
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    publisher = FeishuBitablePublisher(
        app_id="cli-test",
        app_secret="secret-test",
        wiki_node_token="wiki-test",
        table_id="tbl-test",
        table_url="https://example.feishu.cn/wiki/wiki-test?table=tbl-test",
        transport=httpx.MockTransport(handler),
    )

    result = await publisher.publish(build_validation_research_report(_project()))
    repeated = await publisher.publish(build_validation_research_report(_project()))

    assert result.records_created == 4
    assert result.category_counts["待真实验证"] == 1
    assert result.table_id == "tbl-product"
    assert result.table_name.startswith("eufy Horizon · ")
    assert result.table_url == "https://example.feishu.cn/wiki/wiki-test?table=tbl-product"
    assert result.overview_table_url == (
        "https://example.feishu.cn/wiki/wiki-test?table=tbl-overview"
    )
    assert repeated.records_created == 0
    assert write_attempts == 2
    assert overview_updates == 1
    assert any(request.url.path.endswith("/wiki/v2/spaces/get_node") for request in requests)
    created_fields = [
        request
        for request in requests
        if request.url.path.endswith("/fields") and request.method == "POST"
    ]
    assert len(created_fields) == 0


@pytest.mark.asyncio
async def test_feishu_publisher_reports_missing_configuration_without_network() -> None:
    publisher = FeishuBitablePublisher(app_id="", app_secret="", table_id="")
    with pytest.raises(FeishuConfigurationError, match="FEISHU_APP_ID"):
        await publisher.publish(build_validation_research_report(_project()))
