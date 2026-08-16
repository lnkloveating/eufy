import { useState, type FormEvent } from "react";
import { CheckCircle2, ShieldCheck } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import type { SurveyAnswerValue, SurveyQuestion } from "../../types/api";
import { usePublicSurvey, useSubmitSurveyResponse } from "../../lib/queries";
import { ApiError } from "../../lib/api/client";
import { Button } from "../../components/ui/Button";
import { EmptyState } from "../../components/EmptyState/EmptyState";
import { ErrorState } from "../../components/ErrorState/ErrorState";

function QuestionInput({
  question,
  value,
  onChange,
}: {
  question: SurveyQuestion;
  value: SurveyAnswerValue | undefined;
  onChange: (value: SurveyAnswerValue) => void;
}) {
  if (question.question_type === "rating") {
    return (
      <div className="survey-rating" role="radiogroup" aria-label={question.prompt}>
        {Array.from(
          { length: question.rating_max - question.rating_min + 1 },
          (_, index) => question.rating_min + index,
        ).map((rating) => (
          <button
            type="button"
            key={rating}
            className={value === rating ? "is-selected" : ""}
            onClick={() => onChange(rating)}
            aria-pressed={value === rating}
          >
            <strong>{rating}</strong>
            <span>{rating === question.rating_min ? "很低" : rating === question.rating_max ? "很高" : ""}</span>
          </button>
        ))}
      </div>
    );
  }
  if (question.question_type === "long_text") {
    return (
      <textarea
        className="survey-textarea"
        rows={4}
        maxLength={1200}
        value={typeof value === "string" ? value : ""}
        onChange={(event) => onChange(event.target.value)}
        placeholder="请填写你的真实顾虑或建议（选填）"
      />
    );
  }
  const selected = Array.isArray(value) ? value : [];
  const multiple = question.question_type === "multiple_choice";
  return (
    <div className="survey-options">
      {question.options.map((option) => {
        const checked = multiple ? selected.includes(option) : value === option;
        return (
          <label key={option} className={checked ? "is-selected" : ""}>
            <input
              type={multiple ? "checkbox" : "radio"}
              name={question.id}
              checked={checked}
              onChange={() => {
                if (!multiple) return onChange(option);
                onChange(
                  checked
                    ? selected.filter((item) => item !== option)
                    : [...selected, option],
                );
              }}
            />
            <span>{option}</span>
          </label>
        );
      })}
    </div>
  );
}

export function PublicSurveyPage() {
  const { token } = useParams<{ token: string }>();
  const survey = usePublicSurvey(token);
  const submit = useSubmitSurveyResponse(token ?? "");
  const [answers, setAnswers] = useState<Record<string, SurveyAnswerValue>>({});
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  if (survey.isLoading) {
    return <div className="survey-public-shell"><div className="survey-public-card">正在加载调查…</div></div>;
  }
  if (survey.isError || !survey.data) {
    const notFound = survey.error instanceof ApiError && survey.error.isNotFound;
    return (
      <div className="survey-public-shell">
        <div className="survey-public-card">
          {notFound ? (
            <EmptyState title="调查链接无效" description="该调查不存在、已关闭或链接不完整。" />
          ) : (
            <ErrorState title="无法加载调查" error={survey.error} onRetry={() => survey.refetch()} />
          )}
        </div>
      </div>
    );
  }
  if (submit.isSuccess) {
    return (
      <div className="survey-public-shell">
        <div className="survey-public-card survey-success">
          <CheckCircle2 size={44} aria-hidden="true" />
          <h1>提交成功，感谢参与</h1>
          <p>{submit.data.message}</p>
          <span className="chip chip-outline">
            当前共 {submit.data.total_responses} 份 · {submit.data.sample_status_label}
          </span>
          <Link to="/">返回 eufy FutureLab</Link>
        </div>
      </div>
    );
  }

  const access = survey.data;
  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const missing = access.survey.questions.find((question) => {
      if (!question.required) return false;
      const value = answers[question.id];
      return value === undefined || value === "" || (Array.isArray(value) && value.length === 0);
    });
    if (missing) {
      setValidationMessage(`请完成必填问题：“${missing.prompt}”`);
      document.getElementById(`survey-${missing.id}`)?.scrollIntoView({ behavior: "smooth" });
      return;
    }
    setValidationMessage(null);
    submit.mutate({ answers });
  }

  return (
    <div className="survey-public-shell">
      <main className="survey-public-card">
        <header className="survey-public-header">
          <div className="survey-brand">eufy FutureLab · 真实用户调研</div>
          <h1>{access.survey.title}</h1>
          <p>{access.survey.description}</p>
          <div className="survey-privacy-note">
            <ShieldCheck size={17} aria-hidden="true" />
            匿名提交，不收集姓名、住址或设备标识
          </div>
        </header>
        <form onSubmit={onSubmit} className="survey-form">
          {access.survey.questions.map((question, index) => (
            <fieldset id={`survey-${question.id}`} key={question.id}>
              <legend>
                <span>{index + 1}</span>
                {question.prompt}
                {question.required && <em>必填</em>}
              </legend>
              <QuestionInput
                question={question}
                value={answers[question.id]}
                onChange={(value) =>
                  setAnswers((current) => ({ ...current, [question.id]: value }))
                }
              />
              {question.linked_experiment_id && (
                <small className="survey-boundary">{question.evidence_boundary}</small>
              )}
            </fieldset>
          ))}
          {(validationMessage || submit.isError) && (
            <div className="alert alert-danger" role="alert">
              {validationMessage ?? submit.error?.detail}
            </div>
          )}
          <Button variant="primary" loading={submit.isPending} type="submit">
            提交调查
          </Button>
          <p className="survey-footer-note">提交结果会回流到该产品的验证实验室，仅用于方向性研究判断。</p>
        </form>
      </main>
    </div>
  );
}
