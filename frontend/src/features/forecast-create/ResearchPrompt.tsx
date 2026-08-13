import { ArrowRight, Search, Sparkles } from "lucide-react";

import { Button } from "../../components/ui/Button";
import { EXAMPLE_PROMPTS, type ExamplePrompt } from "./researchBrief";

const REGION_LABELS: Record<string, string> = {
  China: "中国",
  "United States": "美国",
  "European Union": "欧盟",
  Global: "全球",
};

function formatRegion(region: string) {
  return REGION_LABELS[region] ?? region;
}

export interface ResearchPromptProps {
  question: string;
  onQuestionChange: (question: string) => void;
  onPickExample: (example: ExamplePrompt) => void;
  onStart: () => void;
  starting: boolean;
  canStart: boolean;
  disabledReason?: string;
}

export function ResearchPrompt({
  question,
  onQuestionChange,
  onPickExample,
  onStart,
  starting,
  canStart,
  disabledReason,
}: ResearchPromptProps) {
  return (
    <div className="stack stack-6">
      <div className="research-input-wrap">
        <div className="research-input-label">
          <Search size={18} aria-hidden="true" />
          你想研究 eufy Security 未来什么产品机会？
        </div>
        <textarea
          className="research-input"
          value={question}
          onChange={(event) => onQuestionChange(event.target.value)}
          rows={3}
          maxLength={1000}
          placeholder="例如：未来三年美国独栋家庭有哪些不依赖订阅的安防机会？"
          aria-label="研究问题"
          onKeyDown={(event) => {
            if ((event.metaKey || event.ctrlKey) && event.key === "Enter" && canStart) {
              event.preventDefault();
              onStart();
            }
          }}
        />
        <div className="research-input-foot">
          {disabledReason ? (
            <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
              {disabledReason}
            </span>
          ) : (
            <span />
          )}
          <Button
            variant="primary"
            size="lg"
            onClick={onStart}
            loading={starting}
            disabled={!canStart || starting}
            iconEnd={<ArrowRight size={17} aria-hidden="true" />}
          >
            {starting ? "正在启动研究…" : "开始深度研究"}
          </Button>
        </div>
      </div>

      <div className="stack stack-3">
        <span className="eyebrow row row-gap-2">
          <Sparkles size={13} aria-hidden="true" />
          示例研究方向
        </span>
        <div className="example-grid">
          {EXAMPLE_PROMPTS.map((example) => (
            <button
              key={example.id}
              type="button"
              className="example-card"
              onClick={() => onPickExample(example)}
            >
              <span className="example-q">{example.question}</span>
              <span className="example-hint">
                {[
                  example.preset.regions?.map(formatRegion).join("、"),
                  example.preset.forecast_horizon_years
                    ? `未来 ${example.preset.forecast_horizon_years} 年`
                    : null,
                  example.preset.constraints?.join("、"),
                ]
                  .filter(Boolean)
                  .join(" · ") || "点击填入研究问题"}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
