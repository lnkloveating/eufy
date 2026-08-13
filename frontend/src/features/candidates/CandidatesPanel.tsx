import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Award,
  Boxes,
  LayoutGrid,
  Table2,
} from "lucide-react";

import type {
  CandidateNoveltyAssessment,
  EvidenceRecord,
  NoveltyAudit,
  RankedCandidate,
} from "../../types/api";
import { SCORE_DIMENSIONS } from "../../types/api";
import { getDimensionLabel } from "../../lib/agentLabels";
import { orderForDisplay, topCandidate } from "../../lib/candidates";
import { formatScore } from "../../lib/formatters";
import { rememberProduct } from "../../lib/recent";
import { ApiError } from "../../lib/api/client";
import { useCreateSelection } from "../../lib/queries";
import { Button } from "../../components/ui/Button";
import { ScoreRadar, type RadarSeries } from "../../components/ScoreRadar/ScoreRadar";
import { EmptyState } from "../../components/EmptyState/EmptyState";
import { useToast } from "../../components/ui/Toast";
import { CandidateDetailDrawer } from "./CandidateDetailDrawer";
import { SelectCandidateDialog } from "./SelectCandidateDialog";

const SERIES_COLORS = [
  "var(--accent)",
  "#7c5cff",
  "#f59e0b",
  "#ec4899",
  "#10b981",
  "#3b82f6",
  "#ef4444",
  "#14b8a6",
  "#a855f7",
  "#eab308",
];

function colorAt(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length] ?? "var(--accent)";
}

export interface CandidatesPanelProps {
  runId: string;
  candidates: RankedCandidate[];
  evidence: EvidenceRecord[];
  noveltyAudit: NoveltyAudit | null;
}

/** Product candidate comparison: cards, compare table, radar, human selection. */
export function CandidatesPanel({ runId, candidates, noveltyAudit }: CandidatesPanelProps) {
  const navigate = useNavigate();
  const toast = useToast();
  const selection = useCreateSelection(runId);

  const [view, setView] = useState<"cards" | "compare">("cards");
  const [detail, setDetail] = useState<RankedCandidate | null>(null);
  const [selecting, setSelecting] = useState<RankedCandidate | null>(null);
  const [selectError, setSelectError] = useState<string | null>(null);

  if (candidates.length === 0) {
    return (
      <EmptyState
        icon={<Boxes size={24} aria-hidden="true" />}
        title="暂无产品候选"
        description="预测完成后，AI 生成的候选产品会显示在这里。"
      />
    );
  }

  const ordered = orderForDisplay(candidates);
  const best = topCandidate(candidates);
  const noveltyByCandidate = new Map(
    (noveltyAudit?.assessments ?? []).map((item) => [item.candidate_id, item]),
  );

  const openSelect = (ranked: RankedCandidate) => {
    setSelectError(null);
    setSelecting(ranked);
    setDetail(null);
  };

  const handleConfirm = async (input: {
    selectionReason: string | null;
    requestedChanges: string[];
  }) => {
    if (!selecting || selection.isPending) return;
    setSelectError(null);
    try {
      const product = await selection.mutateAsync({
        candidate_id: selecting.candidate.id,
        selection_reason: input.selectionReason,
        requested_changes: input.requestedChanges,
        idempotency_key: `selection:${runId}:${selecting.candidate.id}`,
      });
      rememberProduct(product.id);
      toast.success("ProductSpec 已生成", "正在打开标准产品定义…");
      navigate(`/products/${product.id}`);
    } catch (error) {
      const detail =
        error instanceof ApiError ? error.detail : "生成 ProductSpec 失败，请稍后重试。";
      setSelectError(detail);
      toast.error("生成 ProductSpec 失败", detail);
    }
  };

  return (
    <div className="stack stack-5">
      <div className="row between wrap row-gap-3">
        <p className="muted" style={{ fontSize: "var(--text-sm)", maxWidth: "60ch" }}>
          以下候选由 Product Architect 依据机会与证据动态生成，并经过五个维度独立盲评。
          你可以自由选择任意候选（包括排名最后的方向），系统不会替你决定。
        </p>
        <div className="row" role="group" aria-label="视图切换" style={{ gap: 2 }}>
          <Button
            size="sm"
            variant={view === "cards" ? "dark" : "ghost"}
            onClick={() => setView("cards")}
            iconStart={<LayoutGrid size={15} aria-hidden="true" />}
          >
            卡片视图
          </Button>
          <Button
            size="sm"
            variant={view === "compare" ? "dark" : "ghost"}
            onClick={() => setView("compare")}
            iconStart={<Table2 size={15} aria-hidden="true" />}
          >
            对比视图
          </Button>
        </div>
      </div>

      {view === "cards" ? (
        <div className="grid-cards">
          {ordered.map((ranked) => (
            <CandidateCard
              key={ranked.candidate.id}
              ranked={ranked}
              novelty={noveltyByCandidate.get(ranked.candidate.id)}
              isTop={best?.candidate.id === ranked.candidate.id}
              onDetail={() => setDetail(ranked)}
              onSelect={() => openSelect(ranked)}
            />
          ))}
        </div>
      ) : (
        <CompareView ordered={ordered} best={best} onSelect={openSelect} onDetail={setDetail} />
      )}

      <CandidateDetailDrawer
        ranked={detail}
        novelty={detail ? noveltyByCandidate.get(detail.candidate.id) : undefined}
        onClose={() => setDetail(null)}
        onSelect={openSelect}
      />

      <SelectCandidateDialog
        ranked={selecting}
        pending={selection.isPending}
        error={selectError}
        onClose={() => {
          if (selection.isPending) return;
          setSelecting(null);
          setSelectError(null);
        }}
        onConfirm={handleConfirm}
      />
    </div>
  );
}

