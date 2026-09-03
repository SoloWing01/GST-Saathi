"use client";

import { useState, useCallback, useEffect } from "react";
import ProcessingState from "./components/processing-state";
import ResultsView from "./components/results-view";
import SettingsPanel from "./components/settings-panel";
import type { CredentialStatus } from "./components/settings-panel";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

function getTenantId(): string {
  if (typeof window === "undefined") return "default";
  try {
    let id = window.localStorage.getItem("gst_tenant_id");
    if (!id) {
      id = `tenant-${Date.now().toString(36)}-${Math.random()
        .toString(36)
        .slice(2, 8)}`;
      window.localStorage.setItem("gst_tenant_id", id);
    }
    return id;
  } catch {
    return "default";
  }
}

type PipelineResult = {
  extraction: {
    fields: Record<string, unknown>;
    confidence: string;
    missing_fields: string[];
    provider_used: string;
  };
  cross_reference: {
    matched_transactions: Array<{
      payment_id: string;
      amount: number;
      date: string;
      status: string;
    }>;
    flagged_transactions: Array<{
      payment_id: string;
      amount: number;
      date: string;
      status: string;
      mismatch_reason?: string;
    }>;
    kb_entry: unknown;
    total_transactions_in_period: number;
    total_amount_in_period: number;
    total_tax_in_period: number;
  };
  explanation: {
    sections: {
      what_it_means?: { title: string; content: string; citations: any[] };
      why_you_got_it?: { title: string; content: string; citations: any[] };
      what_to_do?: { title: string; content: string; citations: any[] };
      confidence?: { title: string; content: string; citations: any[] };
    };
    overall_confidence: string;
    is_low_confidence: boolean;
    ca_escalation_note?: string;
    provider_used: string;
  };
  audit_log: Array<{
    step: string;
    action: string;
    result: string;
    details?: string;
  }>;
};

type AppStep = "input" | "processing" | "results" | "error";

