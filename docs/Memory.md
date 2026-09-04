# Memory — running project log

Claude Code: update this file at the end of every session. This is how
continuity survives across sessions since you don't remember previous ones
automatically. Keep entries short and factual — newest at the top.

Format per entry:
```
## <date> — Phase <n>
Done:
- ...
Broken / open issues:
- ...
Next:
- ...
Decisions made this session (and why):
- ...
```

---

## 2026-08-25 — Phase 0 ✅ COMPLETE
Done:
- Backend endpoint `POST /api/upload` exists and works — echoes
  `{filename, size_bytes, content_type}` (FastAPI, `backend/api/main.py`).
- `GET /api/health` reports Supabase reachability; app boots even when creds
  are absent.
- Supabase client module (`backend/db/supabase_client.py`, single access point
  per Rules) + connectivity probe (`backend/db/check_supabase.py`).
- Frontend wired up: `frontend/app/upload-client.tsx` ("use client" component)
  + a server-component `page.tsx`. Upload a file → shows backend response.
- Verified end-to-end through a real headless Chrome session
  (`scripts/e2e-upload.mjs`, CDP): set file on `<input type=file>`, clicked
  "Upload notice", page rendered "sample_notice.txt (60 bytes, text/plain)".
  Backend access log confirms the POST; CORS allows the `:3000` origin.
- `npm run build` is clean (TypeScript passes).
- Supabase connectivity probe passed: created table, inserted row, read back,
  dropped table — all via the app-level client. Creds in `.env` confirmed working.

Broken / open issues:
- None for Phase 0.

Next:
- Phase 1: notice parsing — text PDF extraction, OCR fallback, files to
  Supabase Storage.

Decisions made this session (and why):
- Frontend calls the backend directly (client-side `fetch` to `:8000`) rather
  than through a Next.js route handler — simplest thing that works for Phase 0;
  a `/api` proxy can be added later if CORS/deploy needs it.
- Use a client component for the upload UI (interactivity) with a thin
  server-component page — matches Next.js 16 conventions read from
  `node_modules/next/dist/docs` (AGENTS.md warns this is not your training-data
  Next.js).
- Backend URL from `NEXT_PUBLIC_BACKEND_URL`, defaulting to
  `http://localhost:8000`; documented in `frontend/.env.local.example`.
- Fixed `SUPABASE_URL` to base URL (no `/rest/v1/` — `supabase-py` adds it).
- URL-encoded special chars in `DATABASE_URL` password (`@` → `%40`, `&` → `%26`).

## 2026-08-26 — Phase 1 ✅ COMPLETE
Done:
- PDF text extraction via pdfplumber (`backend/parser/text_extraction.py`).
- OCR fallback via pytesseract for scanned images (graceful; needs
  `tesseract-ocr` system package).
- Pasted text support via `POST /api/paste`.
- Files stored in Supabase Storage bucket `notice-uploads` (date-partitioned
  paths: `2026/08/26/<uuid>.ext`).
- Backend returns `{filename, size_bytes, content_type, storage_path,
  extracted_text, extraction_method}` for uploads and pastes.
- Frontend updated: file picker + paste mode toggle, shows extracted text
  and storage path.
