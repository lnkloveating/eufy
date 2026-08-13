import { useState } from "react";
import { AlertTriangle, Loader2, Wand2 } from "lucide-react";
import type { RankedCandidate } from "../../types/api";
import { Dialog } from "../../components/ui/Dialog";
import { Button } from "../../components/ui/Button";
import { Field } from "../../components/ui/Field";
import { TagInput } from "../../components/ui/TagInput";

export interface SelectCandidateDialogProps {
  ranked: RankedCandidate | null;
  pending: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: (input: {
    selectionReason: string | null;
    requestedChanges: string[];
  }) => void;
}

/**
 * Confirmation dialog for selecting a candidate. The confirm action triggers a
 * long-running LLM call, so the dialog shows an explicit long-loading state and
 * blocks duplicate submissions.
 */
export function SelectCandidateDialog({
  ranked,
  pending,
  error,
  onClose,
  onConfirm,
}: SelectCandidateDialogProps) {
  const [reason, setReason] = useState("");
  const [changes, setChanges] = useState<string[]>([]);

  const open = Boolean(ranked);

  return (
    <Dialog
      open={open}
      busy={pending}
      onClose={() => {
        if (pending) return;
        setReason("");
        setChanges([]);
        onClose();
      }}
      title="选择该方向并生成 ProductSpec"
      description={
        ranked ? (
          <span>
            将 <strong>{ranked.candidate.name}</strong>（排名 #{ranked.rank}）转换为标准产品定义。
          </span>
        ) : undefined
      }
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={pending}>
            取消
          </Button>
          <Button
            variant="primary"
            loading={pending}
            onClick={() =>
              onConfirm({
                selectionReason: reason.trim() ? reason.trim() : null,
                requestedChanges: changes,
              })
            }
            iconStart={!pending ? <Wand2 size={16} aria-hidden="true" /> : undefined}
          >
            {pending ? "正在生成 ProductSpec…" : "确认并生成"}
          </Button>
        </>
      }
    >
      {pending ? (
        <div className="alert alert-info" role="status">
          <Loader2 size={18} className="alert-icon spin-inline" aria-hidden="true" />
          <div className="alert-body">
            <span className="alert-title">正在将候选方向转换为标准产品定义</span>
            <span>
              该步骤由 LLM 生成完整 ProductSpec，可能需要数十秒，请勿关闭页面或重复提交。
            </span>
          </div>
        </div>
      ) : (
        <>
          <Field
            label="选择理由 Selection reason"
            hint="可选：说明你为什么选择这个方向，会写入 ProductSpec。"
          >
            {(aria) => (
              <textarea
                {...aria}
                className="textarea"
                value={reason}
                onChange={(event) => setReason(event.target.value)}
                maxLength={1000}
                rows={3}
                placeholder="例如：更契合本地隐私优先策略，长期生态价值更高…"
              />
            )}
          </Field>

          <Field
            label="希望 AI 调整的内容 Requested changes"
            hint="可选：逐条列出希望在 ProductSpec 中调整或强化的点。"
          >
            {(aria) => (
              <TagInput
                values={changes}
                onChange={setChanges}
                placeholder="输入一条调整建议后回车…"
                id={aria.id}
                ariaLabel="希望调整的内容"
              />
            )}
          </Field>

          {error && (
            <div className="alert alert-danger" role="alert">
              <AlertTriangle size={18} className="alert-icon" aria-hidden="true" />
              <div className="alert-body">
                <span className="alert-title">生成失败</span>
                <span>{error}</span>
              </div>
            </div>
          )}
        </>
      )}
    </Dialog>
  );
}
