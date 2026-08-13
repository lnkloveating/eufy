import { useMemo } from "react";
import { Layers } from "lucide-react";

import {
  SCORE_DIMENSIONS,
  type ForecastOptions,
  type ResearchContext,
  type ScoreWeights,
} from "../../types/api";
import { DIMENSION_LABELS } from "../../lib/agentLabels";
import { useKnowledgeCoverage } from "../../lib/queries";
import { Field } from "../../components/ui/Field";
import { TagInput } from "../../components/ui/TagInput";
import { areWeightsValid, type ResearchBrief } from "./researchBrief";

/** Redistribute weight fractions so they sum to exactly 1.0 (integer percents). */
function normalizeWeights(weights: ScoreWeights): ScoreWeights {
  const pct = SCORE_DIMENSIONS.map((key) => Math.round((weights[key] || 0) * 100));
  const total = pct.reduce((sum, value) => sum + value, 0);
  const base = total > 0 ? pct.map((value) => (value * 100) / total) : SCORE_DIMENSIONS.map(() => 20);
  const floored = base.map((value) => Math.floor(value));
  let remainder = 100 - floored.reduce((sum, value) => sum + value, 0);
  const order = base
    .map((value, index) => ({ index, frac: value - Math.floor(value) }))
    .sort((a, b) => b.frac - a.frac);
  let cursor = 0;
  while (remainder > 0) {
    const target = order[cursor % order.length];
    if (target) {
      floored[target.index] = (floored[target.index] ?? 0) + 1;
      remainder -= 1;
    }
    cursor += 1;
  }
  const next = {} as ScoreWeights;
  SCORE_DIMENSIONS.forEach((key, index) => {
    next[key] = (floored[index] ?? 0) / 100;
  });
  return next;
}

export interface AdvancedResearchSettingsProps {
  brief: ResearchBrief;
  options: ForecastOptions;
  onChange: (patch: Partial<ResearchBrief>) => void;
}

const CONTEXT_FIELDS: { key: Exclude<keyof ResearchContext, "innovation_posture">; label: string }[] = [
  { key: "housing_types", label: "住宅类型" },
  { key: "household_members", label: "家庭成员" },
  { key: "security_scenarios", label: "安全场景" },
  { key: "current_devices", label: "现有设备" },
  { key: "pain_points", label: "现有痛点" },
  { key: "allowed_sensors", label: "可接受传感器" },
  { key: "privacy_preferences", label: "隐私偏好" },
  { key: "installation_constraints", label: "安装维护限制" },
  { key: "connectivity_constraints", label: "连接与离线限制" },
  { key: "business_preferences", label: "商业模式偏好" },
  { key: "desired_outcomes", label: "期望结果" },
  { key: "validation_priorities", label: "验证优先级" },
];

function ContextChoiceField({
  field,
  label,
  brief,
  options,
  onChange,
}: {
  field: Exclude<keyof ResearchContext, "innovation_posture">;
  label: string;
  brief: ResearchBrief;
  options: ForecastOptions;
  onChange: (patch: Partial<ResearchBrief>) => void;
}) {
  const values = brief.research_context[field];
  const presets = options.research_context_options[field] ?? [];
  const custom = values.filter((value) => !presets.includes(value));
  const update = (next: string[]) =>
    onChange({ research_context: { ...brief.research_context, [field]: next } });
  return (
    <Field label={label} hint="可多选，也可自定义">
      {() => (
        <div className="stack stack-2">
          <div className="optiongrid">
            {presets.map((option) => (
              <button
                key={option}
                type="button"
                className={`option-pill ${values.includes(option) ? "is-on" : ""}`}
                aria-pressed={values.includes(option)}
                onClick={() =>
                  update(
                    values.includes(option)
                      ? values.filter((value) => value !== option)
                      : [...values, option],
                  )
                }
              >
                {option}
              </button>
            ))}
          </div>
          <TagInput
            values={custom}
            onChange={(next) => update([...values.filter((value) => presets.includes(value)), ...next])}
            placeholder="自定义后回车…"
            ariaLabel={`${label}自定义值`}
          />
        </div>
      )}
    </Field>
  );
}

