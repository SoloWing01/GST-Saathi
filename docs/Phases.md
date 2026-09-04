# Phases — build order with acceptance criteria

Work through these in order. Do not start a phase until the previous one's
acceptance criteria are demonstrably met. Update Memory.md when a phase
completes.

## Phase 0 — Skeleton
Goal: something runs end to end, even if it does nothing smart yet.
- Backend (FastAPI) with one endpoint that accepts an uploaded file and
  returns its filename + size.
- Frontend (Next.js) with an upload button that hits that endpoint and
  shows the response.
- Supabase project created; connection from the backend confirmed working
  (a trivial read/write to a test table).
- Acceptance: you can upload a file in the browser and see a real response
  come back from the backend, and confirm the backend can talk to Supabase.

## Phase 1 — Notice parsing
- Extract raw text from a PDF notice (text-based).
- Add OCR fallback for image/scanned notices.
- Uploaded files are stored in Supabase Storage instead of local disk.
- Acceptance: given 3 sample notices (1 text PDF, 1 scanned image, 1 pasted
  text), raw text is correctly extracted for all 3, and the files are
  visible in the Supabase Storage bucket.

## Phase 2 — Field extraction
- LLM-based extraction (Groq free tier) of {notice_type, gstin, tax_period,
  amount, section_cited, due_date} into validated JSON.
- Low-confidence flagging when fields can't be extracted cleanly.
- Acceptance: run against 10 synthetic sample notices, report how many
  extracted cleanly vs. flagged low-confidence, and manually verify accuracy.

## Phase 3 — Synthetic data + knowledge base
- Create the `transactions` table in Supabase, seed it with synthetic
  Razorpay-style records including a handful of deliberate mismatches
  (timing lag, unreconciled refund, genuine gap).
- Write 10–15 GST rules KB markdown files (notice type, meaning, common
  triggers, typical response, statutory reference).
- Enable the `pgvector` extension in Supabase, embed the KB files locally
  with `sentence-transformers`, and load the vectors into a
  `gst_kb_embeddings` table.
- Acceptance: both data sources exist in Supabase and are queryable; a
  manual spot-check confirms the deliberate mismatches are actually present
  in the transactions table, and a test similarity query against
  `gst_kb_embeddings` returns sensible matches.

## Phase 4 — Cross-reference logic
- Given extracted notice fields, query Supabase for matching/near-matching
  transactions.
- Embed the notice fields and run a `pgvector` similarity query against the
  KB embeddings to find the matching notice type/section.
- Acceptance: for each of the 10 synthetic notices, correct transactions and
  correct KB entry are retrieved (or correctly nothing is retrieved, if
  that's the right answer).

## Phase 5 — Reasoning agent + explanation output ✅ COMPLETE
- Combine notice fields + matched transactions + matched KB entry into the
  four-part explanation (what it means / why / what to do / confidence),
  every claim cited, generated via Groq free tier.
- Low-confidence fallback path implemented and visibly distinct in output.
- Audit log captures every lookup step and is stored in the `notices` table.
- Acceptance: run the full pipeline on all 10 synthetic notices, manually
  grade each output for correctness and citation coverage.

## Phase 6 — Real payment provider integrations ✅ COMPLETE
- Razorpay Test Mode API client (`backend/razorpay/`) with sync to
  transactions table, source column (`razorpay`), idempotent upserts.
- PayPal Reporting API integration (`backend/paypal/`) — Transaction Search
  (Reporting) API, OAuth2 token exchange, INR filtering, status mapping,
  tax period derivation, GST auto-calc at 18%, source column (`paypal`).
- `source` column on `transactions` table distinguishes `synthetic`,
  `razorpay`, and `paypal` data.
- Acceptance: both sync endpoints exist and can pull real test data.

## Phase 7 — Frontend polish ✅ COMPLETE
- Two-page structure: landing page (`/`) and explainer page (`/explainer`).
- Results view: four sections, citations, confidence badge, audit trail
  visible (strong demo moment).
- Error/low-confidence states visually distinct from confident answers.
- `SettingsPanel` component: collapsible API key entry with live validation,
  provider toggles, mini status indicators. Auto-opens when keys not ready.
- `SiteHeader` / `SiteFooter` components for consistent navigation.
- Tailwind CSS v4 design system with custom animations and color palette.
- Acceptance: full upload-to-result demo run looks presentable end to end.

## Phase 8 — Deploy + metrics + packaging ✅ COMPLETE
- Backend Dockerfile for HuggingFace Spaces (Docker, 16 GB RAM free tier,
  port 7860).
- Frontend deployable to Vercel.
- Test metrics script (`backend/scripts/test_metrics.py`) — classification
  accuracy, amount accuracy, citation coverage, low-confidence fallback rate.
- Project README with architecture diagram, tech stack, API endpoints,
  deployment guide, environment variables reference.
- Acceptance: all infrastructure files in place. Pending: actual HF Space
  creation and Vercel deploy (requires manual account setup).

## Phase 8b — Multi-tenancy / BYOK ✅ COMPLETE
- In-memory per-tenant credential store (`backend/tenancy.py`):
  TenantCredentials dataclass, thread-safe store, required-field validation.
- Credential management endpoints: `POST /api/credentials`,
  `DELETE /api/credentials`, `POST /api/credentials/validate`,
  `GET /api/credentials/status`.
- All tenant-aware endpoints read `X-Tenant-ID` header; per-tenant LLM
  client instances cached in-memory.
- Frontend settings panel with provider toggles, live validation,
  per-provider check results.
- `X-Tenant-ID` generated client-side via localStorage, never sent to
  third parties.
- Acceptance: app boots without `.env`; every endpoint returns validation
  errors until tenant supplies keys via settings panel; keys are never
  returned in API responses or stored on disk.
