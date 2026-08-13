import { useState } from "react";
import { Check, SlidersHorizontal, Target } from "lucide-react";

import type { StrategyPreset } from "../../types/api";
import { dominantSummary } from "../../lib/strategy";
import { type ResearchBrief } from "./researchBrief";
import { WeightSliders } from "./WeightSliders";

export interface StrategyPreferenceCardProps {
  brief: ResearchBrief;
  presets: StrategyPreset[];
  onChange: (patch: Partial<ResearchBrief>) => void;
}

/**
 * Prominent (not hidden in advanced settings) "产品预测偏好" card. Preset
 * buttons apply backend-authored weights only — no weights are hardcoded here
 * and no extra LLM request is made. Opening custom reuses the shared
 * WeightSliders, so there is a single weight-editing surface and one state.
 */
export function StrategyPreferenceCard({ brief, presets, onChange }: StrategyPreferenceCardProps) {
  const isCustom = brief.strategy_profile === "custom";
  const [showCustom, setShowCustom] = useState(isCustom);

  const selectPreset = (preset: StrategyPreset) => {
    setShowCustom(false);
    onChange({ strategy_profile: preset.id, weights: { ...preset.weights } });
  };

  return (
    <div className="card card-pad stack stack-4">
      <div className="row row-gap-3">
        <span
          className="agent-avatar"
          style={{ background: "var(--accent-soft)", color: "var(--accent-deep)" }}
        >
          <Target size={18} aria-hidden="true" />
        </span>
        <div className="stack" style={{ gap: 2 }}>
          <strong style={{ fontSize: "var(--text-base)" }}>产品预测偏好</strong>
          <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
            选择本次 AI 产品预测更偏向的方向。它会影响证据检索、分析关注点、候选组合与评分权重，
            但不会预设任何具体产品，也不额外调用模型。
          </span>
        </div>
      </div>

      <div
        className="strategy-grid"
        role="radiogroup"
        aria-label="产品预测偏好预设"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
          gap: "var(--space-3)",
        }}
      >
        {presets.map((preset) => {
          const active = !isCustom && brief.strategy_profile === preset.id;
          return (
            <button
              key={preset.id}
              type="button"
              role="radio"
              aria-checked={active}
              className={`strategy-preset ${active ? "is-on" : ""}`}
              onClick={() => selectPreset(preset)}
              style={{
                textAlign: "left",
                padding: "var(--space-3)",
                borderRadius: "var(--radius-md, 10px)",
                border: active ? "2px solid var(--accent)" : "1px solid var(--line)",
                background: active ? "var(--accent-soft)" : "var(--surface-1, transparent)",
                cursor: "pointer",
              }}
            >
              <div className="row between" style={{ alignItems: "flex-start" }}>
                <strong>{preset.label}</strong>
                {active && <Check size={16} aria-hidden="true" style={{ color: "var(--accent)" }} />}
              </div>
              <p className="subtle" style={{ fontSize: "var(--text-xs)", margin: "4px 0 8px" }}>
                {preset.description}
              </p>
              <span className="chip chip-outline" style={{ fontSize: "var(--text-xs)" }}>
                {dominantSummary(preset.weights)}
              </span>
            </button>
          );
        })}
      </div>

      <div className="row between wrap row-gap-2">
        <button
          type="button"
          className={`btn btn-sm ${isCustom ? "btn-dark" : ""}`}
          aria-expanded={showCustom}
          onClick={() => setShowCustom((value) => !value)}
        >
          <SlidersHorizontal size={14} aria-hidden="true" /> 自定义权重
        </button>
        {isCustom && (
          <span className="chip chip-accent" style={{ fontSize: "var(--text-xs)" }}>
            当前：自定义权重 · {dominantSummary(brief.weights)}
          </span>
        )}
      </div>

      {showCustom && (
        <div className="card-pad" style={{ borderTop: "1px solid var(--line)", paddingBottom: 0 }}>
          <WeightSliders brief={brief} onChange={onChange} />
        </div>
      )}
    </div>
  );
}
