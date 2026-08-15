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


def test_forecast_options_expose_strategy_presets() -> None:
    body = TestClient(create_app()).get("/api/v1/forecast-options").json()
    assert body["default_strategy_profile"] == "balanced"
    # default_weights is now six-dimensional.
    assert "cost_effectiveness" in body["default_weights"]
    presets = body["strategy_presets"]
    assert {preset["id"] for preset in presets} == {
        "balanced",
        "breakthrough",
        "value",
        "ecosystem",
    }
    for preset in presets:
        assert set(preset) >= {"id", "label", "description", "weights"}
        assert "cost_effectiveness" in preset["weights"]
        assert abs(sum(preset["weights"].values()) - 1.0) < 1e-9


def test_product_workbench_endpoints_reject_unknown_product() -> None:
    client = TestClient(create_app())
    assert client.get("/api/v1/products/does-not-exist").status_code == 404
    assert client.get("/api/v1/products/does-not-exist/questions").status_code == 404
    assert client.get("/api/v1/products/does-not-exist/revisions").status_code == 404
    assert client.get("/api/v1/products/does-not-exist/readiness").status_code == 404
    assert client.post("/api/v1/products/does-not-exist/confirm").status_code == 404


def test_product_definition_state_rejects_unknown_run() -> None:
    response = TestClient(create_app()).get(
        "/api/v1/forecast-runs/does-not-exist/product-definition-state"
    )
    assert response.status_code == 404


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


def test_validation_endpoints_reject_unknown_ids() -> None:
    client = TestClient(create_app())
    assert (
        client.post("/api/v1/products/does-not-exist/validation-projects").status_code == 404
    )
    assert (
        client.get(
            "/api/v1/products/does-not-exist/validation-projects/latest"
        ).status_code
        == 404
    )
    assert client.get("/api/v1/validation-projects/does-not-exist").status_code == 404
    assert client.post("/api/v1/validation-projects/does-not-exist/run").status_code == 404
    assert client.get("/api/v1/validation-projects/does-not-exist/events").status_code == 404
    assert (
        client.post("/api/v1/validation-findings/does-not-exist/send-back").status_code == 404
    )
