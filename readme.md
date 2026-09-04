# GST Saathi
 
A hackathon project for the **Razorpay Buildathon** that helps small merchants understand GST/tax compliance notices in plain language.
 
## The problem
 
Small merchants selling through Razorpay panic when they get a GST notice (GSTR-3A, ASMT-10, DRC-01, REG-17, etc.) because the language is dense, the reply deadlines are short, and most can't afford a CA for every notice they receive. That leads to two failure modes: paying a claimed amount without checking if it's accurate, or missing the deadline entirely because the notice was too confusing to act on in time.
 
## What it does
 
1. **Input** — choose one of two methods: **paste text** (copy-paste from a GST notice) or **upload a file** (PDF, image, or text file). Pick the method that fits your notice.
2. **Extract** structured fields: notice type, GSTIN, tax period, amount, section cited, due date
3. **Cross-reference** against the merchant's transaction history and a GST rules knowledge base
4. **Explain** in plain language with four sections: what it means, why you got it, what to do next, and confidence level
## Disclaimer
 
This is not professional tax or legal advice, and it never files or submits anything on the merchant's behalf. Notices that use fraud/suppression language, or demand notices above a set threshold, are flagged for a CA instead of being auto-resolved. Every explanation carries a visible confidence level so a low-confidence or unverifiable case is never presented with false certainty.
 
## Bring-your-own-keys (BYOK)
 
This is a **multi-tenant** app. Every user supplies their **own** API keys — there is no shared/fallback server-side secret pool.
 
- The backend stores each tenant's credentials **in memory only** (`backend/tenancy.py`), never on disk, never returned in responses.
- A tenant is identified by an arbitrary `X-Tenant-ID` header.
- The frontend generates a per-browser tenant id in localStorage and exposes a settings panel to enter keys.
- Required: at least one **LLM key** (Groq or Gemini). Recommended: Supabase / Postgres **and/or** a payment provider (Razorpay / PayPal).
- Keys are lost on server restart by design.
 
## Architecture
 
```
Frontend (Next.js)  →  Backend (FastAPI)  →  Supabase (Postgres + pgvector + Storage)
                          (BYOK: in-memory         ↑
                           per-tenant keys)        |
                          ↓                        ↓
                     Groq / Gemini (free LLM)      |
                          ↓                   sentence-transformers (local embeddings)
                     Razorpay / PayPal (test or live — tenant's choice)
```
 
## Stack
 
| Layer | Tech | Hosting |
|-------|------|---------|
| Frontend | Next.js, React 19, Tailwind CSS v4 | Vercel (free) |
| Backend | Python 3.11, FastAPI, uvicorn | HuggingFace Spaces (free, Python SDK) |
| Database | Supabase Postgres + pgvector | Supabase (free tier) |
| Storage | Supabase Storage | Supabase (free tier) |
| LLM | Groq free tier (primary), Gemini free tier (fallback) | — |
| Embeddings | `sentence-transformers` (`all-MiniLM-L6-v2`) | Runs locally in backend |
| Payments | Razorpay API (primary integration) + PayPal Reporting API | — |
| Tenancy | In-memory per-tenant credential store (`tenancy.py`) | Backend process |
 
> Razorpay is the core integration this project is built around — it's what makes the cross-reference step possible, and this is Razorpay's own buildathon. PayPal support (see API endpoints below) was added afterward as an optional multi-provider bonus and isn't required to run the demo.
 
## Quick start (local)
 
### Backend
 
```bash
cd backend
uv sync
uv run uvicorn api.main:app --reload --port 8000
```
 
Health check: `GET http://localhost:8000/api/health`
 
> The backend boots and reports `mode: bring_your_own_keys`. Endpoints that need keys return validation errors until the tenant supplies credentials via `POST /api/credentials`.
 
### Frontend
 
```bash
cd frontend
npm install
npm run dev
```
 
Open `http://localhost:3000`, open the "Set up your API keys" panel, enter at least one LLM key (plus Supabase/Postgres or a payment provider — test/sandbox keys recommended), then choose **Paste text** or **Upload file** and submit your notice.
 
## Create your own database
 
Follow these steps to set up your own Supabase (Postgres + pgvector) database:
 
