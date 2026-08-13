import { useId, useState, type ChangeEvent, type KeyboardEvent } from "react";
import { FilePlus2, Link2, Search, Trash2 } from "lucide-react";

import { Button } from "../../components/ui/Button";
import {
  fileToSourceDraft,
  isHttpUrl,
  type SupplementalResearchSources,
  type SupplementalSourceDraft,
} from "./supplementalSources";

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function SourceCollection({
  title,
  sources,
  onChange,
  accept,
}: {
  title: string;
  sources: SupplementalSourceDraft[];
  onChange: (sources: SupplementalSourceDraft[]) => void;
  accept: string;
}) {
  const inputId = useId();
  const [url, setUrl] = useState("");
  const [urlError, setUrlError] = useState(false);

  const addUrl = () => {
    const normalized = url.trim();
    if (!isHttpUrl(normalized)) {
      setUrlError(true);
      return;
    }
    if (!sources.some((source) => source.kind === "url" && source.url === normalized)) {
      onChange([
        ...sources,
        {
          id: `url-${normalized}`,
          kind: "url",
          name: normalized,
          url: normalized,
        },
      ]);
    }
    setUrl("");
    setUrlError(false);
  };

  const addFiles = (event: ChangeEvent<HTMLInputElement>) => {
    const drafts = Array.from(event.target.files ?? []).map(fileToSourceDraft);
    const existingIds = new Set(sources.map((source) => source.id));
    onChange([...sources, ...drafts.filter((source) => !existingIds.has(source.id))]);
    event.target.value = "";
  };

  const onUrlKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addUrl();
    }
  };

  return (
    <div className="source-collection stack stack-3">
      <span className="field-label">{title}（选填）</span>
      <div className="source-entry-row">
        <div className="grow">
          <input
            className={`input ${urlError ? "input-invalid" : ""}`}
            value={url}
            onChange={(event) => {
              setUrl(event.target.value);
              setUrlError(false);
            }}
            onKeyDown={onUrlKeyDown}
            placeholder="粘贴 URL…"
            aria-label={`${title} URL`}
            aria-invalid={urlError}
          />
          {urlError && <span className="field-error">请输入有效的 http(s) URL</span>}
        </div>
        <Button variant="secondary" onClick={addUrl} disabled={!url.trim()} iconStart={<Link2 size={15} />}>
          添加 URL
        </Button>
        <label className="btn btn-secondary" htmlFor={inputId}>
          <FilePlus2 size={15} aria-hidden="true" /> 选择文件
        </label>
        <input
          id={inputId}
          className="source-file-input"
          type="file"
          multiple
          accept={accept}
          onChange={addFiles}
        />
      </div>
      {sources.length > 0 && (
        <div className="source-list">
          {sources.map((source) => (
            <div className="source-item" key={source.id}>
              <span className="source-item-icon">
                {source.kind === "url" ? <Link2 size={14} /> : <FilePlus2 size={14} />}
              </span>
              <span className="source-item-main">
                <span className="source-item-name">{source.name}</span>
                {source.kind === "file" && source.fileSize != null && (
                  <span className="subtle" style={{ fontSize: "var(--text-xs)" }}>
                    {formatBytes(source.fileSize)}
                  </span>
                )}
              </span>
              <button
                type="button"
                className="icon-btn"
                aria-label={`删除 ${source.name}`}
                onClick={() => onChange(sources.filter((item) => item.id !== source.id))}
              >
                <Trash2 size={14} aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function SupplementalSourcesPanel({
  value,
  onChange,
  onAutoResearchUnavailable,
}: {
  value: SupplementalResearchSources;
  onChange: (value: SupplementalResearchSources) => void;
  onAutoResearchUnavailable: () => void;
}) {
  return (
    <div className="card card-pad stack stack-5">
      <div className="row between wrap row-gap-3">
        <div className="row row-gap-3">
          <span className="agent-avatar" style={{ background: "var(--accent-soft)", color: "var(--accent-deep)" }}>
            <Search size={17} aria-hidden="true" />
          </span>
          <strong>研究资料</strong>
        </div>
        <button
          type="button"
          className="source-switch-row"
          role="switch"
          aria-checked={value.autoPublicResearch}
          onClick={onAutoResearchUnavailable}
        >
          <span>自动补充公开资料</span>
          <span className="source-switch" aria-hidden="true"><span /></span>
        </button>
      </div>

      <SourceCollection
        title="企业内部数据"
        sources={value.enterpriseSources}
        onChange={(enterpriseSources) => onChange({ ...value, enterpriseSources })}
        accept=".pdf,.doc,.docx,.xls,.xlsx,.csv,.txt,.md"
      />
      <SourceCollection
        title="重点调研资源"
        sources={value.focusSources}
        onChange={(focusSources) => onChange({ ...value, focusSources })}
        accept=".pdf,.doc,.docx,.txt,.md,.mp4,.mov,.webm"
      />
    </div>
  );
}
