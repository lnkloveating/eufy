import type { RunStatus } from "../../types/api";

const LABELS: Record<RunStatus, string> = {
  pending: "排队中",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
};

export interface StatusBadgeProps {
  status: RunStatus;
}

/** Coloured pill reflecting the run lifecycle status. */
export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <span className={`badge badge-${status}`}>
      <span className="badge-dot" aria-hidden="true" />
      {LABELS[status]}
    </span>
  );
}
