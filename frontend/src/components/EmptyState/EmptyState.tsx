import type { ReactNode } from "react";

export interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  tone?: "neutral" | "accent";
}

/** Neutral placeholder for legitimately empty result sets. */
export function EmptyState({
  icon,
  title,
  description,
  action,
  tone = "neutral",
}: EmptyStateProps) {
  return (
    <div className="state">
      {icon && (
        <div className={`state-icon ${tone === "accent" ? "tone-accent" : ""}`}>
          {icon}
        </div>
      )}
      <div className="state-title">{title}</div>
      {description && <div className="state-desc">{description}</div>}
      {action}
    </div>
  );
}