interface CandidateCardProps {
  ranked: RankedCandidate;
  novelty?: CandidateNoveltyAssessment;
  isTop: boolean;
  onDetail: () => void;
  onSelect: () => void;
}

function CandidateCard({ ranked, novelty, isTop, onDetail, onSelect }: CandidateCardProps) {
  const { candidate, dimension_scores, weighted_score, rank } = ranked;
  return (
    <article className={`card cand-card ${isTop ? "is-top" : ""}`}>
      <div className="row between" style={{ alignItems: "flex-start" }}>
        <div className="row row-gap-3">
          <span className="cand-rank">{rank}</span>
          {isTop && (
            <span className="chip chip-accent">
              <Award size={12} aria-hidden="true" /> AI 综合评分最高 · 推荐
            </span>
          )}
        </div>
        <div className="cand-score-box">
          <div className="cand-score">{formatScore(weighted_score)}</div>
          <div className="cand-score-label">加权综合分</div>
        </div>
      </div>

      <div className="stack stack-2">
        <h3 className="cand-name">{candidate.name}</h3>
        <p className="cand-tagline">{candidate.tagline}</p>
        {novelty && (
          <span className="chip chip-accent" style={{ width: "fit-content" }}>
            创新门槛已通过 · {noveltyLabel(novelty.classification)} · 与现有能力重合 {Math.round(novelty.overlap_ratio * 100)}%
          </span>
        )}
      </div>

      <div className="dimscore-row">
        {SCORE_DIMENSIONS.map((dimension) => (
          <div className="dimscore" key={dimension}>
            <span className="dimscore-name">{getDimensionLabel(dimension)}</span>
            <span className="dimscore-track">
              <span
                className="dimscore-fill"
                style={{ width: `${dimension_scores[dimension] ?? 0}%` }}
              />
            </span>
            <span className="dimscore-val">
              {formatScore(dimension_scores[dimension] ?? 0)}
            </span>
          </div>
        ))}
      </div>

      <div className="deflist">
        <MiniDef label="核心问题" value={candidate.core_problem} />
        <MiniDef label="AI 原生机制" value={candidate.ai_native_mechanism} />
        <MiniDef label="形态 / 价格" value={`${candidate.form_factor} · ${candidate.estimated_price_range}`} />
      </div>

      {candidate.differentiators.length > 0 && (
        <div className="taglist">
          {candidate.differentiators.slice(0, 3).map((item) => (
            <span className="chip chip-outline" key={item}>
              {item}
            </span>
          ))}
        </div>
      )}

      <div className="row row-gap-3" style={{ marginTop: "auto" }}>
        <Button variant="secondary" onClick={onDetail} className="grow">
          查看详情与评审
        </Button>
        <Button variant="primary" onClick={onSelect} className="grow">
          选择该方向
        </Button>
      </div>
    </article>
  );
}

function noveltyLabel(classification: CandidateNoveltyAssessment["classification"]): string {
  const labels = {
    existing_equivalent: "现有能力等价",
    feature_extension: "功能升级",
    adjacent_innovation: "邻近创新",
    new_product_category: "新品类",
  } as const;
  return labels[classification];
}

