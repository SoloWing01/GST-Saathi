---
title: GST Saathi
emoji: 🧾
colorFrom: teal
colorTo: gray
sdk: docker
pinned: false
app_port: 7860
---

# GST Saathi — Backend

FastAPI backend that parses GST/tax notices, cross-references transaction history,
and generates plain-language explanations with citations.

## Stack

- **FastAPI** — REST API
- **Supabase** — Postgres + pgvector + Storage
- **Groq / Gemini** — free-tier LLM for extraction + reasoning
- **sentence-transformers** — local embeddings for KB similarity search
- **Razorpay Test Mode** — real payment data integration
- **PayPal Reporting API** — real payment data integration
