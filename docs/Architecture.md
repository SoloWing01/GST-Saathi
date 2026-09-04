# Architecture — GST / Tax Notice Explainer

## Pipeline (see PRD for the "why" of each step)
Notice upload → Parse & extract → [Transaction history + GST rules KB] →
Reasoning agent → Explanation output (with citations + audit log)

## Components

### 1. Upload & intake
- Accepts PDF, image (jpg/png), or pasted text.
- File goes to Supabase Storage (a bucket for uploaded notices) rather than
  local disk — this matters once anything is deployed, not just local.
- Text PDFs: extract text directly.
- Scanned/image notices: OCR first, then extract.
- Output: raw text of the notice + a reference to the stored file.

### 2. Parser / field extractor
- Input: raw notice text.
- Output: structured JSON — `{notice_type, gstin, tax_period, amount,
  section_cited, due_date, raw_text}`.
- Uses the runtime LLM (Groq free tier, see Component 6) with a strict
  extraction prompt + JSON schema validation. If required fields can't be
  extracted confidently, flag `extraction_confidence: low` rather than
  guessing.

### 3. Transaction history source
- Stored in Supabase Postgres: a `transactions` table modeled on Razorpay
  payment/settlement records (payment ID, amount, date, status, refunds,
  settlement date), seeded with synthetic data.
- Three data sources coexist in one table, distinguished by a `source` column:
  `synthetic` (seeded), `razorpay` (Test Mode API), `paypal` (Reporting API).
- At least one live call to Razorpay Test Mode or PayPal Sandbox so the
  integration is real, not 100% synthetic.
- Query interface: given a tax period + amount, query Supabase for
  matching/near-matching transactions with enough detail to explain a
  mismatch (timing lag, refund not netted, etc.).

### 4. GST rules knowledge base (RAG)
- 15 markdown files, one per common notice type/section. Each contains:
  what it means, common triggers, typical required response, statutory
  reference.
- Retrieval: embed the KB files with a local Hugging Face
  `sentence-transformers` model (`all-MiniLM-L6-v2`), store the vectors in
  a Supabase Postgres table using the `pgvector` extension, and do
  similarity search against it with SQL. The embedding step runs locally
  (no API call, no cost); only the storage/query lives in Supabase.
- Notice fields get embedded the same way at query time and matched against
  the KB vectors.

### 5. Multi-tenancy / credential store (BYOK)
- **No server-side `.env` fallback at runtime.** Every user supplies their own
  API keys via the frontend settings panel (`POST /api/credentials`).
- Credentials are held **in-memory only** in `backend/tenancy.py` — never
  written to disk, never returned through any API.
- A tenant is identified by an arbitrary `X-Tenant-ID` HTTP header
  (generated client-side via `localStorage`).
- Required: at least one LLM provider key (Groq and/or Gemini) **and** at
  least one of Supabase / Postgres / Razorpay / PayPal.
- `/api/credentials/validate` live-tests every key with lightweight
  verification calls (Groq, Gemini, Supabase REST, Postgres connect,
  Razorpay list payments, PayPal OAuth exchange).
- Per-tenant LLM client instances are cached in-memory and replaced on key
  rotation.

### 6. Reasoning agent
- Input: structured notice fields + matched transactions + matched KB entry.
- Does the actual comparison: does the flagged amount/period reconcile with
  what actually happened in the transaction history? Explainable gap or real
  gap?
- LLM calls for this step use Groq free tier (primary) or Gemini free tier
  (backup) — not Hugging Face, which is reserved for embeddings only in
  this project.
- Output: structured response object (see PRD's four-part format) with a
  citation attached to every factual claim, plus a confidence score.
- Logs every step it takes (what it looked up, what it matched, what it
  discarded) — this log is the audit trail, stored alongside the response.

### 7. Output / frontend
- Two pages: landing page (`/`) and explainer page (`/explainer`).
- Landing page: value proposition, how-it-works steps, features, CTA to
  explainer.
- Explainer page: file picker or paste input, settings panel for API keys,
  processing state (live audit trail steps), results view with four sections
  + citations + confidence badge.
- Settings panel (`components/settings-panel.tsx`): collapsible key-entry UI,
  toggle sections per provider, live validation, min status indicators.
- Low-confidence responses get a visually distinct "escalate to a CA" banner
  instead of a confident-looking answer.
- Tenant id persisted per browser in `localStorage`; never sent to
  third-party services.

## Tech stack (all free)
- Frontend: Node.js + Next.js (React 19), Tailwind CSS v4. Deploys free on Vercel.
- Backend: Python 3.11, FastAPI, uvicorn. Version `0.4.0`.
- Database / storage: Supabase — Postgres for structured data (extracted
  notices, transactions, audit logs) with the `pgvector` extension for KB
  embeddings, plus Supabase Storage for uploaded notice files.
- PDF/text extraction: `pdfplumber` or `PyMuPDF`.
- OCR: Tesseract (`pytesseract`).
- Retrieval embeddings: Hugging Face `sentence-transformers`
  (`all-MiniLM-L6-v2`), run locally — this is the only Hugging Face
  component in the stack. No paid HF surface is used.
- Runtime LLM (reasoning/generation): Groq free tier (primary), Gemini free
  tier (backup).
- Payments: Razorpay Test Mode API (`httpx`-based client), PayPal Reporting
  (Transaction Search) API (`httpx`-based client, sandbox).
- Backend deploy: HuggingFace Spaces (Docker, 16 GB RAM on free tier).

## Folder structure
```
/backend
  /parser        - notice text extraction (pdfplumber, OCR via tesseract)
  /data          - sample_notices/
  /kb            - gst_rules/*.md  (15 files)
  /agent         - cross-reference, reasoning, field extraction, LLM client
  /api           - FastAPI routes
  /db            - Supabase client, migration/setup scripts, pgvector embedding
  /razorpay      - Razorpay client + sync module
  /paypal        - PayPal client + sync module
  tenancy.py     - in-memory per-tenant credential store (BYOK)
  Dockerfile     - HuggingFace Spaces Docker deployment
/frontend
  /app
    page.tsx     - landing page (marketing / explainer link)
    /explainer   - main notice explainer page
    upload-client.tsx  - client component: input, settings panel, results
    /components  - UI components (settings-panel, results-view, audit-trail, etc.)
  globals.css    - Tailwind v4 design tokens + custom animations
/docs
  - this file, PRD.md, Memory.md, etc.
```

## Data contracts between components
- Parser → Agent: the structured JSON above.
- Transaction source (Supabase) → Agent: list of `{payment_id, amount, date,
  status, refund_of}` matches, with `source` tag (`synthetic`, `razorpay`,
  `paypal`).
- KB (Supabase pgvector) → Agent: `{section, summary, common_triggers,
  typical_response, statutory_reference}`.
- Agent → Frontend: `{what_it_means, why_you_got_it, what_to_do,
  confidence, citations: [...], audit_log: [...]}`.
- Frontend → Backend: `X-Tenant-ID` header on every request; `POST /api/credentials`
  receives all key fields as JSON (never stored in cookies, never sent to third parties).

## Supabase schema (starting point)
- `transactions` — synthetic Razorpay-style payment/settlement records
  plus Razorpay and PayPal synced records (`source` column distinguishes).
- `gst_kb_embeddings` — `pgvector` column holding the embedded KB entries,
  plus the source text and metadata.
- `notices` — each processed notice: extracted fields, matched
  transactions, matched KB entry, final response, confidence, audit log.
- Storage bucket `notice-uploads` — original uploaded files.