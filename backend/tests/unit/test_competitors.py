from pathlib import Path

from eufy_security_agents.domain.models import ForecastRequest
from eufy_security_agents.infrastructure.competitors import LocalCompetitorStore


def test_competitor_store_preserves_brand_diversity_and_region_fit() -> None:
    store = LocalCompetitorStore(Path(__file__).resolve().parents[2] / "data" / "competitors")
    request = ForecastRequest(
        question="预测未来三年美国独栋家庭无需订阅的AI原生安防产品",
        regions=["United States"],
        target_users=["Detached-home households"],
        constraints=["no mandatory subscription"],
    )

    records = store.retrieve(request)

    assert len(store.load()) == 18
    assert len(records) == 12
    assert len(records) < len(store.load())
    assert len({record.brand for record in records}) == 6
    assert all(
        "Global" in record.regions or "United States" in record.regions for record in records
    )
    assert all(record.source_url.startswith("https://") for record in records)
