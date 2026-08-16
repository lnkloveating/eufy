"""Auditable layered retrieval over the local evidence knowledge base."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from eufy_security_agents.domain.models import (
    ClaimStatus,
    EvidenceRecord,
    ForecastRequest,
    KnowledgeCoverage,
    KnowledgeLayer,
    RegionCoverage,
    RetrievalPlan,
)
from eufy_security_agents.domain.strategy import (
    strategy_explanation,
    strategy_layer_adjustments,
    strategy_topic_boosts,
)

ALL_LAYERS = list(KnowledgeLayer)
DEFAULT_LAYER_QUOTAS = {
    KnowledgeLayer.EUFY_FOUNDATION: 5,
    KnowledgeLayer.REGIONAL_MARKET: 7,
    KnowledgeLayer.USER_NEEDS: 4,
    KnowledgeLayer.TECHNOLOGY: 4,
    KnowledgeLayer.PRIVACY_REGULATION: 3,
    KnowledgeLayer.BUSINESS: 3,
    KnowledgeLayer.RISK_COUNTEREVIDENCE: 4,
}

REGION_GROUPS = {
    "European Union": {"Germany", "France", "European Union"},
    "Germany": {"Germany", "European Union"},
    "France": {"France", "European Union"},
    "United Kingdom": {"United Kingdom"},
}

TOPIC_ALIASES = {
    "apartment": {"apartment", "flat", "公寓", "高层", "入户"},
    "detached_home": {"detached", "suburban", "yard", "garage", "独栋", "车库", "庭院"},
    "privacy": {"privacy", "consent", "retention", "隐私", "同意", "人脸"},
    "eldercare": {"elder", "senior", "aging", "老人", "老年", "养老"},
    "child_safety": {"child", "baby", "children", "儿童", "孩子", "婴儿"},
    "pet": {"pet", "dog", "cat", "宠物", "猫", "狗"},
    "package": {"package", "delivery", "parcel", "包裹", "快递"},
    "vehicle": {"vehicle", "car", "garage", "汽车", "车辆", "车库"},
    "subscription": {"subscription", "recurring", "订阅", "月费"},
    "low_power": {"battery", "low-power", "power", "电池", "低功耗", "功耗"},
    "edge_ai": {"edge ai", "local ai", "on-device", "ai原生", "边缘ai", "本地ai", "端侧"},
    "interoperability": {"matter", "interoperability", "ecosystem", "互联", "生态", "兼容"},
}


class LocalEvidenceStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._records: list[EvidenceRecord] | None = None

    def load(self) -> list[EvidenceRecord]:
        if self._records is not None:
            return list(self._records)
        records: list[EvidenceRecord] = []
        seen_ids: set[str] = set()
        for path in sorted(self._root.rglob("*.jsonl")):
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    record = EvidenceRecord.model_validate_json(line)
                except Exception as exc:
                    raise ValueError(f"invalid evidence at {path}:{line_number}") from exc
                if record.id in seen_ids:
                    raise ValueError(f"duplicate evidence ID {record.id} at {path}:{line_number}")
                seen_ids.add(record.id)
                records.append(record)
        if not records:
            raise ValueError(f"no evidence records found in {self._root}")
        self._records = records
        return list(records)

    def coverage(self, regions: list[str] | None = None) -> KnowledgeCoverage:
        records = self.load()
        requested = regions or sorted(
            {region for record in records for region in record.regions if region != "Global"}
        )
        counts = Counter(record.layer.value for record in records if record.layer)
        return KnowledgeCoverage(
            total_records=len(records),
            records_by_layer=dict(sorted(counts.items())),
            regions=[self._region_coverage(region, records) for region in requested],
        )

    def plan(self, request: ForecastRequest) -> RetrievalPlan:
        text = " ".join(
            [
                request.question,
                request.category,
                request.price_segment or "",
                *request.regions,
                *request.target_users,
                *request.constraints,
                *request.research_context.search_terms(),
            ]
        ).lower()
        query_topics = sorted(
            topic
            for topic, aliases in TOPIC_ALIASES.items()
            if any(alias in text for alias in aliases)
        )
        required_layers = list(ALL_LAYERS)
        quotas = {layer.value: quota for layer, quota in DEFAULT_LAYER_QUOTAS.items()}
        # Strategy tilts quotas on top of the base (never below the base, so every
        # one of the seven layers keeps its minimum), then region hard-routing is
        # re-applied last to preserve its highest priority.
        strategy_adjustments = strategy_layer_adjustments(request.weights)
        for layer_value, delta in strategy_adjustments.items():
            quotas[layer_value] = quotas.get(layer_value, 0) + delta
        if len(request.regions) > 1:
            quotas[KnowledgeLayer.REGIONAL_MARKET.value] = max(
                quotas[KnowledgeLayer.REGIONAL_MARKET.value], min(12, 4 * len(request.regions))
            )
            quotas[KnowledgeLayer.PRIVACY_REGULATION.value] = max(
                quotas[KnowledgeLayer.PRIVACY_REGULATION.value], min(6, 2 * len(request.regions))
            )
        coverage = self.coverage(request.regions).regions
        fallback = any(item.level == "limited" for item in coverage)
        strategy_topics = sorted(strategy_topic_boosts(request.weights))
        return RetrievalPlan(
            requested_regions=request.regions,
            query_topics=query_topics,
            required_layers=required_layers,
            excluded_topics=[],
            layer_quotas=quotas,
            coverage=coverage,
            fallback_used=fallback,
            selected_evidence_ids=[],
            selection_reasons={},
            explanation=(
                "按 eufy 基础、所选地区、用户需求、技术、隐私法规、商业与反证七层进行配额检索；"
                "地区记录采用硬路由，全球记录作为共同基线；结构化 ResearchContext "
                "参与主题识别与层内证据排序。"
            ),
            strategy_profile=request.strategy_profile,
            strategy_adjustments=strategy_adjustments,
            strategy_topics=strategy_topics,
            strategy_explanation=strategy_explanation(request.weights, request.strategy_profile),
        )

    def retrieve(self, request: ForecastRequest) -> tuple[RetrievalPlan, list[EvidenceRecord]]:
        plan = self.plan(request)
        records = self.load()
        requested_regions = self._expanded_requested_regions(request.regions)
        query_text = " ".join(
            [
                request.question,
                request.category,
                request.price_segment or "",
                *request.target_users,
                *request.constraints,
                *request.research_context.search_terms(),
            ]
        )
        query_tokens = _tokens(query_text)
        strategy_topics = strategy_topic_boosts(request.weights)
        selected: list[EvidenceRecord] = []
        reasons: dict[str, list[str]] = {}

        def eligible(record: EvidenceRecord) -> bool:
            record_regions = set(record.regions)
            return bool(
                "Global" in record_regions
                or "Global" in request.regions
                or record_regions & requested_regions
            )

        for layer in plan.required_layers:
            candidates = [
                record for record in records if record.layer == layer and eligible(record)
            ]
            ranked = sorted(
                candidates,
                key=lambda record: self._score(
                    record,
                    requested_regions,
                    query_tokens,
                    set(plan.query_topics),
                    strategy_topics,
                ),
                reverse=True,
            )
            quota = plan.layer_quotas.get(layer.value, 0)
            for record in ranked[:quota]:
                if record in selected:
                    continue
                selected.append(record)
                why = [f"知识层：{layer.value}"]
                if set(record.regions) & requested_regions:
                    why.append("匹配所选地区")
                elif "Global" in record.regions:
                    why.append("全球共同基线")
                matched_topics = sorted(set(record.topics) & set(plan.query_topics))
                if matched_topics:
                    why.append(f"主题匹配：{', '.join(matched_topics)}")
                strategy_matches = sorted(set(record.topics) & set(strategy_topics))
                if strategy_matches:
                    why.append(f"策略偏好：{', '.join(strategy_matches)}")
                why.append(f"可信度：{record.credibility:.2f}")
                reasons[record.id] = why

        # Guarantee every selected region is represented when the knowledge base has records for it.
        for region in request.regions:
            if any(region in item.regions for item in selected):
                continue
            regional = [record for record in records if region in record.regions]
            if regional:
                record = max(
                    regional,
                    key=lambda item: self._score(
                        item,
                        requested_regions,
                        query_tokens,
                        set(plan.query_topics),
                        strategy_topics,
                    ),
                )
                selected.append(record)
                reasons[record.id] = [
                    f"确保地区覆盖：{region}",
                    f"可信度：{record.credibility:.2f}",
                ]

        completed = plan.model_copy(
            update={
                "selected_evidence_ids": [record.id for record in selected],
                "selection_reasons": reasons,
            }
        )
        return completed, selected

    def search(self, request: ForecastRequest, limit: int = 40) -> list[EvidenceRecord]:
        """Backward-compatible entry point; layered retrieval remains authoritative."""
        _, records = self.retrieve(request)
        return records[:limit]

    @staticmethod
    def _score(
        record: EvidenceRecord,
        requested_regions: set[str],
        query_tokens: set[str],
        query_topics: set[str],
        strategy_topics: dict[str, float] | None = None,
    ) -> float:
        region_overlap = set(record.regions) & requested_regions
        region_score = 12.0 if region_overlap else (3.0 if "Global" in record.regions else 0.0)
        record_tokens = _tokens(
            " ".join([record.title, record.content, record.category, *record.tags, *record.topics])
        )
        token_score = min(8.0, len(query_tokens & record_tokens) * 0.8)
        topic_score = len(query_topics & set(record.topics)) * 3.0
        claim_status = record.claim_status or ClaimStatus.HYPOTHESIS
        status_score = {
            ClaimStatus.VERIFIED: 3.0,
            ClaimStatus.OFFICIAL_CLAIM: 2.8,
            ClaimStatus.RESEARCH_SYNTHESIS: 1.4,
            ClaimStatus.HYPOTHESIS: 0.5,
        }[claim_status]
        counter_score = 1.5 if record.contradicts else 0.0
        # Strategy only reorders *within* a layer (max ~2.5 per matched topic),
        # deliberately below the region hard-routing score so region priority
        # always dominates.
        strategy_score = 0.0
        if strategy_topics:
            strategy_score = 2.5 * sum(strategy_topics.get(topic, 0.0) for topic in record.topics)
        return (
            region_score
            + token_score
            + topic_score
            + status_score
            + counter_score
            + strategy_score
            + 4 * record.credibility
        )

    @staticmethod
    def _expanded_requested_regions(regions: list[str]) -> set[str]:
        expanded: set[str] = set()
        for region in regions:
            expanded.add(region)
            expanded.update(REGION_GROUPS.get(region, set()))
        return expanded

    def _region_coverage(self, region: str, records: list[EvidenceRecord]) -> RegionCoverage:
        expanded = self._expanded_requested_regions([region])
        regional = [record for record in records if set(record.regions) & expanded]
        represented = sorted(
            {record.layer for record in regional if record.layer}, key=lambda layer: layer.value
        )
        required_regional = {
            KnowledgeLayer.REGIONAL_MARKET,
            KnowledgeLayer.USER_NEEDS,
            KnowledgeLayer.PRIVACY_REGULATION,
            KnowledgeLayer.BUSINESS,
        }
        missing = sorted(required_regional - set(represented), key=lambda layer: layer.value)
        verified = sum(
            record.claim_status in {ClaimStatus.VERIFIED, ClaimStatus.OFFICIAL_CLAIM}
            for record in regional
        )
        hypotheses = sum(record.claim_status == ClaimStatus.HYPOTHESIS for record in regional)
        if len(regional) >= 10 and len(missing) <= 1 and verified >= 5:
            level = "strong"
        elif len(regional) >= 5 and len(missing) <= 2:
            level = "moderate"
        else:
            level = "limited"
        return RegionCoverage(
            region=region,
            total_records=len(regional),
            verified_records=verified,
            hypothesis_records=hypotheses,
            represented_layers=represented,
            missing_layers=missing,
            level=level,
        )


def _tokens(text: str) -> set[str]:
    """English words plus Chinese uni/bi-grams; dependency-free and deterministic."""
    lowered = text.casefold()
    tokens = set(re.findall(r"[a-z0-9][a-z0-9_-]+", lowered))
    for sequence in re.findall(r"[\u4e00-\u9fff]+", lowered):
        tokens.update(sequence)
        tokens.update(sequence[index : index + 2] for index in range(len(sequence) - 1))
    return tokens
