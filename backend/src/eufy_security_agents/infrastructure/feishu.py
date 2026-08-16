"""Feishu OpenAPI adapter for publishing validation reports to Bitable."""

from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from eufy_security_agents.domain.reporting import (
    FeishuSyncResult,
    ValidationResearchReport,
    category_counts,
)

PRIMARY_FIELD_NAME = "验证假设"
REPORT_FIELD_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {"field_name": PRIMARY_FIELD_NAME, "type": 1},
    {
        "field_name": "结论分类",
        "type": 3,
        "property": {
            "options": [
                {"name": "不合格", "color": 0},
                {"name": "待真实验证", "color": 1},
                {"name": "待真实调研", "color": 3},
                {"name": "模拟支持", "color": 5},
            ]
        },
    },
    {"field_name": "原因", "type": 1},
    {"field_name": "证据摘要", "type": 1},
    {"field_name": "建议行动", "type": 1},
    {
        "field_name": "优先级",
        "type": 3,
        "property": {
            "options": [
                {"name": "高", "color": 0},
                {"name": "中", "color": 2},
                {"name": "低", "color": 5},
            ]
        },
    },
    {"field_name": "产品版本", "type": 1},
    {"field_name": "研究编号", "type": 1},
    {
        "field_name": "同步时间",
        "type": 5,
        "property": {"date_formatter": "yyyy/MM/dd HH:mm"},
    },
)

OVERVIEW_TABLE_NAME = "研究总览"
OVERVIEW_PRIMARY_FIELD = "产品名称"
OVERVIEW_FIELD_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {"field_name": OVERVIEW_PRIMARY_FIELD, "type": 1},
    {"field_name": "研究编号", "type": 1},
    {"field_name": "产品版本", "type": 1},
    {"field_name": "验证假设总数", "type": 2},
    {"field_name": "模拟支持", "type": 2},
    {"field_name": "待真实调研", "type": 2},
    {"field_name": "待真实验证", "type": 2},
    {"field_name": "不合格", "type": 2},
    {"field_name": "高优先级", "type": 2},
    {"field_name": "调查样本", "type": 2},
    {"field_name": "调查问卷链接", "type": 1},
    {"field_name": "产品明细链接", "type": 1},
    {
        "field_name": "更新时间",
        "type": 5,
        "property": {"date_formatter": "yyyy/MM/dd HH:mm"},
    },
)

RETRYABLE_CODES = {1254290, 1254291, 1254607, 1255040}


class FeishuConfigurationError(RuntimeError):
    pass


