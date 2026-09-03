"use client";

import { useCallback, useEffect, useState } from "react";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export type CredentialStatus = {
  tenant_id: string;
  source: "tenant" | "none";
  ready: boolean;
  validation_errors: string[];
  supabase: boolean;
  database: boolean;
  llm: {
    groq: boolean;
    google: boolean;
    active: string | null;
  };
  razorpay: boolean;
  paypal: boolean;
} | null;

type ValidationResults = {
  results: Record<string, { ok: boolean; error: string | null }>;
  requirements_met: boolean;
  llm_ok: boolean;
  db_ok: boolean;
  payment_ok: boolean;
} | null;

type SettingsPanelProps = {
  tenantId: string;
  onUpdated?: (status: CredentialStatus) => void;
  onReadyChange?: (ready: boolean) => void;
};

export default function SettingsPanel({
  tenantId,
  onUpdated,
  onReadyChange,
}: SettingsPanelProps) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<CredentialStatus>(null);
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] = useState<ValidationResults>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [clearMsg, setClearMsg] = useState(false);

  const [supabaseUrl, setSupabaseUrl] = useState("");
  const [supabaseKey, setSupabaseKey] = useState("");
  const [databaseUrl, setDatabaseUrl] = useState("");
  const [groqKey, setGroqKey] = useState("");
  const [groqModel, setGroqModel] = useState("");
  const [googleKey, setGoogleKey] = useState("");
  const [googleModel, setGoogleModel] = useState("");
  const [razorpayKeyId, setRazorpayKeyId] = useState("");
  const [razorpayKeySecret, setRazorpayKeySecret] = useState("");
  const [paypalClientId, setPaypalClientId] = useState("");
  const [paypalClientSecret, setPaypalClientSecret] = useState("");

  const [supabaseOn, setSupabaseOn] = useState(true);
  const [postgresOn, setPostgresOn] = useState(true);
  const [llmOn, setLlmOn] = useState(true);
  const [razorpayOn, setRazorpayOn] = useState(false);
  const [paypalOn, setPaypalOn] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/credentials/status`, {
        headers: { "X-Tenant-ID": tenantId },
      });
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
        onUpdated?.(data);
        onReadyChange?.(data.ready);
      }
    } catch {
      onReadyChange?.(false);
    }
  }, [tenantId, onUpdated, onReadyChange]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // Auto-open the panel when requirements are not met
  useEffect(() => {
    if (status && !status.ready && !open) {
      setOpen(true);
    }
  }, [status, open]);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    setClearMsg(false);
    try {
      const body = {
        supabase_url: supabaseOn ? supabaseUrl.trim() || null : null,
        supabase_service_role_key: supabaseOn ? supabaseKey.trim() || null : null,
        database_url: postgresOn ? databaseUrl.trim() || null : null,
        groq_api_key: llmOn ? groqKey.trim() || null : null,
        groq_model: llmOn ? groqModel.trim() || null : null,
        google_api_key: llmOn ? googleKey.trim() || null : null,
        google_model: llmOn ? googleModel.trim() || null : null,
        razorpay_key_id: razorpayOn ? razorpayKeyId.trim() || null : null,
        razorpay_key_secret: razorpayOn ? razorpayKeySecret.trim() || null : null,
        paypal_client_id: paypalOn ? paypalClientId.trim() || null : null,
        paypal_client_secret: paypalOn ? paypalClientSecret.trim() || null : null,
      };
      const res = await fetch(`${BACKEND_URL}/api/credentials`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-ID": tenantId,
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(
          Array.isArray(err.missing)
            ? err.missing.join(" ")
            : err.detail || `Server error ${res.status}`
        );
      }
      setMessage("Credentials saved for this session.");
      setClearMsg(false);
      setSupabaseUrl("");
      setSupabaseKey("");
      setDatabaseUrl("");
      setGroqKey("");
      setGroqModel("");
      setGoogleKey("");
      setGoogleModel("");
      setRazorpayKeyId("");
      setRazorpayKeySecret("");
      setPaypalClientId("");
      setPaypalClientSecret("");
      await loadStatus();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Failed to save credentials.");
      setClearMsg(false);
    } finally {
      setSaving(false);
    }
  };

  const handleClear = async () => {
    setSaving(true);
    setMessage(null);
    setClearMsg(false);
    try {
      await fetch(`${BACKEND_URL}/api/credentials`, {
        method: "DELETE",
        headers: { "X-Tenant-ID": tenantId },
      });
      setSupabaseUrl("");
      setSupabaseKey("");
      setDatabaseUrl("");
      setGroqKey("");
      setGroqModel("");
      setGoogleKey("");
      setGoogleModel("");
      setRazorpayKeyId("");
      setRazorpayKeySecret("");
      setPaypalClientId("");
      setPaypalClientSecret("");
      setClearMsg(true);
      setValidation(null);
      await loadStatus();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Failed to clear credentials.");
      setClearMsg(false);
    } finally {
      setSaving(false);
    }
  };

  const handleValidate = async () => {
    setValidating(true);
    setMessage(null);
    setValidation(null);
    setClearMsg(false);
    try {
      const body = {
        supabase_url: supabaseOn ? supabaseUrl.trim() || null : null,
        supabase_service_role_key: supabaseOn ? supabaseKey.trim() || null : null,
        database_url: postgresOn ? databaseUrl.trim() || null : null,
        groq_api_key: llmOn ? groqKey.trim() || null : null,
        groq_model: llmOn ? groqModel.trim() || null : null,
        google_api_key: llmOn ? googleKey.trim() || null : null,
        google_model: llmOn ? googleModel.trim() || null : null,
        razorpay_key_id: razorpayOn ? razorpayKeyId.trim() || null : null,
        razorpay_key_secret: razorpayOn ? razorpayKeySecret.trim() || null : null,
        paypal_client_id: paypalOn ? paypalClientId.trim() || null : null,
        paypal_client_secret: paypalOn ? paypalClientSecret.trim() || null : null,
      };
      const res = await fetch(`${BACKEND_URL}/api/credentials/validate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Tenant-ID": tenantId,
        },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`Validation failed (HTTP ${res.status})`);
      const data: ValidationResults = await res.json();
      if (!data) throw new Error("Empty validation response");
      setValidation(data);
      if (data.requirements_met) {
        setMessage("All checks passed! Saving credentials...");
        await handleSave();
      } else {
        const msgs: string[] = [];
        if (!data.llm_ok) msgs.push("Provide at least one valid LLM key.");
        if (!data.db_ok && !data.payment_ok) {
          msgs.push("Provide Supabase or a payment provider key.");
        }
        setMessage(msgs.join(" "));
      }
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Validation failed.");
    } finally {
      setValidating(false);
    }
  };

  const timer = () => {
    setMessage(null);
    setClearMsg(false);
  };

  const ready = status?.ready ?? false;

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors cursor-pointer ${
          ready
            ? "text-ink-muted border border-border hover:border-accent/40 hover:text-ink"
            : "text-accent-foreground bg-accent hover:bg-accent-dark border border-accent"
        }`}
        type="button"
      >
        <svg
          className="h-4 w-4"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.75}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.02-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.28z"
          />
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
          />
        </svg>
        {ready ? "Configure keys" : "Set up your API keys (required)"}
      </button>

      {open && (
        <div className="mt-3 p-4 bg-surface border border-border rounded-2xl animate-fade-in">
          <div className="text-sm font-semibold text-ink mb-1">
            API key setup
          </div>
          <p className="text-xs text-ink-muted mb-4">
            Every user must supply their own API keys to use this application.
            Keys are stored in memory only and lost on server restart. Provide
            at least one LLM key plus at least one of Supabase, Postgres, or
            a payment provider (Razorpay / PayPal).
          </p>

          {/* Status indicators */}
          {status && (
            <div className="mb-4 grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <MiniStatus label="LLM" ok={status.llm.groq || status.llm.google} required />
              <MiniStatus label="Supabase" ok={status.supabase} />
              <MiniStatus label="Razorpay" ok={status.razorpay} />
              <MiniStatus label="PayPal" ok={status.paypal} />
            </div>
          )}

          <div className="space-y-3">
            {/* LLM — REQUIRED */}
            <ToggleSection
              title="LLM (Groq or Gemini) *required"
              description="At least one LLM API key is mandatory. Models that read and explain the notice."
              enabled={llmOn}
              onToggle={setLlmOn}
              required
            >
              <Field
                label="Groq API Key"
                value={groqKey}
                onChange={setGroqKey}
                placeholder="gsk_..."
                secret
              />
              <Field
                label="Groq Model"
                value={groqModel}
                onChange={setGroqModel}
                placeholder="qwen/qwen3.6-27b"
              />
              <Field
                label="Google Gemini API Key"
                value={googleKey}
                onChange={setGoogleKey}
                placeholder="AIza..."
                secret
              />
              <Field
                label="Gemini Model"
                value={googleModel}
                onChange={setGoogleModel}
                placeholder="gemini-3.6-flash"
              />
            </ToggleSection>

            {/* Database — optional */}
            <ToggleSection
              title="Database (Supabase / Postgres)"
              description="Store notices, transactions, and cross-reference data. Provide Supabase credentials or a Postgres connection string."
              enabled={supabaseOn || postgresOn}
              onToggle={(v) => { setSupabaseOn(v); setPostgresOn(v); }}
            >
              <Field
                label="Supabase URL"
                value={supabaseUrl}
                onChange={setSupabaseUrl}
                placeholder="https://xxxx.supabase.co"
              />
              <Field
                label="Service Role Key"
                value={supabaseKey}
                onChange={setSupabaseKey}
                placeholder="eyJhbGciOi..."
                secret
              />
              <Field
                label="DATABASE_URL (alternative)"
                value={databaseUrl}
                onChange={setDatabaseUrl}
                placeholder="postgresql://user:pass@host:5432/db"
                secret
              />
            </ToggleSection>

            {/* Razorpay — optional */}
            <ToggleSection
              title="Razorpay"
              description="Pull real payment transactions to cross-reference against."
              enabled={razorpayOn}
              onToggle={setRazorpayOn}
            >
              <Field
                label="Key ID"
                value={razorpayKeyId}
                onChange={setRazorpayKeyId}
                placeholder="rzp_test_..."
                secret
              />
              <Field
                label="Key Secret"
                value={razorpayKeySecret}
                onChange={setRazorpayKeySecret}
                placeholder="rzp_test_..."
                secret
              />
            </ToggleSection>

            {/* PayPal — optional */}
            <ToggleSection
              title="PayPal"
              description="Pull real payment transactions to cross-reference against."
              enabled={paypalOn}
              onToggle={setPaypalOn}
            >
              <Field
                label="Client ID"
                value={paypalClientId}
                onChange={setPaypalClientId}
                placeholder="sb-..."
                secret
              />
              <Field
                label="Client Secret"
                value={paypalClientSecret}
                onChange={setPaypalClientSecret}
                placeholder="sb-..."
                secret
              />
            </ToggleSection>
          </div>

          {/* Validation results */}
          {validation && (
            <div className="mt-3 space-y-1.5">
              <div className="text-xs font-medium text-ink-muted">Validation results:</div>
              {Object.entries(validation.results).map(([key, v]) => (
                <div
                  key={key}
                  className={`flex items-center gap-2 text-xs px-2.5 py-1.5 rounded-lg border ${
                    v.ok
                      ? "border-success/30 bg-success-light/40"
                      : "border-danger/30 bg-danger-light/40"
                  }`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${v.ok ? "bg-success" : "bg-danger"}`}
                  />
                  <span className="text-ink capitalize">{key}</span>
                  {v.ok ? (
                    <span className="text-success ml-auto">Valid</span>
                  ) : (
                    <span className="text-danger ml-auto truncate max-w-[200px]">
                      {v.error}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <button
              onClick={handleValidate}
              disabled={validating}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-accent-foreground bg-accent hover:bg-accent-dark disabled:opacity-50 transition-colors cursor-pointer disabled:cursor-not-allowed"
              type="button"
              onMouseLeave={timer}
            >
              {validating ? "Validating..." : "Validate & Save"}
            </button>
            <button
              onClick={handleClear}
              disabled={saving}
              className="px-4 py-2 rounded-lg text-sm font-medium text-danger border border-danger/30 hover:bg-danger-light transition-colors cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
              type="button"
            >
              Clear credentials
            </button>
          </div>

          {message && <StatusMsg tone="error">{message}</StatusMsg>}
          {clearMsg && (
            <StatusMsg tone="ok">
              Credentials cleared.
            </StatusMsg>
          )}
        </div>
      )}
    </div>
  );
}

