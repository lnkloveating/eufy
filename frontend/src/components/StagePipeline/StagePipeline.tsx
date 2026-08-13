import clsx from "clsx";
import { Check, X } from "lucide-react";
import { STAGE_ORDER, stageIndex } from "../../lib/stageLabels";

export interface StagePipelineProps {
  /** The stage the run is currently at (a key from STAGE_ORDER). */
  activeStageKey: string;
  /** When true, the active node is rendered as a failure. */
  failed?: boolean;
}

/** Horizontal stage pipeline visualising the multi-agent workflow. */
export function StagePipeline({ activeStageKey, failed = false }: StagePipelineProps) {
  const activeIndex = stageIndex(activeStageKey);

  return (
    <div className="pipeline" role="list" aria-label="工作流阶段">
      {STAGE_ORDER.map((stage, index) => {
        const isDone = activeIndex >= 0 && index < activeIndex;
        const isActive = index === activeIndex && !failed;
        const isFailed = index === activeIndex && failed;
        const isUpcoming = activeIndex < 0 || index > activeIndex;

        return (
          <div
            key={stage.key}
            role="listitem"
            className={clsx("pipe-step", {
              "is-done": isDone,
              "is-active": isActive,
              "is-failed": isFailed,
              "is-upcoming": isUpcoming && !isFailed,
            })}
            aria-current={isActive ? "step" : undefined}
          >
            <div className="pipe-node">
              <span className="pipe-dot">
                {isDone ? (
                  <Check size={14} aria-hidden="true" />
                ) : isFailed ? (
                  <X size={14} aria-hidden="true" />
                ) : (
                  <span style={{ fontSize: 12, fontWeight: 700 }}>{index + 1}</span>
                )}
              </span>
              <span className="pipe-label">{stage.label}</span>
            </div>
            <span className="pipe-hint">{stage.hint}</span>
          </div>
        );
      })}
    </div>
  );
}