class FeishuAPIError(RuntimeError):
    def __init__(self, message: str, *, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class FeishuBitablePublisher:
    def __init__(
        self,
        *,
        app_id: str,
        app_secret: str,
        table_id: str,
        app_token: str = "",
        wiki_node_token: str = "",
        table_url: str = "",
        api_base_url: str = "https://open.feishu.cn/open-apis",
        timeout_seconds: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._app_id = app_id.strip()
        self._app_secret = app_secret.strip()
        # Kept only so existing deployments do not need an environment migration.
        # New reports resolve/create a dedicated table for each product.
        self._table_id = table_id.strip()
        self._app_token = app_token.strip()
        self._wiki_node_token = wiki_node_token.strip()
        self._table_url = table_url.strip() or None
        self._api_base_url = api_base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def _assert_configured(self) -> None:
        missing: list[str] = []
        if not self._app_id:
            missing.append("FEISHU_APP_ID")
        if not self._app_secret:
            missing.append("FEISHU_APP_SECRET")
        if not self._app_token and not self._wiki_node_token:
            missing.append("FEISHU_BITABLE_APP_TOKEN 或 FEISHU_WIKI_NODE_TOKEN")
        if missing:
            raise FeishuConfigurationError("飞书配置不完整：" + "、".join(missing))

    async def publish(self, report: ValidationResearchReport) -> FeishuSyncResult:
        self._assert_configured()
        async with httpx.AsyncClient(
            base_url=self._api_base_url,
            timeout=self._timeout_seconds,
            transport=self._transport,
        ) as client:
            access_token = await self._tenant_access_token(client)
            app_token = await self._resolve_app_token(client, access_token)
            table_name = _product_table_name(report.product_name, report.product_id)
            table_id = await self._get_or_create_product_table(
                client,
                access_token,
                app_token,
                table_name,
            )
            primary_field, existing_fields = await self._ensure_fields(
                client,
                access_token,
                app_token,
                table_id,
                REPORT_FIELD_DEFINITIONS,
            )
            records = [
                {
                    "fields": {
                        primary_field: row.conclusion,
                        "结论分类": row.conclusion_type.label,
                        "原因": row.reason,
                        "证据摘要": row.evidence_summary,
                        "建议行动": row.recommended_action,
                        "优先级": row.priority,
                        "产品版本": report.product_version,
                        "研究编号": row.project_id,
                        "同步时间": int(row.generated_at.timestamp() * 1000),
                    }
                }
                for row in report.rows
            ]
            unknown = set(records[0]["fields"]) - existing_fields - {primary_field}
            if unknown:
                raise FeishuAPIError("飞书表格字段初始化未完成，请稍后重试。")
            try:
                data = await self._request(
                    client,
                    "POST",
                    f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
                    access_token=access_token,
                    params={"client_token": _idempotency_token(report.project_id, table_id)},
                    json={"records": records},
                )
            except FeishuAPIError as exc:
                # The detail report is immutable for a completed validation run.
                # A later sync may only refresh survey counts in the overview.
                if exc.code != 1254608:
                    raise
                data = {"records": []}

            overview_table_id = await self._get_or_create_overview_table(
                client,
                access_token,
                app_token,
            )
            await self._ensure_fields(
                client,
                access_token,
                app_token,
                overview_table_id,
                OVERVIEW_FIELD_DEFINITIONS,
            )
            await self._upsert_overview_record(
                client,
                access_token,
                app_token,
                overview_table_id,
                report,
                product_table_url=_table_url(self._table_url, table_id),
            )
        created = data.get("records", [])
        return FeishuSyncResult(
            project_id=report.project_id,
            table_id=table_id,
            table_name=table_name,
            records_created=len(created) if isinstance(created, list) else len(records),
            category_counts=category_counts(report),
            table_url=_table_url(self._table_url, table_id),
            overview_table_url=_table_url(self._table_url, overview_table_id),
        )

    async def _get_or_create_product_table(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        app_token: str,
        table_name: str,
    ) -> str:
        tables = await self._list_tables(client, access_token, app_token)
        existing = next((table for table in tables if table.get("name") == table_name), None)
        if existing is not None:
            table_id = existing.get("table_id")
            if isinstance(table_id, str) and table_id:
                return table_id
            raise FeishuAPIError("飞书返回的数据表缺少有效 ID。")

        data = await self._request(
            client,
            "POST",
            f"/bitable/v1/apps/{app_token}/tables",
            access_token=access_token,
            json={
                "table": {
                    "name": table_name,
                    "default_view_name": "验证结论",
                    "fields": list(REPORT_FIELD_DEFINITIONS),
                }
            },
        )
        table_id = data.get("table_id")
        if not isinstance(table_id, str) or not table_id:
            raise FeishuAPIError("飞书创建产品数据表后未返回有效 ID。")
        # Let the following schema read observe the newly created fields.
        await asyncio.sleep(0.5)
        return table_id

    async def _get_or_create_overview_table(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        app_token: str,
    ) -> str:
        tables = await self._list_tables(client, access_token, app_token)
        existing = next(
            (table for table in tables if table.get("name") == OVERVIEW_TABLE_NAME),
            None,
        )
        if existing is not None:
            table_id = existing.get("table_id")
            if isinstance(table_id, str) and table_id:
                return table_id
            raise FeishuAPIError("飞书研究总览缺少有效 ID。")
        data = await self._request(
            client,
            "POST",
            f"/bitable/v1/apps/{app_token}/tables",
            access_token=access_token,
            json={
                "table": {
                    "name": OVERVIEW_TABLE_NAME,
                    "default_view_name": "研究概览",
                    "fields": list(OVERVIEW_FIELD_DEFINITIONS),
                }
            },
        )
        table_id = data.get("table_id")
        if not isinstance(table_id, str) or not table_id:
            raise FeishuAPIError("飞书创建研究总览后未返回有效 ID。")
        await asyncio.sleep(0.5)
        return table_id

    async def _upsert_overview_record(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        app_token: str,
        table_id: str,
        report: ValidationResearchReport,
        *,
        product_table_url: str | None,
    ) -> None:
        counts = category_counts(report)
        fields: dict[str, Any] = {
            OVERVIEW_PRIMARY_FIELD: report.product_name,
            "研究编号": report.project_id,
            "产品版本": report.product_version,
            "验证假设总数": len(report.rows),
            "模拟支持": counts.get("模拟支持", 0),
            "待真实调研": counts.get("待真实调研", 0),
            "待真实验证": counts.get("待真实验证", 0),
            "不合格": counts.get("不合格", 0),
            "高优先级": sum(row.priority == "高" for row in report.rows),
            "调查样本": report.survey_response_count,
            "调查问卷链接": report.survey_url or "尚未生成",
            "产品明细链接": product_table_url or "请在当前多维表格中查看产品明细表",
            "更新时间": int(datetime.now(UTC).timestamp() * 1000),
        }
        records = await self._list_records(client, access_token, app_token, table_id)
        existing = next(
            (
                item
                for item in records
                if isinstance(item.get("fields"), dict)
                and item["fields"].get("研究编号") == report.project_id
            ),
            None,
        )
        if existing is None:
            await self._request(
                client,
                "POST",
                f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
                access_token=access_token,
                params={
                    "client_token": _idempotency_token(
                        f"overview:{report.project_id}", table_id
                    )
                },
                json={"records": [{"fields": fields}]},
            )
            return
        record_id = existing.get("record_id")
        if not isinstance(record_id, str) or not record_id:
            raise FeishuAPIError("飞书研究总览记录缺少有效 ID。")
        await self._request(
            client,
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
            access_token=access_token,
            json={"records": [{"record_id": record_id, "fields": fields}]},
        )

    async def _list_records(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        app_token: str,
        table_id: str,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token
            data = await self._request(
                client,
                "GET",
                f"/bitable/v1/apps/{app_token}/tables/{table_id}/records",
                access_token=access_token,
                params=params,
            )
            items = data.get("items")
            if isinstance(items, list):
                records.extend(item for item in items if isinstance(item, dict))
            if not data.get("has_more"):
                return records
            next_token = data.get("page_token")
            if not isinstance(next_token, str) or not next_token:
                raise FeishuAPIError("飞书研究总览分页响应缺少 page_token。")
            page_token = next_token

    async def _list_tables(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        app_token: str,
    ) -> list[dict[str, Any]]:
        tables: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": 100}
            if page_token:
                params["page_token"] = page_token
            data = await self._request(
                client,
                "GET",
                f"/bitable/v1/apps/{app_token}/tables",
                access_token=access_token,
                params=params,
            )
            items = data.get("items")
            if isinstance(items, list):
                tables.extend(item for item in items if isinstance(item, dict))
            if not data.get("has_more"):
                return tables
            next_token = data.get("page_token")
            if not isinstance(next_token, str) or not next_token:
                raise FeishuAPIError("飞书数据表分页响应缺少 page_token。")
            page_token = next_token

    async def _tenant_access_token(self, client: httpx.AsyncClient) -> str:
        data = await self._request(
            client,
            "POST",
            "/auth/v3/tenant_access_token/internal",
            json={"app_id": self._app_id, "app_secret": self._app_secret},
        )
        token = data.get("tenant_access_token")
        if not isinstance(token, str) or not token:
            raise FeishuAPIError("飞书未返回有效的应用访问凭证。")
        return token

    async def _resolve_app_token(self, client: httpx.AsyncClient, access_token: str) -> str:
        if self._app_token:
            return self._app_token
        data = await self._request(
            client,
            "GET",
            "/wiki/v2/spaces/get_node",
            access_token=access_token,
            params={"token": self._wiki_node_token},
        )
        node = data.get("node")
        if not isinstance(node, dict) or node.get("obj_type") != "bitable":
            raise FeishuAPIError("配置的 Wiki 节点不是多维表格。")
        token = node.get("obj_token")
        if not isinstance(token, str) or not token:
            raise FeishuAPIError("无法从 Wiki 链接解析多维表格 app_token。")
        return token

    async def _ensure_fields(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        app_token: str,
        table_id: str,
        field_definitions: tuple[dict[str, Any], ...],
    ) -> tuple[str, set[str]]:
        path = f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields"
        data = await self._request(
            client,
            "GET",
            path,
            access_token=access_token,
            params={"page_size": 100},
        )
        items = data.get("items")
        if not isinstance(items, list) or not items:
            raise FeishuAPIError("目标多维表格中没有可用字段。")
        fields = [item for item in items if isinstance(item, dict)]
        primary = next((item for item in fields if item.get("is_primary") is True), fields[0])
        primary_name = primary.get("field_name")
        if not isinstance(primary_name, str) or not primary_name:
            raise FeishuAPIError("无法识别多维表格主字段。")
        existing = {
            str(item["field_name"]) for item in fields if isinstance(item.get("field_name"), str)
        }
        created_any = False
        for field_definition in field_definitions:
            field_name = str(field_definition["field_name"])
            if field_name in existing:
                continue
            await self._request(
                client,
                "POST",
                path,
                access_token=access_token,
                json=field_definition,
            )
            existing.add(field_name)
            created_any = True
        if created_any:
            # Bitable applies schema edits serially; a short pause prevents the
            # immediately following batch write from observing stale metadata.
            await asyncio.sleep(0.5)
        return primary_name, existing

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        path: str,
        *,
        access_token: str | None = None,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        max_attempts = 5
        for attempt in range(max_attempts):
            try:
                response = await client.request(
                    method, path, headers=headers, params=params, json=json
                )
            except httpx.TimeoutException as exc:
                if attempt < max_attempts - 1:
                    await asyncio.sleep(min(0.75 * (2**attempt), 4.0))
                    continue
                raise FeishuAPIError("连接飞书超时，请稍后重试。") from exc
            except httpx.HTTPError as exc:
                raise FeishuAPIError("无法连接飞书开放平台。") from exc
            try:
                body = response.json()
            except ValueError as exc:
                raise FeishuAPIError("飞书返回了无法解析的响应。") from exc
            if not isinstance(body, dict):
                raise FeishuAPIError("飞书返回了无效响应。")
            code = body.get("code", 0 if response.is_success else response.status_code)
            numeric_code = code if isinstance(code, int) else None
            if response.is_success and numeric_code == 0:
                data = body.get("data")
                return data if isinstance(data, dict) else body
            if attempt < max_attempts - 1 and (
                response.status_code in {429, 500, 502, 503, 504} or numeric_code in RETRYABLE_CODES
            ):
                await asyncio.sleep(min(0.75 * (2**attempt), 4.0))
                continue
            raise FeishuAPIError(
                _friendly_error(response.status_code, numeric_code), code=numeric_code
            )
        raise FeishuAPIError("飞书请求失败，请稍后重试。")


def _idempotency_token(project_id: str, table_id: str) -> str:
    # Tokens are scoped to both the report and its destination. Older builds wrote
    # the same project to a shared table; reusing that token for a new product table
    # causes Feishu 1254608 even though the new table is fully writable.
    identity = f"validation-report-v3:{project_id}:{table_id}"
    digest = bytearray(hashlib.sha256(identity.encode("utf-8")).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x40
    digest[8] = (digest[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(digest)))


def _product_table_name(product_name: str, product_id: str) -> str:
    clean_name = re.sub(r"[\r\n\t]+", " ", product_name).strip() or "未命名产品"
    clean_name = re.sub(r"\s{2,}", " ", clean_name)
    suffix = hashlib.sha256(product_id.encode("utf-8")).hexdigest()[:8]
    # Leave room for the separator and stable suffix within Feishu's 100-char name limit.
    return f"{clean_name[:89]} · {suffix}"


def _table_url(configured_url: str | None, table_id: str) -> str | None:
    if not configured_url:
        return None
    parts = urlsplit(configured_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["table"] = table_id
    query.pop("view", None)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _friendly_error(status_code: int, code: int | None) -> str:
    if code == 1254608:
        return "飞书拒绝了重复的同步请求标识，请重启后端后再次同步。"
    if status_code in {401, 403} or code in {99991663, 99991668}:
        return "飞书应用权限不足，请检查应用权限、发布版本和文档应用授权。"
    if code in {1254027, 1254302, 1254303}:
        return "飞书应用没有目标多维表格的编辑权限，请重新添加文档应用。"
    if code in {1254003, 1254004, 1254040, 1254041}:
        return "飞书多维表格 Token 或数据表 ID 无效。"
    if code == 131006:
        return "飞书应用没有该 Wiki 节点的阅读权限。"
    if status_code == 429 or code in RETRYABLE_CODES:
        return "飞书服务繁忙，请稍后重试。"
    return f"飞书同步失败（错误码 {code or status_code}）。"
