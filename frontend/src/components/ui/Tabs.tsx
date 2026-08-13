import clsx from "clsx";
import type { ReactNode } from "react";

export interface TabItem {
  key: string;
  label: string;
  count?: number;
  icon?: ReactNode;
}

export interface TabsProps {
  items: TabItem[];
  active: string;
  onChange: (key: string) => void;
  ariaLabel?: string;
}

/** Accessible tab bar (role=tablist) with optional per-tab count badges. */
export function Tabs({ items, active, onChange, ariaLabel }: TabsProps) {
  return (
    <div className="tabs" role="tablist" aria-label={ariaLabel}>
      {items.map((item) => {
        const isActive = item.key === active;
        return (
          <button
            key={item.key}
            role="tab"
            type="button"
            aria-selected={isActive}
            tabIndex={isActive ? 0 : -1}
            className={clsx("tab", isActive && "is-active")}
            onClick={() => onChange(item.key)}
          >
            {item.icon}
            {item.label}
            {typeof item.count === "number" && (
              <span className="tab-count">{item.count}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
