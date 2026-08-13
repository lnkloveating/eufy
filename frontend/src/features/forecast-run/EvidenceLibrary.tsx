import { useMemo, useState } from "react";
import { Database, Search } from "lucide-react";
import type { EvidenceRecord } from "../../types/api";
import { EvidenceCard } from "../../components/EvidenceDrawer/EvidenceDrawer";
import { EmptyState } from "../../components/EmptyState/EmptyState";

export interface EvidenceLibraryProps {
  evidence: EvidenceRecord[];
}

/** Full evidence library tab with a lightweight client-side filter. */
export function EvidenceLibrary({ evidence }: EvidenceLibraryProps) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    if (!term) return evidence;
    return evidence.filter((record) =>
      [record.title, record.content, record.source_name, ...record.tags, ...record.regions]
        .join(" ")
        .toLowerCase()
        .includes(term),
    );
  }, [evidence, query]);

  if (evidence.length === 0) {
    return (
      <EmptyState
        icon={<Database size={24} aria-hidden="true" />}
        title="暂无证据记录"
        description="本次预测未选择任何本地证据。"
      />
    );
  }

  return (
    <div className="stack stack-4">
      <div className="row between wrap row-gap-3">
        <span className="muted" style={{ fontSize: "var(--text-sm)" }}>
          共 {evidence.length} 条本地证据{query && `，匹配 ${filtered.length} 条`}
        </span>
        <div className="row row-gap-2" style={{ position: "relative", minWidth: 240 }}>
          <Search
            size={15}
            aria-hidden="true"
            style={{
              position: "absolute",
              left: 12,
              top: "50%",
              transform: "translateY(-50%)",
              color: "var(--ink-400)",
            }}
          />
          <input
            className="input"
            style={{ paddingLeft: 34 }}
            placeholder="搜索标题、标签或来源…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            aria-label="搜索证据"
          />
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon={<Search size={24} aria-hidden="true" />}
          title="没有匹配的证据"
          description="尝试更换关键词。"
        />
      ) : (
        <div className="grid-cards">
          {filtered.map((record) => (
            <EvidenceCard key={record.id} record={record} />
          ))}
        </div>
      )}
    </div>
  );
}
