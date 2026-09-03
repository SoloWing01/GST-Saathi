"use client";

import { useState } from "react";

const levels = {
  high: {
    bg: "bg-success-light",
    text: "text-success",
    border: "border-success/20",
    label: "High confidence",
    dot: "bg-success",
  },
  medium: {
    bg: "bg-accent-light",
    text: "text-accent",
    border: "border-accent/20",
    label: "Medium confidence",
    dot: "bg-accent",
  },
  low: {
    bg: "bg-danger-light",
    text: "text-danger",
    border: "border-danger-border/30",
    label: "Low confidence",
    dot: "bg-danger",
  },
} as const;

type ConfidenceLevel = keyof typeof levels;

export default function ConfidenceBadge({ level }: { level: ConfidenceLevel }) {
  const s = levels[level] ?? levels.medium;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-medium border ${s.bg} ${s.text} ${s.border}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  );
}
