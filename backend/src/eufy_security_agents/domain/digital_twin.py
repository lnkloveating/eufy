"""Deterministic, product-specific contracts for validation digital twins.

The builder intentionally lives in the domain layer.  It turns a snapshotted
``ProductSpec`` into renderer-neutral geometry and component parameters; the
frontend only visualizes this contract and never guesses what the product is.
"""

from __future__ import annotations

from enum import StrEnum
from hashlib import sha256

from pydantic import BaseModel, Field

from .models import ProductSpec


class DigitalTwinArchetype(StrEnum):
    SENSOR_PUCK = "sensor_puck"
    GATEWAY = "gateway"
    CAMERA = "camera"
    DOORBELL = "doorbell"
    WEARABLE = "wearable"
    ROBOT = "robot"
    MODULAR_SYSTEM = "modular_system"
    GENERIC_DEVICE = "generic_device"


class DigitalTwinProfile(StrEnum):
    COMPACT = "compact"
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    WALL_MOUNTED = "wall_mounted"
    DESKTOP = "desktop"
    DISTRIBUTED = "distributed"


class DigitalTwinComponentKind(StrEnum):
    CAMERA = "camera"
    RADAR = "radar"
    MOTION = "motion"
    CONTACT = "contact"
    ACOUSTIC = "acoustic"
    ENVIRONMENTAL = "environmental"
    EDGE_AI = "edge_ai"
    SECURE_ELEMENT = "secure_element"
    LOCAL_STORAGE = "local_storage"
    PRIVACY_SWITCH = "privacy_switch"
    DISPLAY = "display"
    SPEAKER = "speaker"
    MICROPHONE = "microphone"
    SIREN = "siren"
    WIRELESS = "wireless"
    BATTERY = "battery"
    HOMEBASE = "homebase"


class DigitalTwinDimensions(BaseModel):
    """Relative dimensions, not a claim about production millimetres."""

    width: float = Field(gt=0, le=3)
    height: float = Field(gt=0, le=3)
    depth: float = Field(gt=0, le=3)


class DigitalTwinComponent(BaseModel):
    id: str
    kind: DigitalTwinComponentKind
    label: str
    emphasis: float = Field(default=1, ge=0.5, le=1.5)


class ProductDigitalTwinSpec(BaseModel):
    """Stable renderer-neutral description of one product's digital twin."""

    product_id: str
    signature: str
    archetype: DigitalTwinArchetype
    profile: DigitalTwinProfile
    design_variant: int = Field(ge=0, le=7)
    dimensions: DigitalTwinDimensions
    base_color: str
    accent_color: str
    components: list[DigitalTwinComponent] = Field(default_factory=list)
    generation_basis: list[str] = Field(default_factory=list)


