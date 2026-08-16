import {
  Fragment,
  Suspense,
  lazy,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { Link, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ChevronLeft,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  FlaskConical,
  Lock,
  Pause,
  PlayCircle,
  RotateCcw,
  Send,
  ShieldQuestion,
} from "lucide-react";

import type {
  ObservationSourceType,
  ValidationAnalysisStep,
  ValidationEvent,
  ValidationExperiment,
  ValidationFinding,
  ValidationProject,
} from "../../types/api";
import { ApiError } from "../../lib/api/client";
import { formatClock, formatDateTime } from "../../lib/formatters";
import { rememberRun } from "../../lib/recent";
import { localizeProductSpecForDisplay } from "../../lib/displayLocalization";
import {
  queryKeys,
  useCreateValidationProject,
  useLatestValidationProject,
  useProduct,
  useRunValidationProject,
  useSendBackFinding,
  useValidationEvents,
  useValidationProject,
} from "../../lib/queries";
import {
  EXPERIMENT_TYPE_META,
  PROJECT_STATUS_META,
  SEVERITY_META,
  SIMULATION_BOUNDARY,
  SOURCE_TYPE_META,
  VERDICT_META,
  eventDotClass,
  feasibilityAssessment,
  isFindingSent,
} from "../../lib/validationLab";
import { EmptyState } from "../../components/EmptyState/EmptyState";
import { ErrorState } from "../../components/ErrorState/ErrorState";
import { Skeleton, SkeletonText } from "../../components/LoadingSkeleton/LoadingSkeleton";
import { Button } from "../../components/ui/Button";
import { useToast } from "../../components/ui/Toast";

// The 3D digital twin pulls in three.js / react-three-fiber (~1MB). Lazy-load it
// so that heavy chunk is fetched only when a validation project is opened, not
// on the rest of the app's initial bundle.
const ProductDigitalTwin = lazy(() =>
  import("./ProductDigitalTwin").then((module) => ({ default: module.ProductDigitalTwin })),
);

const ROLES: readonly { name: string; description: string }[] = [
  { name: "技术验证", description: "检查硬件、AI 能力与决策边界是否支撑假设。" },
  { name: "隐私安全", description: "检查敏感区域、数据处理与高影响动作的边界。" },
  { name: "用户场景", description: "以参数化 3D 数字样机检验真实使用链路是否成立。" },
  { name: "商业验证", description: "识别付费、价格与市场类经验指标的边界。" },
  { name: "反方审查", description: "红队式质疑，确保正向结论不被高估。" },
  { name: "最终裁决器", description: "综合角色与场景，给出模拟裁决枚举。" },
];

export function ValidationLabPage() {
  const { productId } = useParams<{ productId: string }>();
  const product = useProduct(productId);

  useEffect(() => {
    if (product.data?.source_run_id) rememberRun(product.data.source_run_id);
  }, [product.data?.source_run_id]);

  if (product.isLoading && !product.data) {
    return (
      <div className="page">
        <Skeleton width="45%" height={30} radius={8} />
        <div style={{ height: 20 }} />
        <div className="card card-pad">
          <SkeletonText lines={6} />
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
            description={`未找到产品 ${productId}。`}
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

  const isReady = product.data.definition_status === "validation_ready";
  if (!isReady) {
    return (
      <div className="page page-narrow">
        <EmptyState
          icon={<Lock size={26} aria-hidden="true" />}
          title="请先完成产品定义"
          description="验证实验室仅在产品定义达到验证准备完成后开放。请回到产品定义页处理阻塞项并确认。"
          action={
            <Link to={`/products/${encodeURIComponent(product.data.id)}`}>
              <Button variant="primary">前往产品定义</Button>
            </Link>
          }
        />
      </div>
    );
  }

  return <ValidationLabView productId={product.data.id} productVersion={product.data.version} />;
}

function ValidationLabView({
  productId,
  productVersion,
}: {
  productId: string;
  productVersion: string;
}) {
  const queryClient = useQueryClient();
  const latest = useLatestValidationProject(productId);
  const createProject = useCreateValidationProject(productId);

  const noProjectYet =
    latest.isError && latest.error instanceof ApiError && latest.error.isNotFound;
  // The newest project may belong to an older ProductSpec version (e.g. after a
  // revision). We only reuse a project whose snapshot matches the current
  // version; otherwise we create a fresh one for the current version.
  const latestMatchesVersion =
    latest.data?.product_version === productVersion ? latest.data : undefined;
  const staleProject = Boolean(latest.data) && !latestMatchesVersion;

  // Auto-create the plan from validation_readiness for the current version.
  useEffect(() => {
    if ((noProjectYet || staleProject) && createProject.isIdle) {
      createProject.mutate();
    }
  }, [noProjectYet, staleProject, createProject]);

  const baseProject = createProject.data ?? latestMatchesVersion;
  const projectId = baseProject?.id;
  const projectQuery = useValidationProject(projectId);
  const project = projectQuery.data ?? baseProject;
  const isRunning = project?.status === "running";
  const events = useValidationEvents(projectId, isRunning);

  // Pull the final events / project once the run leaves the running state.
  useEffect(() => {
    if (projectId && project && project.status !== "running") {
      void queryClient.invalidateQueries({ queryKey: queryKeys.validationEvents(projectId) });
    }
  }, [projectId, project, queryClient]);

  if (createProject.isError) {
    return (
      <div className="page page-narrow">
        <ErrorState
          title="无法创建预验证项目"
          error={createProject.error}
          onRetry={() => createProject.mutate()}
        />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="page">
        <div style={{ height: 16 }} />
        <div className="card card-pad">
          <SkeletonText lines={5} />
        </div>
      </div>
    );
  }

  return (
    <ValidationLabContent
      productId={productId}
      project={project}
      events={events.data ?? []}
    />
  );
}

function ValidationLabContent({
  productId,
  project,
  events,
}: {
  productId: string;
  project: ValidationProject;
  events: ValidationEvent[];
}) {
  const toast = useToast();
  const displayProduct = useMemo(
    () => localizeProductSpecForDisplay(project.product_snapshot),
    [project.product_snapshot],
  );
  const runMutation = useRunValidationProject(productId, project.id);
  const sendBack = useSendBackFinding(productId, project.id);
  const statusMeta = PROJECT_STATUS_META[project.status];
  const overall = VERDICT_META[project.overall_verdict];
  const allFindings = useMemo(
    () => project.experiments.flatMap((experiment) => experiment.findings),
    [project.experiments],
  );
  const canStart = project.status === "planned" || project.status === "failed";
  const isRunning = project.status === "running";

  function onStart() {
    runMutation.mutate(undefined, {
      onError: (error) => toast.error("无法开始预验证", error.detail),
    });
  }

  function onSendBack(finding: ValidationFinding) {
    sendBack.mutate(finding.id, {
      onSuccess: (response) =>
        toast.success("已发送回产品定义", response.message),
      onError: (error) => toast.error("发送失败", error.detail),
    });
  }

  return (
    <div className="page">
      {/* A. Header */}
      <section className="hero" style={{ marginTop: "var(--space-4)" }}>
        <div className="row row-gap-2 wrap spec-hero-tags">
          <span className="chip chip-accent">
            <FlaskConical size={13} aria-hidden="true" /> 预验证实验室
          </span>
          <span className="chip" style={{ background: "rgba(255,255,255,0.1)", color: "#cdd9e8" }}>
            产品定义 V{project.product_version}
          </span>
          <span className={`badge ${statusMeta.badge}`}>{statusMeta.label}</span>
        </div>
        <h1>{displayProduct.name}</h1>
        <p className="hero-sub" style={{ maxWidth: "72ch" }}>
          {displayProduct.one_sentence_definition}
        </p>
        <div className="hero-health">
          <div className="hero-stat">
            <span className="hero-stat-label">验证准备状态</span>
            <span className="hero-stat-value" style={{ fontSize: "var(--text-base)" }}>
              已就绪
            </span>
          </div>
          <div className="hero-stat">
            <span className="hero-stat-label">整体裁决（模拟）</span>
            <span className="hero-stat-value" style={{ fontSize: "var(--text-base)" }}>
              {overall.label}
            </span>
          </div>
          <div className="hero-stat">
            <span className="hero-stat-label">创建时间</span>
            <span className="hero-stat-value" style={{ fontSize: "var(--text-base)" }}>
              {formatDateTime(project.created_at)}
            </span>
          </div>
        </div>
      </section>

      {/* D. Product-specific parametric digital twin — usage tutorial */}
      <Section
        title="3D 产品数字样机"
        subtitle="根据当前产品定义的产品形态与硬件模块生成，仅用于展示产品的大致外观，不代表真实工程验证。"
      >
        {project.digital_twin ? (
          <Suspense
            fallback={
              <div className="vlab-twin-loading">
                <Skeleton width="100%" height={360} radius={12} />
                <span className="subtle">正在加载 3D 数字样机…</span>
              </div>
            }
          >
            <ProductDigitalTwin
              spec={project.digital_twin}
              product={displayProduct}
              productName={displayProduct.name}
            />
          </Suspense>
        ) : (
          <div className="alert alert-warn" role="status">
            <AlertTriangle size={18} className="alert-icon" aria-hidden="true" />
            <div className="alert-body">
              <span className="alert-title">数字样机参数正在生成</span>
              <span>刷新项目后即可查看，不会使用通用占位模型替代当前产品。</span>
            </div>
          </div>
        )}
      </Section>

      <div className="alert alert-warn" role="note" style={{ marginTop: "var(--space-4)" }}>
        <ShieldQuestion size={18} className="alert-icon" aria-hidden="true" />
        <div className="alert-body">
          <span className="alert-title">预验证 / 模拟验证边界</span>
          <span>{project.disclaimer || SIMULATION_BOUNDARY}</span>
        </div>
      </div>

      {/* Run control */}
      <div className="card card-pad spec-toolbar" style={{ marginTop: "var(--space-4)" }}>
        <div className="row row-gap-2 wrap" style={{ minWidth: 0 }}>
          <span className="strong">{project.summary}</span>
        </div>
        {canStart ? (
          <Button
            variant="primary"
            loading={runMutation.isPending}
            onClick={onStart}
            iconStart={<PlayCircle size={16} aria-hidden="true" />}
          >
            {project.status === "failed" ? "重新开始预验证" : "开始预验证"}
          </Button>
        ) : isRunning ? (
          <span className="badge badge-running">预验证进行中…</span>
        ) : (
          <span className="badge badge-completed">已完成（模拟）</span>
        )}
      </div>

      {project.error && (
        <div className="alert alert-danger" role="alert" style={{ marginTop: "var(--space-3)" }}>
          <AlertTriangle size={18} className="alert-icon" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">运行提示</span>
            <span>{project.error}</span>
          </div>
        </div>
      )}

      {/* B. Hypothesis matrix */}
      <Section title="验证假设矩阵" subtitle="每条假设一个实验，展示类型、状态、模拟裁决与证据来源。">
        <HypothesisMatrix experiments={project.experiments} />
      </Section>

      {/* C. Multi-agent process */}
      <Section title="多智能体预验证过程" subtitle="技术、隐私、场景、商业、反方审查与裁决器的实时活动。">
        <div className="vlab-roles">
          {ROLES.map((role) => (
            <div className="vlab-role-card" key={role.name}>
              <strong>{role.name}</strong>
              <span className="muted" style={{ fontSize: "var(--text-sm)" }}>
                {role.description}
              </span>
            </div>
          ))}
        </div>
        <ActivityFeed events={events} running={isRunning} />
      </Section>

      {/* E. Verdicts */}
      <Section title="验证结论（模拟）" subtitle="每条假设的模拟裁决与理由，均非真实验证。">
        <VerdictCarousel experiments={project.experiments} />
      </Section>

      {/* F. Feedback to product definition */}
      <Section
        title="反馈产品定义"
        subtitle="将模拟发现发送回产品定义助手；不会自动修改产品定义，需用户在定义页确认。"
      >
        {allFindings.length === 0 ? (
          <EmptyState
            title={isRunning ? "预验证进行中…" : "暂无需要反馈的发现"}
            description={
              isRunning
                ? "运行完成后，这里会列出可发送回产品定义的改进建议。"
                : "本次模拟未发现需要修改产品定义的阻断项或缺口。"
            }
          />
        ) : (
          <div className="stack stack-3">
            {allFindings.map((finding) => (
              <FindingCard
                key={finding.id}
                finding={finding}
                onSendBack={() => onSendBack(finding)}
                pending={sendBack.isPending && sendBack.variables === finding.id}
              />
            ))}
            <Link
              to={`/products/${encodeURIComponent(productId)}#sec-copilot`}
              className="row row-gap-2 muted spec-back-link"
            >
              前往产品定义助手审查已发送的建议 →
            </Link>
          </div>
        )}
      </Section>
    </div>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <section className="card card-pad spec-section" style={{ marginTop: "var(--space-5)" }}>
      <div className="spec-section-head">
        <span
          className="agent-avatar spec-section-icon"
          style={{ background: "var(--accent-soft)", color: "var(--accent-deep)" }}
        >
          <Activity size={16} aria-hidden="true" />
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

function HypothesisMatrix({ experiments }: { experiments: ValidationExperiment[] }) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [sourceFilters, setSourceFilters] = useState<
    Record<string, ObservationSourceType | "all">
  >({});

  function toggle(experimentId: string) {
    setExpandedId((current) => (current === experimentId ? null : experimentId));
  }

  function revealSource(experimentId: string, source: ObservationSourceType) {
    setExpandedId(experimentId);
    setSourceFilters((current) => ({ ...current, [experimentId]: source }));
  }

  return (
    <div className="vlab-matrix-wrap">
      <table className="vlab-matrix">
        <thead>
          <tr>
            <th>假设</th>
            <th>实验类型</th>
            <th>状态</th>
            <th>模拟裁决</th>
            <th>证据来源</th>
          </tr>
        </thead>
        <tbody>
          {experiments.map((experiment) => {
            const verdict = VERDICT_META[experiment.verdict];
            const assessment = feasibilityAssessment(experiment);
            const sources = Array.from(
              new Set(experiment.observations.map((obs) => obs.source_type)),
            );
            const expanded = expandedId === experiment.id;
            const sourceFilter = sourceFilters[experiment.id] ?? "all";
            return (
              <Fragment key={experiment.id}>
              <tr
                className={`vlab-matrix-row ${expanded ? "is-expanded" : ""}`}
                tabIndex={0}
                aria-expanded={expanded}
                onClick={() => toggle(experiment.id)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    toggle(experiment.id);
                  }
                }}
              >
                <td>
                  <div className="vlab-matrix-title">
                    <div>
                      <span className="mono subtle" style={{ fontSize: "var(--text-xs)" }}>
                        {experiment.hypothesis_id}
                      </span>
                      <div>{experiment.assumption}</div>
                    </div>
                    {expanded ? (
                      <ChevronUp size={16} aria-hidden="true" />
                    ) : (
                      <ChevronDown size={16} aria-hidden="true" />
                    )}
                  </div>
                  <div className="vlab-matrix-reason">
                    {experiment.status === "not_run" ? (
                      <>
                        <strong>评估：</strong>
                        尚未评估，运行后将基于知识库证据判断可行性。
                      </>
                    ) : (
                      <>
                        <strong>{assessment.label}：</strong>
                        {assessment.reason}
                      </>
                    )}
                  </div>
                </td>
                <td>{EXPERIMENT_TYPE_META[experiment.experiment_type]}</td>
                <td>
                  <span className="chip chip-outline">
                    {experiment.status === "completed"
                      ? "已完成"
                      : experiment.status === "running"
                        ? "运行中"
                        : experiment.status === "failed"
                          ? "失败"
                          : "未运行"}
                  </span>
                </td>
                <td>
                  <span className={`badge ${verdict.badge}`}>{verdict.label}</span>
                </td>
                <td>
                  <div className="row row-gap-2 wrap">
                    {sources.length === 0 ? (
                      <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
                        —
                      </span>
                    ) : (
                      sources.map((source) => (
                        <button
                          key={source}
                          type="button"
                          className={`badge vlab-source-button ${SOURCE_TYPE_META[source].badge}`}
                          title={`查看${SOURCE_TYPE_META[source].label}的具体内容`}
                          onClick={(event) => {
                            event.stopPropagation();
                            revealSource(experiment.id, source);
                          }}
                        >
                          {SOURCE_TYPE_META[source].label}
                        </button>
                      ))
                    )}
                  </div>
                </td>
              </tr>
              {expanded && (
                <tr className="vlab-matrix-detail-row">
                  <td colSpan={5}>
                    <ExperimentAnalysisDetail
                      experiment={experiment}
                      sourceFilter={sourceFilter}
                      onSourceFilter={(source) =>
                        setSourceFilters((current) => ({
                          ...current,
                          [experiment.id]: source,
                        }))
                      }
                    />
                  </td>
                </tr>
              )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ExperimentAnalysisDetail({
  experiment,
  sourceFilter,
  onSourceFilter,
}: {
  experiment: ValidationExperiment;
  sourceFilter: ObservationSourceType | "all";
  onSourceFilter: (source: ObservationSourceType | "all") => void;
}) {
  const sources = Array.from(new Set(experiment.observations.map((item) => item.source_type)));
  const observations =
    sourceFilter === "all"
      ? experiment.observations
      : experiment.observations.filter((item) => item.source_type === sourceFilter);

  return (
    <div className="vlab-analysis-detail" onClick={(event) => event.stopPropagation()}>
      <div className="vlab-analysis-heading">
        <div>
          <span className="eyebrow">EXPLAINABLE VERDICT</span>
          <h3>为什么这样判断</h3>
        </div>
        <span className="subtle">本分析来自已保存的本次实验结果</span>
      </div>

      <div className="vlab-reason-grid">
        <ReasonPanel title="支持依据" tone="support" items={experiment.supporting_points} />
        <ReasonPanel title="反例与顾虑" tone="counter" items={experiment.counter_points} />
        <ReasonPanel title="仍未确定" tone="uncertain" items={experiment.uncertainties} />
        <div className="vlab-reason-panel is-next">
          <strong>下一步建议实验</strong>
          <p>{experiment.next_recommended_test || "完成本次预验证后生成。"}</p>
        </div>
      </div>

      <div className="vlab-evidence-section">
        <div className="row between wrap row-gap-2">
          <div>
            <strong>证据与分析内容</strong>
            <p className="muted vlab-detail-note">点击来源筛选，查看标签背后的具体判断。</p>
          </div>
          <div className="row row-gap-2 wrap">
            <button
              type="button"
              className={`chip vlab-filter-button ${sourceFilter === "all" ? "is-active" : "chip-outline"}`}
              aria-pressed={sourceFilter === "all"}
              onClick={() => onSourceFilter("all")}
            >
              全部
            </button>
            {sources.map((source) => (
              <button
                key={source}
                type="button"
                className={`badge vlab-filter-button ${SOURCE_TYPE_META[source].badge} ${
                  sourceFilter === source ? "is-active" : ""
                }`}
                aria-pressed={sourceFilter === source}
                onClick={() => onSourceFilter(source)}
              >
                {SOURCE_TYPE_META[source].label}
              </button>
            ))}
          </div>
        </div>
        <div className="vlab-observation-list">
          {observations.length === 0 ? (
            <p className="subtle">尚无该来源的分析内容。</p>
          ) : (
            observations.map((observation) => (
              <article className="vlab-observation" key={observation.id}>
                <div className="row between wrap row-gap-2">
                  <strong>{observation.source_label}</strong>
                  <span className={`badge ${SOURCE_TYPE_META[observation.source_type].badge}`}>
                    {SOURCE_TYPE_META[observation.source_type].label}
                  </span>
                </div>
                <p>{observation.content}</p>
              </article>
            ))
          )}
        </div>
      </div>

      <AnalysisReplay steps={experiment.analysis_trace} />
    </div>
  );
}

function ReasonPanel({
  title,
  tone,
  items,
}: {
  title: string;
  tone: "support" | "counter" | "uncertain";
  items: string[];
}) {
  return (
    <div className={`vlab-reason-panel is-${tone}`}>
      <strong>{title}</strong>
      {items.length === 0 ? (
        <p className="subtle">本次分析未记录相关项。</p>
      ) : (
        <ul>
          {items.map((item, index) => (
            <li key={`${tone}-${index}`}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

const ANALYSIS_ACTOR_LABELS: Record<ValidationAnalysisStep["actor"], string> = {
  hypothesis_parser: "验证问题解析",
  evidence_retrieval: "已有证据检索",
  deterministic_simulation: "确定性场景模拟",
  technology: "技术验证智能体",
  privacy_security: "隐私安全智能体",
  user_scenario: "用户场景智能体",
  business: "商业验证智能体",
  adversarial: "反方审查智能体",
  ai_analysis: "AI 补充分析",
  adjudicator: "最终裁决器",
};

function AnalysisReplay({ steps }: { steps: ValidationAnalysisStep[] }) {
  const ordered = useMemo(() => [...steps].sort((a, b) => a.sequence - b.sequence), [steps]);
  const [cursor, setCursor] = useState(Math.max(ordered.length - 1, -1));
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    setCursor(Math.max(ordered.length - 1, -1));
    setPlaying(false);
  }, [ordered]);

  useEffect(() => {
    if (!playing) return;
    if (cursor >= ordered.length - 1) {
      setPlaying(false);
      return;
    }
    const timer = window.setTimeout(() => setCursor((current) => current + 1), 850);
    return () => window.clearTimeout(timer);
  }, [cursor, ordered.length, playing]);

  if (ordered.length === 0) {
    return (
      <div className="vlab-replay-empty">
        <strong>分析过程</strong>
        <p className="subtle">运行实验后会保存完整分析轨迹，并可在这里重放。</p>
      </div>
    );
  }

  function startReplay() {
    setCursor(-1);
    setPlaying(true);
  }

  return (
    <div className="vlab-replay">
      <div className="row between wrap row-gap-2">
        <div>
          <strong>可重放分析链路</strong>
          <p className="muted vlab-detail-note">重放只读取已保存轨迹，不会重新调用模型。</p>
        </div>
        <div className="row row-gap-2 wrap">
          <Button
            variant="secondary"
            className="btn-sm"
            onClick={playing ? () => setPlaying(false) : startReplay}
            iconStart={
              playing ? <Pause size={14} aria-hidden="true" /> : <RotateCcw size={14} aria-hidden="true" />
            }
          >
            {playing ? "暂停" : "重放分析过程"}
          </Button>
          <Button
            variant="secondary"
            className="btn-sm"
            disabled={cursor >= ordered.length - 1}
            onClick={() => {
              setPlaying(false);
              setCursor((current) => Math.min(current + 1, ordered.length - 1));
            }}
          >
            下一步
          </Button>
        </div>
      </div>
      <ol className="vlab-analysis-trace">
        {ordered.map((step, index) => {
          const revealed = index <= cursor;
          const active = index === cursor;
          return (
            <li
              key={step.id}
              className={`${revealed ? "is-revealed" : "is-pending"} ${active ? "is-active" : ""}`}
            >
              <span className="vlab-trace-index">{step.sequence}</span>
              <div>
                <div className="row row-gap-2 wrap">
                  <strong>{ANALYSIS_ACTOR_LABELS[step.actor]}</strong>
                  <span className={`badge ${SOURCE_TYPE_META[step.source_type].badge}`}>
                    {SOURCE_TYPE_META[step.source_type].label}
                  </span>
                  <span className="chip chip-outline">{step.outcome}</span>
                </div>
                <div className="vlab-trace-action">{step.action}</div>
                <p>{step.reasoning}</p>
                {step.evidence_ids.length > 0 && (
                  <div className="mono subtle vlab-trace-evidence">
                    引用：{step.evidence_ids.join(" · ")}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function ActivityFeed({
  events,
  running,
}: {
  events: ValidationEvent[];
  running: boolean;
}) {
  if (events.length === 0) {
    return (
      <EmptyState
        title={running ? "正在收集角色活动…" : "尚未开始预验证"}
        description={running ? undefined : "点击上方“开始预验证”后，这里会实时显示各角色的活动。"}
      />
    );
  }
  const ordered = [...events].reverse();
  return (
    <div className="timeline vlab-activity">
      {ordered.map((event) => (
        <div className="tl-item" key={event.sequence}>
          <div className="tl-rail">
            <span className={`tl-dot ${eventDotClass(event.event_type)}`} />
            <span className="tl-line" />
          </div>
          <div className="tl-body">
            <div className="tl-head">
              <span className="tl-agent">{event.validator_name ?? "预验证编排"}</span>
              <span className="tl-time">{formatClock(event.created_at)}</span>
            </div>
            <div className="tl-msg">{event.message}</div>
          </div>
        </div>
      ))}
    </div>
  );
}

function VerdictCarousel({ experiments }: { experiments: ValidationExperiment[] }) {
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    setActiveIndex(0);
  }, [experiments]);

  if (experiments.length === 0) {
    return <EmptyState title="暂无验证结论" description="当前项目还没有生成任何假设验证结果。" />;
  }

  const activeExperiment = experiments[Math.min(activeIndex, experiments.length - 1)]!;
  const verdict = VERDICT_META[activeExperiment.verdict];
  const canNavigate = experiments.length > 1;

  const goPrevious = () => {
    if (!canNavigate) return;
    setActiveIndex((current) => (current - 1 + experiments.length) % experiments.length);
  };

  const goNext = () => {
    if (!canNavigate) return;
    setActiveIndex((current) => (current + 1) % experiments.length);
  };

  return (
    <article className="card card-pad stack stack-3 verdict-carousel-card">
      <div className="row between wrap row-gap-2 verdict-carousel-head">
        <div className="row row-gap-2 wrap verdict-carousel-title" style={{ minWidth: 0 }}>
          <strong>验证结论</strong>
          {canNavigate && (
            <span className="chip chip-outline">
              {activeIndex + 1} / {experiments.length}
            </span>
          )}
        </div>
        <div className="row row-gap-2 verdict-carousel-actions">
          <button
            type="button"
            className="carousel-arrow"
            onClick={goPrevious}
            disabled={!canNavigate}
            aria-label="上一个假设"
            title="上一个假设"
          >
            <ChevronLeft size={16} aria-hidden="true" />
          </button>
          <button
            type="button"
            className="carousel-arrow"
            onClick={goNext}
            disabled={!canNavigate}
            aria-label="下一个假设"
            title="下一个假设"
          >
            <ChevronRight size={16} aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="verdict-carousel-body" key={activeExperiment.id} aria-live="polite">
        <div className="row between wrap row-gap-2">
          <span className="mono subtle" style={{ fontSize: "var(--text-xs)" }}>
            {activeExperiment.hypothesis_id}
          </span>
          <span className={`badge ${verdict.badge}`}>{verdict.label}</span>
        </div>
        <strong>{activeExperiment.assumption}</strong>
        <p className="muted" style={{ fontSize: "var(--text-sm)", margin: 0 }}>
          {activeExperiment.summary || verdict.description}
        </p>
        <div className="row row-gap-2 wrap">
          <span className="chip chip-outline">度量：{activeExperiment.metric}</span>
        </div>
      </div>
    </article>
  );
}

function FindingCard({
  finding,
  onSendBack,
  pending,
}: {
  finding: ValidationFinding;
  onSendBack: () => void;
  pending: boolean;
}) {
  const severity = SEVERITY_META[finding.severity];
  const source = SOURCE_TYPE_META[finding.source_type];
  const sent = isFindingSent(finding.feedback_status);
  return (
    <div className="card card-pad stack stack-2" style={{ background: "var(--surface-2)" }}>
      <div className="row between wrap row-gap-2" style={{ alignItems: "flex-start" }}>
        <div className="row row-gap-2 wrap">
          <span className={`badge ${severity.badge}`}>{severity.label}</span>
          <span className="chip chip-outline">{finding.category}</span>
          <span className={`badge ${source.badge}`}>{source.label}</span>
        </div>
        {sent ? (
          <span className="badge badge-completed">已发送回产品定义</span>
        ) : (
          <Button
            variant="primary"
            className="btn-sm"
            loading={pending}
            onClick={onSendBack}
            iconStart={<Send size={14} aria-hidden="true" />}
          >
            发送回产品定义
          </Button>
        )}
      </div>
      <strong>{finding.title}</strong>
      <p className="muted" style={{ fontSize: "var(--text-sm)", margin: 0 }}>
        {finding.detail}
      </p>
      <div className="spec-muted-note">
        <strong>建议修改：</strong>
        {finding.recommended_change}
      </div>
    </div>
  );
}
