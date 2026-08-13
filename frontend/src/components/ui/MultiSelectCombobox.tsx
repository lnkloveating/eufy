import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Check, ChevronDown, Search, X } from "lucide-react";

export interface MultiSelectComboboxProps {
  options: string[];
  values: string[];
  onChange: (values: string[]) => void;
  formatOptionLabel?: (option: string) => string;
  placeholder?: string;
  id?: string;
  ariaLabel?: string;
  ariaDescribedby?: string;
  allowCustom?: boolean;
  emptyText?: string;
}

function dedupe(values: string[]) {
  return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

export function MultiSelectCombobox({
  options,
  values,
  onChange,
  formatOptionLabel,
  placeholder = "搜索或选择…",
  id,
  ariaLabel,
  ariaDescribedby,
  allowCustom = false,
  emptyText = "没有匹配项",
}: MultiSelectComboboxProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const normalizedOptions = useMemo(() => dedupe(options), [options]);
  const selectedSet = useMemo(() => new Set(values), [values]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return normalizedOptions;
    return normalizedOptions.filter((option) => option.toLowerCase().includes(q));
  }, [normalizedOptions, query]);

  const customCandidate = useMemo(() => {
    const value = query.trim();
    if (!allowCustom || !value) return null;
    const exists = normalizedOptions.some((option) => option.toLowerCase() === value.toLowerCase());
    const alreadySelected = values.some((option) => option.toLowerCase() === value.toLowerCase());
    return exists || alreadySelected ? null : value;
  }, [allowCustom, normalizedOptions, query, values]);

  useEffect(() => {
    const onPointerDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  const commit = (option: string) => {
    const next = selectedSet.has(option)
      ? values.filter((value) => value !== option)
      : [...values, option];
    onChange(dedupe(next));
    setQuery("");
    setOpen(true);
    inputRef.current?.focus();
  };

  const remove = (option: string) => {
    onChange(values.filter((value) => value !== option));
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      if (filtered[0] && query.trim()) {
        commit(filtered[0]);
        return;
      }
      if (customCandidate) {
        commit(customCandidate);
      }
    } else if (event.key === "Backspace" && !query && values.length) {
      event.preventDefault();
      remove(values[values.length - 1] as string);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="multicombobox" ref={rootRef}>
      <div
        className={`multicombobox-control ${open ? "is-open" : ""}`}
        onClick={() => {
          setOpen(true);
          inputRef.current?.focus();
        }}
      >
        <div className="multicombobox-values">
          {values.map((value) => (
            <span className="tag-token" key={value}>
              {formatOptionLabel ? formatOptionLabel(value) : value}
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  remove(value);
                }}
                aria-label={`移除 ${value}`}
              >
                <X size={12} aria-hidden="true" />
              </button>
            </span>
          ))}
          <div className="multicombobox-input-wrap">
            <Search size={14} aria-hidden="true" className="multicombobox-search" />
            <input
              ref={inputRef}
              id={id}
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setOpen(true);
              }}
              onFocus={() => setOpen(true)}
              onKeyDown={onKeyDown}
              placeholder={values.length ? "" : placeholder}
              aria-label={ariaLabel}
              aria-describedby={ariaDescribedby}
            />
          </div>
        </div>
        <ChevronDown size={16} aria-hidden="true" className="multicombobox-caret" />
      </div>

      {open && (
        <div className="multicombobox-menu" role="listbox" aria-multiselectable="true">
          {filtered.map((option) => {
            const selected = selectedSet.has(option);
            return (
              <button
                key={option}
                type="button"
                className={`multicombobox-option ${selected ? "is-selected" : ""}`}
                onClick={() => commit(option)}
              >
                <span>{formatOptionLabel ? formatOptionLabel(option) : option}</span>
                {selected && <Check size={14} aria-hidden="true" />}
              </button>
            );
          })}

          {!filtered.length && customCandidate && (
            <button
              type="button"
              className="multicombobox-option multicombobox-option-create"
              onClick={() => commit(customCandidate)}
            >
              <span>添加自定义地区 “{customCandidate}”</span>
            </button>
          )}

          {!filtered.length && !customCandidate && (
            <div className="multicombobox-empty">{emptyText}</div>
          )}
        </div>
      )}
    </div>
  );
}