### 1. Create a Supabase project
- Go to [supabase.com](https://supabase.com) and sign up / log in
- Click **New Project**
- Choose a project name, database password, and region
- Wait for the project to be provisioned
### 2. Get your credentials
- In the Supabase dashboard, go to **Settings → API**
- Copy the **Project URL** and **service_role** key (under "Project API keys")
- Note: the service_role key bypasses Row Level Security entirely. That's fine for this demo's in-memory, single-user-per-tenant setup, but a production version would use a scoped key + RLS policies instead.
### 3. Set up the schema
- Go to the **SQL Editor** in the Supabase dashboard
- Run the following SQL to enable pgvector and create the required tables:
```sql
-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;
 
-- Notices table
CREATE TABLE IF NOT EXISTS notices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL DEFAULT 'default',
  notice_type TEXT,
  gstin TEXT,
  tax_period TEXT,
  amount NUMERIC,
  section_cited TEXT,
  due_date TEXT,
  raw_text TEXT,
  file_name TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
 
-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id TEXT NOT NULL DEFAULT 'default',
  transaction_id TEXT,
  date DATE,
  amount NUMERIC,
  counterparty TEXT,
  description TEXT,
  source TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
 
-- Knowledge base chunks with embeddings
CREATE TABLE IF NOT EXISTS kb_chunks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source TEXT,
  section TEXT,
  content TEXT,
  embedding VECTOR(384),
  created_at TIMESTAMPTZ DEFAULT now()
);
 
-- Index for vector similarity search
CREATE INDEX IF NOT EXISTS idx_kb_chunks_embedding
  ON kb_chunks USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 10);
```
 
### 4. Connect via the app
- Start the backend and frontend (see Quick Start above)
- Open the frontend at `http://localhost:3000`
- Open the **"Set up your API keys"** panel
- Enter your Supabase credentials:
  - **Supabase URL**: `https://<your-project>.supabase.co`
  - **Supabase Service Role Key**: `eyJ...`
- The backend stores your keys in memory and uses them for all requests
### 5. (Optional) Seed the knowledge base
- Add GST rule documents to `backend/data/kb/` as `.txt` or `.md` files
- The backend will chunk and embed them into `kb_chunks` on first use
That's it — your own database is ready.
 
## API endpoints
 
| Method | Path | Description |
|--------|------|--------------|
| `GET` | `/api/health` | Health check + provider status |
| `POST` | `/api/credentials` | Store per-tenant API keys (in memory, BYOK) |
| `DELETE` | `/api/credentials` | Clear a tenant's credentials |
| `POST` | `/api/credentials/validate` | Live-test user-supplied keys per provider |
| `GET` | `/api/credentials/status` | What a tenant has configured (no secrets) |
| `POST` | `/api/upload` | Upload a file, extract text |
| `POST` | `/api/paste` | Paste text directly |
| `POST` | `/api/extract` | Extract structured fields from text |
| `POST` | `/api/upload-and-extract` | File upload → text → field extraction |
| `GET` | `/api/llm-status` | Which LLM providers are active for the tenant |
| `POST` | `/api/cross-reference` | Cross-reference extracted fields |
| `POST` | `/api/analyze` | Full pipeline: text → extract → cross-ref |
| `POST` | `/api/upload-and-analyze` | File upload → full pipeline |
| `POST` | `/api/explain` | Fields → cross-ref → explanation |
| `POST` | `/api/analyze-full` | Full pipeline: text → extract → cross-ref → explain |
| `POST` | `/api/upload-and-explain` | File upload → full pipeline |
| `GET` | `/api/notices` | List recently processed notices |
| `POST` | `/api/razorpay/sync` | Sync transactions from Razorpay |
| `GET` | `/api/razorpay/status` | Check Razorpay configuration |
| `POST` | `/api/paypal/sync` | *(optional)* Sync transactions from PayPal Reporting API |
| `GET` | `/api/paypal/status` | *(optional)* Check PayPal configuration |
 
Tenant-scoped endpoints read the `X-Tenant-ID` header (defaults to `default`).

## Deployment

### Backend — HuggingFace Spaces (Python SDK, free)

The backend is configured as a **Python SDK** Space (the `sdk: python` SDK is free; the Docker SDK is paid). It runs `app.py` which launches uvicorn on port `7860`.

1. Go to [huggingface.co/new-space](https://huggingface.co/new-space) and create a Space:
   - **Space name:** e.g. `gst-saathi`
   - **SDK:** `Python`
   - **Visibility:** Public or Private
2. In the Space, go to **Settings → Repository** and connect your GitHub repo, or push the `backend/` directory contents directly to the Space repo.
3. Make sure `backend/app.py`, `backend/requirements.txt`, and `backend/README.md` are at the repo root targeted by the Space.
4. The Space builds and runs automatically. Your backend URL becomes:
   ```
   https://<your-username>-gst-saathi.hf.space
   ```
5. Health check: `GET https://<your-username>-gst-saathi.hf.space/api/health`

> **OCR caveat:** the Python SDK Space does not install the `tesseract` system binary, so uploads that need OCR (scanned PDFs and JPG/PNG/TIFF images) may fail. **Pasted text** and **text-based PDFs** work fine. For full OCR support you'd need the Docker SDK (paid) or a different host.

### Frontend — Vercel (already deployed)

```bash
cd frontend
vercel deploy
```

Set the `NEXT_PUBLIC_BACKEND_URL` environment variable in Vercel to your HuggingFace Space URL:

```
NEXT_PUBLIC_BACKEND_URL=https://<your-username>-gst-saathi.hf.space
```

Then redeploy the frontend so it points at the hosted backend.

## Demo
 
- Pitch video: _add link before submission_
- Live demo: _add link before submission_

