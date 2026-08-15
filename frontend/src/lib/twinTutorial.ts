/**
 * Builds a deterministic "how this device works" tutorial from a product's
 * digital-twin spec and its ProductSpec. This is presentation only — every step
 * is derived from the real product definition (components, AI capabilities,
 * privacy principles, ecosystem), never invented, and it makes no validation
 * claim. It replaces the earlier multi-scenario walkthrough.
 */

import type {
  DigitalTwinComponentKind,
  ProductDigitalTwinSpec,
  ProductSpec,
} from "../types/api";

export type TwinTutorialPhase =
  | "standby"
  | "sensing"
  | "analysis"
  | "privacy"
  | "response"
  | "ecosystem";

export interface TwinTutorialStep {
  id: string;
  phase: TwinTutorialPhase;
  phaseLabel: string;
  title: string;
  /** What the device does at this step. */
  description: string;
  /** How the user interacts with / uses the device here. */
  usage: string;
  /** Twin component kinds to light up on the 3D model. */
  activeKinds: DigitalTwinComponentKind[];
  tone: "neutral" | "active" | "success" | "alarm";
}

const SENSING_KINDS: DigitalTwinComponentKind[] = [
  "camera",
  "radar",
  "motion",
  "contact",
  "acoustic",
  "environmental",
];
const PRIVACY_KINDS: DigitalTwinComponentKind[] = [
  "privacy_switch",
  "secure_element",
  "local_storage",
];
const RESPONSE_KINDS: DigitalTwinComponentKind[] = ["siren", "speaker", "display", "wireless"];

function firstOrNull(items: string[] | undefined): string | null {
  return items?.[0] ?? null;
}

/** Map a component kind to which tutorial step it belongs to (for chip clicks). */
export function stepPhaseForKind(kind: DigitalTwinComponentKind): TwinTutorialPhase {
  if (SENSING_KINDS.includes(kind)) return "sensing";
  if (kind === "edge_ai") return "analysis";
  if (PRIVACY_KINDS.includes(kind)) return "privacy";
  if (kind === "homebase") return "ecosystem";
  return "response";
}

export function buildTwinTutorialSteps(
  spec: ProductDigitalTwinSpec,
  product: Pick<
    ProductSpec,
    "ai_capabilities" | "privacy_principles" | "ecosystem_relationships"
  >,
): TwinTutorialStep[] {
  const have = new Set(spec.components.map((component) => component.kind));
  const labelsOf = (kinds: DigitalTwinComponentKind[]): string =>
    spec.components
      .filter((component) => kinds.includes(component.kind))
      .map((component) => component.label)
      .join("、");

  const steps: TwinTutorialStep[] = [
    {
      id: "standby",
      phase: "standby",
      phaseLabel: "待机守护",
      title: "设备待机守护",
      description: "设备默认处于低打扰守护状态，隐藏式指示灯常亮，不主动打扰家庭。",
      usage: "点击样机启动设备，或点击右侧任一模块，查看它对应的功能。",
      activeKinds: [],
      tone: "neutral",
    },
  ];

  const sensing = SENSING_KINDS.filter((kind) => have.has(kind));
  if (sensing.length > 0) {
    steps.push({
      id: "sensing",
      phase: "sensing",
      phaseLabel: "多信号感知",
      title: "多信号感知环境",
      description: `产品通过 ${labelsOf(sensing)} 持续感知周界与室内变化，多路信号相互印证。`,
      usage: "在 App 中可按区域开关每一路传感，敏感区域（如卧室）可单独屏蔽。",
      activeKinds: sensing,
      tone: "active",
    });
  }

  if (have.has("edge_ai")) {
    const capability = firstOrNull(product.ai_capabilities) ?? "端侧 AI 融合多路信号";
    steps.push({
      id: "analysis",
      phase: "analysis",
      phaseLabel: "本地 AI 判断",
      title: "端侧 AI 融合判断",
      description: `${capability}，在本地形成可解释判断，用来降低误报。`,
      usage: "每条判断都带可解释理由，用户可以确认或纠正，设备据此持续优化。",
      activeKinds: ["edge_ai"],
      tone: "active",
    });
  }

  const privacy = PRIVACY_KINDS.filter((kind) => have.has(kind));
  if (privacy.length > 0) {
    steps.push({
      id: "privacy",
      phase: "privacy",
      phaseLabel: "隐私边界",
      title: "隐私与决策边界",
      description: firstOrNull(product.privacy_principles) ?? "敏感数据默认在本地处理。",
      usage: have.has("privacy_switch")
        ? "拨动机身上的物理隐私开关即可立即切断感知，状态对家人可见。"
        : "隐私设置在 App 中集中管理，敏感数据可一键删除。",
      activeKinds: privacy,
      tone: "success",
    });
  }

  const response = RESPONSE_KINDS.filter((kind) => have.has(kind));
  steps.push({
    id: "response",
    phase: "response",
    phaseLabel: "响应与告警",
    title: "识别到风险时如何告警",
    description:
      response.length > 0
        ? `识别到风险时，触发 ${labelsOf(response)}，并通过 App 实时推送提醒。`
        : "识别到风险时通过 App 实时推送提醒。",
    usage: "高影响动作（如联动门锁）需在 App 中确认；告警可一键静音或升级给家人。",
    activeKinds: response.length > 0 ? response : (["wireless"] as DigitalTwinComponentKind[]),
    tone: "alarm",
  });

  if (have.has("homebase")) {
    const ecosystem = (product.ecosystem_relationships ?? []).slice(0, 2).join("、") || "HomeBase";
    steps.push({
      id: "ecosystem",
      phase: "ecosystem",
      phaseLabel: "生态联动",
      title: "生态联动与断网兜底",
      description: `与 ${ecosystem} 联动；断网时以本地中枢兜底，继续侦测与本地告警。`,
      usage: "接入 HomeBase 后，可与家中其他 eufy 设备协同布防、共享事件。",
      activeKinds: ["homebase", "wireless"],
      tone: "active",
    });
  }

  return steps;
}
