import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  CircuitBoard,
  History,
  MapPin,
  Network,
  ShieldCheck,
  Target,
} from "lucide-react";

import type { ProductSpec, RiskItem } from "../../types/api";
import { useProduct, useProductRevisions } from "../../lib/queries";
import { formatDateTime } from "../../lib/formatters";
import { rememberRun } from "../../lib/recent";
import { DEFINITION_STATUS_META } from "../../lib/productWorkbench";
import { ApiError } from "../../lib/api/client";
import { EmptyState } from "../../components/EmptyState/EmptyState";
import { ErrorState } from "../../components/ErrorState/ErrorState";
import { Skeleton, SkeletonText } from "../../components/LoadingSkeleton/LoadingSkeleton";
import { Button } from "../../components/ui/Button";
import { ProductDefinitionCopilot } from "./ProductDefinitionCopilot";
import { DefinitionReadinessPanel } from "./DefinitionReadinessPanel";
import { RevisionHistoryDialog } from "./RevisionHistoryDialog";

type SpecPageKey = "overview" | "design" | "market" | "workbench";

type TocItem = {
  label: string;
  page: SpecPageKey;
  anchor: string;
};

type TocGroup = {
  label: string;
  page: SpecPageKey;
  items: readonly TocItem[];
};

const PAGE_BY_ANCHOR: Record<string, SpecPageKey> = {
  "sec-overview": "overview",
  "sec-core": "overview",
  "sec-implementation": "design",
  "sec-delta": "design",
  "sec-lifecycle": "design",
  "sec-market": "market",
  "sec-risks": "market",
  "sec-copilot": "workbench",
  "sec-readiness": "workbench",
};

const TOC_GROUPS: readonly TocGroup[] = [
  {
    label: "概览",
    page: "overview",
    items: [
      { label: "产品概览", page: "overview", anchor: "sec-overview" },
      { label: "核心定义", page: "overview", anchor: "sec-core" },
    ],
  },
  {
    label: "设计",
    page: "design",
    items: [
      { label: "实现方式", page: "design", anchor: "sec-implementation" },
      { label: "能力增量", page: "design", anchor: "sec-delta" },
      { label: "生态与隐私", page: "design", anchor: "sec-lifecycle" },
    ],
  },
  {
    label: "市场与验证",
    page: "market",
    items: [
      { label: "市场与商业", page: "market", anchor: "sec-market" },
      { label: "风险与假设", page: "market", anchor: "sec-risks" },
    ],
  },
  {
    label: "工作台",
    page: "workbench",
    items: [
      { label: "产品定义 Copilot", page: "workbench", anchor: "sec-copilot" },
      { label: "确认准备度", page: "workbench", anchor: "sec-readiness" },
    ],
  },
];

export function ProductSpecPage() {
  const { productId } = useParams<{ productId: string }>();
  const product = useProduct(productId);

  useEffect(() => {
    if (product.data?.source_run_id) rememberRun(product.data.source_run_id);
  }, [product.data?.source_run_id]);

  if (product.isLoading && !product.data) {
    return (
      <div className="page page-narrow">
        <Skeleton width="50%" height={34} radius={8} />
        <div style={{ height: 24 }} />
        <div className="card card-pad">
          <SkeletonText lines={8} />
        </div>
      </div>
    );
  }

  if (product.isError || !product.data) {
    const notFound = product.error instanceof ApiError && product.error.isNotFound;
    return (
      <div className="page page-narrow">
        {notFound ? (
          <EmptyState
            icon={<AlertTriangle size={26} aria-hidden="true" />}
            title="产品定义不存在"
            description={`未找到产品 ${productId}，它可能尚未生成。`}
            action={
              <Link to="/">
                <Button variant="primary">返回研究首页</Button>
              </Link>
            }
          />
        ) : (
          <ErrorState
            title="无法加载产品定义"
            error={product.error}
            onRetry={() => product.refetch()}
          />
        )}
      </div>
    );
  }

  return <ProductSpecView spec={product.data} />;
}

