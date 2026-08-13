import { ChevronDown, Settings2 } from "lucide-react";

import type { ForecastOptions } from "../../types/api";
import { AdvancedResearchSettings } from "./AdvancedResearchSettings";
import { getBriefCompleteness, type ResearchBrief } from "./researchBrief";

export function AdvancedSettingsCard({
  brief,
  options,
  open,
  onToggle,
  onChange,
}: {
  brief: ResearchBrief;
  options: ForecastOptions;
  open: boolean;
  onToggle: () => void;
  onChange: (patch: Partial<ResearchBrief>) => void;
}) {
  return (
    <div className="card">
      <button
        type="button"
        className="advanced-toggle"
        aria-expanded={open}
        onClick={onToggle}
      >
        <span className="row row-gap-3">
          <Settings2 size={17} aria-hidden="true" />
          <span className="stack stack-none">
            <span className="strong">高级研究设置</span>
            <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
              地区、目标用户、预测周期、价格、约束、候选数量与评估权重
            </span>
          </span>
        </span>
        <span className="row row-gap-2">
          <span className="chip chip-accent">信息完整度 {getBriefCompleteness(brief)}%</span>
          <ChevronDown
            size={18}
            aria-hidden="true"
            style={{
              transition: "transform 160ms",
              transform: open ? "rotate(180deg)" : "none",
            }}
          />
        </span>
      </button>
      {open && (
        <div className="card-pad" style={{ borderTop: "1px solid var(--line)" }}>
          <AdvancedResearchSettings brief={brief} options={options} onChange={onChange} />
        </div>
      )}
    </div>
  );
}
