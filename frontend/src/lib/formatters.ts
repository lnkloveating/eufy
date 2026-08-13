/** Small, dependency-free formatting helpers for display. */

/** Format an ISO datetime as a compact local timestamp. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

/** Format only the clock time (HH:mm:ss) — used in the activity timeline. */
export function formatClock(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

/** Format a date-only value (evidence published_at may be date or datetime). */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

/** 0–1 confidence → integer percent. */
export function toPercent(value: number): number {
  return Math.round(clamp01(value) * 100);
}

export function clamp01(value: number): number {
  if (Number.isNaN(value)) return 0;
  return Math.min(1, Math.max(0, value));
}

/** 0–100 weighted score → one decimal string. */
export function formatScore(value: number): string {
  return value.toFixed(1);
}

/** True for an externally openable evidence link. `local://` is not. */
export function isExternalUrl(url: string | null | undefined): boolean {
  if (!url) return false;
  return /^https?:\/\//i.test(url);
}

export function confidenceTone(value: number): "high" | "medium" | "low" {
  const pct = clamp01(value);
  if (pct >= 0.66) return "high";
  if (pct >= 0.4) return "medium";
  return "low";
}

/** Ordinal rank badge text, e.g. 1 → "#1". */
export function rankLabel(rank: number): string {
  return `#${rank}`;
}
