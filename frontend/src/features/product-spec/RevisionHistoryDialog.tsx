import type { ProductRevision } from "../../types/api";
import { DISPOSITION_META, sectionLabel } from "../../lib/productWorkbench";
import { formatDateTime } from "../../lib/formatters";
import { Dialog } from "../../components/ui/Dialog";

interface Props {
  open: boolean;
  onClose: () => void;
  revisions: ProductRevision[];
}

/** Read-only audit trail of every accepted ProductSpec revision. */
export function RevisionHistoryDialog({ open, onClose, revisions }: Props) {
  const ordered = [...revisions].reverse();
  return (
    <Dialog open={open} onClose={onClose} title="修订历史 Revision history" size="xl">
      {ordered.length === 0 ? (
        <p className="subtle">尚无修订记录。接受修改建议后，这里会记录每一次版本变更。</p>
      ) : (
        <div className="stack stack-4">
          {ordered.map((revision) => (
            <div key={revision.id} className="card card-pad stack stack-3">
              <div className="row between wrap row-gap-2">
                <div className="row row-gap-2">
                  <span className="chip mono">V{revision.from_version}</span>
                  <span aria-hidden="true">→</span>
                  <span className="chip chip-accent">V{revision.to_version}</span>
                </div>
                <span className="tl-time">{formatDateTime(revision.created_at)}</span>
              </div>
              <p className="def-val">{revision.change_reason}</p>
              <div className="stack stack-2">
                <span className="opp-section-label">本次应用的修改</span>
                {revision.accepted_changes.map((change) => (
                  <div
                    key={change.suggestion_id}
                    className="card"
                    style={{ padding: "var(--space-3)", background: "var(--surface-2)" }}
                  >
                    <div className="row row-gap-2 wrap">
                      <span className="chip chip-outline">{sectionLabel(change.section)}</span>
                      <span className="badge badge-info">
                        {DISPOSITION_META[change.disposition]}
                      </span>
                    </div>
                    <p style={{ marginTop: 8, color: "var(--ink-800)" }}>
                      {change.proposed_change}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Dialog>
  );
}
