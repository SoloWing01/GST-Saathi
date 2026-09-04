# Rules — non-negotiable, apply for the whole project

These are hard constraints, not suggestions. If a task conflicts with one of
these, stop and flag it instead of proceeding.

## Cost
- No paid runtime API calls anywhere in the deployed app. Approved free
  options:
  - Groq free tier or Gemini free tier for reasoning/generation LLM calls.
  - Hugging Face `sentence-transformers`, run locally, for KB retrieval
    embeddings — this is the only approved use of Hugging Face in this
    project. Do not add Hugging Face's Inference API, Inference Providers,
    or Inference Endpoints for generation — those are out of scope here.
  - Supabase free tier for Postgres, `pgvector`, Storage, and Auth.
  - Vercel free tier for frontend hosting, HuggingFace Spaces free tier
    (Docker, 16 GB RAM) for backend hosting.
  - Razorpay Test Mode and PayPal sandbox for payment-provider integration.
  - If a task seems to require a paid API or paid tier on any of the above,
    stop and propose a free alternative instead of just using it.
- Never hardcode an API key or Supabase service key in source.
- **BYOK (Bring Your Own Keys):** the deployed app holds no shared key pool.
  Users supply their own key material at runtime. Keys live **in memory
  only** (`backend/tenancy.py`), never on disk, never returned through any
  API. The committed `.env.example` keeps optional placeholders for local
  dev defaults but is not required at runtime.

## Data & honesty
- Never use real merchant data. Synthetic transactions and synthetic/sample
  notices only.
- Every factual claim in a generated explanation must carry a citation
  (a transaction ID or a KB source). No unsourced claims — this is the
  single most important rule in this project.
- When confidence is low, say so explicitly and suggest escalation. Never
  produce a confident-sounding answer on a low-confidence extraction or match.
- Never phrase output as binding legal/tax advice. Use "likely," "based on
  the information available."

## Process
- Build in the order defined in Phases.md. Don't start a phase until the
  previous one's acceptance criteria are met and demonstrated working.
- After every meaningful change, run the thing and show the actual output —
  don't report a feature as done without having run it.
- Small, testable commits. Commit message describes what changed and why.
- Update Memory.md at the end of every work session with: what got done,
  what's broken, what's next. This is how continuity survives between
  sessions — don't skip it.

## Code
- Prefer boring, readable code over clever code. This is a hackathon project
  a judge and future-you both need to understand fast.
- No unused dependencies. If a library gets added and then not used, remove it.
- Validate all extracted/parsed fields before using them downstream — never
  assume the parser got it right.
- Supabase REST access goes through a single client module in `/backend/db` —
  don't scatter raw Supabase client/query code across the codebase. (Direct
  `psycopg` connections are allowed only for DDL and idempotent transaction
  upserts, i.e. `razorpay/sync.py`, `paypal/sync.py`, and the `db/` setup
  scripts — the same pattern as the existing setup scripts.)
- Per-tenant credential resolution stays in `tenancy.py` + the per-tenant
  LLM/Supabase/payment client resolution — don't read raw keys directly in
  route handlers.

## Scope discipline
- Stretch goals in PRD.md are explicitly out of scope until the MVP works
  end to end. Don't build a stretch feature while the MVP has an open gap.
- If asked to add something not in PRD.md or Phases.md, ask whether it
  belongs in Phases.md first rather than building it ad hoc.
