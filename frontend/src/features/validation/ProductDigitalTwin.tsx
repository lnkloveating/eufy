import { Canvas, useFrame, type ThreeEvent } from "@react-three/fiber";
import { ContactShadows, OrbitControls, RoundedBox } from "@react-three/drei";
import { Suspense, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import type { Group, Mesh, MeshBasicMaterial, PointLight, TorusGeometry } from "three";
import {
  BellRing,
  BrainCircuit,
  Box,
  Lock,
  MousePointerClick,
  Network,
  Pause,
  Play,
  Power,
  Radar,
  RefreshCw,
  ShieldCheck,
  SkipBack,
  SkipForward,
} from "lucide-react";

import type {
  DigitalTwinComponentKind,
  ProductDigitalTwinSpec,
  ProductSpec,
} from "../../types/api";
import {
  buildTwinTutorialSteps,
  stepPhaseForKind,
  type TwinTutorialPhase,
} from "../../lib/twinTutorial";
import { Button } from "../../components/ui/Button";
import { DIGITAL_TWIN_COMPONENT_LABELS } from "../../lib/displayLocalization";

interface Props {
  spec: ProductDigitalTwinSpec;
  product: ProductSpec;
  productName: string;
}

const FRAME_DURATION_MS = 3000;

const ARCHETYPE_LABELS: Record<ProductDigitalTwinSpec["archetype"], string> = {
  sensor_puck: "智能传感节点",
  gateway: "家庭安全网关",
  camera: "智能摄像设备",
  doorbell: "智能门铃",
  wearable: "可穿戴设备",
  robot: "移动安防终端",
  modular_system: "分布式安防系统",
  generic_device: "智能安防设备",
};

function phaseIcon(phase: TwinTutorialPhase): ReactNode {
  const props = { size: 15, "aria-hidden": true } as const;
  return {
    standby: <Power {...props} />,
    sensing: <Radar {...props} />,
    analysis: <BrainCircuit {...props} />,
    privacy: <Lock {...props} />,
    response: <BellRing {...props} />,
    ecosystem: <Network {...props} />,
  }[phase];
}

function hasWebGL(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return Boolean(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

function hasComponent(spec: ProductDigitalTwinSpec, kind: DigitalTwinComponentKind) {
  return spec.components.some((component) => component.kind === kind);
}

function DeviceMaterial({
  spec,
  active = false,
  accent = false,
}: {
  spec: ProductDigitalTwinSpec;
  active?: boolean;
  accent?: boolean;
}) {
  return (
    <meshPhysicalMaterial
      color={accent ? spec.accent_color : spec.base_color}
      roughness={accent ? 0.28 : 0.42}
      metalness={accent ? 0.35 : 0.14}
      clearcoat={0.55}
      clearcoatRoughness={0.28}
      emissive={active ? spec.accent_color : "#000000"}
      emissiveIntensity={active ? 1.2 : 0}
    />
  );
}

function SignalPulse({ color, active }: { color: string; active: boolean }) {
  const ref = useRef<Mesh<TorusGeometry, MeshBasicMaterial>>(null);
  useFrame(({ clock }) => {
    if (!ref.current) return;
    const scale = active ? 1 + ((Math.sin(clock.elapsedTime * 4) + 1) / 2) * 0.45 : 0.8;
    ref.current.scale.setScalar(scale);
    ref.current.material.opacity = active ? 0.34 : 0;
  });
  return (
    <mesh ref={ref} rotation={[Math.PI / 2, 0, 0]}>
      <torusGeometry args={[0.74, 0.025, 12, 64]} />
      <meshBasicMaterial color={color} transparent opacity={0} depthWrite={false} />
    </mesh>
  );
}

function Lens({
  spec,
  position = [0, 0, 0.54],
  active,
  scale = 1,
}: {
  spec: ProductDigitalTwinSpec;
  position?: [number, number, number];
  active: boolean;
  scale?: number;
}) {
  return (
    <group position={position} scale={scale}>
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.25, 0.3, 0.14, 48]} />
        <meshPhysicalMaterial color="#121820" roughness={0.22} metalness={0.58} />
      </mesh>
      <mesh position={[0, 0, 0.08]}>
        <sphereGeometry args={[0.17, 32, 18, 0, Math.PI * 2, 0, Math.PI / 2]} />
        <meshPhysicalMaterial
          color="#182a43"
          roughness={0.05}
          metalness={0.35}
          transmission={0.15}
          emissive={active ? spec.accent_color : "#07101e"}
          emissiveIntensity={active ? 1.6 : 0.25}
        />
      </mesh>
    </group>
  );
}

function StatusStrip({
  spec,
  position,
  active,
}: {
  spec: ProductDigitalTwinSpec;
  position: [number, number, number];
  active: boolean;
}) {
  return (
    <mesh position={position}>
      <boxGeometry args={[0.56, 0.035, 0.025]} />
      <meshBasicMaterial
        color={active ? spec.accent_color : "#617080"}
        toneMapped={false}
      />
    </mesh>
  );
}

function SensorPuck({
  spec,
  activeKinds,
}: {
  spec: ProductDigitalTwinSpec;
  activeKinds: ReadonlySet<DigitalTwinComponentKind>;
}) {
  const { width, height, depth } = spec.dimensions;
  const sensing = activeKinds.has("radar") || activeKinds.has("motion") || activeKinds.has("camera");
  return (
    <group rotation={[Math.PI / 2, 0, 0]}>
      <mesh>
        <cylinderGeometry args={[width / 2, width / 2.08, height, 64]} />
        <DeviceMaterial spec={spec} />
      </mesh>
      <mesh position={[0, height / 2 + 0.012, 0]}>
        <cylinderGeometry args={[width * 0.33, width * 0.33, 0.03, 64]} />
        <DeviceMaterial spec={spec} accent active={sensing} />
      </mesh>
      <mesh position={[0, height / 2 + 0.03, depth * 0.08]}>
        <ringGeometry args={[width * 0.17, width * 0.2, 48]} />
        <meshBasicMaterial color={spec.accent_color} toneMapped={false} />
      </mesh>
      <SignalPulse color={spec.accent_color} active={sensing} />
    </group>
  );
}

function Gateway({
  spec,
  activeKinds,
  compact = false,
}: {
  spec: ProductDigitalTwinSpec;
  activeKinds: ReadonlySet<DigitalTwinComponentKind>;
  compact?: boolean;
}) {
  const scale = compact ? 0.72 : 1;
  const { width, height, depth } = spec.dimensions;
  const computeActive = activeKinds.has("edge_ai") || activeKinds.has("homebase");
  return (
    <group scale={scale}>
      <RoundedBox args={[width, height, depth]} radius={0.16 + spec.design_variant * 0.008} smoothness={5}>
        <DeviceMaterial spec={spec} />
      </RoundedBox>
      {hasComponent(spec, "display") ? (
        <RoundedBox position={[0, height * 0.14, depth / 2 + 0.012]} args={[width * 0.72, height * 0.36, 0.035]} radius={0.06} smoothness={3}>
          <meshPhysicalMaterial
            color="#101722"
            roughness={0.12}
            emissive={computeActive ? spec.accent_color : "#102037"}
            emissiveIntensity={computeActive ? 0.7 : 0.18}
          />
        </RoundedBox>
      ) : (
        <group position={[0, -height * 0.07, depth / 2 + 0.018]}>
          {Array.from({ length: 15 }).map((_, index) => (
            <mesh
              key={index}
              position={[
                ((index % 5) - 2) * width * 0.105,
                (Math.floor(index / 5) - 1) * 0.11,
                0,
              ]}
            >
              <circleGeometry args={[0.018, 12]} />
              <meshBasicMaterial color="#60707c" />
            </mesh>
          ))}
        </group>
      )}
      <StatusStrip spec={spec} position={[0, -height * 0.38, depth / 2 + 0.022]} active={computeActive} />
      {hasComponent(spec, "privacy_switch") && (
        <mesh position={[width / 2 + 0.015, height * 0.16, 0]}>
          <boxGeometry args={[0.035, 0.28, 0.16]} />
          <DeviceMaterial spec={spec} accent active={activeKinds.has("privacy_switch")} />
        </mesh>
      )}
      <SignalPulse color={spec.accent_color} active={computeActive} />
    </group>
  );
}

function Camera({
  spec,
  activeKinds,
  compact = false,
}: {
  spec: ProductDigitalTwinSpec;
  activeKinds: ReadonlySet<DigitalTwinComponentKind>;
  compact?: boolean;
}) {
  const active = activeKinds.has("camera") || activeKinds.has("motion");
  const scale = compact ? 0.65 : 1;
  return (
    <group scale={scale}>
      <RoundedBox args={[1.1, 0.86, 0.78]} radius={0.24} smoothness={5}>
        <DeviceMaterial spec={spec} />
      </RoundedBox>
      <Lens spec={spec} active={active} position={[0, 0.06, 0.44]} />
      <mesh position={[0, -0.65, 0]}>
        <cylinderGeometry args={[0.36, 0.48, 0.16, 48]} />
        <DeviceMaterial spec={spec} />
      </mesh>
      <mesh position={[0, -0.47, 0]}>
        <cylinderGeometry args={[0.09, 0.09, 0.34, 24]} />
        <meshStandardMaterial color="#7b8791" metalness={0.55} roughness={0.35} />
      </mesh>
      <SignalPulse color={spec.accent_color} active={active} />
    </group>
  );
}

function Doorbell({ spec, activeKinds }: ModelProps) {
  const active = activeKinds.has("camera") || activeKinds.has("motion");
  return (
    <group>
      <RoundedBox args={[0.72, 1.75, 0.4]} radius={0.18} smoothness={5}>
        <DeviceMaterial spec={spec} />
      </RoundedBox>
      <Lens spec={spec} active={active} position={[0, 0.39, 0.23]} scale={0.72} />
      <mesh position={[0, -0.42, 0.225]}>
        <cylinderGeometry args={[0.16, 0.16, 0.04, 40]} />
        <DeviceMaterial spec={spec} accent active={activeKinds.has("speaker")} />
      </mesh>
      <SignalPulse color={spec.accent_color} active={active} />
    </group>
  );
}

function Wearable({ spec, activeKinds }: ModelProps) {
  const active = activeKinds.size > 0;
  return (
    <group rotation={[Math.PI / 2, 0, 0]}>
      <mesh>
        <torusGeometry args={[0.72, 0.16, 24, 72]} />
        <DeviceMaterial spec={spec} />
      </mesh>
      <RoundedBox args={[0.78, 0.78, 0.22]} radius={0.18} smoothness={5}>
        <DeviceMaterial spec={spec} accent active={active} />
      </RoundedBox>
      <SignalPulse color={spec.accent_color} active={active} />
    </group>
  );
}

function Robot({ spec, activeKinds }: ModelProps) {
  const active = activeKinds.has("camera") || activeKinds.has("radar");
  return (
    <group>
      <mesh position={[0, -0.28, 0]}>
        <cylinderGeometry args={[0.88, 0.95, 0.46, 48]} />
        <DeviceMaterial spec={spec} />
      </mesh>
      <mesh position={[0, 0.22, 0]}>
        <cylinderGeometry args={[0.12, 0.16, 0.62, 24]} />
        <meshStandardMaterial color="#71808b" metalness={0.5} roughness={0.32} />
      </mesh>
      <group position={[0, 0.58, 0]}>
        <RoundedBox args={[0.76, 0.42, 0.5]} radius={0.16} smoothness={4}>
          <DeviceMaterial spec={spec} />
        </RoundedBox>
        <Lens spec={spec} active={active} position={[0, 0, 0.28]} scale={0.55} />
      </group>
      <SignalPulse color={spec.accent_color} active={active} />
    </group>
  );
}

function ModularSystem({ spec, activeKinds }: ModelProps) {
  const variantOffset = (spec.design_variant - 3.5) * 0.04;
  return (
    <group>
      <group position={[-0.28, 0, 0]}>
        <Gateway spec={spec} activeKinds={activeKinds} compact />
      </group>
      <group position={[1.08 + variantOffset, 0.13, 0.12]}>
        {hasComponent(spec, "camera") ? (
          <Camera spec={spec} activeKinds={activeKinds} compact />
        ) : (
          <group scale={0.72}>
            <SensorPuck spec={spec} activeKinds={activeKinds} />
          </group>
        )}
      </group>
      <group position={[-1.1 - variantOffset, -0.45, 0.24]} scale={0.48}>
        <SensorPuck spec={spec} activeKinds={activeKinds} />
      </group>
      <mesh position={[0.52, 0.62, -0.24]} rotation={[0, 0, Math.PI / 2]}>
        <torusGeometry args={[0.72, 0.016, 10, 48, Math.PI]} />
        <meshBasicMaterial
          color={spec.accent_color}
          transparent
          opacity={activeKinds.size ? 0.8 : 0.18}
          depthWrite={false}
        />
      </mesh>
    </group>
  );
}

function GenericDevice({ spec, activeKinds }: ModelProps) {
  const { width, height, depth } = spec.dimensions;
  return (
    <group>
      <RoundedBox args={[width, height, depth]} radius={0.2} smoothness={5}>
        <DeviceMaterial spec={spec} />
      </RoundedBox>
      <StatusStrip spec={spec} position={[0, -height * 0.28, depth / 2 + 0.022]} active={activeKinds.size > 0} />
      <SignalPulse color={spec.accent_color} active={activeKinds.size > 0} />
    </group>
  );
}

interface ModelProps {
  spec: ProductDigitalTwinSpec;
  activeKinds: ReadonlySet<DigitalTwinComponentKind>;
}

/** Red expanding rings + pulsing light shown during the alarm/response step. */
function AlarmFx({ active }: { active: boolean }) {
  const ring1 = useRef<Mesh<TorusGeometry, MeshBasicMaterial>>(null);
  const ring2 = useRef<Mesh<TorusGeometry, MeshBasicMaterial>>(null);
  const light = useRef<PointLight>(null);
  useFrame(({ clock }) => {
    const t = clock.elapsedTime;
    const a = (t * 1.3) % 1;
    const b = ((t * 1.3) + 0.5) % 1;
    if (ring1.current) {
      ring1.current.scale.setScalar(active ? 1 + a * 0.9 : 0.001);
      ring1.current.material.opacity = active ? 0.55 * (1 - a) : 0;
    }
    if (ring2.current) {
      ring2.current.scale.setScalar(active ? 1 + b * 0.9 : 0.001);
      ring2.current.material.opacity = active ? 0.55 * (1 - b) : 0;
    }
    if (light.current) {
      light.current.intensity = active ? 1.4 + ((Math.sin(t * 7) + 1) / 2) * 2.6 : 0;
    }
  });
  return (
    <group>
      <pointLight ref={light} position={[0, 0.6, 1.7]} color="#ff3b30" intensity={0} distance={9} />
      {[ring1, ring2].map((ref, index) => (
        <mesh key={index} ref={ref} position={[0, -1.12, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[0.82, 0.028, 12, 72]} />
          <meshBasicMaterial
            color="#ff3b30"
            transparent
            opacity={0}
            depthWrite={false}
            toneMapped={false}
          />
        </mesh>
      ))}
    </group>
  );
}

function ProductModel({
  spec,
  activeKinds,
  playing,
  alarm,
  onSelect,
}: ModelProps & { playing: boolean; alarm: boolean; onSelect?: () => void }) {
  const group = useRef<Group>(null);
  const [hovered, setHovered] = useState(false);
  useFrame(({ clock }, delta) => {
    if (!group.current) return;
    const targetY = playing ? Math.sin(clock.elapsedTime * 0.34) * 0.32 : 0;
    group.current.rotation.y += (targetY - group.current.rotation.y) * Math.min(delta * 2, 1);
    group.current.position.y = Math.sin(clock.elapsedTime * 1.15) * 0.025;
  });

  useEffect(() => {
    if (!onSelect) return;
    document.body.style.cursor = hovered ? "pointer" : "";
    return () => {
      document.body.style.cursor = "";
    };
  }, [hovered, onSelect]);

  const model = {
    sensor_puck: <SensorPuck spec={spec} activeKinds={activeKinds} />,
    gateway: <Gateway spec={spec} activeKinds={activeKinds} />,
    camera: <Camera spec={spec} activeKinds={activeKinds} />,
    doorbell: <Doorbell spec={spec} activeKinds={activeKinds} />,
    wearable: <Wearable spec={spec} activeKinds={activeKinds} />,
    robot: <Robot spec={spec} activeKinds={activeKinds} />,
    modular_system: <ModularSystem spec={spec} activeKinds={activeKinds} />,
    generic_device: <GenericDevice spec={spec} activeKinds={activeKinds} />,
  }[spec.archetype];

  return (
    <group
      ref={group}
      onClick={(event: ThreeEvent<MouseEvent>) => {
        event.stopPropagation();
        onSelect?.();
      }}
      onPointerOver={(event: ThreeEvent<PointerEvent>) => {
        event.stopPropagation();
        setHovered(true);
      }}
      onPointerOut={() => setHovered(false)}
    >
      {model}
      <AlarmFx active={alarm} />
    </group>
  );
}

function DigitalTwinScene({
  spec,
  activeKinds,
  playing,
  alarm,
  onSelect,
}: ModelProps & { playing: boolean; alarm: boolean; onSelect?: () => void }) {
  return (
    <>
      <color attach="background" args={["#eef3f5"]} />
      <fog attach="fog" args={["#eef3f5", 6, 12]} />
      <ambientLight intensity={1.6} />
      <directionalLight position={[4, 5, 4]} intensity={2.5} castShadow />
      <pointLight
        position={[-3, 1, 3]}
        color={alarm ? "#ff5a4d" : spec.accent_color}
        intensity={2.2}
      />
      <Suspense fallback={null}>
        <ProductModel
          spec={spec}
          activeKinds={activeKinds}
          playing={playing}
          alarm={alarm}
          onSelect={onSelect}
        />
      </Suspense>
      <ContactShadows position={[0, -1.18, 0]} opacity={0.3} scale={6} blur={2.4} far={4} />
      <gridHelper position={[0, -1.16, 0]} args={[8, 16, "#c9d4d8", "#dfe7ea"]} />
      <OrbitControls
        makeDefault
        enablePan={false}
        minDistance={3.3}
        maxDistance={7}
        minPolarAngle={Math.PI * 0.22}
        maxPolarAngle={Math.PI * 0.68}
        target={[0, 0, 0]}
      />
    </>
  );
}

function DigitalTwinFallback({ spec }: { spec: ProductDigitalTwinSpec }) {
  return (
    <div className="vlab-twin-fallback" role="img" aria-label="3D 数字样机静态说明">
      <Box size={46} aria-hidden="true" />
      <strong>{ARCHETYPE_LABELS[spec.archetype]}</strong>
      <span>当前设备无法启用 WebGL，以下产品组件仍可查看：</span>
      <div className="row row-gap-2 wrap">
        {spec.components.map((component) => (
          <span className="chip" key={component.id}>
            {DIGITAL_TWIN_COMPONENT_LABELS[component.kind] ?? component.label}
          </span>
        ))}
      </div>
    </div>
  );
}

export function ProductDigitalTwin({ spec, product, productName }: Props) {
  const tutorialSpec = useMemo(
    () => ({
      ...spec,
      components: spec.components.map((component) => ({
        ...component,
        label: DIGITAL_TWIN_COMPONENT_LABELS[component.kind] ?? component.label,
      })),
    }),
    [spec],
  );
  const steps = useMemo(
    () => buildTwinTutorialSteps(tutorialSpec, product),
    [tutorialSpec, product],
  );
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(true);
  const webgl = useMemo(hasWebGL, []);
  const lastFrame = Math.max(steps.length - 1, 0);
  const step = steps[Math.min(frameIndex, lastFrame)];

  useEffect(() => {
    setFrameIndex(0);
    setPlaying(true);
  }, [spec.signature]);

  // react-three-fiber sizes its canvas from a ResizeObserver on the container.
  // When the twin is revealed behind a lazy Suspense boundary, that first
  // measurement can land at 0 and leave the canvas stuck at its 300x150 default.
  // Nudge a re-measure across the next frames once layout has settled.
  useEffect(() => {
    if (!webgl) return;
    const nudges = [
      requestAnimationFrame(() => window.dispatchEvent(new Event("resize"))),
      requestAnimationFrame(() =>
        requestAnimationFrame(() => window.dispatchEvent(new Event("resize"))),
      ),
    ];
    const timer = window.setTimeout(() => window.dispatchEvent(new Event("resize")), 200);
    return () => {
      nudges.forEach((id) => cancelAnimationFrame(id));
      window.clearTimeout(timer);
    };
  }, [webgl]);

  useEffect(() => {
    if (!playing) return;
    if (frameIndex >= lastFrame) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(
      () => setFrameIndex((value) => Math.min(value + 1, lastFrame)),
      FRAME_DURATION_MS,
    );
    return () => window.clearTimeout(timer);
  }, [playing, frameIndex, lastFrame]);

  const activeKinds = useMemo(
    () => new Set<DigitalTwinComponentKind>(step?.activeKinds ?? []),
    [step?.activeKinds],
  );
  const alarm = step?.phase === "response";
  const progress = steps.length ? ((frameIndex + 1) / steps.length) * 100 : 0;

  function restart() {
    setFrameIndex(0);
    setPlaying(true);
  }

  // Tapping the 3D device steps the tutorial forward (loops at the end) so the
  // model itself is the primary "start / continue" control.
  function selectModel() {
    setPlaying(false);
    setFrameIndex((value) => (value >= lastFrame ? 0 : value + 1));
  }

  function jumpToKind(kind: DigitalTwinComponentKind) {
    const phase = stepPhaseForKind(kind);
    const index = steps.findIndex((item) => item.phase === phase);
    if (index >= 0) {
      setPlaying(false);
      setFrameIndex(index);
    }
  }

  const componentNotes = tutorialSpec.components.map((component) => component.label);
  const privacyNotes = [...product.privacy_principles, product.ai_decision_boundary].filter(Boolean);

  return (
    <div className="vlab-scenario vlab-digital-twin">
      <div className="vlab-scenario-stage vlab-twin-stage">
        <div className="vlab-twin-canvas-wrap">
          <div className="vlab-scene-hud">
            <span className={`vlab-live-status ${playing ? "is-live" : ""}`}>
              <span className="vlab-live-status-dot" />
              {playing ? "设备运行中" : frameIndex === lastFrame ? "导览完成" : "已暂停"}
            </span>
            <span className="mono">DT-{spec.signature.slice(0, 8).toUpperCase()}</span>
          </div>
          {webgl ? (
            <Canvas
              className="vlab-twin-canvas"
              camera={{ position: [3.6, 2.2, 4.8], fov: 38 }}
              dpr={[1, 1.5]}
              gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
              shadows
              fallback={<DigitalTwinFallback spec={spec} />}
              aria-label={`${productName} 参数化 3D 数字样机`}
            >
              <DigitalTwinScene
                spec={spec}
                activeKinds={activeKinds}
                playing={playing}
                alarm={alarm}
                onSelect={selectModel}
              />
            </Canvas>
          ) : (
            <DigitalTwinFallback spec={spec} />
          )}
          <button type="button" className="vlab-twin-hint" onClick={selectModel}>
            <MousePointerClick size={13} aria-hidden="true" />
            {frameIndex === 0
              ? "点击样机启动设备"
              : frameIndex >= lastFrame
                ? "点击样机重新演示"
                : "点击样机继续下一步"}
          </button>
          <div className="vlab-twin-caption">
            <div>
              <span className="eyebrow">参数化 3D 数字样机</span>
              <strong>{productName}</strong>
              <span>{ARCHETYPE_LABELS[spec.archetype]} · 设计变体 {spec.design_variant + 1}</span>
            </div>
            <span className="vlab-twin-orbit-help">拖动旋转 · 滚轮缩放</span>
          </div>
        </div>
        <div className="vlab-twin-components" aria-label="样机组件">
          {spec.components.map((component) => (
            <button
              type="button"
              className={`vlab-twin-component ${activeKinds.has(component.kind) ? "is-active" : ""}`}
              key={component.id}
              onClick={() => jumpToKind(component.kind)}
              title={`查看「${component.label}」如何使用`}
            >
              <span /> {DIGITAL_TWIN_COMPONENT_LABELS[component.kind] ?? component.label}
            </button>
          ))}
        </div>
      </div>

      <div className="vlab-scenario-side">
        <div className="vlab-demo-head">
          <div>
            <span className="eyebrow">产品功能教程 · 设备使用导览</span>
            <h3>{step?.phaseLabel ?? "设备导览"}</h3>
          </div>
          <div className="row row-gap-2 wrap">
            <span className="chip chip-outline">功能导览 · 非验证</span>
          </div>
        </div>

        <div className={`vlab-live-card tone-${step?.tone ?? "neutral"}`} aria-live="polite">
          <div className="vlab-live-card-progress"><span style={{ width: `${progress}%` }} /></div>
          <div className="row between row-gap-2">
            <span className="vlab-live-kicker">
              步骤 {frameIndex + 1} / {steps.length}
            </span>
            {alarm && <span className="badge badge-failed">告警演示</span>}
          </div>
          <div className="vlab-live-section">
            <strong>{step?.title}</strong>
            <p>{step?.description}</p>
          </div>
          <div className="vlab-live-section is-product">
            <span>怎么使用 / 如何交互</span>
            <p>{step?.usage}</p>
          </div>
          <div className="vlab-active-signals">
            <span>当前激活模块</span>
            {[...activeKinds].length ? (
              [...activeKinds].map((kind) => (
                <span className="vlab-signal-chip" key={kind}>
                  <span /> {DIGITAL_TWIN_COMPONENT_LABELS[kind] ?? kind}
                </span>
              ))
            ) : (
              <span className="subtle">设备待机，尚未唤醒硬件模块</span>
            )}
          </div>
        </div>

        <ol className="vlab-product-flow" aria-label="产品功能导览">
          {steps.map((item, index) => (
            <li
              key={item.id}
              className={`${index === frameIndex ? "is-active" : ""} ${index < frameIndex ? "is-done" : ""}`}
            >
              <button
                type="button"
                onClick={() => { setPlaying(false); setFrameIndex(index); }}
                aria-current={index === frameIndex ? "step" : undefined}
              >
                <span className="vlab-flow-icon">{phaseIcon(item.phase)}</span>
                <span>{item.phaseLabel}</span>
              </button>
            </li>
          ))}
        </ol>

        <div className="vlab-step-controls row row-gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => { setPlaying(false); setFrameIndex((value) => Math.max(value - 1, 0)); }}
            disabled={frameIndex === 0}
            iconStart={<SkipBack size={14} aria-hidden="true" />}
          >上一步</Button>
          <Button
            variant="primary"
            size="sm"
            onClick={() => { if (frameIndex >= lastFrame) restart(); else setPlaying((value) => !value); }}
            iconStart={frameIndex >= lastFrame && !playing ? <RefreshCw size={14} aria-hidden="true" /> : playing ? <Pause size={14} aria-hidden="true" /> : <Play size={14} aria-hidden="true" />}
          >{frameIndex >= lastFrame && !playing ? "重新演示" : playing ? "暂停演示" : "继续演示"}</Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => { setPlaying(false); setFrameIndex((value) => Math.min(value + 1, lastFrame)); }}
            disabled={frameIndex >= lastFrame}
            iconStart={<SkipForward size={14} aria-hidden="true" />}
          >下一步</Button>
          <span className="subtle vlab-demo-duration">点击样机可单步启动设备，或拖动旋转查看</span>
        </div>
      </div>

      <div className="vlab-scenario-notes">
        <InfoNoteBlock icon={<Box size={12} aria-hidden="true" />} title="产品硬件模块" items={componentNotes} />
        <InfoNoteBlock icon={<BrainCircuit size={12} aria-hidden="true" />} title="AI 能力" items={product.ai_capabilities} />
        <InfoNoteBlock icon={<ShieldCheck size={12} aria-hidden="true" />} title="隐私与决策边界" items={privacyNotes} />
        <InfoNoteBlock icon={<Radar size={12} aria-hidden="true" />} title="典型使用方式" items={product.user_journeys} />
      </div>
    </div>
  );
}

function InfoNoteBlock({
  title,
  items,
  icon,
}: {
  title: string;
  items: string[];
  icon?: ReactNode;
}) {
  if (!items.length) return null;
  return (
    <div className="stack stack-2">
      <span className="opp-section-label">
        {icon} {title}
      </span>
      <div className="bullets">
        {items.map((item, index) => (
          <div className="bullet" key={index}>{item}</div>
        ))}
      </div>
    </div>
  );
}
