import { useEffect, useState, type MouseEvent } from "react";
import { ChevronRight, History, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";

import { StatusBadge } from "../../components/StatusBadge/StatusBadge";
import { SkeletonText } from "../../components/LoadingSkeleton/LoadingSkeleton";
import { Button } from "../../components/ui/Button";
import { Dialog } from "../../components/ui/Dialog";
import { useToast } from "../../components/ui/Toast";
import { formatDateTime } from "../../lib/formatters";
import { forgetRecentRun, getRecentRun } from "../../lib/recent";
import { useDeleteForecastRun, useRecentRuns } from "../../lib/queries";
import type { ForecastRunSummary } from "../../types/api";

interface ContextMenuState {
  x: number;
  y: number;
  run: ForecastRunSummary;
}

export function RecentResearchEntry() {
  const recentRuns = useRecentRuns(3);
  const toast = useToast();
  const deleteRun = useDeleteForecastRun();
  const [menu, setMenu] = useState<ContextMenuState | null>(null);
  const [confirmRun, setConfirmRun] = useState<ForecastRunSummary | null>(null);

  useEffect(() => {
    if (!menu) return;

    const close = () => setMenu(null);
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };

    document.addEventListener("mousedown", close);
    document.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menu]);

  const openMenu = (event: MouseEvent<HTMLAnchorElement>, run: ForecastRunSummary) => {
    event.preventDefault();
    setMenu({
      x: Math.max(8, Math.min(event.clientX, window.innerWidth - 180)),
      y: Math.max(8, Math.min(event.clientY, window.innerHeight - 72)),
      run,
    });
  };

  const requestDelete = () => {
    if (!menu) return;
    setConfirmRun(menu.run);
    setMenu(null);
  };

  const confirmDelete = async () => {
    if (!confirmRun) return;
    try {
      await deleteRun.mutateAsync(confirmRun.id);
      if (getRecentRun() === confirmRun.id) {
        forgetRecentRun();
      }
      toast.success("研究任务已删除", confirmRun.question);
      setConfirmRun(null);
    } catch (error) {
      const detail = error instanceof Error ? error.message : "删除失败，请稍后重试。";
      toast.error("删除研究任务失败", detail);
    }
  };

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
    <>
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
            <Link
              key={run.id}
              to={`/runs/${run.id}`}
              className="recent-entry recent-entry-rich"
              onContextMenu={(event) => openMenu(event, run)}
              aria-label={`打开研究 ${run.question}`}
            >
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

      {menu && (
        <div
          className="recent-context-menu"
          style={{ left: menu.x, top: menu.y }}
          role="menu"
          aria-label="研究任务操作"
          onMouseDown={(event) => event.stopPropagation()}
          onClick={(event) => event.stopPropagation()}
        >
          <button type="button" className="recent-context-menu-item danger" onClick={requestDelete}>
            <Trash2 size={14} aria-hidden="true" />
            删除
          </button>
        </div>
      )}

      <Dialog
        open={confirmRun !== null}
        title="删除研究任务"
        description={
          confirmRun
            ? `确认删除「${confirmRun.question}」？删除后任务、事件和关联结果都会从本地数据库中清除。`
            : undefined
        }
        onClose={() => {
          if (!deleteRun.isPending) setConfirmRun(null);
        }}
        busy={deleteRun.isPending}
        footer={
          <div className="row end row-gap-2" style={{ width: "100%" }}>
            <Button variant="ghost" onClick={() => setConfirmRun(null)} disabled={deleteRun.isPending}>
              取消
            </Button>
            <Button variant="danger" loading={deleteRun.isPending} onClick={confirmDelete}>
              删除
            </Button>
          </div>
        }
      >
        {confirmRun && (
          <div className="stack stack-2">
            <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
              这个操作不会影响其他已保存的研究记录，但会移除该 run 下的候选、产品定义与验证数据。
            </p>
            <p className="subtle" style={{ fontSize: "var(--text-xs)" }}>
              Run ID: {confirmRun.id}
            </p>
          </div>
        )}
      </Dialog>
    </>
  );
}
