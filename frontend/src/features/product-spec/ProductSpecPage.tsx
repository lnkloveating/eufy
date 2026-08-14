import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import {
  AlertTriangle,
  ArrowLeft,
  Brain,
  CircuitBoard,
  Coins,
  FlaskConical,
  Gauge,
  History,
  Layers,
  Lock,
  MapPin,
  Network,
  Route,
  ShieldOff,
  ShieldCheck,
  Target,
  Swords,
} from "lucide-react";

import type { ProductSpec, RiskItem, ValidationHypothesis } from "../../types/api";
import { useProduct, useProductRevisions } from "../../lib/queries";
import { formatDateTime } from "../../lib/formatters";
import { rememberProduct } from "../../lib/recent";
import {
  DEFINITION_STATUS_META,
  SECTION_META,
  TOC_SECTIONS,
} from "../../lib/productWorkbench";
import { ApiError } from "../../lib/api/client";
import { EmptyState } from "../../components/EmptyState/EmptyState";
import { ErrorState } from "../../components/ErrorState/ErrorState";
import { Skeleton, SkeletonText } from "../../components/LoadingSkeleton/LoadingSkeleton";
import { Button } from "../../components/ui/Button";
import { ProductDefinitionCopilot } from "./ProductDefinitionCopilot";
import { DefinitionReadinessPanel } from "./DefinitionReadinessPanel";
import { RevisionHistoryDialog } from "./RevisionHistoryDialog";

