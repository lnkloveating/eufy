import clsx from "clsx";
import { Check, Loader2, X } from "lucide-react";
import { STAGE_ORDER, stageIndex } from "../../lib/stageLabels";

export interface ResearchStageViewProps {
  /** The stage the run is currently at (a key from STAGE_ORDER). */
  activeStageKey: string;
  /** When true, the active node is rendered as a failure. */
  failed?: boolean;
}

/** Left-rail vertical research pipeline (Deep Research style). */
export function ResearchStageView({ activeStageKey, failed = false }: ResearchStageViewProps) {
  const activeIndex = stageIndex(activeStageKey);
  const done = activeIndex < 0 ? 0 : Math.min(activeIndex, STAGE_ORDER.length);

  return (
    <div className="panel">
      <div className="panel-head">
        <span className="panel-title">研究流水线</span>
        <span className="chip">
          {done}/{STAGE_ORDER.length}
        </span>
      </div>
      <div className="panel-body">
        <ol className="vstage" aria-label="研究流水线阶段">
          {STAGE_ORDER.map((stage, index) => {
            const isDone = activeIndex >= 0 && index < activeIndex;
            const isActive = index === activeIndex && !failed;
            const isFailed = index === activeIndex && failed;
            const isUpcoming = activeIndex < 0 || index > activeIndex;

            return (
              <li
                key={stage.key}
                className={clsx("vstage-step", {
                  "is-done": isDone,
                  "is-active": isActive,
                  "is-failed": isFailed,
                  "is-upcoming": isUpcoming && !isFailed,
                })}
                aria-current={isActive ? "step" : undefined}
              >
                <span className="vstage-rail">
                  <span className="vstage-dot">
                    {isDone ? (
                      <Check size={13} aria-hidden="true" />
                    ) : isFailed ? (
                      <X size={13} aria-hidden="true" />
                    ) : isActive ? (
                      <Loader2 size={13} className="spin-inline" aria-hidden="true" />
                    ) : (
                      <span style={{ fontSize: 11, fontWeight: 700 }}>{index + 1}</span>
                    )}
                  </span>
                  {index < STAGE_ORDER.length - 1 && <span className="vstage-line" />}
                </span>
                <span className="vstage-body">
                  <span className="vstage-label">{stage.label}</span>
                  <span className="vstage-hint">{stage.hint}</span>
                </span>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
