import { ArrowRight, Pencil, Rocket, Target } from "lucide-react";
import { Button } from "../../components/ui/Button";
import { describeBrief, getBriefCompleteness, type ResearchBrief } from "./researchBrief";

export interface ResearchBriefCardProps {
  brief: ResearchBrief;
  regionLabel: (region: string) => string;
  onEdit: () => void;
  onStart: () => void;
  starting: boolean;
  canStart: boolean;
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="meta-item">
      <span className="meta-label">{label}</span>
      <span className="meta-value">{value || "—"}</span>
    </div>
  );
}

/** Confirmation card shown once the brief is complete, before the backend call. */
export function ResearchBriefCard({
  brief,
  regionLabel,
  onEdit,
  onStart,
  starting,
  canStart,
}: ResearchBriefCardProps) {
  return (
    <div className="card card-pad stack stack-5">
      <div className="row row-gap-3">
        <span
          className="agent-avatar"
          style={{ background: "var(--accent-soft)", color: "var(--accent-deep)" }}
        >
          <Target size={18} aria-hidden="true" />
        </span>
        <div className="stack stack-micro">
          <span className="eyebrow">
            研究任务确认 Research Brief · 信息完整度 {getBriefCompleteness(brief)}%
          </span>
          <strong style={{ fontSize: "var(--text-lg)" }}>
            {describeBrief(brief, regionLabel)}
          </strong>
        </div>
      </div>

      <div className="card" style={{ padding: "var(--space-4)", background: "var(--surface-2)" }}>
        <span className="meta-label">原始研究问题</span>
        <p style={{ marginTop: 6, color: "var(--ink-800)" }}>{brief.question}</p>
      </div>

      <div className="metagrid">
        <Fact label="预测周期" value={`未来 ${brief.forecast_horizon_years ?? 3} 年`} />
        <Fact label="地区" value={brief.regions.map(regionLabel).join("、")} />
        <Fact label="目标用户" value={brief.target_users.join("、")} />
        <Fact label="价格区间" value={brief.price_segment ?? "不限"} />
        <Fact
          label="产品限制"
          value={brief.constraints.length ? brief.constraints.join("、") : "无"}
        />
        <Fact label="候选数量" value={`${brief.candidate_count} 个`} />
        <Fact
          label="住宅类型"
          value={brief.research_context.housing_types.join("、") || "开放探索"}
        />
        <Fact
          label="家庭成员"
          value={brief.research_context.household_members.join("、") || "开放探索"}
        />
        <Fact
          label="重点场景"
          value={brief.research_context.security_scenarios.join("、") || "开放探索"}
        />
        <Fact
          label="现有设备"
          value={brief.research_context.current_devices.join("、") || "未指定"}
        />
        <Fact
          label="核心痛点"
          value={brief.research_context.pain_points.join("、") || "开放探索"}
        />
        <Fact
          label="隐私偏好"
          value={brief.research_context.privacy_preferences.join("、") || "未指定"}
        />
        <Fact
          label="期望结果"
          value={brief.research_context.desired_outcomes.join("、") || "开放探索"}
        />
        <Fact
          label="创新尺度"
          value={brief.research_context.innovation_posture ?? "平衡探索"}
        />
      </div>

      <div className="row between wrap row-gap-3">
        <Button variant="secondary" onClick={onEdit} iconStart={<Pencil size={15} aria-hidden="true" />}>
          修改研究条件
        </Button>
        <Button
          variant="primary"
          size="lg"
          onClick={onStart}
          loading={starting}
          disabled={!canStart || starting}
          iconStart={<Rocket size={16} aria-hidden="true" />}
          iconEnd={<ArrowRight size={16} aria-hidden="true" />}
        >
          {starting ? "正在启动深度研究…" : "开始深度研究"}
        </Button>
      </div>
    </div>
  );
}
