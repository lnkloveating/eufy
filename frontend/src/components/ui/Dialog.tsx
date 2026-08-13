import { useEffect, useId, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { Button } from "./Button";

export interface DialogProps {
  open: boolean;
  title: string;
  description?: ReactNode;
  onClose: () => void;
  children?: ReactNode;
  footer?: ReactNode;
  /** Block closing (e.g. while a request is in flight). */
  busy?: boolean;
}

/** Modal dialog rendered in a portal, with Escape-to-close and scroll lock. */
export function Dialog({
  open,
  title,
  description,
  onClose,
  children,
  footer,
  busy = false,
}: DialogProps) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onClose();
    };
    document.addEventListener("keydown", onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, busy, onClose]);

  if (!open) return null;

  return createPortal(
    <div
      className="dialog-overlay"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
    >
      <div
        className="dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className="dialog-head">
          <div className="row between" style={{ alignItems: "flex-start" }}>
            <div className="stack stack-2">
              <h2 id={titleId} style={{ fontSize: "var(--text-xl)" }}>
                {title}
              </h2>
              {description && <p className="muted">{description}</p>}
            </div>
            <Button
              variant="ghost"
              className="btn-icon"
              onClick={onClose}
              disabled={busy}
              aria-label="关闭对话框"
            >
              <X size={18} aria-hidden="true" />
            </Button>
          </div>
        </div>
        {children && <div className="dialog-body">{children}</div>}
        {footer && <div className="dialog-foot">{footer}</div>}
      </div>
    </div>,
    document.body,
  );
}
