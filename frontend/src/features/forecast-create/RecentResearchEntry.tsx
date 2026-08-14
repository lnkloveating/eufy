import { ChevronRight, History } from "lucide-react";
import { Link } from "react-router-dom";

import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { SkeletonText } from "../../components/LoadingSkeleton/LoadingSkeleton";
import { formatDateTime } from "../../lib/formatters";
import { useRecentRuns } from "../../lib/queries";

export function RecentResearchEntry() {
  const recentRuns = useRecentRuns(3);

  if (recentRuns.isLoading) {
    return (
      <section className="stack stack-3" aria-label="最近研究">
        <div className="row row-gap-2">
          <History size={16} aria-hidden="true" />
          <span className="strong">最近研究</span>
        </div>
        <div className="card card-pad">
          <SkeletonText lines={4} />
        </div>
      </section>
    );
  }

  if (recentRuns.isError) {
    return (
      <section className="stack stack-3" aria-label="最近研究">
        <div className="row row-gap-2">
          <History size={16} aria-hidden="true" />
          <span className="strong">最近研究</span>
        </div>
        <div className="card card-pad stack stack-3">
          <span className="strong">历史研究暂时不可用</span>
          <span className="subtle" style={{ fontSize: "var(--text-sm)" }}>
            当前无法读取最近研究记录。你可以直接重新发起一轮研究。
          </span>
          <div>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            >
              重新研究
            </button>
          </div>
        </div>
      </section>
    );
  }

  if (!recentRuns.data || recentRuns.data.items.length === 0) {
    return (
      <section className="stack stack-3" aria-label="最近研究">
        <div className="row row-gap-2">
          <History size={16} aria-hidden="true" />
          <span className="strong">最近研究</span>
        </div>
        <div className="card card-pad stack stack-3">
          <span className="strong">还没有历史研究</span>
          <span className="subtle" style={{ fontSize: "var(--text-sm)" }}>
            你可以从上面的研究入口开始第一轮产品研究。
          </span>
          <div>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            >
              开始研究
            </button>
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="stack stack-3" aria-label="最近研究">
      <div className="row between wrap row-gap-2">
        <span className="row row-gap-2">
          <History size={16} aria-hidden="true" />
          <span className="strong">最近研究</span>
        </span>
        <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
          最近 {recentRuns.data.items.length} 条
        </span>
      </div>

      <div className="stack stack-3">
        {recentRuns.data.items.map((run) => (
          <Link key={run.id} to={`/runs/${run.id}`} className="recent-entry recent-entry-rich">
            <div className="stack stack-2 grow" style={{ minWidth: 0 }}>
              <div className="row between wrap row-gap-2">
                <span className="recent-entry-title">{run.question}</span>
                <StatusBadge status={run.status} />
              </div>
              <div className="row wrap row-gap-2">
                <span className="chip chip-outline">{run.category}</span>
                {run.regions.slice(0, 2).map((region) => (
                  <span className="chip" key={`${run.id}-${region}`}>
                    {region}
                  </span>
                ))}
                {run.regions.length > 2 ? (
                  <span className="chip">+{run.regions.length - 2}</span>
                ) : null}
              </div>
              <div className="row between wrap row-gap-2">
                <span className="mono subtle" style={{ fontSize: "var(--text-xs)" }}>
                  {run.id}
                </span>
                <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
                  {formatDateTime(run.created_at)}
                </span>
              </div>
            </div>

            <ChevronRight size={16} aria-hidden="true" />
          </Link>
        ))}
      </div>
    </section>
  );
}
