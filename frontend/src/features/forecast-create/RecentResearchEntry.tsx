import { ChevronRight, History } from "lucide-react";
import { Link } from "react-router-dom";

import { getRecentRun } from "../../lib/recent";

export function RecentResearchEntry() {
  const recentRun = getRecentRun();

  if (!recentRun) {
    return null;
  }

  return (
    <Link to={`/runs/${recentRun}`} className="recent-entry">
      <span className="row row-gap-3" style={{ minWidth: 0 }}>
        <History size={16} aria-hidden="true" />
        <span className="stack" style={{ gap: 0, minWidth: 0 }}>
          <span className="strong">继续上次研究</span>
          <span className="mono subtle" style={{ fontSize: "var(--text-xs)" }}>
            {recentRun}
          </span>
        </span>
      </span>
      <ChevronRight size={16} aria-hidden="true" />
    </Link>
  );
}