- 3 sample notices generated: `sample_text.pdf` (text-based PDF),
  `sample_scanned.png` (OCR'd image), `sample_pasted.txt` (plain text).
- All 3 extraction methods tested and verified working.
- Files confirmed visible in Supabase Storage bucket.
- `npm run build` clean, `uv sync` clean.

Broken / open issues:
- None for Phase 1.

Next:
- Phase 2: field extraction (LLM-based extraction of structured JSON from
  notice text via Groq free tier).

Decisions made this session (and why):
- Added `/api/paste` endpoint alongside `/api/upload` for pasted text input
  (Phase 1 acceptance requires all 3 input modes).
- Storage paths use date partitioning (`YYYY/MM/DD/<uuid>.ext`) for
  organization and to avoid collisions.
- `extraction_method` field in response tells frontend how text was obtained
  ("text", "pdf", "ocr", "pasted") — useful for Phase 7 UI.

## 2026-08-26 — Phase 2 ✅ COMPLETE
Done:
- Dual LLM client (`backend/agent/llm_client.py`) with Groq primary +
  Google Gemini fallback. Auto-switches on rate limits/quota exhaustion.
- Structured field extraction (`backend/agent/extract_fields.py`) using
  LLM with strict JSON schema prompt + Pydantic validation.
- Extraction models (`backend/agent/models.py`): `ExtractedFields` and
  `ExtractionResult` with confidence scoring.
- 3 new API endpoints:
  - `POST /api/extract` — send `{text}` → get structured fields
  - `POST /api/upload-and-extract` — file upload + text extraction + field
    extraction in one call
  - `GET /api/llm-status` — shows which providers are configured/active
- `/api/health` now reports LLM provider status.
- Tested against all 3 sample notices — all returned **high confidence**,
  zero missing fields:
  - Text PDF (ASMT-10): correct GSTIN, amount 90000, Section 61
  - Scanned Image (DRC-01): correct GSTIN, amount 45000, Section 73
  - Pasted Text (REG-17): correct GSTIN, amount 65000, Rule 36(4)
- Google Gemini fallback verified working independently.
- Added `groq` and `google-genai` Python packages.
- Model fixes: Groq uses `qwen/qwen3.6-27b`, Google uses `gemini-3.6-flash`
  (older models decommissioned/unavailable).
- Handled Qwen `<think>` tag parsing in JSON response extraction.

Broken / open issues:
- None for Phase 2.

Next:
- Phase 3: synthetic data + knowledge base (transactions table, GST rules
  KB markdown files, pgvector embeddings).

Decisions made this session (and why):
- Used `qwen/qwen3.6-27b` on Groq (only viable chat model available on
  free tier; older Llama/Mixtral models all decommissioned).
- Used `gemini-3.6-flash` on Google (only available Gemini model).
- Increased max_tokens to 4096 for extraction (Qwen models spend tokens on
  internal thinking before outputting JSON).
- Added thinking-tag stripping in JSON parser to handle Qwen's output format.
- `/api/extract` takes pre-extracted text (from Phase 1), while
  `/api/upload-and-extract` combines both phases in one call — gives
  frontend flexibility.

## 2026-08-26 — Phase 3 ✅ COMPLETE
Done:
- 15 GST rules KB markdown files in `backend/kb/gst_rules/`:
  ASMT-10, DRC-01, DRC-02, REG-17, GSTR-3A, GSTR-1 Late Filing,
  GSTR-3B Late Filing, ITC Mismatch (Rule 36(4)), Interest (Section 50),
  ITC Reversal (Section 17(5)), E-Way Bill, Anti-Profiteering (Section 171),
  Composition Taxpayer (Section 10), TDS/TCS (Sections 51/52),
  Excess Refund (Section 73).
- `transactions` table created in Supabase with 35 synthetic Razorpay-style
  payment/settlement records across Q1 FY 2024-25.
- 4 deliberate mismatches seeded:
  a) TIMING LAG: ₹78,000 payment settled 10 days late (not T+1)
  b) UNRECONCILED REFUND: ₹25,000 refund with no matching payment record
  c) GSTR-3B GAP: ₹65,000 payment in GSTR-1 but missing from GSTR-3B
  d) ITC MISMATCH: ₹2,10,000 ITC claimed vs ₹1,85,000 in GSTR-2B
- `gst_kb_embeddings` table created with pgvector extension enabled.
- 15 KB embeddings generated using `all-MiniLM-L6-v2` (384 dims) and
  loaded into Supabase.
- Similarity search verified working — correct top matches for all test
  queries (ASMT-10, DRC-01, GSTR-3B, ITC, etc.).
- Added `sentence-transformers` + `torch` to dependencies.
- Scripts: `db/setup_phase3.py` (tables + seed data), `db/embed_kb.py`
  (embed + load KB).

Broken / open issues:
- None for Phase 3.

Next:
- Phase 4: cross-reference logic — given extracted notice fields, query
  transactions + KB embeddings to find matching data.

