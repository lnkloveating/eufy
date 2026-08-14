import { useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  FileEdit,
  Lightbulb,
  Loader2,
  MessageCircleQuestion,
  RefreshCw,
  Send,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

import type {
  ProductDesignIssue,
  ProductQuestion,
  ProductQuestionAnswer,
  ProductSpec,
  ProductSuggestedChange,
  SuggestionDisposition,
} from "../../types/api";
import {
  useApplyProductRevision,
  useAskProductQuestion,
  useDismissDesignIssues,
  useDismissSuggestions,
  useGenerateIssueProposal,
  useProductQuestions,
  useRunResult,
} from "../../lib/queries";
import {
  ANSWER_MODE_META,
  CATEGORY_META,
  DISPOSITION_META,
  EPISTEMIC_STATUS_META,
  QUICK_QUESTIONS,
  RESOLUTION_META,
  SECTION_META,
  newIdempotencyKey,
  sectionLabel,
  severityBadge,
} from "../../lib/productWorkbench";
import { formatDateTime } from "../../lib/formatters";
import { Button } from "../../components/ui/Button";
import { Dialog } from "../../components/ui/Dialog";
import { SkeletonText } from "../../components/LoadingSkeleton/LoadingSkeleton";
import { useToast } from "../../components/ui/Toast";

interface Props {
  product: ProductSpec;
  draft: string;
  onDraftChange: (value: string) => void;
  onScrollToSection: (anchor: string) => void;
}

function scrollToInput() {
  document.getElementById("copilot-input")?.scrollIntoView({ behavior: "smooth", block: "center" });
}

export function ProductDefinitionCopilot({
  product,
  draft,
  onDraftChange,
  onScrollToSection,
}: Props) {
  const toast = useToast();
  const questions = useProductQuestions(product.id);
  const ask = useAskProductQuestion(product.id);
  const applyRevision = useApplyProductRevision(product.id);
  const dismiss = useDismissSuggestions(product.id);
  const generateProposal = useGenerateIssueProposal(product.id);
  const dismissIssue = useDismissDesignIssues(product.id);
  const runResult = useRunResult(product.source_run_id, true);

  const [lastAsked, setLastAsked] = useState<string | null>(null);
  const [confirmTarget, setConfirmTarget] = useState<{
    suggestion: ProductSuggestedChange;
    disposition: SuggestionDisposition;
  } | null>(null);

  const evidenceTitles = useMemo(() => {
    const map: Record<string, string> = {};
    runResult.data?.evidence.forEach((item) => {
      map[item.id] = item.title;
    });
    runResult.data?.competitor_evidence.forEach((item) => {
      map[item.id] = `${item.brand} ${item.product_name}`;
    });
    return map;
  }, [runResult.data]);

  const busy = ask.isPending;

  function askQuestion(question: string, options: { clearDraft?: boolean } = {}) {
    const trimmed = question.trim();
    if (!trimmed || busy) return;
    setLastAsked(trimmed);
    ask.mutate(
      { question: trimmed, idempotency_key: newIdempotencyKey() },
      {
        onSuccess: () => {
          if (options.clearDraft) onDraftChange("");
        },
        onError: (error) => toast.error("提问失败", error.detail),
      },
    );
  }

  function confirmDisposition() {
    if (!confirmTarget) return;
    const previousVersion = product.version;
    applyRevision.mutate(
      {
        decisions: [
          {
            suggestion_id: confirmTarget.suggestion.id,
            disposition: confirmTarget.disposition,
          },
        ],
        idempotency_key: newIdempotencyKey(),
      },
      {
        onSuccess: (updated) => {
          setConfirmTarget(null);
          toast.success(
            "产品定义已更新",
            `已从 V${previousVersion} 更新到 V${updated.version}`,
          );
        },
        onError: (error) => toast.error("应用修改失败", error.detail),
      },
    );
  }

  function dismissSuggestion(suggestion: ProductSuggestedChange) {
    dismiss.mutate(
      { suggestion_ids: [suggestion.id] },
      {
        onSuccess: () => toast.info("已忽略该修改建议"),
        onError: (error) => toast.error("操作失败", error.detail),
      },
    );
  }

  function onGenerateProposal(questionId: string) {
    generateProposal.mutate(questionId, {
      onSuccess: () => toast.info("已根据该缺口生成修改方案", "请在下方选择是否接受。"),
      onError: (error) => toast.error("生成修改方案失败", error.detail),
    });
  }

  function onDismissIssue(issueId: string) {
    dismissIssue.mutate(
      { issue_ids: [issueId] },
      {
        onSuccess: () => toast.info("已将该缺口标记为暂不处理"),
        onError: (error) => toast.error("操作失败", error.detail),
      },
    );
  }

  const records = questions.data ?? [];
  const ordered = [...records].reverse();

  return (
    <section className="card card-pad" id="sec-copilot">
      <div className="row row-gap-2" style={{ marginBottom: "var(--space-2)" }}>
        <span
          className="agent-avatar"
          style={{ background: "var(--accent-soft)", color: "var(--accent-deep)" }}
        >
          <MessageCircleQuestion size={16} aria-hidden="true" />
        </span>
        <div className="stack stack-micro">
          <h2 className="section-title">产品定义审查 Copilot</h2>
          <span className="muted" style={{ fontSize: "var(--text-sm)" }}>
            向审查 Agent 提问。它基于研究证据、当前 eufy 能力与竞品作答，并区分证据、推断、假设与未知。
          </span>
        </div>
      </div>

      <div className="alert alert-info" role="note" style={{ margin: "var(--space-4) 0" }}>
        <ShieldAlert size={16} className="alert-icon" aria-hidden="true" />
        <div className="alert-body">
          <span>
            审查 Agent 只解释与审查产品定义，不会声称技术、商业、隐私或场景验证已通过；这些结论将由后续验证实验室产生。
          </span>
        </div>
      </div>

      {/* Quick questions */}
      <div className="taglist" style={{ marginBottom: "var(--space-4)" }}>
        {QUICK_QUESTIONS.map((quick) => (
          <button
            key={quick.label}
            type="button"
            className="option-pill"
            disabled={busy}
            onClick={() => askQuestion(quick.question)}
            title={quick.question}
          >
            <Sparkles size={13} aria-hidden="true" />
            {quick.label}
          </button>
        ))}
      </div>

      {/* Composer */}
      <form
        id="copilot-input"
        onSubmit={(event) => {
          event.preventDefault();
          askQuestion(draft, { clearDraft: true });
        }}
        className="stack stack-3"
      >
        <textarea
          className="textarea"
          value={draft}
          onChange={(event) => onDraftChange(event.target.value)}
          rows={3}
          maxLength={1000}
          disabled={busy}
          placeholder="例如：断网后还能工作吗？哪些能力可以在端侧运行？访客数据保留多久？"
          aria-label="向产品定义审查 Agent 提问"
        />
        <div className="row between wrap row-gap-2">
          <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
            回答来自后端真实 Agent，可能需要数十秒，请勿重复提交。
          </span>
          <Button
            type="submit"
            variant="primary"
            loading={busy}
            disabled={busy || !draft.trim()}
            iconStart={!busy ? <Send size={15} aria-hidden="true" /> : undefined}
          >
            {busy ? "审查 Agent 正在分析…" : "提问"}
          </Button>
        </div>
      </form>

      {busy && (
        <div className="alert alert-info" role="status" style={{ marginTop: "var(--space-4)" }}>
          <Loader2 size={16} className="alert-icon spin-inline" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">产品定义审查 Agent 正在分析…</span>
            <span>正在结合研究证据、当前能力与竞品资料生成回答。</span>
          </div>
        </div>
      )}

      {ask.isError && !busy && (
        <div className="alert alert-danger" role="alert" style={{ marginTop: "var(--space-4)" }}>
          <AlertTriangle size={16} className="alert-icon" aria-hidden="true" />
          <div className="alert-body grow">
            <span className="alert-title">提问失败</span>
            <span>{ask.error?.detail}</span>
          </div>
          {lastAsked && (
            <Button
              variant="secondary"
              className="btn-sm"
              onClick={() => askQuestion(lastAsked)}
              iconStart={<RefreshCw size={14} aria-hidden="true" />}
            >
              重试
            </Button>
          )}
        </div>
      )}

      {/* Conversation */}
      <div className="stack stack-4" style={{ marginTop: "var(--space-5)" }}>
        {questions.isLoading && !questions.data ? (
          <div className="card card-pad">
            <SkeletonText lines={4} />
          </div>
        ) : ordered.length === 0 && !busy ? (
          <p className="subtle" style={{ fontSize: "var(--text-sm)" }}>
            还没有提问。点击上方快捷问题，或直接输入你的问题。
          </p>
        ) : (
          ordered.map((record) => (
            <QaEntry
              key={record.answer.id}
              question={record.question}
              answer={record.answer}
              evidenceTitles={evidenceTitles}
              onScrollToSection={onScrollToSection}
              onFollowUp={(text) => {
                onDraftChange(text);
                scrollToInput();
              }}
              onAccept={(suggestion, disposition) =>
                setConfirmTarget({ suggestion, disposition })
              }
              onDismiss={dismissSuggestion}
              actionsBusy={applyRevision.isPending || dismiss.isPending}
              onGenerateProposal={onGenerateProposal}
              onDismissIssue={onDismissIssue}
              issueBusy={generateProposal.isPending || dismissIssue.isPending}
            />
          ))
        )}
      </div>

      <ConfirmChangeDialog
        target={confirmTarget}
        pending={applyRevision.isPending}
        onClose={() => {
          if (!applyRevision.isPending) setConfirmTarget(null);
        }}
        onConfirm={confirmDisposition}
      />
    </section>
  );
}

function QaEntry({
  question,
  answer,
  evidenceTitles,
  onScrollToSection,
  onFollowUp,
  onAccept,
  onDismiss,
  actionsBusy,
  onGenerateProposal,
  onDismissIssue,
  issueBusy,
}: {
  question: ProductQuestion;
  answer: ProductQuestionAnswer;
  evidenceTitles: Record<string, string>;
  onScrollToSection: (anchor: string) => void;
  onFollowUp: (text: string) => void;
  onAccept: (s: ProductSuggestedChange, d: SuggestionDisposition) => void;
  onDismiss: (s: ProductSuggestedChange) => void;
  actionsBusy: boolean;
  onGenerateProposal: (questionId: string) => void;
  onDismissIssue: (issueId: string) => void;
  issueBusy: boolean;
}) {
  const hasDefinitionProposal = answer.suggested_changes.some(
    (suggestion) => suggestion.kind !== "validation_hypothesis",
  );
  return (
    <div className="card card-pad stack stack-4" style={{ background: "var(--surface-2)" }}>
      <div className="row row-gap-2 wrap">
        <span className="chip chip-accent">{CATEGORY_META[answer.category]}</span>
        {answer.answer_mode !== "explanation" && (
          <span className="chip chip-outline">{ANSWER_MODE_META[answer.answer_mode]}</span>
        )}
        <strong style={{ color: "var(--ink-900)" }}>{question.question}</strong>
      </div>

      <p className="def-val" style={{ whiteSpace: "pre-wrap" }}>
        {answer.direct_answer}
      </p>

      {answer.claims.length > 0 && (
        <div className="stack stack-3">
          <span className="opp-section-label">结论与证据分级</span>
          {answer.claims.map((claim, index) => {
            const meta = EPISTEMIC_STATUS_META[claim.epistemic_status];
            const references = [...claim.evidence_ids, ...claim.competitor_evidence_ids];
            return (
              <div key={index} className="stack stack-2">
                <div className="row row-gap-2 wrap" style={{ alignItems: "flex-start" }}>
                  <span className={`badge ${meta.badge}`}>{meta.label}</span>
                  <span className="grow" style={{ minWidth: 0 }}>
                    {claim.text}
                  </span>
                </div>
                {references.length > 0 && (
                  <div className="row row-gap-2 wrap" style={{ paddingLeft: 2 }}>
                    <span className="subtle" style={{ fontSize: 11 }}>
                      证据
                    </span>
                    {references.map((id) => (
                      <span key={id} className="chip chip-evidence" title={id}>
                        {evidenceTitles[id] ?? id}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {answer.assumptions.length > 0 && (
        <div className="stack stack-2">
          <span className="opp-section-label">设计假设</span>
          <Bullets items={answer.assumptions} />
        </div>
      )}

      {answer.unknowns.length > 0 && (
        <div className="stack stack-2">
          <span className="opp-section-label">未知项 / 待验证</span>
          <Bullets items={answer.unknowns} />
        </div>
      )}

      {answer.integrity_notes.length > 0 && (
        <div className="alert alert-warn" role="note">
          <ShieldAlert size={16} className="alert-icon" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">证据完整性提示</span>
            {answer.integrity_notes.map((note, index) => (
              <span key={index}>{note}</span>
            ))}
          </div>
        </div>
      )}

      {answer.affected_sections.length > 0 && (
        <div className="row row-gap-2 wrap">
          <span className="subtle" style={{ fontSize: 11 }}>
            相关章节
          </span>
          {answer.affected_sections.map((section) => (
            <button
              key={section}
              type="button"
              className="chip chip-outline"
              style={{ cursor: "pointer" }}
              onClick={() => {
                const anchor = SECTION_META[section]?.anchor;
                if (anchor) onScrollToSection(anchor);
              }}
            >
              {sectionLabel(section)}
            </button>
          ))}
        </div>
      )}

      {answer.design_issue && (
        <DesignIssueCard
          issue={answer.design_issue}
          hasProposal={hasDefinitionProposal}
          busy={issueBusy}
          onScrollToSection={onScrollToSection}
          onGenerate={() => onGenerateProposal(question.id)}
          onDismiss={() => answer.design_issue && onDismissIssue(answer.design_issue.id)}
        />
      )}

      {answer.suggested_changes.length > 0 && (
        <div className="stack stack-3">
          <span className="opp-section-label">
            {answer.design_issue
              ? "需要你确认的产品定义与验证建议"
              : "需要你确认的建议"}
          </span>
          {answer.suggested_changes.map((suggestion) => (
            <SuggestionCard
              key={suggestion.id}
              suggestion={suggestion}
              busy={actionsBusy}
              onAccept={onAccept}
              onDismiss={onDismiss}
              onFollowUp={onFollowUp}
            />
          ))}
        </div>
      )}

      <span className="tl-time">{formatDateTime(answer.created_at)}</span>
    </div>
  );
}

function DesignIssueCard({
  issue,
  hasProposal,
  busy,
  onScrollToSection,
  onGenerate,
  onDismiss,
}: {
  issue: ProductDesignIssue;
  hasProposal: boolean;
  busy: boolean;
  onScrollToSection: (anchor: string) => void;
  onGenerate: () => void;
  onDismiss: () => void;
}) {
  const resolved = issue.resolution ? RESOLUTION_META[issue.resolution] : null;
  return (
    <div className="alert alert-warn" role="note">
      <ShieldAlert size={18} className="alert-icon" aria-hidden="true" />
      <div className="alert-body grow" style={{ gap: "var(--space-2)" }}>
        <div className="row between wrap row-gap-2">
          <span className="alert-title">发现一个产品定义缺口：{issue.title}</span>
          <div className="row row-gap-2 wrap">
            <span className={`badge ${severityBadge(issue.severity)}`}>{issue.severity}</span>
            {issue.blocks_readiness && (
              <span className="badge badge-failed">影响验证准备度</span>
            )}
            {resolved && <span className={`badge ${resolved.badge}`}>{resolved.label}</span>}
          </div>
        </div>
        <span>{issue.description}</span>
        <span className="muted" style={{ fontSize: "var(--text-sm)" }}>
          判定理由：{issue.reason}
        </span>
        {issue.affected_sections.length > 0 && (
          <div className="row row-gap-2 wrap">
            <span className="subtle" style={{ fontSize: 11 }}>
              影响章节
            </span>
            {issue.affected_sections.map((section) => (
              <button
                key={section}
                type="button"
                className="chip chip-outline"
                style={{ cursor: "pointer" }}
                onClick={() => {
                  const anchor = SECTION_META[section]?.anchor;
                  if (anchor) onScrollToSection(anchor);
                }}
              >
                {sectionLabel(section)}
              </button>
            ))}
          </div>
        )}
        {!resolved && !hasProposal && (
          <div className="row row-gap-2 wrap" style={{ marginTop: "var(--space-1)" }}>
            <Button
              variant="primary"
              className="btn-sm"
              loading={busy}
              disabled={busy}
              onClick={onGenerate}
              iconStart={!busy ? <Lightbulb size={14} aria-hidden="true" /> : undefined}
            >
              生成修改方案
            </Button>
            <Button variant="ghost" className="btn-sm" disabled={busy} onClick={onDismiss}>
              暂不处理
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function SuggestionCard({
  suggestion,
  busy,
  onAccept,
  onDismiss,
  onFollowUp,
}: {
  suggestion: ProductSuggestedChange;
  busy: boolean;
  onAccept: (s: ProductSuggestedChange, d: SuggestionDisposition) => void;
  onDismiss: (s: ProductSuggestedChange) => void;
  onFollowUp: (text: string) => void;
}) {
  const resolved = suggestion.resolution ? RESOLUTION_META[suggestion.resolution] : null;
  const isValidationProposal = suggestion.kind === "validation_hypothesis";
  return (
    <div className="card" style={{ padding: "var(--space-4)" }}>
      <div className="row between wrap row-gap-2" style={{ alignItems: "flex-start" }}>
        <span className="chip chip-outline">
          <FileEdit size={12} aria-hidden="true" />
          {isValidationProposal ? "Validation 候选" : sectionLabel(suggestion.section)}
        </span>
        {resolved && <span className={`badge ${resolved.badge}`}>{resolved.label}</span>}
      </div>
      {isValidationProposal && !resolved && (
        <div className="alert alert-info" role="note" style={{ marginTop: "var(--space-3)" }}>
          <Lightbulb size={16} className="alert-icon" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">是否根据本次提问增加一个 Validation？</span>
            <span>Copilot 只生成候选；只有你确认后，它才会写入 Validation Readiness 并生成新版本。</span>
          </div>
        </div>
      )}
      <div className="deflist" style={{ marginTop: "var(--space-3)" }}>
        <Def label={isValidationProposal ? "当前状态" : "当前定义"} value={suggestion.current_summary} />
        <Def label={isValidationProposal ? "待验证假设" : "建议修改"} value={suggestion.proposed_change} />
        {isValidationProposal && suggestion.validation_hypothesis && (
          <>
            <Def label="衡量指标" value={suggestion.validation_hypothesis.metric} />
            <Def label="验证方法" value={suggestion.validation_hypothesis.proposed_method} />
            <Def label="通过条件" value={suggestion.validation_hypothesis.pass_condition} />
            <Def label="终止条件" value={suggestion.validation_hypothesis.kill_condition} />
          </>
        )}
        <Def label="理由" value={suggestion.rationale} />
      </div>
      {!resolved && (
        <div className="row row-gap-2 wrap" style={{ marginTop: "var(--space-4)" }}>
          {isValidationProposal ? (
            <Button
              variant="primary"
              className="btn-sm"
              disabled={busy}
              onClick={() => onAccept(suggestion, "as_hypothesis")}
              iconStart={<Check size={14} aria-hidden="true" />}
            >
              加入 Validation
            </Button>
          ) : (
            <>
              <Button
                variant="primary"
                className="btn-sm"
                disabled={busy}
                onClick={() => onAccept(suggestion, "apply")}
                iconStart={<Check size={14} aria-hidden="true" />}
              >
                {DISPOSITION_META.apply}
              </Button>
              <Button
                variant="secondary"
                className="btn-sm"
                disabled={busy}
                onClick={() => onAccept(suggestion, "as_risk")}
              >
                {DISPOSITION_META.as_risk}
              </Button>
              <Button
                variant="secondary"
                className="btn-sm"
                disabled={busy}
                onClick={() => onAccept(suggestion, "as_hypothesis")}
              >
                {DISPOSITION_META.as_hypothesis}
              </Button>
            </>
          )}
          <Button
            variant="ghost"
            className="btn-sm"
            disabled={busy}
            onClick={() => onDismiss(suggestion)}
          >
            {isValidationProposal ? "暂不加入" : DISPOSITION_META.dismiss}
          </Button>
          <Button
            variant="ghost"
            className="btn-sm"
            disabled={busy}
            onClick={() =>
              onFollowUp(
                `关于「${sectionLabel(suggestion.section)}」的建议：${suggestion.proposed_change} 请进一步解释其依据与影响。`,
              )
            }
          >
            继续追问
          </Button>
        </div>
      )}
    </div>
  );
}

function ConfirmChangeDialog({
  target,
  pending,
  onClose,
  onConfirm,
}: {
  target: { suggestion: ProductSuggestedChange; disposition: SuggestionDisposition } | null;
  pending: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog
      open={Boolean(target)}
      busy={pending}
      onClose={onClose}
      title="确认修改产品定义"
      description={
        target ? (
          <span>
            {target.suggestion.kind === "validation_hypothesis" ? (
              <>
                将把这条候选写入 <strong>Validation Readiness</strong>。这会生成新的 ProductSpec 版本。
              </>
            ) : (
              <>
                将对「{sectionLabel(target.suggestion.section)}」执行：
                <strong> {DISPOSITION_META[target.disposition]}</strong>。这会生成新的 ProductSpec 版本。
              </>
            )}
          </span>
        ) : undefined
      }
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={pending}>
            取消
          </Button>
          <Button variant="primary" loading={pending} onClick={onConfirm}>
            {pending ? "正在生成新版本…" : "确认并生成新版本"}
          </Button>
        </>
      }
    >
      {target && (
        <div className="deflist">
          <Def label="建议修改" value={target.suggestion.proposed_change} />
          <Def label="理由" value={target.suggestion.rationale} />
        </div>
      )}
    </Dialog>
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