_COMPONENT_RULES: tuple[tuple[DigitalTwinComponentKind, str, tuple[str, ...]], ...] = (
    (DigitalTwinComponentKind.CAMERA, "Camera", ("camera", "摄像", "镜头", "视觉")),
    (DigitalTwinComponentKind.RADAR, "mmWave radar", ("radar", "mmwave", "毫米波", "雷达")),
    (DigitalTwinComponentKind.MOTION, "Motion sensor", ("pir", "motion", "运动传感", "人体感应")),
    (
        DigitalTwinComponentKind.CONTACT,
        "Contact sensor",
        ("contact", "door/window", "门窗", "接触传感"),
    ),
    (DigitalTwinComponentKind.ACOUSTIC, "Acoustic sensing", ("acoustic", "sound", "声音", "声学")),
    (
        DigitalTwinComponentKind.ENVIRONMENTAL,
        "Environment sensor",
        ("temperature", "humidity", "温度", "湿度", "环境传感"),
    ),
    (
        DigitalTwinComponentKind.EDGE_AI,
        "Edge AI",
        ("edge ai", "npu", "ai chip", "端侧", "本地 ai", "本地推理"),
    ),
    (
        DigitalTwinComponentKind.SECURE_ELEMENT,
        "Secure element",
        ("secure element", "security chip", "安全芯片", "安全元件"),
    ),
    (
        DigitalTwinComponentKind.LOCAL_STORAGE,
        "Local storage",
        ("local storage", "本地存储", "sd card", "emmc"),
    ),
    (
        DigitalTwinComponentKind.PRIVACY_SWITCH,
        "Privacy switch",
        ("privacy switch", "physical switch", "privacy shutter", "隐私开关", "物理开关", "遮挡"),
    ),
    (
        DigitalTwinComponentKind.DISPLAY,
        "Display",
        ("display", "screen", "touchscreen", "屏幕", "触摸屏"),
    ),
    (DigitalTwinComponentKind.SPEAKER, "Speaker", ("speaker", "扬声器", "音箱")),
    (DigitalTwinComponentKind.MICROPHONE, "Microphone", ("microphone", "mic", "麦克风")),
    (DigitalTwinComponentKind.SIREN, "Siren", ("siren", "alarm", "警报器", "声光报警")),
    (
        DigitalTwinComponentKind.WIRELESS,
        "Wireless radio",
        ("wifi", "wi-fi", "thread", "zigbee", "bluetooth", "无线"),
    ),
    (DigitalTwinComponentKind.BATTERY, "Battery", ("battery", "电池", "充电")),
    (
        DigitalTwinComponentKind.HOMEBASE,
        "HomeBase module",
        ("homebase", "gateway", "hub", "网关", "中枢"),
    ),
)

_PALETTES: tuple[tuple[str, str], ...] = (
    ("#dce4ea", "#19c38c"),
    ("#171a20", "#68a7ff"),
    ("#f1eee7", "#ef8354"),
    ("#263342", "#8be28b"),
    ("#e9e7f4", "#806cff"),
    ("#233138", "#59d5e0"),
)


def _semantic_text(spec: ProductSpec) -> str:
    values = [
        spec.name,
        spec.one_sentence_definition,
        spec.category,
        spec.form_factor,
        *spec.hardware_architecture,
        *spec.ai_capabilities,
        spec.ai_decision_boundary,
        *spec.ecosystem_relationships,
        *spec.privacy_principles,
    ]
    return " | ".join(value.strip().lower() for value in values if value.strip())


def _contains(text: str, *keywords: str) -> bool:
    return any(keyword in text for keyword in keywords)


def _classify_archetype(text: str) -> DigitalTwinArchetype:
    # Multiple physical units take precedence over one unit mentioned inside
    # the description (for example a gateway with a detachable camera).
    if _contains(
        text,
        "detachable",
        "distributed",
        "satellite",
        "多节点",
        "分布式",
        "可拆卸",
        "传感节点",
        "privacy module",
        "隐私模块",
    ):
        return DigitalTwinArchetype.MODULAR_SYSTEM
    if _contains(text, "robot", "机器人", "巡检车"):
        return DigitalTwinArchetype.ROBOT
    if _contains(text, "wearable", "watch", "wrist", "pendant", "可穿戴", "手表", "腕带"):
        return DigitalTwinArchetype.WEARABLE
    if _contains(text, "doorbell", "门铃"):
        return DigitalTwinArchetype.DOORBELL
    if _contains(text, "gateway", "homebase", "hub", "smart speaker", "网关", "中枢", "音箱"):
        return DigitalTwinArchetype.GATEWAY
    if _contains(
        text, "puck", "sensor node", "sensor puck", "radar sensor", "传感器", "雷达节点", "圆盘"
    ):
        return DigitalTwinArchetype.SENSOR_PUCK
    if _contains(text, "camera", "摄像头", "摄像机"):
        return DigitalTwinArchetype.CAMERA
    return DigitalTwinArchetype.GENERIC_DEVICE


