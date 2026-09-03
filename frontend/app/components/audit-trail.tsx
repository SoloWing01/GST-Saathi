"use client";

import { useState } from "react";

type AuditEntry = {
  step: string;
  action: string;
  result: string;
  details?: string;
};

export default function AuditTrail({ entries }: { entries: AuditEntry[] }) {
  const [expanded, setExpanded] = useState(false);

  if (!entries.length) return null;

  return (
    <div className="border-t border-border mt-8 pt-6">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-sm text-ink-muted hover:text-ink transition-colors cursor-pointer"
        aria-expanded={expanded}
      >
        <svg
          className={`h-4 w-4 transition-transform ${expanded ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
        Full audit trail ({entries.length} steps)
      </button>

      {expanded && (
        <div className="mt-4 space-y-0 animate-fade-in">
          {entries.map((entry, i) => (
            <div
              key={i}
              className="flex gap-3 py-3 border-b border-border last:border-0"
            >
              <span className="text-xs font-mono text-ink-faint mt-0.5 shrink-0 w-5 text-right">
                {i + 1}
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink">{entry.step}</p>
                <p className="text-sm text-ink-muted mt-0.5">{entry.action}</p>
                <p className="text-sm text-ink-faint mt-0.5">{entry.result}</p>
                {entry.details && (
                  <p className="text-xs text-ink-faint mt-1 font-mono">
                    {entry.details}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
