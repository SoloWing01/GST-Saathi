# Frontend — GST Saathi

React 19 + Next.js + Tailwind CSS v4 frontend deployed on Vercel.

## How to run

Run the backend first (`cd backend && uv run uvicorn api.main:app --reload --port 8000`), then:

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Pages

### Landing page (`/`)
Marketing page: hero with value proposition, three-step how-it-works, feature cards, CTA to the explainer.

### Explainer page (`/explainer`)
The main product screen. You must configure API keys before using it — a settings panel will prompt you on first visit.

- **Paste mode**: paste GST notice text into the textarea.
- **File upload mode**: drag-drop or pick a file (PDF, image, text).
- Click **Analyze notice** to run the full pipeline.

## Settings panel (BYOK)

Located at the top of the explainer page. Every user supplies their own API keys:

- **LLM** (required): Groq API key and/or Google Gemini API key.
- **Supabase**: URL + service role key. Used for storage and notices table.
- **Postgres**: `DATABASE_URL` — alternative to Supabase for the transaction database.
- **Razorpay**: Key ID + Key Secret (test mode). For syncing real payment data.
- **PayPal**: Client ID + Client Secret (sandbox). For syncing PayPal transactions.

Click **Validate & Save** — the backend live-tests each key, then saves them in-memory for your session. Keys are never written to disk or shared between users.

## Components (`app/components/`)

| Component | Purpose |
|-----------|---------|
| `settings-panel.tsx` | API key entry, validation, status indicators |
| `results-view.tsx` | Four-section explanation output with citations + audit trail |
| `processing-state.tsx` | Animated 5-step progress indicator |
| `confidence-badge.tsx` | Green / amber / red confidence pill |
| `citation-marker.tsx` | Inline `[n]` superscript, click to expand source |
| `audit-trail.tsx` | Collapsible step-by-step audit log |
| `escalation-banner.tsx` | Warning banner for low-confidence results |
| `transaction-list.tsx` | Matched / flagged transaction display |
| `site-header.tsx` | Site header with logo |
| `site-footer.tsx` | Footer disclaimer |

## Environment

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_BACKEND_URL` | No | Backend URL (defaults to `http://localhost:8000`) |

## Build

```bash
npm run build   # TypeScript check + production build
```