def _profile_for(text: str, archetype: DigitalTwinArchetype) -> DigitalTwinProfile:
    if archetype == DigitalTwinArchetype.MODULAR_SYSTEM:
        return DigitalTwinProfile.DISTRIBUTED
    if _contains(text, "wall", "ceiling", "墙", "壁挂", "吸顶"):
        return DigitalTwinProfile.WALL_MOUNTED
    if archetype in {DigitalTwinArchetype.DOORBELL, DigitalTwinArchetype.GATEWAY}:
        return DigitalTwinProfile.VERTICAL
    if archetype in {DigitalTwinArchetype.SENSOR_PUCK, DigitalTwinArchetype.WEARABLE}:
        return DigitalTwinProfile.COMPACT
    if archetype == DigitalTwinArchetype.ROBOT:
        return DigitalTwinProfile.HORIZONTAL
    return DigitalTwinProfile.DESKTOP


def _dimensions_for(
    archetype: DigitalTwinArchetype, profile: DigitalTwinProfile, variant: int
) -> DigitalTwinDimensions:
    base = {
        DigitalTwinArchetype.SENSOR_PUCK: (1.25, 0.42, 1.25),
        DigitalTwinArchetype.GATEWAY: (1.05, 1.75, 0.85),
        DigitalTwinArchetype.CAMERA: (1.2, 1.1, 1.0),
        DigitalTwinArchetype.DOORBELL: (0.72, 1.75, 0.42),
        DigitalTwinArchetype.WEARABLE: (1.0, 0.32, 1.0),
        DigitalTwinArchetype.ROBOT: (1.7, 0.72, 1.35),
        DigitalTwinArchetype.MODULAR_SYSTEM: (1.2, 1.55, 0.9),
        DigitalTwinArchetype.GENERIC_DEVICE: (1.3, 0.95, 0.85),
    }[archetype]
    width, height, depth = base
    adjustment = (variant - 3.5) * 0.035
    if profile == DigitalTwinProfile.VERTICAL:
        height += adjustment
    else:
        width += adjustment
        depth -= adjustment / 2
    return DigitalTwinDimensions(
        width=round(width, 3), height=round(height, 3), depth=round(depth, 3)
    )


def build_product_digital_twin(spec: ProductSpec) -> ProductDigitalTwinSpec:
    """Build the same digital twin for the same semantic ProductSpec snapshot."""

    text = _semantic_text(spec)
    signature_source = f"v1|{spec.id}|{spec.version}|{text}"
    signature = sha256(signature_source.encode("utf-8")).hexdigest()[:16]
    signature_number = int(signature, 16)
    archetype = _classify_archetype(text)
    profile = _profile_for(text, archetype)
    variant = signature_number % 8
    base_color, accent_color = _PALETTES[(signature_number >> 5) % len(_PALETTES)]

    components: list[DigitalTwinComponent] = []
    for kind, label, keywords in _COMPONENT_RULES:
        if _contains(text, *keywords):
            components.append(
                DigitalTwinComponent(
                    id=f"component-{kind.value}",
                    kind=kind,
                    label=label,
                    emphasis=round(0.8 + ((signature_number >> len(components)) % 7) / 10, 1),
                )
            )

    # Every twin exposes the product's compute core even when the ProductSpec
    # describes it only through AI capabilities instead of hardware wording.
    if spec.ai_capabilities and not any(
        component.kind == DigitalTwinComponentKind.EDGE_AI for component in components
    ):
        components.append(
            DigitalTwinComponent(
                id="component-edge_ai",
                kind=DigitalTwinComponentKind.EDGE_AI,
                label="AI decision core",
            )
        )

    return ProductDigitalTwinSpec(
        product_id=spec.id,
        signature=signature,
        archetype=archetype,
        profile=profile,
        design_variant=variant,
        dimensions=_dimensions_for(archetype, profile, variant),
        base_color=base_color,
        accent_color=accent_color,
        components=components,
        generation_basis=[
            f"Form factor: {spec.form_factor}",
            f"Hardware modules: {len(spec.hardware_architecture)}",
            f"Detected components: {len(components)}",
        ],
    )
