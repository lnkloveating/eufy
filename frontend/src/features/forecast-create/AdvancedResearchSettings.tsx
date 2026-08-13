import { useMemo } from "react";

import type { ForecastOptions, ResearchContext } from "../../types/api";
import { useKnowledgeCoverage } from "../../lib/queries";
import { Field } from "../../components/ui/Field";
import { TagInput } from "../../components/ui/TagInput";
import type { ResearchBrief } from "./researchBrief";

export interface AdvancedResearchSettingsProps {
  brief: ResearchBrief;
  options: ForecastOptions;
  onChange: (patch: Partial<ResearchBrief>) => void;
  section?: "all" | "scope" | "context";
}

const CONTEXT_FIELDS: {
  key: Exclude<keyof ResearchContext, "innovation_posture">;
  label: string;
}[] = [
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
            onChange={(next) =>
              update([...values.filter((value) => presets.includes(value)), ...next])
            }
            placeholder="自定义后回车…"
            ariaLabel={`${label}自定义值`}
          />
        </div>
      )}
    </Field>
  );
}

function ScopeSettings({
  brief,
  options,
  onChange,
}: Omit<AdvancedResearchSettingsProps, "section">) {
  const coverage = useKnowledgeCoverage(brief.regions);
  const presetRegions = options.regions;
  const customRegions = useMemo(
    () => brief.regions.filter((region) => !presetRegions.includes(region)),
    [brief.regions, presetRegions],
  );
  const toggleRegion = (region: string) =>
    onChange({
      regions: brief.regions.includes(region)
        ? brief.regions.filter((item) => item !== region)
        : [...brief.regions, region],
    });

  return (
    <div className="stack stack-5">
      <Field label="研究问题" required>
        {(aria) => (
          <textarea
            {...aria}
            className="textarea"
            rows={3}
            maxLength={1000}
            value={brief.question}
            onChange={(event) => onChange({ question: event.target.value })}
          />
        )}
      </Field>

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
          required
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
                  >
                    {item.region} · {item.level === "strong" ? "资料充分" : item.level === "moderate" ? "资料一般" : "资料有限"}
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
            <span className="strong" style={{ minWidth: 52 }}>{brief.candidate_count} 个</span>
          </div>
        )}
      </Field>
    </div>
  );
}

function ContextSettings({
  brief,
  options,
  onChange,
}: Omit<AdvancedResearchSettingsProps, "section">) {
  return (
    <div className="stack stack-5">
      <div className="row between wrap row-gap-2">
        <div className="stack" style={{ gap: 2 }}>
          <strong>详细研究上下文</strong>
          <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
            选填；已填写内容会参与本地 RAG 和所有 Agent 分析。
          </span>
        </div>
        <span className="chip chip-outline">全部选填</span>
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
  );
}

/** Shared settings surface. The setup dialog renders scope and context as separate steps. */
export function AdvancedResearchSettings({
  brief,
  options,
  onChange,
  section = "all",
}: AdvancedResearchSettingsProps) {
  return (
    <div className="stack stack-6">
      {(section === "all" || section === "scope") && (
        <ScopeSettings brief={brief} options={options} onChange={onChange} />
      )}
      {(section === "all" || section === "context") && (
        <ContextSettings brief={brief} options={options} onChange={onChange} />
      )}
    </div>
  );
}
