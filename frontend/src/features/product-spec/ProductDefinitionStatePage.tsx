import { AlertTriangle, ArrowLeft, CheckCircle2, Loader2, ScrollText } from "lucide-react";
import { Link, Navigate, useParams } from "react-router-dom";

import { ErrorState } from "../../components/ErrorState/ErrorState";
import { SkeletonText } from "../../components/LoadingSkeleton/LoadingSkeleton";
import { Button } from "../../components/ui/Button";
import { useRunProductDefinitionState, useRunResult } from "../../lib/queries";
import { CandidatesPanel } from "../candidates/CandidatesPanel";

export function ProductDefinitionStatePage() {
  const { runId } = useParams<{ runId: string }>();
  const state = useRunProductDefinitionState(runId);
  const result = useRunResult(runId, state.data?.status === "awaiting_selection");

  if (state.isLoading && !state.data) {
    return (
      <div className="page page-narrow">
        <div className="card card-pad">
          <SkeletonText lines={5} />
        </div>
      </div>
    );
  }

  if (state.isError || !state.data || !runId) {
    return (
      <div className="page page-narrow">
        <ErrorState
          title="无法加载产品定义状态"
          error={state.error}
          onRetry={() => state.refetch()}
        />
      </div>
    );
  }

  if (state.data.status === "ready" && state.data.product_id) {
    return <Navigate to={`/products/${encodeURIComponent(state.data.product_id)}`} replace />;
  }

  if (state.data.status === "awaiting_selection") {
    return (
      <div className="page">
        <div className="page-header">
          <Link to={`/runs/${encodeURIComponent(runId)}`} className="row row-gap-2 muted">
            <ArrowLeft size={15} aria-hidden="true" />
            返回多 Agent 实时研究
          </Link>
        </div>

        <div className="card card-pad stack stack-3" style={{ marginBottom: "var(--space-5)" }}>
          <div className="row row-gap-3">
            <CheckCircle2 size={26} aria-hidden="true" />
            <div className="stack stack-1">
              <span className="eyebrow">Product Definition · 候选产品</span>
              <h1 style={{ fontSize: "var(--text-2xl)" }}>研究完成，选择一个产品方向</h1>
            </div>
          </div>
          <p className="muted" style={{ fontSize: "var(--text-sm)", maxWidth: "75ch" }}>
            以下产品由当前研究任务生成。你可以查看多维评审和证据，自由选择任意候选；选择后系统才会生成最终 ProductSpec。
          </p>
          <span className="chip mono" style={{ width: "fit-content" }}>{runId}</span>
        </div>

        {result.isLoading && (
          <div className="card card-pad">
            <SkeletonText lines={8} />
          </div>
        )}
        {result.isError && (
          <ErrorState
            title="无法加载候选产品"
            error={result.error}
            onRetry={() => result.refetch()}
          />
        )}
        {result.data && (
          <CandidatesPanel
            runId={runId}
            candidates={result.data.candidates}
            evidence={result.data.evidence}
            noveltyAudit={result.data.novelty_audit}
          />
        )}
      </div>
    );
  }

  const content = STATE_CONTENT[state.data.status];
  const Icon = content.icon;
  const runPath = `/runs/${encodeURIComponent(runId)}`;

  return (
    <div className="page page-narrow">
      <div className="page-header">
        <Link to={`/runs/${encodeURIComponent(runId)}`} className="row row-gap-2 muted">
          <ArrowLeft size={15} aria-hidden="true" />
          返回当前研究
        </Link>
      </div>

      <div className="card card-pad stack stack-5" role="status" aria-live="polite">
        <div className="row row-gap-3">
          <Icon
            size={28}
            className={content.spinning ? "spin-inline" : undefined}
            aria-hidden="true"
          />
          <div className="stack stack-1">
            <span className="eyebrow">Product Definition</span>
            <h1 style={{ fontSize: "var(--text-2xl)" }}>{content.title}</h1>
          </div>
        </div>

        <p className="muted" style={{ fontSize: "var(--text-base)", maxWidth: "65ch" }}>
          {state.data.error || content.description}
        </p>

        <div className="row row-gap-3 wrap">
          <Link to={runPath}>
            <Button variant="primary">{content.action}</Button>
          </Link>
          <span className="chip mono">{runId}</span>
        </div>
      </div>
    </div>
  );
}

const STATE_CONTENT = {
  researching: {
    title: "正在研究与预测候选产品",
    description: "多 Agent 正在分析证据、机会和候选方向。研究完成后，这里会进入候选选择阶段。",
    action: "查看实时研究",
    icon: Loader2,
    spinning: true,
  },
  generating: {
    title: "正在生成产品定义",
    description: "系统正在把你选择的候选方向转换为标准 ProductSpec，完成后会自动打开结果。",
    action: "查看生成进度",
    icon: Loader2,
    spinning: true,
  },
  failed: {
    title: "产品定义尚未生成",
    description: "研究或产品定义生成失败。请返回当前研究查看错误并重新尝试。",
    action: "返回当前研究",
    icon: AlertTriangle,
    spinning: false,
  },
  ready: {
    title: "产品定义已生成",
    description: "正在打开当前研究对应的产品定义。",
    action: "返回当前研究",
    icon: ScrollText,
    spinning: false,
  },
} as const;
