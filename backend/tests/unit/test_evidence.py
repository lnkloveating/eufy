from pathlib import Path

from eufy_security_agents.domain.models import ForecastRequest, ResearchContext
from eufy_security_agents.infrastructure.evidence import LocalEvidenceStore


def test_local_evidence_prioritizes_selected_region() -> None:
    evidence_path = Path(__file__).resolve().parents[2] / "data" / "evidence"
    store = LocalEvidenceStore(evidence_path)
    request = ForecastRequest(
        question="预测未来三年中国城市家庭的AI原生安防消费电子产品",
        regions=["China"],
        target_users=["Urban apartment households"],
    )

    records = store.search(request)

    assert len(records) >= 10
    assert any("China" in record.regions for record in records[:8])
    assert len({record.id for record in records}) == len(records)


def test_layered_retrieval_routes_regions_and_does_not_return_entire_store() -> None:
    evidence_path = Path(__file__).resolve().parents[2] / "data" / "evidence"
    store = LocalEvidenceStore(evidence_path)
    china_request = ForecastRequest(
        question="预测未来三年中国城市公寓家庭的AI原生安防产品机会",
        regions=["China"],
        target_users=["Urban apartment households"],
    )
    us_request = china_request.model_copy(
        update={"regions": ["United States"], "target_users": ["Detached-home households"]}
    )

    china_plan, china_records = store.retrieve(china_request)
    us_plan, us_records = store.retrieve(us_request)

    assert len(china_records) < len(store.load())
    assert len(us_records) < len(store.load())
    assert "apartment" in china_plan.query_topics
    assert {record.id for record in china_records} != {record.id for record in us_records}
    assert sum("China" in record.regions for record in china_records) >= 8
    assert sum("United States" in record.regions for record in us_records) >= 8
    assert china_plan.coverage[0].level == "strong"


def test_unknown_region_reports_limited_coverage_and_global_fallback() -> None:
    evidence_path = Path(__file__).resolve().parents[2] / "data" / "evidence"
    store = LocalEvidenceStore(evidence_path)
    plan, records = store.retrieve(
        ForecastRequest(
            question="预测未来三年冰岛家庭的AI原生安防产品机会",
            regions=["Iceland"],
            target_users=["Households"],
        )
    )

    assert plan.coverage[0].level == "limited"
    assert plan.fallback_used is True
    assert records
    assert all("Global" in record.regions for record in records)


def test_structured_research_context_changes_retrieval_topics() -> None:
    evidence_path = Path(__file__).resolve().parents[2] / "data" / "evidence"
    store = LocalEvidenceStore(evidence_path)
    common = {
        "question": "预测未来三年欧美家庭的AI原生安防产品机会",
        "regions": ["United States"],
        "target_users": ["Households"],
    }
    private_request = ForecastRequest(
        **common,
        research_context=ResearchContext(
            housing_types=["城市公寓"],
            privacy_preferences=["敏感数据不出户", "优先端侧 AI"],
            desired_outcomes=["保护隐私"],
        ),
    )
    perimeter_request = ForecastRequest(
        **common,
        research_context=ResearchContext(
            housing_types=["独栋住宅"],
            security_scenarios=["车辆与车库", "包裹与门前"],
        ),
    )

    private_plan, private_records = store.retrieve(private_request)
    perimeter_plan, perimeter_records = store.retrieve(perimeter_request)

    assert {"apartment", "privacy", "edge_ai"} <= set(private_plan.query_topics)
    assert {"detached_home", "vehicle", "package"} <= set(perimeter_plan.query_topics)
    assert [record.id for record in private_records] != [record.id for record in perimeter_records]