export function ProductSpecPage() {
  const { productId } = useParams<{ productId: string }>();
  const product = useProduct(productId);

  useEffect(() => {
    if (product.data?.id) rememberProduct(product.data.id);
  }, [product.data?.id]);

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
                <Button variant="primary">返回创建预测</Button>
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
  const revisions = useProductRevisions(spec.id);
  const statusMeta = DEFINITION_STATUS_META[spec.definition_status ?? "draft"];

  const scrollToSection = (anchor: string) =>
    document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth", block: "start" });

  const askRecommended = (question: string) => {
    setDraft(question);
    scrollToSection("sec-copilot");
  };

  return (
    <div className="page">
      <div className="page-header">
        <Link to="/" className="row row-gap-2 muted" style={{ fontSize: "var(--text-sm)" }}>
          <ArrowLeft size={15} aria-hidden="true" />
          创建新的预测
        </Link>
      </div>

      <div className="spec-workbench">
        <SpecToc onNavigate={scrollToSection} />

        <div className="spec-main stack stack-5">
          {/* Hero header */}
          <div className="hero" id="sec-overview">
            <div className="row row-gap-2 wrap" style={{ marginBottom: "var(--space-3)" }}>
              <span className="chip chip-accent">{spec.category}</span>
              <span
                className="chip"
                style={{ background: "rgba(255,255,255,0.1)", color: "#cdd9e8" }}
              >
                版本 {spec.version}
              </span>
              <span
                className="chip mono"
                style={{ background: "rgba(255,255,255,0.08)", color: "#9fb2cc" }}
              >
                {spec.id}
              </span>
            </div>
            <h1>{spec.name}</h1>
            <p className="hero-sub" style={{ fontSize: "var(--text-lg)", maxWidth: "72ch" }}>
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
          </div>

          {/* Definition status toolbar */}
          <div className="card card-pad row between wrap row-gap-3">
            <div className="row row-gap-2 wrap" style={{ minWidth: 0 }}>
              <span className={`badge ${statusMeta.badge}`}>{statusMeta.label}</span>
              <span className="chip chip-outline">当前版本 V{spec.version}</span>
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

          <Section id="sec-users" icon={<Target size={16} />} title="核心问题与价值主张">
            <div className="deflist">
              <Def label="核心问题" value={spec.core_problem} />
              <Def label="价值主张" value={spec.value_proposition} />
              <Def label="产品形态" value={spec.form_factor} />
            </div>
          </Section>

          <div className="spec-grid">
            <Section id="sec-hardware" icon={<CircuitBoard size={16} />} title="硬件架构">
              <Bullets items={spec.hardware_architecture} />
            </Section>
            <Section id="sec-ai" icon={<Brain size={16} />} title="AI 能力">
              <Bullets items={spec.ai_capabilities} />
            </Section>
          </div>

          <Section icon={<Gauge size={16} />} title="AI 决策边界">
            <p className="def-val">{spec.ai_decision_boundary}</p>
          </Section>

          {spec.capability_delta && (
            <Section
              id="sec-delta"
              icon={<ShieldCheck size={16} />}
              title="未来能力增量 Capability Delta"
            >
              <div className="deflist">
                <Def label="创新探索向量" value={spec.capability_delta.innovation_vector} />
                <Def label="为什么今天还没有" value={spec.capability_delta.why_not_available_today} />
                <Def label="硬件 / 系统增量" value={spec.capability_delta.hardware_or_system_delta} />
              </div>
              <div className="spec-grid" style={{ marginTop: "var(--space-4)" }}>
                <div className="stack stack-2">
                  <span className="opp-section-label">今天已有的相近能力</span>
                  <Bullets items={spec.capability_delta.today_equivalents} />
                </div>
                <div className="stack stack-2">
                  <span className="opp-section-label">真正新增的能力</span>
                  <Bullets items={spec.capability_delta.new_capabilities} />
                </div>
              </div>
            </Section>
          )}

          <div className="spec-grid">
            <Section icon={<Route size={16} />} title="用户旅程">
              <Bullets items={spec.user_journeys} />
            </Section>
            <Section id="sec-ecosystem" icon={<Network size={16} />} title="eufy 生态关系">
              <Bullets items={spec.ecosystem_relationships} />
            </Section>
          </div>

          <Section id="sec-privacy" icon={<Lock size={16} />} title="隐私原则">
            <Bullets items={spec.privacy_principles} />
          </Section>

          {spec.regional_fit.length > 0 && (
            <Section id="sec-regional" icon={<MapPin size={16} />} title="地区适配 Regional Fit">
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
            </Section>
          )}

          <Section id="sec-competition" icon={<Swords size={16} />} title="竞争定位与可防御差异">
            <div className="spec-grid">
              <div className="stack stack-2">
                <span className="opp-section-label">最接近的现有方案</span>
                <Bullets items={spec.competitive_positioning.closest_alternatives} />
              </div>
              <div className="stack stack-2">
                <span className="opp-section-label">可防御差异</span>
                <Bullets items={spec.competitive_positioning.defensible_differences} />
              </div>
            </div>
            <div className="alert alert-info" style={{ marginTop: "var(--space-4)" }}>
              <ShieldCheck size={16} className="alert-icon" />
              <div className="alert-body">
                <span className="alert-title">为什么不是竞品功能拼接</span>
                <span>{spec.competitive_positioning.non_copycat_rationale}</span>
              </div>
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
          </Section>

          <Section id="sec-business" icon={<Coins size={16} />} title="商业模式">
            <div className="deflist">
              <Def label="硬件收入" value={spec.business_model.hardware_revenue} />
              {spec.business_model.recurring_revenue && (
                <Def label="持续性收入" value={spec.business_model.recurring_revenue} />
              )}
            </div>
            <div className="spec-grid" style={{ marginTop: "var(--space-4)" }}>
              <div className="stack stack-2">
                <span className="opp-section-label">生态带动 Pull-through</span>
                <Bullets items={spec.business_model.ecosystem_pull_through} />
              </div>
              <div className="stack stack-2">
                <span className="opp-section-label">成本驱动 Cost drivers</span>
                <Bullets items={spec.business_model.cost_drivers} />
              </div>
            </div>
          </Section>

          <Section id="sec-risks" icon={<AlertTriangle size={16} />} title="风险及缓解方案">
            <div className="stack stack-3">
              {spec.risks.map((risk, index) => (
                <RiskCard key={index} risk={risk} />
              ))}
            </div>
          </Section>

          <div className="spec-grid">
            <Section id="sec-assumptions" icon={<Layers size={16} />} title="关键假设">
              <Bullets items={spec.key_assumptions} />
            </Section>
            <Section icon={<ShieldOff size={16} />} title="Kill Criteria" tone="danger">
              <Bullets items={spec.kill_criteria} />
            </Section>
          </div>

          <Section id="sec-validation" icon={<FlaskConical size={16} />} title="Validation Readiness">
            <p
              className="muted"
              style={{ fontSize: "var(--text-sm)", marginBottom: "var(--space-3)" }}
            >
              以下为可证伪的验证假设，尚未执行 —— 供后续验证实验室运行。
            </p>
            <div className="stack stack-3">
              {spec.validation_readiness.map((hypothesis) => (
                <ValidationCard key={hypothesis.id} hypothesis={hypothesis} />
              ))}
            </div>
          </Section>

          <ProductDefinitionCopilot
            product={spec}
            draft={draft}
            onDraftChange={setDraft}
            onScrollToSection={scrollToSection}
          />

          <DefinitionReadinessPanel product={spec} onAskRecommended={askRecommended} />
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

function SpecToc({ onNavigate }: { onNavigate: (anchor: string) => void }) {
  return (
    <nav className="spec-toc" aria-label="产品定义目录">
      <span className="spec-toc-label">产品定义</span>
      {TOC_SECTIONS.map((key) => {
        const meta = SECTION_META[key];
        if (!meta) return null;
        return (
          <button
            key={key}
            type="button"
            className="spec-toc-link"
            onClick={() => onNavigate(meta.anchor)}
          >
            {meta.label}
          </button>
        );
      })}
      <span className="spec-toc-label">工作台</span>
      <button type="button" className="spec-toc-link" onClick={() => onNavigate("sec-copilot")}>
        产品定义 Copilot
      </button>
      <button type="button" className="spec-toc-link" onClick={() => onNavigate("sec-readiness")}>
        确认与验证准备度
      </button>
    </nav>
  );
}

function Section({
  icon,
  title,
  children,
  tone,
  id,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
  tone?: "danger";
  id?: string;
}) {
  return (
    <section className="card card-pad" id={id}>
      <div className="row row-gap-2" style={{ marginBottom: "var(--space-4)" }}>
        <span
          className="agent-avatar"
          style={
            tone === "danger"
              ? { background: "var(--danger-soft)", color: "var(--danger-ink)" }
              : { background: "var(--accent-soft)", color: "var(--accent-deep)" }
          }
        >
          {icon}
        </span>
        <h2 className="section-title">{title}</h2>
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
  if (["high", "critical", "高", "严重"].some((token) => value.includes(token))) return "badge-failed";
  if (["low", "低"].some((token) => value.includes(token))) return "badge-completed";
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

function ValidationCard({ hypothesis }: { hypothesis: ValidationHypothesis }) {
  return (
    <div className="card" style={{ padding: "var(--space-4)" }}>
      <div className="row row-gap-2" style={{ marginBottom: 8 }}>
        <span className="chip mono">{hypothesis.id}</span>
      </div>
      <p style={{ color: "var(--ink-900)", fontWeight: 600, marginBottom: 10 }}>
        {hypothesis.assumption}
      </p>
      <div className="deflist">
        <Def label="度量指标" value={hypothesis.metric} />
        <Def label="验证方法" value={hypothesis.proposed_method} />
      </div>
      <div className="spec-grid" style={{ marginTop: "var(--space-3)" }}>
        <div
          className="card"
          style={{
            padding: "var(--space-3)",
            background: "var(--success-soft)",
            border: "1px solid #bfead2",
          }}
        >
          <span className="pro-con-title pro">通过条件 Pass</span>
          <p style={{ fontSize: "var(--text-sm)", marginTop: 4, color: "var(--success-ink)" }}>
            {hypothesis.pass_condition}
          </p>
        </div>
        <div
          className="card"
          style={{
            padding: "var(--space-3)",
            background: "var(--danger-soft)",
            border: "1px solid #f6cdd6",
          }}
        >
          <span className="pro-con-title con" style={{ color: "var(--danger-ink)" }}>
            终止条件 Kill
          </span>
          <p style={{ fontSize: "var(--text-sm)", marginTop: 4, color: "var(--danger-ink)" }}>
            {hypothesis.kill_condition}
          </p>
        </div>
      </div>
    </div>
  );
}
