import { Compass } from "lucide-react";
import type { ForecastRequest, ResearchContext } from "../../types/api";

const CONTEXT_LABELS: Record<keyof ResearchContext, string> = {
  housing_types: "住房类型",
  household_members: "家庭成员",
  security_scenarios: "重点安全场景",
  current_devices: "现有设备",
  pain_points: "核心痛点",
  allowed_sensors: "可接受传感器",
  privacy_preferences: "隐私偏好",
  installation_constraints: "安装维护限制",
  connectivity_constraints: "连接与离线限制",
  business_preferences: "商业模式偏好",
  desired_outcomes: "期望结果",
  validation_priorities: "验证优先级",
  innovation_posture: "创新姿态",
};

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="meta-item">
      <span className="meta-label">{label}</span>
      <span className="meta-value">{value}</span>
    </div>
  );
}

function joinValues(values: string[]): string {
  return values.join("、") || "未填写";
}

/** Auditable copy of the exact user context that drove retrieval and agents. */
export function ResearchContextPanel({ request }: { request: ForecastRequest }) {
  const populated = (Object.keys(request.research_context) as (keyof ResearchContext)[])
    .map((key) => {
      const raw = request.research_context[key];
      const values = Array.isArray(raw) ? raw : raw ? [raw] : [];
      return { key, values };
    })
    .filter((entry) => entry.values.length > 0);
  const weightItems = Object.entries(request.weights);

  return (
    <div className="stack stack-5">
      <div className="card card-pad stack stack-4">
        <div className="row row-gap-3">
          <Compass size={18} style={{ color: "var(--accent)" }} aria-hidden="true" />
          <div className="stack stack-micro">
            <strong>结构化研究上下文</strong>
          </div>
        </div>

        {populated.length ? (
          <div className="metagrid">
            {populated.map(({ key, values }) => (
              <MetaItem key={key} label={CONTEXT_LABELS[key]} value={joinValues(values)} />
            ))}
          </div>
        ) : (
          <div className="empty-inline">本次研究未设置详细上下文，智能体保持开放探索。</div>
        )}
      </div>

      <div className="card card-pad stack stack-3">
        <span className="opp-section-label">策略权重</span>
        <div className="metagrid">
          {weightItems.map(([key, value]) => (
            <MetaItem key={key} label={key} value={`${Math.round(value * 100)}%`} />
          ))}
        </div>
      </div>
    </div>
  );
}
