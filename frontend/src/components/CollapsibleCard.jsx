import React, { useEffect, useState } from "react";
import { ChevronUp, ChevronDown } from "lucide-react";

const STORAGE_PREFIX = "nxt8.collapse.";

function readState(storageKey, defaultOpen) {
  if (!storageKey || typeof window === "undefined") return defaultOpen;
  try {
    const raw = window.localStorage.getItem(STORAGE_PREFIX + storageKey);
    if (raw === null) return defaultOpen;
    return raw === "1";
  } catch {
    return defaultOpen;
  }
}

function writeState(storageKey, open) {
  if (!storageKey || typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_PREFIX + storageKey, open ? "1" : "0");
  } catch {
    /* localStorage unavailable — ignore */
  }
}

/**
 * Collapsible window wrapper with persisted state in localStorage.
 *
 * Renders the canonical glass-card frame. Clicking the header strip toggles
 * the body's open/closed state. When collapsed, only the header remains
 * visible — the body is removed from layout via max-height + opacity.
 */
export default function CollapsibleCard({
  storageKey,
  title,
  titleRight,
  children,
  className = "",
  bodyClassName = "px-5 pb-5 pt-1",
  headerClassName = "px-5 py-3",
  testId,
  defaultOpen = true,
}) {
  const [open, setOpen] = useState(() => readState(storageKey, defaultOpen));

  useEffect(() => {
    writeState(storageKey, open);
  }, [storageKey, open]);

  const toggle = () => setOpen((o) => !o);

  return (
    <section
      className={`glass-card rounded-2xl window-border glow-turquoise-subtle overflow-hidden ${className}`}
      data-testid={testId}
      data-collapsed={open ? "false" : "true"}
    >
      <button
        type="button"
        onClick={toggle}
        aria-expanded={open}
        className={`w-full flex justify-between items-center cursor-pointer hover:bg-white/[0.02] transition-colors ${headerClassName}`}
        data-testid={testId ? `${testId}-toggle` : undefined}
      >
        <div className="flex items-center gap-2 min-w-0 flex-1 text-left">
          {title}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {titleRight}
          {open ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </div>
      </button>
      <div
        className={`overflow-hidden transition-[max-height,opacity] duration-300 ease-out ${
          open ? "max-h-[4000px] opacity-100" : "max-h-0 opacity-0"
        }`}
        aria-hidden={!open}
      >
        <div className={bodyClassName}>{children}</div>
      </div>
    </section>
  );
}
