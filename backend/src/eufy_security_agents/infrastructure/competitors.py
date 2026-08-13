"""Local, source-audited competitor intelligence retrieval."""

from __future__ import annotations

import re
from pathlib import Path

from eufy_security_agents.domain.models import CompetitorRecord, ForecastRequest


class LocalCompetitorStore:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._cache: list[CompetitorRecord] | None = None

    def load(self) -> list[CompetitorRecord]:
        if self._cache is not None:
            return list(self._cache)
        records: list[CompetitorRecord] = []
        for path in sorted(self._root.rglob("*.jsonl")):
            for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if not raw.strip():
                    continue
                try:
                    records.append(CompetitorRecord.model_validate_json(raw))
                except Exception as exc:
                    raise ValueError(f"invalid competitor record {path}:{line_number}") from exc
        ids = [record.id for record in records]
        if len(ids) != len(set(ids)):
            raise ValueError("competitor evidence IDs must be unique")
        self._cache = records
        return list(records)

    def retrieve(self, request: ForecastRequest, *, limit: int = 12) -> list[CompetitorRecord]:
        requested_regions = {region.casefold() for region in request.regions}
        query = " ".join(
            [
                request.question,
                *request.target_users,
                *request.constraints,
                *request.research_context.search_terms(),
                request.category,
            ]
        ).casefold()
        tokens = _tokens(query)

        def score(record: CompetitorRecord) -> tuple[float, str]:
            record_regions = {region.casefold() for region in record.regions}
            region_score = 4.0 if requested_regions & record_regions else 0.0
            if "global" in record_regions:
                region_score += 2.0
            searchable = " ".join(
                [
                    record.brand,
                    record.product_name,
                    record.product_family,
                    *record.verified_capabilities,
                    *record.documented_constraints,
                    *record.tags,
                ]
            ).casefold()
            topic_score = sum(0.6 for token in tokens if token in searchable)
            return region_score + topic_score + record.credibility, record.id

        eligible = [
            record
            for record in self.load()
            if "Global" in record.regions
            or any(region.casefold() in requested_regions for region in record.regions)
        ]
        ranked = sorted(eligible, key=score, reverse=True)

        # Preserve brand diversity before filling remaining high-scoring records.
        selected: list[CompetitorRecord] = []
        seen_brands: set[str] = set()
        for record in ranked:
            if record.brand not in seen_brands:
                selected.append(record)
                seen_brands.add(record.brand)
        for record in ranked:
            if record not in selected and len(selected) < limit:
                selected.append(record)
        return selected[:limit]


def _tokens(text: str) -> set[str]:
    english = set(re.findall(r"[a-z0-9][a-z0-9_-]{2,}", text))
    chinese_runs = re.findall(r"[\u4e00-\u9fff]+", text)
    chinese = {
        run[index : index + 2] for run in chinese_runs for index in range(max(0, len(run) - 1))
    }
    return english | chinese
