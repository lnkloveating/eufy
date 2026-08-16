import { BarChart3, ClipboardCopy, ExternalLink, Link2, Users } from "lucide-react";

import type { SurveyQuestionResult, ValidationVisualSummary } from "../../types/api";
import {
  useCreateValidationSurvey,
  useValidationSurvey,
  useValidationSurveyResults,
  useValidationVisualSummary,
} from "../../lib/queries";
import { Button } from "../../components/ui/Button";
import { useToast } from "../../components/ui/Toast";

const CONCLUSION_META = [
  { key: "simulation_supported", label: "模拟支持", color: "#0f9f62" },
  { key: "research_required", label: "待真实调研", color: "#d58a16" },
  { key: "real_validation_required", label: "待真实验证", color: "#3578e5" },
  { key: "unqualified", label: "不合格", color: "#d94a55" },
] as const;

function Donut({ summary }: { summary: ValidationVisualSummary }) {
  const total = Math.max(summary.total_experiments, 1);
  let cursor = 0;
  const stops = CONCLUSION_META.map((item) => {
    const start = cursor;
    cursor += ((summary.conclusion_counts[item.key] ?? 0) / total) * 360;
    return `${item.color} ${start}deg ${cursor}deg`;
  });
  if (cursor < 360) stops.push(`#edf0f3 ${cursor}deg 360deg`);
  return (
    <div
      className="vlab-insight-donut"
      style={{ background: `conic-gradient(${stops.join(", ")})` }}
      role="img"
      aria-label={`共 ${summary.total_experiments} 条验证假设`}
    >
      <div>
        <strong>{summary.total_experiments}</strong>
        <span>验证假设</span>
      </div>
    </div>
  );
}

function ResultBars({ result }: { result: SurveyQuestionResult }) {
  const entries = Object.entries(result.option_counts).sort((a, b) => b[1] - a[1]);
  const maximum = Math.max(...entries.map(([, count]) => count), 1);
  return (
    <div className="vlab-survey-result">
      <div className="row between row-gap-2 wrap">
        <strong>{result.prompt}</strong>
        {result.average_rating !== null && (
          <span className="badge badge-completed">平均 {result.average_rating.toFixed(1)} / 5</span>
        )}
      </div>
      {entries.slice(0, 7).map(([label, count]) => (
        <div className="vlab-result-row" key={label}>
          <span title={label}>{label}</span>
          <div className="vlab-result-track">
            <i style={{ width: `${(count / maximum) * 100}%` }} />
          </div>
          <b>{count}</b>
        </div>
      ))}
    </div>
  );
}

export function ValidationInsightsPanel({
  projectId,
  completed,
}: {
  projectId: string;
  completed: boolean;
}) {
  const toast = useToast();
  const summary = useValidationVisualSummary(projectId, completed);
  const survey = useValidationSurvey(projectId, completed);
  const createSurvey = useCreateValidationSurvey(projectId);
  const access = createSurvey.data ?? survey.data;
  const results = useValidationSurveyResults(projectId, completed && Boolean(access));

  async function copySurveyLink() {
    if (!access) return;
    try {
      await navigator.clipboard.writeText(access.public_url);
      toast.success("调查链接已复制", "可以直接发给真实目标用户填写。");
    } catch {
      toast.error("复制失败", "请打开调查页后从浏览器地址栏复制链接。");
    }
  }

  if (!completed) {
    return (
      <div className="vlab-insight-placeholder">
        完成预验证后，系统会生成结论图表、指标卡和可分享的动态调查问卷。
      </div>
    );
  }
  if (summary.isLoading || !summary.data) {
    return <div className="vlab-insight-placeholder">正在整理验证指标…</div>;
  }

  const data = summary.data;
  const chartResult = results.data?.questions.find(
    (item) => item.average_rating !== null || Object.keys(item.option_counts).length > 0,
  );
  return (
    <div className="stack stack-4">
      <div className="vlab-kpi-grid">
        <div className="vlab-kpi-card">
          <span>模拟支持率</span>
          <strong>{data.simulation_support_rate}%</strong>
          <small>只代表预验证，不代表真实实验通过</small>
        </div>
        <div className="vlab-kpi-card is-danger">
          <span>高优先级风险</span>
          <strong>{data.high_risk_count}</strong>
          <small>建议提交前优先处理</small>
        </div>
        <div className="vlab-kpi-card is-research">
          <span>可问卷调研假设</span>
          <strong>{data.survey_eligible_experiments}</strong>
          <small>用户、商业和隐私感知类</small>
        </div>
        <div className="vlab-kpi-card is-real">
          <span>需真实实验任务</span>
          <strong>{data.real_experiment_tasks}</strong>
          <small>技术、准确率和可靠性类</small>
        </div>
      </div>

      <div className="vlab-insight-grid">
        <div className="vlab-chart-card">
          <div className="row row-gap-2">
            <BarChart3 size={17} aria-hidden="true" />
            <strong>验证结论分布</strong>
          </div>
          <div className="vlab-donut-layout">
            <Donut summary={data} />
            <div className="vlab-chart-legend">
              {CONCLUSION_META.map((item) => (
                <div key={item.key}>
                  <i style={{ background: item.color }} />
                  <span>{item.label}</span>
                  <strong>{data.conclusion_counts[item.key] ?? 0}</strong>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="vlab-chart-card">
          <div className="row between row-gap-2 wrap">
            <div className="row row-gap-2">
              <Users size={17} aria-hidden="true" />
              <strong>真实用户调查</strong>
            </div>
            <span className="chip chip-outline">
              {results.data?.sample_status_label ?? "尚未收集样本"}
            </span>
          </div>
          <div className="vlab-survey-count">
            <strong>{results.data?.total_responses ?? data.survey_response_count}</strong>
            <span>份有效提交</span>
          </div>
          {!access ? (
            <div className="stack stack-2">
              <p className="muted vlab-insight-note">
                系统会根据用户场景、商业和隐私感知假设生成问卷；技术验证项仍保留为真实实验任务。
              </p>
              <Button
                variant="primary"
                loading={createSurvey.isPending}
                onClick={() =>
                  createSurvey.mutate(undefined, {
                    onSuccess: () => toast.success("动态调查已生成"),
                    onError: (error) => toast.error("无法生成调查", error.detail),
                  })
                }
                iconStart={<Link2 size={15} aria-hidden="true" />}
              >
                生成真实用户调查链接
              </Button>
            </div>
          ) : (
            <div className="stack stack-2">
              <div className="vlab-survey-link mono">{access.public_url}</div>
              <div className="row row-gap-2 wrap">
                <Button
                  variant="secondary"
                  className="btn-sm"
                  onClick={copySurveyLink}
                  iconStart={<ClipboardCopy size={14} aria-hidden="true" />}
                >
                  复制链接
                </Button>
                <a href={access.public_url} target="_blank" rel="noreferrer">
                  <Button
                    variant="secondary"
                    className="btn-sm"
                    iconStart={<ExternalLink size={14} aria-hidden="true" />}
                  >
                    打开调查页
                  </Button>
                </a>
              </div>
            </div>
          )}
        </div>
      </div>

      {chartResult && <ResultBars result={chartResult} />}
      {results.data && <p className="vlab-evidence-boundary">{results.data.disclaimer}</p>}
    </div>
  );
}
