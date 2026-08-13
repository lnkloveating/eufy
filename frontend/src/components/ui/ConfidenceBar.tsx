import { confidenceTone, toPercent } from "../../lib/formatters";

export interface ConfidenceBarProps {
  value: number; // 0..1
  label?: string;
}

/** Horizontal 0–1 confidence meter, coloured by tier. */
export function ConfidenceBar({ value, label = "置信度" }: ConfidenceBarProps) {
  const pct = toPercent(value);
  const tone = confidenceTone(value);
  return (
    <div className="confbar">
      <div
        className="confbar-track"
        role="meter"
        aria-valuenow={pct}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label}
      >
        <div className={`confbar-fill conf-${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="confbar-meta">
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
    </div>
  );
}