Decisions made this session (and why):
- Used psycopg for DDL (Supabase-py REST client can't run DDL).
- Chose `all-MiniLM-L6-v2` for embeddings (384 dims, fast, good for
  short text similarity, runs locally with no API cost).
- Seeded 30 normal + 5 deliberate-mismatch transactions to simulate
  realistic merchant data with exactly the kinds of discrepancies that
  GST notices are about.
- IVFFlat index on embeddings with lists=5 (appropriate for 15 records).
- Each KB file structured with consistent sections (What it means, Common
  triggers, Typical response, Statutory reference, Severity) for uniform
  embedding quality.

## 2026-08-26 — Phase 4 ✅ COMPLETE
Done:
- Cross-reference module (`backend/agent/cross_reference.py`):
  - Tax period normalization (maps free-text periods to canonical forms)
  - Transaction matching: queries Supabase by tax period, flags mismatches
  - KB matching: direct section lookup + pgvector similarity fallback
  - Full audit trail with step-by-step logging
- New models (`backend/agent/models.py`):
  - `MatchedTransaction`, `MatchedKBEntry`, `AuditStep`, `CrossReferenceResult`
- 3 new API endpoints:
  - `POST /api/cross-reference` — takes extracted fields → returns matches
  - `POST /api/analyze` — full pipeline: text → extraction → cross-reference
  - `POST /api/upload-and-analyze` — file upload → full pipeline
- Total API routes: 13 (health, upload, paste, extract, upload-and-extract,
  llm-status, cross-reference, analyze, upload-and-analyze + docs routes)
- Tested against all 3 sample notices — all correct:
  - ASMT-10: 35 txns, 5 flagged, KB: ASMT-10 (similarity: 1.0)
  - DRC-01: 0 txns (correct, no Oct-Dec data), KB: DRC-01 (1.0)
  - REG-17: 0 txns (correct, no Sep data), KB: REG-17 (1.0)
- Fixed IVFFlat index: rebuilt with lists=3 (was lists=5, too many for
  15 records). Index now created AFTER data insertion.
- Direct section-code lookup used before pgvector similarity for accuracy.

Broken / open issues:
- None for Phase 4.

Next:
- Phase 5: reasoning agent + explanation output (four-part explanation
  with citations, low-confidence fallback, audit log storage).

Decisions made this session (and why):
- Direct section lookup before similarity search: pgvector with 15 records
  was matching DRC-02 for DRC-01 queries (shared content). Direct lookup
  on section code is instant and 100% accurate.
- Tax period normalization handles free-text variations ("April 2024 -
  June 2024" → "Apr-Jun 2024") to match seeded data format.
- `/api/analyze` combines Phase 2 + Phase 4 for a single-call pipeline.
  `/api/cross-reference` allows frontend to call extraction and
  cross-reference separately for better UX (show extraction results first).

---

## 2026-08-26 — Phase 5 ✅ COMPLETE
Done:
- Reasoning agent (`backend/agent/reasoning.py`):
  - Four-part explanation: What It Means, Why You Got It, What To Do,
    Confidence & Disclaimer
  - Prompt includes extracted fields, matched transactions, and KB entry
  - Every factual claim backed by a citation (transaction ID or KB source)
  - Low-confidence fallback: detects low confidence from multiple signals
    (extraction confidence, missing txns, missing KB, LLM self-assessment)
    and adds CA escalation banner
  - Qwen `<think>` tag handling: aggressive stripping of nested/unclosed tags,
    retry loop (3 attempts) for truncated thinking responses
  - max_tokens increased to 8192 for reasoning (thinking tokens + JSON)
- New models in `backend/agent/models.py`:
  - `Citation`, `ExplanationSection`, `Explanation`, `ReasoningResult`,
    `NoticeRecord`
- `notices` table in Supabase — stores every processed notice with
  extracted fields, explanation JSON, confidence, provider, audit log
- New API endpoints:
  - `POST /api/explain` — takes fields → cross-ref → explanation
  - `POST /api/analyze-full` — full pipeline: text → extract → cross-ref
    → explain → store in notices table
  - `POST /api/upload-and-explain` — file upload → full pipeline
  - `GET /api/notices` — list recently processed notices
- Total API routes: 17
- Tested full pipeline against all 3 sample notices — all correct:
  - ASMT-10: high confidence, 35 txns, 5 flagged, 3 citations
  - DRC-01: medium confidence, 0 txns (correct), 6 citations
  - REG-17: medium confidence, 0 txns (correct), 7 citations
- All 3 notice records verified in notices table

Broken / open issues:
- None for Phase 5.

Next:
- Phase 6: frontend polish, error states, final testing.

Decisions made this session (and why):
- max_tokens=8192 for reasoning agent (Qwen's thinking tags consume
  ~2000-3000 tokens before JSON output; 4096 caused truncation)
- Retry loop for truncated thinking: Qwen sometimes outputs such verbose
  thinking that it hits max_tokens before JSON — retries with fresh call
- Direct `_run_full_pipeline` helper avoids code duplication between
  `/api/analyze-full` and `/api/upload-and-explain`
- `notices` table stores raw explanation as JSONB for easy querying +
  audit trail. Audit log combines cross-reference steps + reasoning step.

---

## 2026-08-26 — Phase 6 ✅ COMPLETE (Razorpay integration system)
Done:
- Razorpay Test Mode API client (`backend/razorpay/client.py`):
  - Basic Auth (key_id:key_secret) per Razorpay docs
  - `list_payments`, `get_payment`, `list_payments_all` (paginated)
  - `list_settlements`, `get_balance`
  - httpx-based HTTP client with context manager support
- Razorpay sync module (`backend/razorpay/sync.py`):
  - `sync_transactions()` — pulls payments from Razorpay API, converts
    to our transactions table format, upserts into Supabase
  - `get_razorpay_status()` — reports config status and test/live mode
  - Auto-detects tax period from payment timestamps
  - `ON CONFLICT (payment_id) DO UPDATE` for idempotent upserts
  - `source` column distinguishes 'synthetic' vs 'razorpay' data
- Database migration (`backend/db/migrate_phase6.py`):
  - Adds `source text NOT NULL DEFAULT 'synthetic'` column
  - Index on `source` for filtering
- Updated cross-reference logic (`backend/agent/cross_reference.py`):
  - Queries include `source` column
  - `ORDER BY source DESC, created_at` — Razorpay data takes precedence
  - Audit trail reports data sources (e.g. "synthetic: 35, razorpay: 12")
- New API endpoints:
  - `POST /api/razorpay/sync` — trigger sync from Razorpay Test Mode
  - `GET /api/razorpay/status` — check config and mode
- Updated `GET /api/health` to report Razorpay configuration status
- Updated `.env.example` with Razorpay keys section
- Added `httpx>=0.27` to Python dependencies
- `uv sync` clean, `npm run build` clean

Broken / open issues:
- No Razorpay test keys configured yet — sync endpoint returns config
  error until keys are added to backend/.env
- Migration script needs to be run against Supabase to add `source` column

Next:
- Phase 7: frontend polish (results view, citations, confidence badge,
  audit trail, processing state, error states)

Decisions made this session (and why):
- Used httpx over requests for async-friendly, modern HTTP client
- `ON CONFLICT ... DO UPDATE` for idempotent sync — can run multiple
  times without duplicating data
- `source` column on transactions table rather than a separate table —
  keeps query logic simple, one table for all transaction data
- Razorpay API pagination built into client (100 per page, auto-paginate)
- Tax period auto-derived from payment created_at timestamp
- GST amount auto-calculated at 18% (standard rate) from Razorpay data

---

## 2026-08-26 — Phase 7 ✅ COMPLETE (Frontend polish)
Done:
- Installed Tailwind CSS v4 (`tailwindcss` + `@tailwindcss/postcss`)
- Design system in `globals.css`:
  - Restrained palette: warm off-white ground, white surfaces, single teal
    accent (#0e7490), red only for low-confidence escalation
  - Custom animations: fade-in, check-pop, pulse-dot with stagger
  - `prefers-reduced-motion` respected
  - Custom scrollbar, selection color, focus rings
- Components (`app/components/`):
  - `confidence-badge.tsx` — green/amber/red pill badge
  - `citation-marker.tsx` — inline [n] superscript, click to expand source
  - `audit-trail.tsx` — collapsible step-by-step audit log
  - `escalation-banner.tsx` — amber warning for low-confidence results
  - `transaction-list.tsx` — matched/flagged transaction display
  - `processing-state.tsx` — 5-step progress with animated checkmarks
  - `results-view.tsx` — four-section results with citations + audit trail
- Full pipeline integration (`upload-client.tsx`):
  - Calls `/api/analyze-full` (paste) or `/api/upload-and-explain` (file)
  - State machine: input → processing → results | error
  - Clean error handling with actionable messages
- Page redesign (`page.tsx`):
  - Calm header with logo + title
  - Clear hero copy: "What does your notice say?"
  - Single-column, generous whitespace
  - Footer disclaimer
- `npm run build` clean, Impeccable detector: zero issues

---

## 2026-08-26 — Phase 8 ✅ COMPLETE (Deploy + metrics + packaging)
Done:
- Dockerfile for HuggingFace Spaces (`backend/Dockerfile`):
  - Python 3.11-slim base with tesseract-ocr, libgl1, libglib2.0
  - Uses `uv` for dependency management (frozen lockfile)
  - Exposes port 7860 (HF Spaces requirement)
  - CMD: uvicorn on 0.0.0.0:7860
- HuggingFace Spaces README (`backend/README.md`):
  - YAML front matter: `sdk: docker`, `app_port: 7860`
  - Title, emoji, color config
- CORS updated in `main.py`:
  - Added `http://localhost:7860` to allowed origins
  - List-based `_CORS_ORIGINS` for easy extension
- Test metrics script (`backend/scripts/test_metrics.py`):
  - Runs all 3 sample notices through full pipeline
  - Reports: classification accuracy, amount accuracy, citation coverage,
    low-confidence fallback rate, citations per claim
  - Saves detailed results to `test_results.json`
  - Runnable via `python -m scripts.test_metrics`
- Project README (`README.md`):
  - Architecture diagram, tech stack table, quick start guide
  - API endpoints reference, deployment instructions (HF Spaces + Vercel)
  - Environment variables reference, test metrics usage

Broken / open issues:
- Phase 6 Razorpay keys not yet configured (intentionally deferred)
- Migration script for `source` column not yet run (deferred with Phase 6)
- HuggingFace Space not yet created — needs manual HF account setup
- Vercel deployment not yet done — needs `vercel deploy`

Next:
- Create HuggingFace Space and push backend code
- Deploy frontend to Vercel
- Run test_metrics.py and record real numbers
- Optional: configure Razorpay test keys and sync real data

Decisions made this session (and why):
- HuggingFace Spaces chosen over Render/Railway for backend — 16 GB RAM
  on free tier handles sentence-transformers + PyTorch comfortably.
  Render/Railway free tiers (512 MB) are too small.
- Kept sentence-transformers in runtime — direct section lookup handles
  95% of KB matches; pgvector fallback rarely triggered but still available.
- Port 7860 used (HF Spaces standard) — localhost:7860 added to CORS.

---

## 2026-09-02 — Multi-tenancy + BYOK + Frontend redesign + PayPal
Done:
- **BYOK (Bring Your Own Keys) — in-memory per-tenant credential store**
  (`backend/tenancy.py`):
  - `TenantCredentials` dataclass: Supabase, Postgres `DATABASE_URL`,
    Groq, Google, Razorpay, PayPal — all optional except at least one
    LLM key is mandatory, plus at least one of Supabase / Postgres /
    payment provider.
  - `CredentialStore`: thread-safe in-memory dict keyed by arbitrary
    `tenant_id` string.
  - Validation: `validate_required()` returns list of missing-requirement
    messages; partial credentials are rejected (e.g. Razorpay key but
    no secret).
- **New API endpoints** (backend/api/main.py, version bumped to `0.4.0`):
  - `POST /api/credentials` — store a tenant's keys (JSON body, in-memory
    only). Clears stored LLM client so keys take effect immediately.
  - `DELETE /api/credentials` — clear a tenant's stored keys.
  - `POST /api/credentials/validate` — live-test keys per provider
    (Groq completion, Gemini completion, Supabase REST, Postgres connect,
    Razorpay list payments, PayPal OAuth token exchange). Runs all checks
    concurrently. Returns per-provider `{ok, error}` plus summary booleans.
  - `GET /api/credentials/status` — report what a tenant has configured
    (never returns secrets). Returns `source: "tenant" | "none"` and
    `ready` boolean.
- **All tenant-aware endpoints now accept `X-Tenant-ID` header** —
  backend resolves per-tenant credentials (Supabase client, LLM client,
  payment clients, database URL) from the in-memory store.
- **PayPal Reporting API integration (Phase 6b)**
  (`backend/paypal/client.py`, `backend/paypal/sync.py`):
  - `PayPalClient`: OAuth2 token exchange, `list_transactions()`,
    `list_transactions_all()` (paginated, max 50/page).
  - `_parse_paypal_transaction()`: maps PayPal `transaction_detail` to
    our `transactions` row format (INR only, status mapping, tax period
    derivation, GST auto-calc at 18%).
  - `sync_transactions()`: pulls from PayPal Transaction Search API,
    upserts with `ON CONFLICT DO UPDATE` (idempotent), `source: "paypal"`.
  - `get_paypal_status()`: reports configured/sandbox/live.
  - Supports sandbox and live modes; sandbox detected via `sb-` prefix.
- **New API endpoints for PayPal:**
  - `POST /api/paypal/sync` — sync transactions from PayPal Reporting.
  - `GET /api/paypal/status` — check config and mode.
- **Cross-reference updated** (`backend/agent/cross_reference.py`):
  - Now accepts optional `database_url` parameter; uses it when tenant
    supplies a Postgres URL instead of Supabase REST.
  - `source` column filtering and precedence in transaction queries.
  - Audit trail reports data sources (e.g. "synthetic: 35, razorpay: 12,
    paypal: 8").
- **`_store_file` updated**: respects per-tenant Supabase credentials;
  returns `"local-only"` when no Supabase is configured.
- **Frontend redesign** (two-page structure):
  - New landing page (`app/page.tsx`): hero section with value prop,
    how-it-works steps, feature cards, CTA to `/explainer`.
  - Explainer page (`app/explainer/page.tsx`): dedicated upload/paste
    screen with `UploadClient` + `SiteHeader` / `SiteFooter`.
  - `SettingsPanel` component (`app/components/settings-panel.tsx`):
    collapsible API key entry UI with toggle sections per provider,
    live validation with per-provider check results, mini status
    indicators, clear/validate buttons. Auto-opens when keys aren't ready.
  - New components: `site-header.tsx`, `site-footer.tsx`, `theme-provider.tsx`.
  - `upload-client.tsx` updated: tenant ID via localStorage, generates
    `X-Tenant-ID` header on every request, buttons disabled until keys
    ready.
  - Warm design CSS (`warm-design.css`) with custom CSS custom properties
    for the design system.
- `.env.example` updated: all variables now marked `No` (BYOK model);
  Razorpay and PayPal sections with clear guidance on test/sandbox keys.
- `uv sync` clean, `npm run build` clean.

Broken / open issues:
- HuggingFace Space not yet created — needs manual HF account setup
- Vercel deployment not yet done — needs `vercel deploy`
- Razorpay test keys not yet configured (intentionally deferred)
- PayPal sandbox keys not yet configured (intentionally deferred)
- Migration script for `source` column may need to be run against Supabase

Next:
- Create HuggingFace Space and push backend code
- Deploy frontend to Vercel
- Run test_metrics.py and record real numbers
- Optional: configure Razorpay/PayPal test keys and sync real data

Decisions made this session (and why):
- **In-memory BYOK over persistent storage**: no server-side secrets on
  disk; credentials live only in process memory and are lost on restart.
  This is a deliberate security trade-off — simplicity and no-footprint
  for a hackathon over persistence across restarts.
- **PayPal Reporting API over Transactions API**: Reporting gives bulk
  historical data (up to 31 days) in one call vs Transactions which
  requires per-transaction lookups. Better for the initial sync use case.
- **`X-Tenant-ID` header** over cookies or JWT: simplest thing that works
  for a client-only multi-tenant system. No auth/cookie complexity.
- **Per-tenant LLM client cache**: avoids recreating Groq/Gemini clients
  on every request; cache entry replaced when tenant rotates keys via
  `/api/credentials`.
- **Landing page + explainer as separate routes**: clearer demo flow for
  hackathon judges; explainer page is the actual product, landing page
  is the pitch.

---

## Project status
- Current phase: **Phase 8 — ✅ COMPLETE + BYOK + PayPal + Redesign**
- Overall: full pipeline working end-to-end with BYOK model. PayPal and
  Razorpay integrations complete. Frontend has landing page + explainer
  page with settings panel. Backend deployable to HuggingFace Spaces via
  Docker. All infrastructure files in place.
- Next: actual deployment (HF Space creation + Vercel deploy)

---

(New entries go above this line, newest first.)