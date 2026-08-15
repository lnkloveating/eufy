"""Deterministic scenario engine for the pre-validation lab.

No LLM, no physics engine — a pure, reproducible conceptual simulator. Given a
snapshotted :class:`ProductSpec`, it derives which sensing modalities the product
actually has, then plays four fixed household scenarios against that capability
set. The verdict for each scenario is computed from the product's hardware, AI
capabilities, decision boundary, privacy principles and ecosystem — it is never
a hard-coded success for a specific product, and it never claims a real test.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import ProductSpec
from .validation import (
    ExperimentVerdict,
    ScenarioSensor,
    ScenarioSimulation,
    ScenarioTemplate,
    ScenarioTimelineStep,
    ScenarioZone,
)

# Shared apartment floor plan (0-100 SVG space), reused across every scenario so
# the UI can keep a stable mental map.
ZONES: tuple[ScenarioZone, ...] = (
    ScenarioZone(id="bedroom", name="卧室", x=4, y=4, width=44, height=40),
    ScenarioZone(id="kitchen", name="厨房", x=52, y=4, width=44, height=40),
    ScenarioZone(id="living_room", name="客厅", x=4, y=50, width=58, height=46),
    ScenarioZone(id="entryway", name="玄关", x=66, y=50, width=30, height=46),
)


@dataclass(frozen=True)
class Capabilities:
    """Deterministically detected product capabilities used by every scenario."""

    camera: bool
    radar: bool
    motion: bool
    contact: bool
    acoustic: bool
    environmental: bool
    ai_classification: bool
    local_first: bool
    privacy_local: bool
    human_gate: bool

    @property
    def entry_modalities(self) -> int:
        return sum([self.contact, self.motion, self.camera, self.radar])


def _contains(haystack: str, needles: tuple[str, ...]) -> bool:
    return any(needle in haystack for needle in needles)


def detect_capabilities(spec: ProductSpec) -> Capabilities:
    """Infer sensing/decision capabilities from the ProductSpec (deterministic)."""

    hardware = " ".join(spec.hardware_architecture).casefold()
    ai = " ".join(spec.ai_capabilities).casefold()
    boundary = spec.ai_decision_boundary.casefold()
    privacy = " ".join(spec.privacy_principles).casefold()
    ecosystem = " ".join(spec.ecosystem_relationships).casefold()
    sensing = f"{hardware} {spec.form_factor.casefold()} {ai}"

    return Capabilities(
        camera=_contains(sensing, ("camera", "摄像", "视觉", "vision", "doorbell", "门铃", "镜头")),
        radar=_contains(sensing, ("radar", "雷达", "mmwave", "毫米波", "presence", "存在感知")),
        motion=_contains(sensing, ("pir", "motion", "运动", "移动", "红外", "人体感应")),
        contact=_contains(
            sensing, ("door/window", "门窗", "contact", "门磁", "entry sensor", "磁传感")
        ),
        acoustic=_contains(
            sensing,
            ("acoustic", "声学", "audio", "麦克风", "glass break", "碎玻璃", "sound", "声音"),
        ),
        environmental=_contains(
            sensing,
            ("environmental", "环境", "smoke", "烟雾", "温度", "湿度", "water", "水浸", "gas"),
        ),
        ai_classification=_contains(
            f"{ai} {boundary}",
            ("classif", "识别", "分类", "multi-signal", "多信号", "融合", "fusion", "detect"),
        ),
        local_first=_contains(
            f"{hardware} {ai} {boundary} {privacy} {ecosystem}",
            (
                "local", "本地", "端侧", "edge", "on-device", "offline",
                "离线", "断网", "mesh", "homebase", "home base",
            ),
        ),
        privacy_local=_contains(
            privacy, ("local", "本地", "端侧", "on-device", "minimi", "最小", "不出户", "脱敏")
        ),
        human_gate=_contains(
            boundary,
            ("confirm", "确认", "approval", "审批", "human", "人工", "policy", "策略", "用户"),
        ),
    )


def _sensor(
    sensor_id: str, label: str, zone_id: str, sensor_type: str, available: bool, x: float, y: float
) -> ScenarioSensor:
    return ScenarioSensor(
        id=sensor_id,
        label=label,
        zone_id=zone_id,
        sensor_type=sensor_type,
        available=available,
        x=x,
        y=y,
    )


def _decision_prefix(caps: Capabilities) -> str:
    return (
        "先给出可解释判断，高影响动作需用户确认"
        if caps.human_gate
        else "给出判断并触发响应（未强制人工确认）"
    )


def _intrusion(caps: Capabilities) -> ScenarioSimulation:
    sensors = [
        _sensor("s-contact", "门磁", "entryway", "contact", caps.contact, 90, 72),
        _sensor("s-motion", "运动传感", "entryway", "motion", caps.motion, 74, 60),
        _sensor("s-camera", "摄像头", "living_room", "camera", caps.camera, 20, 60),
        _sensor("s-radar", "雷达存在感知", "living_room", "radar", caps.radar, 45, 72),
    ]
    timeline = [
        ScenarioTimelineStep(
            order=1,
            time_label="22:14",
            zone_id="entryway",
            title="陌生人接近入口",
            description="陌生人在玄关外徘徊并尝试开门。",
            expected_decision=(
                "入口感知触发低置信提醒" if caps.entry_modalities else "无入口感知，无法触发提醒"
            ),
            is_failure_point=caps.entry_modalities == 0,
        ),
        ScenarioTimelineStep(
            order=2,
            time_label="22:15",
            zone_id="living_room",
            title="进入室内活动",
            description="陌生人进入客厅并移动。",
            expected_decision=(
                f"多信号交叉确认为人形入侵，{_decision_prefix(caps)}"
                if caps.entry_modalities >= 2
                else "仅单一信号，置信不足，易与正常活动混淆"
            ),
            privacy_note=("室内摄像画面仅本地处理" if caps.camera and caps.privacy_local else None),
            is_failure_point=caps.entry_modalities < 2,
        ),
        ScenarioTimelineStep(
            order=3,
            time_label="22:15",
            zone_id="entryway",
            title="升级响应",
            description="系统决定是否升级为高优先级告警。",
            expected_decision=(
                "推送高优先级告警并联动本地声光"
                if caps.entry_modalities
                else "无法形成入侵结论"
            ),
            is_failure_point=False,
        ),
    ]
    if caps.entry_modalities == 0:
        verdict = ExperimentVerdict.CONTRADICTED
        rationale = "缺少任何入口/周界感知模态，模拟中无法察觉陌生人进入，出现反例。"
    elif caps.entry_modalities >= 2:
        verdict = ExperimentVerdict.SUPPORTED_IN_SIMULATION
        rationale = "多模态入口感知可在模拟中形成可解释入侵判断；真实误报率仍需真实测试。"
    else:
        verdict = ExperimentVerdict.REQUIRES_REAL_WORLD_TEST
        rationale = "仅单一入口感知模态，模拟可触发告警，但真实漏报/误报需真实测试。"
    failures = ["单一传感器易受宠物、气流干扰产生误报"]
    if not caps.camera:
        failures.append("缺少摄像头，无法进行可视化二次确认")
    return ScenarioSimulation(
        template=ScenarioTemplate.URBAN_APARTMENT_INTRUSION,
        title="城市公寓陌生人入侵",
        description="夜间陌生人尝试进入城市公寓，检验入口感知与入侵判断链路。",
        floor_plan=list(ZONES),
        sensors=sensors,
        timeline=timeline,
        expected_product_decisions=[
            "在入口环节形成低置信提醒",
            "多信号交叉后升级为人形入侵判断",
            "触发高优先级告警与本地声光联动",
        ],
        privacy_boundaries=(
            ["室内摄像头画面默认本地处理，可分区遮蔽"]
            if caps.camera
            else ["无室内摄像头，天然规避室内影像隐私顾虑"]
        ),
        failure_conditions=failures,
        observations=[
            f"可用入口感知模态数量：{caps.entry_modalities}",
            ("决策边界要求人工确认高影响动作" if caps.human_gate else "决策边界未强制人工确认"),
        ],
        coverage_notes=["真实入侵误报/漏报率属经验指标，必须真实测试，模拟只验证判断链路。"],
        verdict=verdict,
        verdict_rationale=rationale,
    )


def _elderly(caps: Capabilities) -> ScenarioSimulation:
    presence = caps.radar or caps.motion or caps.acoustic
    sensors = [
        _sensor("s-radar", "雷达存在感知", "bedroom", "radar", caps.radar, 26, 22),
        _sensor("s-motion", "运动传感", "bedroom", "motion", caps.motion, 40, 30),
        _sensor("s-acoustic", "声学传感", "bedroom", "acoustic", caps.acoustic, 14, 12),
        _sensor("s-camera", "摄像头", "living_room", "camera", caps.camera, 20, 62),
    ]
    camera_conflict = caps.camera and not (caps.radar or caps.motion) and not caps.privacy_local
    timeline = [
        ScenarioTimelineStep(
            order=1,
            time_label="03:20",
            zone_id="bedroom",
            title="夜间长时间无活动",
            description="老人夜间起身后长时间未回到正常活动模式。",
            expected_decision=(
                "无接触式感知识别异常静止" if presence else "缺少非影像感知，难以识别异常"
            ),
            privacy_note=("卧室以雷达替代摄像头，避免影像采集" if caps.radar else None),
            is_failure_point=not presence,
        ),
        ScenarioTimelineStep(
            order=2,
            time_label="03:22",
            zone_id="bedroom",
            title="异常模式判定",
            description="系统判断是否构成需要关注的异常。",
            expected_decision=(
                "形成低打扰关怀确认，再决定升级" if presence else "无法形成可靠异常判定"
            ),
            privacy_note=("卧室摄像头与隐私原则冲突" if camera_conflict else "卧室禁用摄像头"),
            is_failure_point=camera_conflict,
        ),
        ScenarioTimelineStep(
            order=3,
            time_label="03:23",
            zone_id="living_room",
            title="通知照护人",
            description="必要时通知家人或照护人。",
            expected_decision="按分级策略通知照护人，保留可撤销与静音选项",
            is_failure_point=False,
        ),
    ]
    if caps.radar:
        verdict = ExperimentVerdict.SUPPORTED_IN_SIMULATION
        rationale = "雷达/存在感知可在模拟中隐私友好地识别夜间异常；真实准确性仍需真实测试。"
    elif camera_conflict:
        verdict = ExperimentVerdict.INCONCLUSIVE
        rationale = "仅靠卧室摄像头识别夜间异常与隐私原则冲突，模拟结论不成立。"
    elif presence:
        verdict = ExperimentVerdict.REQUIRES_REAL_WORLD_TEST
        rationale = "可感知卧室活动，但夜间异常判定的可靠性与打扰程度需真实测试。"
    else:
        verdict = ExperimentVerdict.CONTRADICTED
        rationale = "缺少适合卧室的非影像感知模态，模拟中无法识别老人夜间异常。"
    return ScenarioSimulation(
        template=ScenarioTemplate.ELDERLY_NIGHT_ANOMALY,
        title="老人夜间异常活动",
        description="独居/多代同堂场景下的老人夜间异常，检验隐私友好的关怀式感知。",
        floor_plan=list(ZONES),
        sensors=sensors,
        timeline=timeline,
        expected_product_decisions=[
            "以非影像方式识别夜间异常静止或跌倒模式",
            "先做低打扰关怀确认",
            "按分级策略通知照护人",
        ],
        privacy_boundaries=[
            "卧室优先使用雷达/存在感知替代摄像头",
            ("敏感区域数据默认本地处理" if caps.privacy_local else "需明确卧室数据的本地保留策略"),
        ],
        failure_conditions=[
            "以摄像头覆盖卧室会触碰隐私底线",
            "缺少非影像感知时夜间异常易漏报",
        ],
        observations=[
            ("具备雷达存在感知" if caps.radar else "不具备雷达存在感知"),
            ("隐私原则含本地处理/数据最小化" if caps.privacy_local else "隐私原则未强调本地处理"),
        ],
        coverage_notes=["真实的异常识别灵敏度与误唤醒需在真实照护场景中验证。"],
        verdict=verdict,
        verdict_rationale=rationale,
    )


def _pet(caps: Capabilities) -> ScenarioSimulation:
    multi_signal = sum([caps.camera, caps.radar, caps.motion, caps.acoustic]) >= 2
    can_discriminate = multi_signal or caps.ai_classification
    sensors = [
        _sensor("s-motion", "运动传感", "living_room", "motion", caps.motion, 18, 66),
        _sensor("s-camera", "摄像头", "living_room", "camera", caps.camera, 40, 60),
        _sensor("s-radar", "雷达存在感知", "living_room", "radar", caps.radar, 30, 80),
    ]
    timeline = [
        ScenarioTimelineStep(
            order=1,
            time_label="14:05",
            zone_id="living_room",
            title="宠物在客厅活动",
            description="家中宠物在客厅走动、跳上沙发。",
            expected_decision=(
                "多信号/AI 分类判别为宠物"
                if can_discriminate
                else "单一运动信号，无法区分宠物与人形"
            ),
            is_failure_point=not can_discriminate,
        ),
        ScenarioTimelineStep(
            order=2,
            time_label="14:05",
            zone_id="living_room",
            title="误报抑制决策",
            description="系统决定是否抑制该事件。",
            expected_decision=(
                "抑制为非威胁事件，仅记录不打扰"
                if can_discriminate
                else "错误升级为入侵告警（反例）"
            ),
            is_failure_point=not can_discriminate,
        ),
    ]
    if can_discriminate:
        verdict = ExperimentVerdict.SUPPORTED_IN_SIMULATION
        rationale = "多信号或 AI 分类可在模拟中把宠物判为非威胁并抑制误报；真实误报率需真实测试。"
    elif caps.motion or caps.camera or caps.radar:
        verdict = ExperimentVerdict.CONTRADICTED
        rationale = "仅单一感知且无分类能力时，宠物在模拟中被误判为入侵，出现误报反例。"
    else:
        verdict = ExperimentVerdict.INCONCLUSIVE
        rationale = "缺少客厅活动感知，无法在模拟中运行宠物误报场景。"
    return ScenarioSimulation(
        template=ScenarioTemplate.PET_FALSE_ALARM,
        title="宠物导致误报",
        description="有宠物家庭的高频误报来源，检验误报抑制与人宠区分能力。",
        floor_plan=list(ZONES),
        sensors=sensors,
        timeline=timeline,
        expected_product_decisions=[
            "识别宠物特征并判为非威胁",
            "抑制误报，仅低优先级记录",
            "保留用户可回溯与纠错入口",
        ],
        privacy_boundaries=[
            "误报抑制在端侧完成，减少无关影像上传"
            if caps.privacy_local
            else "需明确误报样本的存储与删除策略"
        ],
        failure_conditions=[
            "单一 PIR 无法区分宠物与人形，导致误报",
            "分类阈值过松会漏报真实入侵",
        ],
        observations=[
            ("具备多信号或 AI 分类能力" if can_discriminate else "缺少多信号或 AI 分类能力"),
        ],
        coverage_notes=["真实家庭误报率是经验指标，必须真实测试；模拟只验证区分逻辑。"],
        verdict=verdict,
        verdict_rationale=rationale,
    )


def _outage(caps: Capabilities) -> ScenarioSimulation:
    sensors = [
        _sensor("s-hub", "本地中枢", "living_room", "hub", caps.local_first, 30, 60),
        _sensor("s-router", "家庭网络", "kitchen", "network", True, 74, 22),
        _sensor("s-camera", "摄像头", "living_room", "camera", caps.camera, 46, 66),
    ]
    timeline = [
        ScenarioTimelineStep(
            order=1,
            time_label="19:40",
            zone_id="kitchen",
            title="家庭网络中断",
            description="家庭宽带 / Wi-Fi 出现中断。",
            expected_decision=(
                "切换到本地/端侧处理，继续侦测" if caps.local_first else "依赖云端的能力开始不可用"
            ),
            is_failure_point=not caps.local_first,
        ),
        ScenarioTimelineStep(
            order=2,
            time_label="19:41",
            zone_id="living_room",
            title="断网期间事件",
            description="断网窗口内发生一次安防事件。",
            expected_decision=(
                "本地侦测并触发本地声光/离线记录" if caps.local_first else "无法侦测或告警（反例）"
            ),
            is_failure_point=not caps.local_first,
        ),
        ScenarioTimelineStep(
            order=3,
            time_label="20:05",
            zone_id="kitchen",
            title="网络恢复",
            description="网络恢复后进行同步。",
            expected_decision=(
                "恢复后补齐云端同步与通知" if caps.local_first else "恢复后才发现断网期间存在盲区"
            ),
            is_failure_point=False,
        ),
    ]
    if caps.local_first:
        verdict = ExperimentVerdict.SUPPORTED_IN_SIMULATION
        rationale = "本地/端侧处理在断网场景下仍可继续侦测与本地告警，恢复后补齐同步；结构成立。"
    else:
        verdict = ExperimentVerdict.CONTRADICTED
        rationale = "产品定义未体现本地兜底，断网窗口内模拟出现侦测与告警盲区，属反例。"
    return ScenarioSimulation(
        template=ScenarioTemplate.HOME_NETWORK_OUTAGE,
        title="家庭网络中断",
        description="断网/弱网场景下的连续性，检验本地兜底与恢复后同步能力。",
        floor_plan=list(ZONES),
        sensors=sensors,
        timeline=timeline,
        expected_product_decisions=[
            "断网时切换到本地/端侧处理",
            "本地侦测并触发本地声光或离线记录",
            "网络恢复后补齐同步与通知",
        ],
        privacy_boundaries=[
            "离线记录默认本地保存，恢复后按策略同步"
            if caps.privacy_local
            else "需明确离线数据的保留与同步策略"
        ],
        failure_conditions=[
            "云端强依赖会在断网窗口内形成盲区",
            "本地存储容量与掉电保护需设计",
        ],
        observations=[
            "产品定义体现本地/端侧或本地中枢能力"
            if caps.local_first
            else "产品定义未体现本地兜底"
        ],
        coverage_notes=["真实断网时长、掉电与恢复行为需在真实设备上验证。"],
        verdict=verdict,
        verdict_rationale=rationale,
    )


_BUILDERS = {
    ScenarioTemplate.URBAN_APARTMENT_INTRUSION: _intrusion,
    ScenarioTemplate.ELDERLY_NIGHT_ANOMALY: _elderly,
    ScenarioTemplate.PET_FALSE_ALARM: _pet,
    ScenarioTemplate.HOME_NETWORK_OUTAGE: _outage,
}


def simulate_scenario(spec: ProductSpec, template: ScenarioTemplate) -> ScenarioSimulation:
    """Run one fixed scenario against a ProductSpec (fully deterministic)."""

    return _BUILDERS[template](detect_capabilities(spec))


def simulate_all_scenarios(spec: ProductSpec) -> list[ScenarioSimulation]:
    """Run all four fixed scenarios in a stable order."""

    caps = detect_capabilities(spec)
    return [_BUILDERS[template](caps) for template in ScenarioTemplate]
