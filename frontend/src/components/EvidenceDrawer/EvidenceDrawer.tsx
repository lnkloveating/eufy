import { ExternalLink, FileText, ChevronLeft, ChevronRight, Lock, ShieldCheck } from "lucide-react";
import type { EvidenceRecord } from "../../types/api";
import { formatDate, isExternalUrl, toPercent } from "../../lib/formatters";
import { Drawer } from "../ui/Drawer";
import { EmptyState } from "../EmptyState/EmptyState";

export interface EvidenceCardProps {
  record: EvidenceRecord;
  carousel?: {
    index: number;
    total: number;
    onPrevious: () => void;
    onNext: () => void;
  };
}

/** A single evidence record rendered as a card. */
export function EvidenceCard({ record, carousel }: EvidenceCardProps) {
  const external = isExternalUrl(record.source_url);
  const credibility = toPercent(record.credibility);

  return (
    <article className="card card-pad stack stack-3">
      {carousel && (
        <div className="row between wrap row-gap-2 evidence-carousel-head">
          <div className="row row-gap-2 wrap evidence-carousel-title" style={{ minWidth: 0 }}>
            <span className="chip mono">{record.id}</span>
            {carousel.total > 1 && (
              <span className="chip chip-outline">
                {carousel.index + 1} / {carousel.total}
              </span>
            )}
          </div>
          <div className="row row-gap-2 evidence-carousel-actions">
            <button
              type="button"
              className="carousel-arrow"
              onClick={carousel.onPrevious}
              disabled={carousel.total <= 1}
              aria-label="上一条证据"
              title="上一条证据"
            >
              <ChevronLeft size={16} aria-hidden="true" />
            </button>
            <button
              type="button"
              className="carousel-arrow"
              onClick={carousel.onNext}
              disabled={carousel.total <= 1}
              aria-label="下一条证据"
              title="下一条证据"
            >
              <ChevronRight size={16} aria-hidden="true" />
            </button>
          </div>
        </div>
      )}

      <div className="row between" style={{ alignItems: "flex-start", gap: "var(--space-3)" }}>
        <div className="stack stack-2" style={{ minWidth: 0 }}>
          <div className="row row-gap-2 wrap">
            <span className="chip chip-accent">{record.evidence_type}</span>
            <span className="chip">{record.layer}</span>
            <span className={`chip ${record.claim_status === "hypothesis" ? "chip-outline" : ""}`}>
              {record.claim_status === "hypothesis" ? "待验证假设" : record.claim_status === "verified" ? "已验证资料" : record.claim_status}
            </span>
            <span className="chip mono">{record.id}</span>
          </div>
          <h4 style={{ fontSize: "var(--text-md)" }}>{record.title}</h4>
        </div>
        <div
          className="stack"
          style={{ alignItems: "flex-end", gap: 2, flexShrink: 0, minWidth: 96 }}
        >
          <span className="meta-label">可信度</span>
          <div className="row row-gap-2">
            <ShieldCheck size={14} className="muted" aria-hidden="true" />
            <span className="strong" style={{ fontVariantNumeric: "tabular-nums" }}>
              {credibility}%
            </span>
          </div>
        </div>
      </div>

      <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
        {record.content}
      </p>

      {record.tags.length > 0 && (
        <div className="taglist">
          {record.tags.map((tag) => (
            <span className="chip chip-outline" key={tag}>
              {tag}
            </span>
          ))}
        </div>
      )}

      <div className="hr" />

      <div className="row between wrap row-gap-3" style={{ fontSize: "var(--text-xs)" }}>
        <div className="row row-gap-2 muted wrap">
          {record.regions.map((region) => (
            <span key={region} className="chip">
              {region}
            </span>
          ))}
        </div>
        <div className="row row-gap-3 muted">
          <span>发布：{formatDate(record.published_at)}</span>
          {external ? (
            <a
              className="row row-gap-2"
              href={record.source_url}
              target="_blank"
              rel="noreferrer noopener"
            >
              <ExternalLink size={13} aria-hidden="true" />
              {record.source_name}
            </a>
          ) : (
            <span
              className="row row-gap-2"
              title="本地研究假设，非公开网页链接"
            >
              <Lock size={13} aria-hidden="true" />
              本地研究假设 · {record.source_name}
            </span>
          )}
        </div>
      </div>
    </article>
  );
}

export interface EvidenceDrawerProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  records: EvidenceRecord[];
}

/** Slide-over showing a set of cited evidence records. */
export function EvidenceDrawer({
  open,
  onClose,
  title = "引用证据",
  records,
}: EvidenceDrawerProps) {
  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={title}
      subtitle={`${records.length} 条证据`}
    >
      {records.length === 0 ? (
        <EmptyState
          icon={<FileText size={24} aria-hidden="true" />}
          title="暂无关联证据"
          description="该条目未引用任何本地证据记录。"
        />
      ) : (
        <div className="stack stack-4">
          {records.map((record) => (
            <EvidenceCard key={record.id} record={record} />
          ))}
        </div>
      )}
    </Drawer>
  );
}