export default function UploadClient() {
  const [selected, setSelected] = useState<File | null>(null);
  const [pastedText, setPastedText] = useState("");
  const [mode, setMode] = useState<"file" | "paste">("paste");
  const [step, setStep] = useState<AppStep>("input");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [tenantId, setTenantId] = useState<string>("default");
  const [keysReady, setKeysReady] = useState(false);

  useEffect(() => {
    setTenantId(getTenantId());
  }, []);

  const [credStatus, setCredStatus] = useState<CredentialStatus | null>(null);

  const reset = useCallback(() => {
    setStep("input");
    setResult(null);
    setError(null);
    setSelected(null);
    setPastedText("");
  }, []);

  const handleAnalyze = useCallback(async () => {
    setStep("processing");
    setError(null);
    setResult(null);

    try {
      let res: Response;
      const headers: Record<string, string> = { "X-Tenant-ID": tenantId };

      if (mode === "paste") {
        if (!pastedText.trim()) {
          setError("Paste some notice text first.");
          setStep("input");
          return;
        }
        res = await fetch(`${BACKEND_URL}/api/analyze-full`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...headers },
          body: JSON.stringify({ text: pastedText }),
        });
      } else {
        if (!selected) {
          setError("Choose a file first.");
          setStep("input");
          return;
        }
        const form = new FormData();
        form.append("file", selected);
        res = await fetch(`${BACKEND_URL}/api/upload-and-explain`, {
          method: "POST",
          headers,
          body: form,
        });
      }

      if (!res.ok) {
        const text = await res.text();
        let detail = `Server error ${res.status}`;
        try {
          const parsed = JSON.parse(text);
          if (parsed && parsed.detail) {
            detail = parsed.detail;
          }
        } catch {
          detail = text.trim() ? text : detail;
        }
        throw new Error(detail);
      }

      const data: PipelineResult = await res.json();
      setResult(data);
      setStep("results");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes("Unexpected token") || msg.includes("JSON")) {
        setError("The backend returned an unexpected response. Check the backend logs.");
      } else {
        setError(msg);
      }
      setStep("error");
    }
  }, [mode, pastedText, selected, tenantId]);

  const canSubmit =
    keysReady &&
    ((mode === "paste" && pastedText.trim()) ||
    (mode === "file" && selected));

  return (
    <div className="w-full max-w-2xl mx-auto">
      {step === "input" && (
        <div className="animate-fade-in">
          {/* API key setup — always shown */}
          <div className="mb-4">
            <SettingsPanel
              tenantId={tenantId}
              onUpdated={setCredStatus}
              onReadyChange={setKeysReady}
            />
          </div>

          {/* Warning banner when keys not ready */}
          {!keysReady && (
            <div className="mb-4 p-3 rounded-xl bg-accent-light/15 border border-accent/25 text-sm text-ink animate-fade-in">
              <p className="font-medium text-accent-dark">
                You must set up your API keys before using this application.
              </p>
              <p className="text-xs text-ink-muted mt-1">
                Provide at least one LLM key (Groq or Gemini) and at least one of
                Supabase, Postgres, or a payment provider (Razorpay / PayPal).
                Expand the settings panel above to get started.
              </p>
            </div>
          )}

          {/* Input method cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
            {/* Paste text card */}
            <button
              type="button"
              onClick={() => setMode("paste")}
              className={`flex items-start gap-3 p-4 rounded-2xl border text-left transition-all cursor-pointer ${
                mode === "paste"
                  ? "border-accent bg-accent-light/10 shadow-sm"
                  : "border-border bg-surface hover:border-accent/30"
              }`}
            >
              <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                mode === "paste" ? "bg-accent text-accent-foreground" : "bg-ground-warm text-ink-muted"
              }`}>
                <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                </svg>
              </div>
              <div>
                <p className={`text-sm font-semibold ${mode === "paste" ? "text-ink" : "text-ink"}`}>Paste text</p>
                <p className="text-xs text-ink-muted mt-0.5">Copy-paste text from a GST notice</p>
              </div>
            </button>

            {/* Upload file card */}
            <button
              type="button"
              onClick={() => setMode("file")}
              className={`flex items-start gap-3 p-4 rounded-2xl border text-left transition-all cursor-pointer ${
                mode === "file"
                  ? "border-accent bg-accent-light/10 shadow-sm"
                  : "border-border bg-surface hover:border-accent/30"
              }`}
            >
              <div className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                mode === "file" ? "bg-accent text-accent-foreground" : "bg-ground-warm text-ink-muted"
              }`}>
                <svg className="h-4.5 w-4.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
                </svg>
              </div>
              <div>
                <p className={`text-sm font-semibold ${mode === "file" ? "text-ink" : "text-ink"}`}>Upload file</p>
                <p className="text-xs text-ink-muted mt-0.5">PDF, image, or text file</p>
              </div>
            </button>
          </div>

          {/* Input area */}
          {mode === "paste" ? (
            <textarea
              data-testid="paste-input"
              value={pastedText}
              onChange={(e) => setPastedText(e.target.value)}
              placeholder="Paste your GST notice text here..."
              rows={8}
              className="w-full p-4 text-[15px] leading-relaxed text-ink bg-surface border border-border rounded-2xl resize-none placeholder:text-ink-faint focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition-colors font-mono"
            />
          ) : (
            <label className="block cursor-pointer">
              <div className="flex flex-col items-center justify-center gap-3 p-10 bg-surface border-2 border-dashed border-border rounded-2xl hover:border-accent/40 hover:bg-accent-light/30 transition-colors">
                <svg
                  className="h-8 w-8 text-ink-faint"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
                  />
                </svg>
                <div className="text-center">
                  <p className="text-sm font-medium text-ink">
                    {selected ? selected.name : "Choose a notice file"}
                  </p>
                  <p className="text-xs text-ink-muted mt-1">
                    PDF, JPG, PNG, TIFF, BMP, WebP, or TXT
                  </p>
                </div>
                {selected && (
                  <p className="text-xs text-accent font-medium">
                    {(selected.size / 1024).toFixed(1)} KB
                  </p>
                )}
              </div>
              <input
                type="file"
                accept=".pdf,.jpg,.jpeg,.png,.tiff,.bmp,.webp,.txt"
                data-testid="file-input"
                className="hidden"
                onChange={(e) => setSelected(e.target.files?.[0] ?? null)}
              />
            </label>
          )}

          {/* Submit */}
          <button
            onClick={handleAnalyze}
            disabled={!canSubmit}
            className="w-full mt-4 py-3 rounded-xl text-sm font-semibold text-accent-foreground bg-accent hover:bg-accent-dark disabled:bg-ink-faint/30 disabled:text-ink-faint transition-colors cursor-pointer disabled:cursor-not-allowed"
          >
            {!keysReady
              ? "Set up your API keys above to continue"
              : "Analyze notice"}
          </button>

          {/* Error */}
          {error && step === "input" && (
            <div className="mt-4 p-4 rounded-xl bg-danger-light border border-danger-border/30 text-sm text-danger animate-fade-in">
              {error}
            </div>
          )}
        </div>
      )}

      {step === "processing" && <ProcessingState />}

      {step === "error" && (
        <div className="text-center animate-fade-in">
          <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-danger-light mb-4">
            <svg
              className="h-6 w-6 text-danger"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
              />
            </svg>
          </div>
          <p className="text-ink font-medium mb-1">Something went wrong</p>
          <p className="text-sm text-ink-muted mb-6 max-w-sm mx-auto">
            {error}
          </p>
          <button
            type="button"
            onClick={reset}
            className="px-5 py-2.5 rounded-xl text-sm font-medium text-accent border border-accent/20 hover:bg-accent-light transition-colors cursor-pointer"
          >
            Try again
          </button>
        </div>
      )}

      {step === "results" && result && (
        <ResultsView
          explanation={result.explanation}
          extraction={{
            fields: result.extraction.fields as any,
            confidence: result.extraction.confidence,
          }}
          cross_reference={{
            matched_transactions: result.cross_reference.matched_transactions,
            flagged_transactions: result.cross_reference.flagged_transactions,
            total_transactions_in_period:
              result.cross_reference.total_transactions_in_period,
            total_amount_in_period:
              result.cross_reference.total_amount_in_period,
          }}
          audit_log={result.audit_log}
          onReset={reset}
        />
      )}
    </div>
  );
}