function MiniStatus({
  label,
  ok,
  required,
}: {
  label: string;
  ok: boolean;
  required?: boolean;
}) {
  return (
    <div
      className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border ${
        ok ? "border-success/30 bg-success-light/40" : "border-border bg-surface-raised"
      }`}
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${
          ok ? "bg-success" : "bg-ink-faint/50"
        }`}
      />
      <span className="text-ink-muted">{label}</span>
      {required && !ok && (
        <span className="ml-auto text-[10px] font-semibold text-danger uppercase tracking-wider">
          req
        </span>
      )}
    </div>
  );
}

function ToggleSection({
  title,
  description,
  enabled,
  onToggle,
  required,
  children,
}: {
  title: string;
  description: string;
  enabled: boolean;
  onToggle: (v: boolean) => void;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className={`rounded-xl border p-3 transition-colors ${
        enabled
          ? required
            ? "border-accent/40 bg-accent-light/15"
            : "border-accent/25 bg-accent-light/10"
          : "border-border bg-surface-raised opacity-70"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-ink flex items-center gap-1.5">
            {title}
            {required && (
              <span className="text-[10px] font-semibold text-danger uppercase tracking-wider">
                *
              </span>
            )}
          </div>
          <div className="text-xs text-ink-muted mt-0.5">{description}</div>
        </div>
        {!required && (
          <label className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => onToggle(e.target.checked)}
              className="sr-only"
            />
            <span
              className={`h-5 w-9 rounded-full transition-colors ${
                enabled ? "bg-accent" : "bg-ink-faint/40"
              }`}
            >
              <span
                className={`block h-4 w-4 rounded-full bg-white shadow transform transition-transform ${
                  enabled ? "translate-x-[18px]" : "translate-x-[2px]"
                }`}
                style={{ marginTop: 2 }}
              />
            </span>
          </label>
        )}
      </div>
      {enabled && <div className="mt-3 space-y-2">{children}</div>}
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  secret,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  secret?: boolean;
}) {
  const [show, setShow] = useState(false);
  return (
    <label className="block">
      <span className="block text-xs text-ink-muted mb-1">{label}</span>
      <div className="relative">
        <input
          type={secret && !show ? "password" : "text"}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className="w-full px-3 py-2 pr-16 text-sm text-ink bg-surface-raised border border-border rounded-lg placeholder:text-ink-faint focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20 transition-colors font-mono"
        />
        {secret && (
          <button
            onClick={() => setShow((v) => !v)}
            className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-accent hover:text-accent-dark cursor-pointer"
            type="button"
          >
            {show ? "Hide" : "Show"}
          </button>
        )}
      </div>
    </label>
  );
}

function StatusMsg({
  tone,
  children,
}: {
  tone: "ok" | "error";
  children: React.ReactNode;
}) {
  return (
    <div
      className={`mt-3 px-3 py-2 rounded-lg text-sm animate-fade-in ${
        tone === "ok"
          ? "bg-success-light text-success"
          : "bg-danger-light text-danger"
      }`}
    >
      {children}
    </div>
  );
}
