import { useState } from "react";
import { HelpCircle, Wand2 } from "lucide-react";

import { Dialog } from "../../components/ui/Dialog";
import { Button } from "../../components/ui/Button";
import { TagInput } from "../../components/ui/TagInput";
import {
  type ClarificationKey,
  type ClarificationQuestion,
  type ContextClarificationKey,
  MIN_QUESTION_LENGTH,
  type ResearchBrief,
} from "./researchBrief";

type Answers = Partial<Record<ClarificationKey, string[]>>;

function seedAnswers(brief: ResearchBrief, questions: ClarificationQuestion[]): Answers {
  const seed: Answers = {};
  for (const question of questions) {
    switch (question.key) {
      case "regions":
        seed.regions = [...brief.regions];
        break;
      case "target_users":
        seed.target_users = [...brief.target_users];
        break;
      case "forecast_horizon_years":
        seed.forecast_horizon_years =
          brief.forecast_horizon_years != null ? [String(brief.forecast_horizon_years)] : [];
        break;
      case "question":
        seed.question = brief.question ? [brief.question] : [];
        break;
      default: {
        const value = brief.research_context[question.key as ContextClarificationKey];
        seed[question.key] = Array.isArray(value) ? [...value] : value ? [value] : [];
      }
    }
  }
  return seed;
}

export interface ClarificationDialogProps {
  open: boolean;
  questions: ClarificationQuestion[];
  brief: ResearchBrief;
  onCancel: () => void;
  onConfirm: (answers: Answers) => void;
}

/** Asks ONLY the currently-missing required fields before any backend call. */
export function ClarificationDialog({
  open,
  questions,
  brief,
  onCancel,
  onConfirm,
}: ClarificationDialogProps) {
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title="补全 Research Brief"
      description="必填项决定研究范围；建议项会直接影响 RAG 取证和多 Agent 的产品判断，也可以留空让 AI 保持开放探索。"
    >
      {open && (
        <ClarificationForm
          key={questions.map((q) => q.key).join("|")}
          questions={questions}
          brief={brief}
          onCancel={onCancel}
          onConfirm={onConfirm}
        />
      )}
    </Dialog>
  );
}

function ClarificationForm({
  questions,
  brief,
  onCancel,
  onConfirm,
}: {
  questions: ClarificationQuestion[];
  brief: ResearchBrief;
  onCancel: () => void;
  onConfirm: (answers: Answers) => void;
}) {
  const [answers, setAnswers] = useState<Answers>(() => seedAnswers(brief, questions));

  const setAnswer = (key: ClarificationKey, value: string[]) =>
    setAnswers((prev) => ({ ...prev, [key]: value }));

  const isRequiredAnswerValid = (question: ClarificationQuestion) => {
    const value = answers[question.key] ?? [];
    if (!value.length) return false;
    return question.key !== "question" || (value[0]?.trim().length ?? 0) >= MIN_QUESTION_LENGTH;
  };
  const requiredQuestions = questions.filter((question) => question.required);
  const isComplete = requiredQuestions.every(isRequiredAnswerValid);
  const completedCount = questions.filter(
    (question) => (answers[question.key]?.length ?? 0) > 0,
  ).length;

  return (
    <div className="stack stack-5">
      <div className="row between wrap row-gap-2">
        <span className="subtle" style={{ fontSize: "var(--text-sm)" }}>
          已回答 {completedCount} / {questions.length} 项
        </span>
        <span className="chip chip-accent">带 * 为必填，其余可跳过</span>
      </div>
      {questions.map((question, index) => (
        <div className="stack stack-3" key={question.key}>
          {(index === 0 || questions[index - 1]?.section !== question.section) && (
            <span className="eyebrow" style={{ marginTop: index ? "var(--space-3)" : 0 }}>
              {question.section}
            </span>
          )}
          <span className="field-label">
            <HelpCircle size={15} aria-hidden="true" /> {question.title}
            {question.required ? " *" : ""}
          </span>
          {question.description && (
            <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
              {question.description}
            </span>
          )}
          <ClarificationControl
            question={question}
            value={answers[question.key] ?? []}
            onChange={(value) => setAnswer(question.key, value)}
          />
        </div>
      ))}

      <div className="row between wrap row-gap-3">
        <Button variant="ghost" onClick={onCancel}>
          返回修改
        </Button>
        <Button
          variant="primary"
          disabled={!isComplete}
          onClick={() => onConfirm(answers)}
          iconStart={<Wand2 size={16} aria-hidden="true" />}
        >
          {requiredQuestions.length ? "确认 Research Brief" : "继续（可跳过建议项）"}
        </Button>
      </div>
    </div>
  );
}

function ClarificationControl({
  question,
  value,
  onChange,
}: {
  question: ClarificationQuestion;
  value: string[];
  onChange: (value: string[]) => void;
}) {
  if (question.kind === "text") {
    return (
      <textarea
        className="textarea"
        rows={2}
        value={value[0] ?? ""}
        onChange={(event) => onChange(event.target.value ? [event.target.value] : [])}
        placeholder="用一句话描述你的研究问题（至少 12 个字符）…"
        aria-label={question.title}
      />
    );
  }

  const optionValues = question.options.map((option) => option.value);
  const customValues = value.filter((item) => !optionValues.includes(item));

  const toggle = (optionValue: string) => {
    if (question.multi) {
      onChange(
        value.includes(optionValue)
          ? value.filter((item) => item !== optionValue)
          : [...value, optionValue],
      );
    } else {
      onChange([optionValue]);
    }
  };

  return (
    <div className="stack stack-3">
      <div className="optiongrid">
        {question.options.map((option) => (
          <button
            key={option.value}
            type="button"
            className={`option-pill ${value.includes(option.value) ? "is-on" : ""}`}
            aria-pressed={value.includes(option.value)}
            onClick={() => toggle(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>
      {question.allowCustom && question.kind === "number" && (
        <input
          className="input"
          type="number"
          min={1}
          max={10}
          placeholder="自定义年数（1–10）"
          aria-label="自定义预测周期"
          onChange={(event) => {
            const raw = event.target.value.trim();
            onChange(raw ? [raw] : []);
          }}
        />
      )}
      {question.allowCustom && question.kind === "list" && (
        <TagInput
          values={customValues}
          onChange={(next) => onChange([...value.filter((item) => optionValues.includes(item)), ...next])}
          placeholder="自定义后回车…"
          ariaLabel={`${question.title} 自定义`}
        />
      )}
    </div>
  );
}