/**
 * The full deterministic research configuration (regions, users, horizon,
 * price, constraints, candidate count, evaluation weights). Extracted so it can
 * live inside the Deep Research home's collapsible "advanced settings" area.
 */
export function AdvancedResearchSettings({
  brief,
  options,
  onChange,
}: AdvancedResearchSettingsProps) {
  const coverage = useKnowledgeCoverage(brief.regions);
  const presetRegions = options.regions;
  const customRegions = useMemo(
    () => brief.regions.filter((region) => !presetRegions.includes(region)),
    [brief.regions, presetRegions],
  );

  const weightPct = (key: (typeof SCORE_DIMENSIONS)[number]) =>
    Math.round((brief.weights[key] || 0) * 100);
  const weightTotal = SCORE_DIMENSIONS.reduce((sum, key) => sum + weightPct(key), 0);
  const weightsOk = areWeightsValid(brief.weights);

  const toggleRegion = (region: string) => {
    const next = brief.regions.includes(region)
      ? brief.regions.filter((item) => item !== region)
      : [...brief.regions, region];
    onChange({ regions: next });
  };

  return (
    <div className="stack stack-5">
      <div className="form-grid">
        <Field label="品类 Category" required>
          {(aria) => (
            <input
              {...aria}
              className="input"
              value={brief.category}
              onChange={(event) => onChange({ category: event.target.value })}
            />
          )}
        </Field>

        <Field
          label="预测周期（年）"
          hint={`范围 ${options.forecast_horizon_years.minimum}–${options.forecast_horizon_years.maximum} 年`}
        >
          {(aria) => (
            <div className="row row-gap-3">
              <input
                {...aria}
                className="weight-range grow"
                type="range"
                min={options.forecast_horizon_years.minimum}
                max={options.forecast_horizon_years.maximum}
                value={brief.forecast_horizon_years ?? options.forecast_horizon_years.default}
                onChange={(event) =>
                  onChange({ forecast_horizon_years: Number(event.target.value) })
                }
              />
              <span className="strong" style={{ minWidth: 52 }}>
                {brief.forecast_horizon_years ?? options.forecast_horizon_years.default} 年
              </span>
            </div>
          )}
        </Field>
      </div>

      <Field label="地区 Regions" required>
        {() => (
          <div className="stack stack-3">
            <div className="optiongrid">
              {presetRegions.map((region) => (
                <button
                  key={region}
                  type="button"
                  className={`option-pill ${brief.regions.includes(region) ? "is-on" : ""}`}
                  aria-pressed={brief.regions.includes(region)}
                  onClick={() => toggleRegion(region)}
                >
                  {region}
                </button>
              ))}
            </div>
            {options.custom_regions_allowed && (
              <TagInput
                values={customRegions}
                onChange={(next) =>
                  onChange({
                    regions: [
                      ...brief.regions.filter((region) => presetRegions.includes(region)),
                      ...next,
                    ],
                  })
                }
                placeholder="添加自定义地区后回车…"
                ariaLabel="自定义地区"
              />
            )}
            {coverage.data && brief.regions.length > 0 && (
              <div className="row wrap row-gap-2" aria-label="地区知识覆盖度">
                {coverage.data.regions.map((item) => (
                  <span
                    className={`chip ${
                      item.level === "strong"
                        ? "chip-accent"
                        : item.level === "limited"
                          ? "chip-outline"
                          : ""
                    }`}
                    key={item.region}
                    title={`${item.verified_records} 条已验证资料，${item.hypothesis_records} 条待验证假设`}
                  >
                    {item.region} ·{" "}
                    {item.level === "strong"
                      ? "资料充分"
                      : item.level === "moderate"
                        ? "资料一般"
                        : "资料有限"}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
      </Field>

      <div className="form-grid">
        <Field label="目标用户 Target Users" required>
          {(aria) => (
            <TagInput
              values={brief.target_users}
              onChange={(next) => onChange({ target_users: next })}
              placeholder="输入用户群体后回车…"
              id={aria.id}
              ariaLabel="目标用户"
            />
          )}
        </Field>

        <Field label="价格带 Price Segment" hint="可选，例如 中高端 / Premium">
          {(aria) => (
            <input
              {...aria}
              className="input"
              value={brief.price_segment ?? ""}
              onChange={(event) => onChange({ price_segment: event.target.value || null })}
              placeholder="不限"
            />
          )}
        </Field>
      </div>

      <Field label="限制条件 Constraints" hint="可选：合规、隐私、成本等约束">
        {(aria) => (
          <TagInput
            values={brief.constraints}
            onChange={(next) => onChange({ constraints: next })}
            placeholder="输入约束条件后回车…"
            id={aria.id}
            ariaLabel="限制条件"
          />
        )}
      </Field>

      <div className="stack stack-4">
        <div className="stack" style={{ gap: 2 }}>
          <span className="field-label">详细研究上下文 Research Context</span>
          <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
            这些结构化信息会参与本地 RAG 检索，并传给预测、审议、竞品与产品定义 Agent；留空表示开放探索。
          </span>
        </div>
        {CONTEXT_FIELDS.map(({ key, label }) => (
          <ContextChoiceField
            key={key}
            field={key}
            label={label}
            brief={brief}
            options={options}
            onChange={onChange}
          />
        ))}
        <Field label="创新尺度" hint="单选；决定候选组合偏量产还是探索">
          {() => (
            <div className="optiongrid">
              {(options.research_context_options.innovation_posture ?? []).map((option) => (
                <button
                  key={option}
                  type="button"
                  className={`option-pill ${brief.research_context.innovation_posture === option ? "is-on" : ""}`}
                  aria-pressed={brief.research_context.innovation_posture === option}
                  onClick={() =>
                    onChange({
                      research_context: {
                        ...brief.research_context,
                        innovation_posture:
                          brief.research_context.innovation_posture === option ? null : option,
                      },
                    })
                  }
                >
                  {option}
                </button>
              ))}
            </div>
          )}
        </Field>
      </div>

      <Field
        label="候选产品数量"
        hint={`范围 ${options.candidate_count.minimum}–${options.candidate_count.maximum} 个`}
      >
        {(aria) => (
          <div className="row row-gap-3">
            <input
              {...aria}
              className="weight-range grow"
              type="range"
              min={options.candidate_count.minimum}
              max={options.candidate_count.maximum}
              value={brief.candidate_count}
              onChange={(event) => onChange({ candidate_count: Number(event.target.value) })}
            />
            <span className="strong" style={{ minWidth: 52 }}>
              {brief.candidate_count} 个
            </span>
          </div>
        )}
      </Field>

      <div className="stack stack-3">
        <div className="row between">
          <span className="field-label">
            <Layers size={15} aria-hidden="true" /> 评估权重（总和须为 100%）
          </span>
        </div>
        {SCORE_DIMENSIONS.map((dimension) => (
          <div className="weight-row" key={dimension}>
            <span className="weight-name">{DIMENSION_LABELS[dimension]}</span>
            <input
              className="weight-range"
              type="range"
              min={0}
              max={100}
              step={1}
              value={weightPct(dimension)}
              aria-label={`${DIMENSION_LABELS[dimension]} 权重`}
              onChange={(event) =>
                onChange({
                  weights: { ...brief.weights, [dimension]: Number(event.target.value) / 100 },
                })
              }
            />
            <span className="weight-pct">{weightPct(dimension)}%</span>
          </div>
        ))}
        <div className={`weight-total ${weightsOk ? "is-ok" : "is-bad"}`}>
          <span>权重总和：{weightTotal}%</span>
          {weightsOk ? (
            <span>已归一化 ✓</span>
          ) : (
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => onChange({ weights: normalizeWeights(brief.weights) })}
            >
              一键归一化为 100%
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