function ProductSpecView({ spec }: { spec: ProductSpec }) {
  const [draft, setDraft] = useState("");
  const [historyOpen, setHistoryOpen] = useState(false);
  const [activePage, setActivePage] = useState<SpecPageKey>("overview");
  const [activeAnchor, setActiveAnchor] = useState<string>("sec-overview");
  const mainRef = useRef<HTMLDivElement | null>(null);
  const revisions = useProductRevisions(spec.id);
  const statusMeta = DEFINITION_STATUS_META[spec.definition_status ?? "draft"];

  const scrollToSection = (anchor: string, page?: SpecPageKey) => {
    const nextPage = page ?? PAGE_BY_ANCHOR[anchor] ?? "overview";
    setActivePage(nextPage);
    setActiveAnchor(anchor);
    window.setTimeout(() => {
      document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
  };

  const askRecommended = (question: string) => {
    setDraft(question);
    setActivePage("workbench");
    setActiveAnchor("sec-copilot");
  };

  useEffect(() => {
    mainRef.current?.scrollTo({ top: 0, behavior: "smooth" });
  }, [activePage]);

  return (
    <div className="page spec-page">
      <div className="spec-workbench">
        <SpecToc
          activePage={activePage}
          activeAnchor={activeAnchor}
          onNavigate={(page, anchor) => scrollToSection(anchor, page)}
        />

        <div ref={mainRef} className="spec-main stack stack-5">
          <div key={activePage} className="spec-page-panel">
            {activePage === "overview" && (
              <>
              <section className="hero" id="sec-overview">
                <div className="row row-gap-2 wrap spec-hero-tags">
                  <span className="chip chip-accent">{spec.category}</span>
                  <span className="chip" style={{ background: "rgba(255,255,255,0.1)", color: "#cdd9e8" }}>
                    版本 {spec.version}
                  </span>
                  <span className="chip mono" style={{ background: "rgba(255,255,255,0.08)", color: "#9fb2cc" }}>
                    {spec.id}
                  </span>
                </div>
                <h1>{spec.name}</h1>
                <p className="hero-sub" style={{ maxWidth: "72ch" }}>
                  {spec.one_sentence_definition}
                </p>
                <div className="hero-health">
                  <div className="hero-stat">
                    <span className="hero-stat-label">目标用户</span>
                    <span className="hero-stat-value" style={{ fontSize: "var(--text-base)" }}>
                      {spec.target_users.join("、")}
                    </span>
                  </div>
                  <div className="hero-stat">
                    <span className="hero-stat-label">目标地区</span>
                    <span className="hero-stat-value" style={{ fontSize: "var(--text-base)" }}>
                      {spec.target_regions.join("、")}
                    </span>
                  </div>
                  <div className="hero-stat">
                    <span className="hero-stat-label">生成时间</span>
                    <span className="hero-stat-value" style={{ fontSize: "var(--text-base)" }}>
                      {formatDateTime(spec.created_at)}
                    </span>
                  </div>
                </div>
              </section>

              <div className="card card-pad spec-toolbar">
                <div className="row row-gap-2 wrap" style={{ minWidth: 0 }}>
                  <span className={`badge ${statusMeta.badge}`}>{statusMeta.label}</span>
                  {spec.last_change_reason && (
                    <span className="muted" style={{ fontSize: "var(--text-sm)" }}>
                      最近修改：{spec.last_change_reason}
                    </span>
                  )}
                </div>
                <Button
                  variant="secondary"
                  className="btn-sm"
                  onClick={() => setHistoryOpen(true)}
                  iconStart={<History size={14} aria-hidden="true" />}
                >
                  修订历史 ({revisions.data?.length ?? 0})
                </Button>
              </div>

              {spec.human_selection_reason && (
                <div className="alert alert-info" role="note">
                  <Target size={18} className="alert-icon" aria-hidden="true" />
                  <div className="alert-body">
                    <span className="alert-title">人工选择理由 Human selection reason</span>
                    <span>{spec.human_selection_reason}</span>
                  </div>
                </div>
              )}

              <Section
                id="sec-core"
                icon={<Target size={16} />}
                title="核心定义"
              >
                <div className="deflist">
                  <Def label="核心问题" value={spec.core_problem} />
                  <Def label="价值主张" value={spec.value_proposition} />
                  <Def label="产品形态" value={spec.form_factor} />
                </div>
              </Section>
              </>
            )}

            {activePage === "design" && (
              <>
              <Section
                id="sec-implementation"
                icon={<CircuitBoard size={16} />}
                title="实现方式"
              >
                <div className="spec-grid">
                  <div className="stack stack-2">
                    <span className="opp-section-label">硬件架构</span>
                    <Bullets items={spec.hardware_architecture} />
                  </div>
                  <div className="stack stack-2">
                    <span className="opp-section-label">AI 能力</span>
                    <Bullets items={spec.ai_capabilities} />
                  </div>
                </div>
                <div className="spec-muted-note">
                  <strong>AI 决策边界：</strong>
                  {spec.ai_decision_boundary}
                </div>
              </Section>

              <Section
                id="sec-delta"
                icon={<ShieldCheck size={16} />}
                title="能力增量"
              >
                <div className="deflist">
                  <Def label="创新探索向量" value={spec.capability_delta?.innovation_vector ?? "—"} />
                  <Def
                    label="为什么今天还没有"
                    value={spec.capability_delta?.why_not_available_today ?? "—"}
                  />
                  <Def
                    label="硬件 / 系统增量"
                    value={spec.capability_delta?.hardware_or_system_delta ?? "—"}
                  />
                </div>
                {spec.capability_delta && (
                  <div className="spec-grid">
                    <div className="stack stack-2">
                      <span className="opp-section-label">今天已有的相近能力</span>
                      <Bullets items={spec.capability_delta.today_equivalents} />
                    </div>
                    <div className="stack stack-2">
                      <span className="opp-section-label">真正新增的能力</span>
                      <Bullets items={spec.capability_delta.new_capabilities} />
                    </div>
                  </div>
                )}
              </Section>

              <Section
                id="sec-lifecycle"
                icon={<Network size={16} />}
                title="生态与隐私"
              >
                <div className="spec-grid">
                  <div className="stack stack-2">
                    <span className="opp-section-label">用户旅程</span>
                    <Bullets items={spec.user_journeys} />
                  </div>
                  <div className="stack stack-2">
                    <span className="opp-section-label">eufy 生态关系</span>
                    <Bullets items={spec.ecosystem_relationships} />
                  </div>
                </div>
                <div className="stack stack-2">
                  <span className="opp-section-label">隐私原则</span>
                  <Bullets items={spec.privacy_principles} />
                </div>
              </Section>
              </>
            )}

            {activePage === "market" && (
              <>
              <Section
                id="sec-market"
                icon={<MapPin size={16} />}
                title="市场与商业"
              >
                {spec.regional_fit.length > 0 && (
                  <div className="grid-cards">
                    {spec.regional_fit.map((fit) => (
                      <div className="card card-pad stack stack-3" key={fit.region}>
                        <div className="row between">
                          <strong>{fit.region}</strong>
                          <span className="chip chip-accent">
                            置信度 {Math.round(fit.confidence * 100)}%
                          </span>
                        </div>
                        <div>
                          <span className="opp-section-label">适配理由</span>
                          <Bullets items={fit.fit_reasons} />
                        </div>
                        <div>
                          <span className="opp-section-label">必要调整</span>
                          <Bullets items={fit.required_adaptations} />
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div className="spec-grid" style={{ marginTop: "var(--space-4)" }}>
                  <div className="stack stack-2">
                    <span className="opp-section-label">最接近的现有方案</span>
                    <Bullets items={spec.competitive_positioning.closest_alternatives} />
                  </div>
                  <div className="stack stack-2">
                    <span className="opp-section-label">可防御差异</span>
                    <Bullets items={spec.competitive_positioning.defensible_differences} />
                  </div>
                </div>

                <div className="spec-muted-note" style={{ marginTop: "var(--space-4)" }}>
                  <strong>为什么不是竞品功能拼接：</strong>
                  {spec.competitive_positioning.non_copycat_rationale}
                </div>

                <div className="spec-grid" style={{ marginTop: "var(--space-4)" }}>
                  <div className="stack stack-2">
                    <span className="opp-section-label">竞品跟进风险</span>
                    <Bullets items={spec.competitive_positioning.copycat_risks} />
                  </div>
                  <div className="stack stack-2">
                    <span className="opp-section-label">后续必须验证</span>
                    <Bullets items={spec.competitive_positioning.validation_questions} />
                  </div>
                </div>

                <div className="deflist" style={{ marginTop: "var(--space-4)" }}>
                  <Def label="硬件收入" value={spec.business_model.hardware_revenue} />
                  {spec.business_model.recurring_revenue && (
                    <Def label="持续性收入" value={spec.business_model.recurring_revenue} />
                  )}
                </div>
                <div className="spec-grid" style={{ marginTop: "var(--space-4)" }}>
                  <div className="stack stack-2">
                    <span className="opp-section-label">生态带动</span>
                    <Bullets items={spec.business_model.ecosystem_pull_through} />
                  </div>
                  <div className="stack stack-2">
                    <span className="opp-section-label">成本驱动</span>
                    <Bullets items={spec.business_model.cost_drivers} />
                  </div>
                </div>
              </Section>

              <Section
                id="sec-risks"
                icon={<AlertTriangle size={16} />}
                title="风险与假设"
                tone="danger"
              >
                <div className="stack stack-3">
                  {spec.risks.map((risk, index) => (
                    <RiskCard key={index} risk={risk} />
                  ))}
                </div>
                <div className="spec-grid" style={{ marginTop: "var(--space-4)" }}>
                  <div className="stack stack-2">
                    <span className="opp-section-label">关键假设</span>
                    <Bullets items={spec.key_assumptions} />
                  </div>
                  <div className="stack stack-2">
                    <span className="opp-section-label">Kill Criteria</span>
                    <Bullets items={spec.kill_criteria} />
                  </div>
                </div>
              </Section>
              </>
            )}

            {activePage === "workbench" && (
              <>
              <div id="sec-copilot">
                <ProductDefinitionCopilot
                  product={spec}
                  draft={draft}
                  onDraftChange={setDraft}
                  onScrollToSection={scrollToSection}
                />
              </div>

              <DefinitionReadinessPanel product={spec} onAskRecommended={askRecommended} />
              </>
            )}
          </div>
        </div>
      </div>

      <RevisionHistoryDialog
        open={historyOpen}
        onClose={() => setHistoryOpen(false)}
        revisions={revisions.data ?? []}
      />
    </div>
  );
}

function SpecToc({
  activePage,
  activeAnchor,
  onNavigate,
}: {
  activePage: SpecPageKey;
  activeAnchor: string;
  onNavigate: (page: SpecPageKey, anchor: string) => void;
}) {
  return (
    <nav className="spec-toc" aria-label="产品定义目录">
      {TOC_GROUPS.map((group) => (
        <div className={`spec-toc-group${activePage === group.page ? " is-active" : ""}`} key={group.label}>
          <span className="spec-toc-label">{group.label}</span>
          {group.items.map((item) => (
            <button
              key={item.label}
              type="button"
              className={`spec-toc-link${
                activeAnchor === item.anchor ? " is-active" : ""
              }`}
              aria-current={
                activeAnchor === item.anchor ? "page" : undefined
              }
              onClick={() => onNavigate(item.page, item.anchor)}
            >
              {item.label}
            </button>
          ))}
        </div>
      ))}
    </nav>
  );
}

function Section({
  icon,
  title,
  subtitle,
  children,
  tone,
  className,
  id,
}: {
  icon: ReactNode;
  title: string;
  subtitle?: string;
  children: ReactNode;
  tone?: "danger";
  className?: string;
  id?: string;
}) {
  return (
    <section className={`card card-pad spec-section${className ? ` ${className}` : ""}`} id={id}>
      <div className="spec-section-head">
        <span
          className="agent-avatar spec-section-icon"
          style={
            tone === "danger"
              ? { background: "var(--danger-soft)", color: "var(--danger-ink)" }
              : { background: "var(--accent-soft)", color: "var(--accent-deep)" }
          }
        >
          {icon}
        </span>
        <div className="spec-section-copy">
          <h2 className="section-title">{title}</h2>
          {subtitle && <p className="spec-section-note">{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

function Def({ label, value }: { label: string; value: string }) {
  return (
    <div className="def-row">
      <span className="def-key">{label}</span>
      <span className="def-val">{value}</span>
    </div>
  );
}

function Bullets({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <span className="subtle" style={{ fontSize: "var(--text-sm)" }}>—</span>;
  }

  return (
    <div className="bullets">
      {items.map((item, index) => (
        <div className="bullet" key={index}>
          {item}
        </div>
      ))}
    </div>
  );
}

function severityClass(severity: string): string {
  const value = severity.toLowerCase();
  if (["high", "critical", "楂?", "涓ラ噸"].some((token) => value.includes(token))) return "badge-failed";
  if (["low", "浣?"].some((token) => value.includes(token))) return "badge-completed";
  return "badge-warn";
}

function RiskCard({ risk }: { risk: RiskItem }) {
  return (
    <div className="card" style={{ padding: "var(--space-4)", background: "var(--surface-2)" }}>
      <div className="row between wrap row-gap-2" style={{ alignItems: "flex-start" }}>
        <div className="row row-gap-2">
          <span className="chip chip-outline">{risk.category}</span>
          <span className={`badge ${severityClass(risk.severity)}`}>{risk.severity}</span>
        </div>
      </div>
      <p style={{ margin: "10px 0 8px", color: "var(--ink-800)" }}>{risk.risk}</p>
      <p className="muted" style={{ fontSize: "var(--text-sm)" }}>
        <strong style={{ color: "var(--success-ink)" }}>缓解：</strong>
        {risk.mitigation}
      </p>
    </div>
  );
}