function MiniDef({ label, value }: { label: string; value: string }) {
  return (
    <div className="def-row" style={{ gridTemplateColumns: "92px 1fr" }}>
      <span className="def-key">{label}</span>
      <span className="def-val" style={{ fontSize: "var(--text-sm)" }}>
        {value}
      </span>
    </div>
  );
}

interface CompareViewProps {
  ordered: RankedCandidate[];
  best: RankedCandidate | undefined;
  onSelect: (ranked: RankedCandidate) => void;
  onDetail: (ranked: RankedCandidate) => void;
}

function CompareView({ ordered, best, onSelect, onDetail }: CompareViewProps) {
  const series: RadarSeries[] = ordered.map((ranked, index) => {
    const scores: Record<string, number> = {};
    for (const dimension of SCORE_DIMENSIONS) {
      scores[dimension] = ranked.dimension_scores[dimension] ?? 0;
    }
    return { label: ranked.candidate.name, color: colorAt(index), scores };
  });

  const isBest = (ranked: RankedCandidate) => best?.candidate.id === ranked.candidate.id;

  return (
    <div className="stack stack-5">
      <div className="card card-pad" style={{ display: "grid", placeItems: "center" }}>
        <ScoreRadar series={series} size={340} />
      </div>

      <div className="card compare-wrap">
        <table className="compare">
          <thead>
            <tr>
              <th className="row-label">对比维度</th>
              {ordered.map((ranked) => (
                <th key={ranked.candidate.id} className={isBest(ranked) ? "col-top" : ""}>
                  <div className="stack stack-2">
                    <div className="row row-gap-2">
                      <span className="cand-rank" style={{ minWidth: 26, height: 26, fontSize: 13 }}>
                        {ranked.rank}
                      </span>
                      <span className="strong">{ranked.candidate.name}</span>
                    </div>
                    {isBest(ranked) && (
                      <span className="chip chip-accent" style={{ width: "fit-content" }}>
                        <Award size={11} aria-hidden="true" /> 推荐
                      </span>
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="row-label">加权综合分</td>
              {ordered.map((ranked) => (
                <td
                  key={ranked.candidate.id}
                  className={`cell-num ${isBest(ranked) ? "col-top" : ""}`}
                >
                  {formatScore(ranked.weighted_score)}
                </td>
              ))}
            </tr>
            {SCORE_DIMENSIONS.map((dimension) => (
              <tr key={dimension}>
                <td className="row-label">{getDimensionLabel(dimension)}</td>
                {ordered.map((ranked) => (
                  <td
                    key={ranked.candidate.id}
                    className={`cell-num ${isBest(ranked) ? "col-top" : ""}`}
                  >
                    {formatScore(ranked.dimension_scores[dimension] ?? 0)}
                  </td>
                ))}
              </tr>
            ))}
            <CompareRow
              label="标语"
              ordered={ordered}
              isBest={isBest}
              render={(r) => r.candidate.tagline}
            />
            <CompareRow
              label="形态"
              ordered={ordered}
              isBest={isBest}
              render={(r) => r.candidate.form_factor}
            />
            <CompareRow
              label="AI 原生机制"
              ordered={ordered}
              isBest={isBest}
              render={(r) => r.candidate.ai_native_mechanism}
            />
            <CompareRow
              label="预估价格"
              ordered={ordered}
              isBest={isBest}
              render={(r) => r.candidate.estimated_price_range}
            />
            <CompareRow
              label="核心问题"
              ordered={ordered}
              isBest={isBest}
              render={(r) => r.candidate.core_problem}
            />
            <tr>
              <td className="row-label">操作</td>
              {ordered.map((ranked) => (
                <td key={ranked.candidate.id} className={isBest(ranked) ? "col-top" : ""}>
                  <div className="stack stack-2">
                    <Button size="sm" variant="secondary" onClick={() => onDetail(ranked)}>
                      详情
                    </Button>
                    <Button size="sm" variant="primary" onClick={() => onSelect(ranked)}>
                      选择
                    </Button>
                  </div>
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CompareRow({
  label,
  ordered,
  isBest,
  render,
}: {
  label: string;
  ordered: RankedCandidate[];
  isBest: (ranked: RankedCandidate) => boolean;
  render: (ranked: RankedCandidate) => string;
}) {
  return (
    <tr>
      <td className="row-label">{label}</td>
      {ordered.map((ranked) => (
        <td key={ranked.candidate.id} className={isBest(ranked) ? "col-top" : ""}>
          {render(ranked)}
        </td>
      ))}
    </tr>
  );
}
