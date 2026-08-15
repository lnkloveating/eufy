"""Product-specific deterministic digital twin contract tests."""

from eufy_security_agents.domain.digital_twin import (
    DigitalTwinArchetype,
    DigitalTwinComponentKind,
    build_product_digital_twin,
)
from eufy_security_agents.domain.models import (
    BusinessModel,
    DefinitionStatus,
    ProductSpec,
    RiskItem,
)


def _spec(
    product_id: str,
    name: str,
    form_factor: str,
    hardware: list[str],
) -> ProductSpec:
    return ProductSpec(
        id=product_id,
        source_run_id="run-digital-twin",
        source_candidate_id=f"candidate-{product_id}",
        name=name,
        one_sentence_definition=f"A product-specific concept for {name}.",
        category="Security",
        target_users=["Households"],
        target_regions=["United States"],
        core_problem="Detect household safety events",
        value_proposition="Private, explainable protection",
        form_factor=form_factor,
        hardware_architecture=hardware,
        ai_capabilities=["Local event classification"],
        ai_decision_boundary="High-impact actions require user confirmation",
        user_journeys=["Install and monitor"],
        ecosystem_relationships=["eufy app"],
        privacy_principles=["Local processing by default"],
        business_model=BusinessModel(
            hardware_revenue="One-time hardware sale",
            ecosystem_pull_through=["eufy app"],
            cost_drivers=["Sensors"],
        ),
        risks=[
            RiskItem(
                category="technical",
                risk="Detection accuracy",
                mitigation="Validate before launch",
                severity="high",
            )
        ],
        key_assumptions=["Users value local processing"],
        kill_criteria=["Unacceptable false alarm rate"],
        evidence_ids=["EV-EUFY-001"],
        validation_readiness=[],
        definition_status=DefinitionStatus.VALIDATION_READY,
    )


def test_same_product_snapshot_always_builds_same_twin() -> None:
    product = _spec(
        "product-puck",
        "AuraSense",
        "Compact wall-mounted sensor puck",
        ["mmWave radar", "PIR motion sensor", "Edge AI NPU", "Privacy switch"],
    )

    assert build_product_digital_twin(product) == build_product_digital_twin(product)


def test_distinct_product_forms_build_distinct_archetypes_and_geometry() -> None:
    sensor = _spec(
        "product-puck",
        "AuraSense",
        "Compact wall-mounted sensor puck",
        ["mmWave radar", "PIR motion sensor", "Edge AI NPU"],
    )
    gateway = _spec(
        "product-gateway",
        "CoGuard",
        "Desktop smart speaker gateway with touchscreen",
        ["Touchscreen display", "Microphone", "Speaker", "Edge AI NPU", "Wi-Fi"],
    )
    modular = _spec(
        "product-modular",
        "PrivacyShield",
        "Home gateway with detachable camera and distributed sensor nodes",
        ["HomeBase gateway", "Detachable camera", "Contact sensor", "Physical privacy switch"],
    )

    sensor_twin = build_product_digital_twin(sensor)
    gateway_twin = build_product_digital_twin(gateway)
    modular_twin = build_product_digital_twin(modular)

    assert sensor_twin.archetype == DigitalTwinArchetype.SENSOR_PUCK
    assert gateway_twin.archetype == DigitalTwinArchetype.GATEWAY
    assert modular_twin.archetype == DigitalTwinArchetype.MODULAR_SYSTEM
    assert len({sensor_twin.signature, gateway_twin.signature, modular_twin.signature}) == 3
    assert len(
        {
            sensor_twin.dimensions.model_dump_json(),
            gateway_twin.dimensions.model_dump_json(),
            modular_twin.dimensions.model_dump_json(),
        }
    ) == 3


def test_visible_components_come_from_product_hardware() -> None:
    gateway = _spec(
        "product-gateway",
        "CoGuard",
        "Desktop smart speaker gateway with touchscreen",
        ["Touchscreen display", "Microphone", "Speaker", "Edge AI NPU", "Wi-Fi"],
    )

    component_kinds = {
        component.kind for component in build_product_digital_twin(gateway).components
    }

    assert DigitalTwinComponentKind.DISPLAY in component_kinds
    assert DigitalTwinComponentKind.MICROPHONE in component_kinds
    assert DigitalTwinComponentKind.SPEAKER in component_kinds
    assert DigitalTwinComponentKind.CAMERA not in component_kinds
