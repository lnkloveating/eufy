import { useState, type KeyboardEvent } from "react";
import { X } from "lucide-react";

export interface TagInputProps {
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  id?: string;
  ariaLabel?: string;
  ariaDescribedby?: string;
}

/**
 * Free-form tag input. Commit a tag with Enter or comma; remove the last tag
 * with Backspace when the field is empty. Duplicates and blanks are ignored.
 */
export function TagInput({
  values,
  onChange,
  placeholder,
  id,
  ariaLabel,
  ariaDescribedby,
}: TagInputProps) {
  const [draft, setDraft] = useState("");

  const commit = (raw: string) => {
    const tag = raw.trim();
    if (!tag) return;
    if (!values.includes(tag)) {
      onChange([...values, tag]);
    }
    setDraft("");
  };

  const remove = (tag: string) => {
    onChange(values.filter((value) => value !== tag));
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      commit(draft);
    } else if (event.key === "Backspace" && !draft && values.length) {
      event.preventDefault();
      remove(values[values.length - 1] as string);
    }
  };

  return (
    <div className="taginput">
      {values.map((tag) => (
        <span className="tag-token" key={tag}>
          {tag}
          <button
            type="button"
            onClick={() => remove(tag)}
            aria-label={`移除 ${tag}`}
          >
            <X size={12} aria-hidden="true" />
          </button>
        </span>
      ))}
      <input
        id={id}
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => commit(draft)}
        placeholder={values.length ? "" : placeholder}
        aria-label={ariaLabel}
        aria-describedby={ariaDescribedby}
      />
    </div>
  );
}
