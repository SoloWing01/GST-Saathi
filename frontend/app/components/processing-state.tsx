"use client";

import { useEffect, useState } from "react";

const steps = [
  { id: "extract", label: "Extracting notice text" },
  { id: "fields", label: "Reading notice fields" },
  { id: "match", label: "Matching transactions" },
  { id: "rules", label: "Checking GST rules" },
  { id: "reason", label: "Generating explanation" },
];

export default function ProcessingState() {
  const [completed, setCompleted] = useState<number>(0);

  useEffect(() => {
    let step = 0;
    const timers: ReturnType<typeof setTimeout>[] = [];

    function scheduleNext() {
      step++;
      if (step <= steps.length) {
        timers.push(
          setTimeout(() => {
            setCompleted(step);
            scheduleNext();
          }, 800 + Math.random() * 600)
        );
      }
    }

    const first = setTimeout(() => {
      setCompleted(1);
      scheduleNext();
    }, 600);
    timers.push(first);

    return () => timers.forEach(clearTimeout);
  }, []);

  return (
    <div className="w-full max-w-md mx-auto animate-fade-in">
      <div className="bg-surface rounded-2xl border border-border p-8 shadow-sm">
        <div className="flex items-center gap-3 mb-6">
          <div className="h-2 w-2 rounded-full bg-accent animate-pulse-dot" />
          <p className="text-sm font-medium text-ink-muted">
            Analyzing your notice...
          </p>
        </div>

        <div className="space-y-3">
          {steps.map((step, i) => {
            const done = i < completed;
            const active = i === completed - 1 && completed < steps.length;

            return (
              <div
                key={step.id}
                className="flex items-center gap-3"
                style={{ animationDelay: `${i * 60}ms` }}
              >
                <div
                  className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full transition-all duration-300 ${
                    done
                      ? "bg-success text-white"
                      : active
                        ? "bg-accent/10 text-accent"
                        : "bg-ground-warm text-ink-faint"
                  }`}
                >
                  {done ? (
                    <svg
                      className="h-3.5 w-3.5 animate-check"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={3}
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M4.5 12.75l6 6 9-13.5"
                      />
                    </svg>
                  ) : active ? (
                    <div className="h-2 w-2 rounded-full bg-accent animate-pulse-dot" />
                  ) : (
                    <div className="h-2 w-2 rounded-full bg-ink-faint/30" />
                  )}
                </div>
                <span
                  className={`text-sm transition-colors duration-300 ${
                    done
                      ? "text-ink"
                      : active
                        ? "text-ink font-medium"
                        : "text-ink-faint"
                  }`}
                >
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
