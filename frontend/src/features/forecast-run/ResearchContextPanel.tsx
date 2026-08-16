import { ClipboardCheck, Compass } from "lucide-react";
import type { ForecastRequest, ResearchContext } from "../../types/api";

const CONTEXT_LABELS: Record<keyof ResearchContext, string> = {
  housing_types: "住宅类型",
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
  innovation_posture: "创新尺度",
};

function Values({ values }: { values: string[] }) {
  return (
    <div className="row wrap row-gap-2">
      {values.map((value) => (
        <span className="chip chip-accent" key={value}>
          {value}
        </span>
      ))}
    </div>
  );
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

  return (
    <div className="stack stack-5">
      <div className="card card-pad stack stack-4">
        <div className="row row-gap-3">
          <ClipboardCheck size={19} style={{ color: "var(--accent)" }} aria-hidden="true" />
          <div className="stack stack-micro">
            <span className="eyebrow">研究任务 · 输入追溯</span>
            <strong>{request.question}</strong>
          </div>
        </div>
        <div className="metagrid">
          <div className="meta-item"><span className="meta-label">预测周期</span><span className="meta-value">未来 {request.forecast_horizon_years} 年</span></div>
          <div className="meta-item"><span className="meta-label">地区</span><span className="meta-value">{request.regions.join("、")}</span></div>
          <div className="meta-item"><span className="meta-label">目标用户</span><span className="meta-value">{request.target_users.join("、")}</span></div>
          <div className="meta-item"><span className="meta-label">价格带</span><span className="meta-value">{request.price_segment ?? "未限定"}</span></div>
        </div>
        {request.constraints.length > 0 && <Values values={request.constraints} />}
      </div>

      <div className="card card-pad stack stack-4">
        <div className="row row-gap-3">
          <Compass size={18} style={{ color: "var(--accent)" }} aria-hidden="true" />
          <div className="stack stack-micro">
            <strong>结构化研究上下文</strong>
            <span className="subtle" style={{ fontSize: "var(--text-sm)" }}>
              下列内容参与了检索增强取证和所有智能体分析；未出现的字段按“未知 / 开放探索”处理。
            </span>
          </div>
        </div>
        {populated.length ? (
          <div className="stack stack-4">
            {populated.map(({ key, values }) => (
              <div className="stack stack-2" key={key}>
                <span className="meta-label">{CONTEXT_LABELS[key]}</span>
                <Values values={values} />
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-inline">本次研究未设置详细上下文，智能体保持开放探索。</div>
        )}
      </div>
    </div>
  );
}
