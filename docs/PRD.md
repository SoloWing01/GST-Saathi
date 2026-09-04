# PRD — GST / Tax Notice Explainer for Small Merchants

## Problem
Small merchants on Razorpay receive GST/tax compliance notices (ASMT-10, DRC-01,
REG-17, GSTR-3A, etc.) and panic — they don't know what the notice means, why
they got it, whether it's serious, or what to do next. They don't have a CA on
speed dial.

## Who this is for
A small merchant (non-accountant) who has just received a notice and wants,
in plain language: what happened, why it likely happened (tied to their own
transactions), how serious it is, and what to do next.

## What the product does (one sentence)
Merchant uploads a notice → agent reads it, cross-references their own
transaction history, retrieves the relevant GST rule, and returns a
plain-language explanation with citations and a confidence level.

## MVP scope (build this, nothing more, first)
1. Upload a notice (PDF / image / pasted text).
2. Extract structured fields: notice type, GSTIN, tax period, amount in
   question, section/rule cited, due date.
3. Cross-reference the amount/period against the merchant's transaction
   history (synthetic Razorpay-style data + at least one real Test Mode
   API call).
4. Retrieve the matching entry from a small curated GST rules knowledge base.
5. Generate a plain-language response with four parts: **what this means**,
   **why you likely got it** (tied to specific transaction IDs), **what to do
   next**, **confidence level**.
6. Every claim in the response is tagged with its source (a KB citation or a
   transaction ID) — no unsourced claims.
7. Explicit "I'm not sure — here's what to check with a CA" fallback when
   confidence is low. This is a feature, not a failure.
8. An audit trail: a visible log of what the agent looked up and in what
   order, for every request.

## Explicitly out of scope for MVP (stretch only, after MVP works)
- Drafting a reply letter to the tax department.
- Supporting every notice type that exists (10–15 curated types is enough).
- Multi-language output (English only for MVP).
- Any claim framed as binding legal advice — always "likely" / "based on
  available information."

## Success metrics (what you report at demo time)
- Notice-type classification accuracy on your synthetic test set (e.g. 12/15).
- Correct mismatch detection rate on synthetic transactions with deliberate
  discrepancies.
- Correct "I don't know" rate — how often it declines rather than guesses on
  ambiguous inputs. This number is a selling point, not something to hide.
- Every response has ≥1 citation per factual claim — measured, not assumed.

## Non-negotiable constraints
- No runtime LLM calls to a paid API — use a free-tier provider (Groq or
  Gemini free tier) for the deployed app. Claude Code itself (the dev tool)
  is a separate cost and is fine.
- No real merchant data — synthetic transactions + synthetic/sample notices only.
- Never state a legal conclusion as certain. Always "likely," "based on the
  information available," with a source.
