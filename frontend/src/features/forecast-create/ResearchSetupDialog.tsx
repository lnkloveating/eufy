import { useEffect, useMemo, useState } from "react";
import { Check, ChevronLeft, ChevronRight, Database, SlidersHorizontal, Target } from "lucide-react";

import type { ForecastOptions } from "../../types/api";
import { Dialog } from "../../components/ui/Dialog";
import { Button } from "../../components/ui/Button";
import { AdvancedResearchSettings } from "./AdvancedResearchSettings";
import { StrategyPreferenceCard } from "./StrategyPreferenceCard";
import { SupplementalSourcesPanel } from "./SupplementalSourcesPanel";
import { ResearchBriefCard } from "./ResearchBriefCard";
import {
  areWeightsValid,
  getMissingFields,
  type ResearchBrief,
} from "./researchBrief";
import type { SupplementalResearchSources } from "./supplementalSources";

const STEPS = [
  { label: "研究范围", icon: Target },
  { label: "研究上下文", icon: Database },
  { label: "预测偏好与资料", icon: SlidersHorizontal },
  { label: "确认研究简报", icon: Check },
] as const;

export interface ResearchSetupDialogProps {
  open: boolean;
  brief: ResearchBrief;
  options: ForecastOptions;
  supplementalSources: SupplementalResearchSources;
  onBriefChange: (patch: Partial<ResearchBrief>) => void;
  onSupplementalSourcesChange: (value: SupplementalResearchSources) => void;
  onClose: () => void;
  onStart: () => void;
  onAutoResearchUnavailable: () => void;
  starting: boolean;
  canStart: boolean;
  disabledReason?: string;
}

export function ResearchSetupDialog({
  open,
  brief,
  options,
  supplementalSources,
  onBriefChange,
  onSupplementalSourcesChange,
  onClose,
  onStart,
  onAutoResearchUnavailable,
  starting,
  canStart,
  disabledReason,
}: ResearchSetupDialogProps) {
  const [step, setStep] = useState(0);
  const missingFields = getMissingFields(brief);
  const scopeValid = missingFields.length === 0;
  const weightsValid = areWeightsValid(brief.weights);
  const contextCount = useMemo(
    () =>
      Object.values(brief.research_context).filter((value) =>
        Array.isArray(value) ? value.length > 0 : Boolean(value),
      ).length,
    [brief.research_context],
  );

  useEffect(() => {
    if (open) setStep(0);
  }, [open]);

  const canVisit = (index: number) => {
    if (index === 0) return true;
    if (!scopeValid) return false;
    if (index === 3 && !weightsValid) return false;
    return true;
  };

  const next = () => {
    if (step === 0 && !scopeValid) return;
    if (step === 2 && !weightsValid) return;
    setStep((current) => Math.min(STEPS.length - 1, current + 1));
  };

  const footer = (
    <div className="setup-footer">
      <div className="setup-footer-status">
        {step === 0 && !scopeValid && `还需填写 ${missingFields.length} 个必填项`}
        {step === 1 && `${contextCount} 项上下文已补充，其余可跳过`}
        {step === 2 && (weightsValid ? "预测权重已归一化为 100%" : "预测权重总和必须为 100%")}
        {step === 3 && (disabledReason ?? `研究范围已完整 · 已补充 ${contextCount} 项上下文`)}
      </div>
      <div className="row row-gap-2">
        {step === 0 ? (
          <Button variant="ghost" onClick={onClose} disabled={starting}>取消</Button>
        ) : (
          <Button
            variant="secondary"
            onClick={() => setStep((current) => current - 1)}
            disabled={starting}
            iconStart={<ChevronLeft size={15} aria-hidden="true" />}
          >
            上一步
          </Button>
        )}
        {step < STEPS.length - 1 ? (
          <Button
            variant="primary"
            onClick={next}
            disabled={(step === 0 && !scopeValid) || (step === 2 && !weightsValid)}
            iconEnd={<ChevronRight size={15} aria-hidden="true" />}
          >
            {step === 1 ? "继续" : "下一步"}
          </Button>
        ) : (
          <Button
            variant="primary"
            size="lg"
            onClick={onStart}
            loading={starting}
            disabled={!canStart || !scopeValid || !weightsValid || starting}
          >
            {starting ? "正在启动深度研究…" : "确认并开始研究"}
          </Button>
        )}
      </div>
    </div>
  );

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="配置深度研究"
      footer={footer}
      busy={starting}
      size="xl"
    >
      <nav className="setup-steps" aria-label="研究配置步骤">
        {STEPS.map(({ label, icon: Icon }, index) => {
          const available = canVisit(index);
          return (
            <button
              key={label}
              type="button"
              className={`setup-step ${step === index ? "is-active" : ""} ${step > index ? "is-done" : ""}`}
              onClick={() => available && setStep(index)}
              disabled={!available || starting}
              aria-current={step === index ? "step" : undefined}
            >
              <span className="setup-step-index">{step > index ? <Check size={14} /> : <Icon size={14} />}</span>
              <span>{label}</span>
            </button>
          );
        })}
      </nav>

      <div className="setup-content">
        {step === 0 && (
          <AdvancedResearchSettings
            brief={brief}
            options={options}
            onChange={onBriefChange}
            section="scope"
          />
        )}
        {step === 1 && (
          <AdvancedResearchSettings
            brief={brief}
            options={options}
            onChange={onBriefChange}
            section="context"
          />
        )}
        {step === 2 && (
          <div className="stack stack-5">
            <StrategyPreferenceCard
              brief={brief}
              presets={options.strategy_presets}
              onChange={onBriefChange}
            />
            <SupplementalSourcesPanel
              value={supplementalSources}
              onChange={onSupplementalSourcesChange}
              onAutoResearchUnavailable={onAutoResearchUnavailable}
            />
          </div>
        )}
        {step === 3 && (
          <ResearchBriefCard
            brief={brief}
            regionLabel={(region) => region}
            onEdit={() => setStep(0)}
            onStart={onStart}
            starting={starting}
            canStart={canStart}
            supplementalSources={supplementalSources}
            embedded
          />
        )}
      </div>
    </Dialog>
  );
}
