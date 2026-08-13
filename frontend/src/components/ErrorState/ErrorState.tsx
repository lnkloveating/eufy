import type { ReactNode } from "react";
import { AlertTriangle, RefreshCw, WifiOff } from "lucide-react";
import { ApiError } from "../../lib/api/client";
import { Button } from "../ui/Button";

export interface ErrorStateProps {
  title?: string;
  error?: unknown;
  onRetry?: () => void;
  action?: ReactNode;
}

/** Turn any thrown error into a readable, non-alarming panel. */
export function ErrorState({ title, error, onRetry, action }: ErrorStateProps) {
  const isNetwork = error instanceof ApiError && error.isNetworkError;
  const detail =
    error instanceof ApiError
      ? error.detail
      : error instanceof Error
        ? error.message
        : error
          ? String(error)
          : undefined;

  return (
    <div className="state">
      <div className="state-icon tone-danger">
        {isNetwork ? (
          <WifiOff size={26} aria-hidden="true" />
        ) : (
          <AlertTriangle size={26} aria-hidden="true" />
        )}
      </div>
      <div className="state-title">
        {title ?? (isNetwork ? "无法连接后端服务" : "出现错误")}
      </div>
      {detail && <div className="state-desc">{detail}</div>}
      <div className="row row-gap-3" style={{ marginTop: "var(--space-2)" }}>
        {onRetry && (
          <Button
            variant="secondary"
            onClick={onRetry}
            iconStart={<RefreshCw size={15} aria-hidden="true" />}
          >
            重试
          </Button>
        )}
        {action}
      </div>
    </div>
  );
}
