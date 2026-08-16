import { Link } from "react-router-dom";
import {
  Boxes,
  CheckCircle2,
  CircleAlert,
  FlaskConical,
  Gauge,
  Lightbulb,
  XCircle,
} from "lucide-react";

import type { ProductSpec, ReadinessItem } from "../../types/api";
import { useConfirmProduct, useProductReadiness } from "../../lib/queries";
import { DEFINITION_STATUS_META, validationLabStatus } from "../../lib/productWorkbench";
import { validationLabEntry } from "../../lib/validationLab";
import { Button } from "../../components/ui/Button";
import { SkeletonText } from "../../components/LoadingSkeleton/LoadingSkeleton";
import { useToast } from "../../components/ui/Toast";

interface Props {
  product: ProductSpec;
  onAskRecommended: (question: string) => void;
}

export function DefinitionReadinessPanel({ product, onAskRecommended }: Props) {
  const toast = useToast();
  const readiness = useProductReadiness(product.id);
  const confirm = useConfirmProduct(product.id);

  const statusMeta = DEFINITION_STATUS_META[product.definition_status ?? "draft"];
  const isValidationReady = product.definition_status === "validation_ready";
  const lab = validationLabStatus(product.definition_status);
  const labEntry = validationLabEntry(product.id, product.definition_status);

  function onConfirm() {
    confirm.mutate(undefined, {
      onSuccess: () =>
        toast.success("产品定义已确认", "状态已更新为验证准备完成，可进入后续验证阶段。"),
      onError: (error) => {
        toast.error("暂无法确认", error.detail);
        void readiness.refetch();
      },
    });
  }

  return (
    <section className="card card-pad stack stack-5" id="sec-readiness">
      <div className="row between wrap row-gap-2">
        <div className="row row-gap-2">
          <span
            className="agent-avatar"
            style={{ background: "var(--accent-soft)", color: "var(--accent-deep)" }}
          >
            <Gauge size={16} aria-hidden="true" />
          </span>
          <h2 className="section-title">确认产品定义 · Definition Readiness</h2>
        </div>
        <span className={`badge ${statusMeta.badge}`}>{statusMeta.label}</span>
      </div>

      {readiness.isLoading && !readiness.data ? (
        <SkeletonText lines={4} />
      ) : readiness.data ? (
        <>
          <div className="stack stack-2">
            <div className="row between">
              <span className="muted" style={{ fontSize: "var(--text-sm)" }}>
                定义完整度（仅检查完整性，不代表任何验证已通过）
              </span>
              <span className="strong" style={{ fontVariantNumeric: "tabular-nums" }}>
                {readiness.data.score}%
              </span>
            </div>
            <div className="confbar-track">
              <div
                className={`confbar-fill ${
                  readiness.data.ready ? "conf-high" : "conf-medium"
                }`}
                style={{ width: `${readiness.data.score}%` }}
              />
            </div>
          </div>

          {readiness.data.ready ? (
            <div className="alert alert-success" role="note">
              <CheckCircle2 size={16} className="alert-icon" aria-hidden="true" />
              <div className="alert-body">
                <span className="alert-title">定义已足够完整</span>
                <span>产品定义已完整到可以进入后续验证阶段，但尚未进行任何验证。</span>
              </div>
            </div>
          ) : (
            <ItemList
              title="阻塞项（需处理后才能确认）"
              tone="danger"
              items={readiness.data.blocking_items}
            />
          )}

          {readiness.data.warnings.length > 0 && (
            <ItemList title="提醒（不阻塞确认）" tone="warn" items={readiness.data.warnings} />
          )}

          {readiness.data.next_recommended_questions.length > 0 && (
            <div className="stack stack-2">
              <span className="opp-section-label">
                <Lightbulb size={12} aria-hidden="true" /> 建议继续询问
              </span>
              <div className="taglist">
                {readiness.data.next_recommended_questions.map((question) => (
                  <button
                    key={question}
                    type="button"
                    className="option-pill"
                    onClick={() => onAskRecommended(question)}
                    title={question}
                  >
                    {question}
                  </button>
                ))}
              </div>
            </div>
          )}

          {!isValidationReady && (
            <div className="row row-gap-3 wrap">
              <Button
                variant="primary"
                loading={confirm.isPending}
                disabled={!readiness.data.ready || confirm.isPending}
                onClick={onConfirm}
              >
                {confirm.isPending ? "正在确认…" : "确认产品定义"}
              </Button>
              {!readiness.data.ready && (
                <span className="subtle" style={{ fontSize: "var(--text-sm)" }}>
                  处理全部阻塞项后即可确认。
                </span>
              )}
            </div>
          )}
        </>
      ) : (
        <span className="subtle">无法加载准备度信息。</span>
      )}

      {/* Validation lab — enabled only once the definition is validation_ready. */}
      <div className="hr" />
      <div className="coming-soon">
        <FlaskConical size={26} className="muted" aria-hidden="true" />
        <div className="stack stack-2 grow">
          <div className="row row-gap-3 wrap">
            <strong>{lab.title}</strong>
            {!isValidationReady && <span className="coming-soon-badge">需先确认定义</span>}
          </div>
          <span className="muted" style={{ fontSize: "var(--text-sm)" }}>
            {isValidationReady
              ? "验证实验室对当前产品定义版本进行预验证 / 模拟，不代表真实硬件或真实用户测试。"
              : lab.description}
          </span>
        </div>
        <div className="row row-gap-3 wrap">
          <Link to={`/runs/${product.source_run_id}`}>
            <Button variant="secondary" iconStart={<Boxes size={16} aria-hidden="true" />}>
              返回候选对比
            </Button>
          </Link>
          {labEntry.enabled ? (
            <Link to={labEntry.path}>
              <Button variant="primary" iconStart={<FlaskConical size={16} aria-hidden="true" />}>
                进入产品验证实验室
              </Button>
            </Link>
          ) : (
            <Button variant="primary" disabled title={labEntry.reason}>
              进入产品验证实验室
            </Button>
          )}
        </div>
      </div>
    </section>
  );
}

function ItemList({
  title,
  tone,
  items,
}: {
  title: string;
  tone: "danger" | "warn";
  items: ReadinessItem[];
}) {
  const Icon = tone === "danger" ? XCircle : CircleAlert;
  const color = tone === "danger" ? "var(--danger-ink)" : "var(--warn-ink)";
  return (
    <div className="stack stack-2">
      <span className="opp-section-label">{title}</span>
      <div className="stack stack-2">
        {items.map((item) => (
          <div key={item.id} className="row row-gap-2" style={{ alignItems: "flex-start" }}>
            <Icon size={15} style={{ color, flexShrink: 0, marginTop: 2 }} aria-hidden="true" />
            <span style={{ minWidth: 0 }}>
              {item.label}
              {item.detail && (
                <span className="muted" style={{ fontSize: "var(--text-sm)" }}>
                  {" "}
                  — {item.detail}
                </span>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
