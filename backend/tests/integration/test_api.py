from fastapi.testclient import TestClient

from eufy_security_agents.api.app import create_app


def test_health_does_not_expose_secret() -> None:
    response = TestClient(create_app()).get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "api_key" not in body
    assert isinstance(body["local_evidence_count"], int)
    assert body["competitor_evidence_count"] == 18


def test_forecast_options_support_regions_and_custom_values() -> None:
    response = TestClient(create_app()).get("/api/v1/forecast-options")
    assert response.status_code == 200
    body = response.json()
    assert "China" in body["regions"]
    assert "United States" in body["regions"]
    assert body["custom_regions_allowed"] is True
    assert "privacy_preferences" in body["research_context_options"]
    assert "innovation_posture" in body["research_context_options"]


def test_knowledge_coverage_and_retrieval_preview_are_auditable() -> None:
    client = TestClient(create_app())
    coverage = client.get("/api/v1/knowledge/coverage", params={"regions": "China"})
    assert coverage.status_code == 200
    assert coverage.json()["regions"][0]["level"] == "strong"

    preview = client.post(
        "/api/v1/knowledge/retrieval-preview",
        json={
            "question": "预测未来三年中国城市家庭的AI原生安防产品机会",
            "regions": ["China"],
            "target_users": ["Urban households"],
        },
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["plan"]["requested_regions"] == ["China"]
    assert len(body["evidence"]) < 49
    assert "regional_market" in {item["layer"] for item in body["evidence"]}
