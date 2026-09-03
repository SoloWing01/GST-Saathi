"use client";

import { useState } from "react";

export default function CitationMarker({
  index,
  source,
}: {
  index: number;
  source: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <span className="relative inline-block">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="inline-flex items-center justify-center h-5 min-w-5 px-1 rounded text-xs font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-colors cursor-pointer align-middle mx-0.5"
        aria-label={`Citation ${index}: ${source}`}
        aria-expanded={open}
      >
        {index}
      </button>
      {open && (
        <span className="absolute z-20 bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 p-3 text-sm text-ink bg-surface rounded-lg shadow-lg border border-border animate-fade-in pointer-events-auto">
          <span className="block text-ink-muted text-xs mb-1">Source</span>
          <span className="text-ink leading-relaxed">{source}</span>
          <span className="absolute top-full left-1/2 -translate-x-1/2 -mt-px border-4 border-transparent border-t-surface" />
        </span>
      )}
    </span>
  );
}
