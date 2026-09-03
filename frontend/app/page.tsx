import Link from "next/link";
import SiteHeader from "./components/site-header";
import SiteFooter from "./components/site-footer";

const STEPS = [
  {
    n: "01",
    title: "Paste or upload your notice",
    desc: "Paste the text or upload a file — PDF, scan, screenshot, any GST letter (ASMT, DRC, REG, GSTR mismatch).",
  },
  {
    n: "02",
    title: "We read it like a tax officer",
    desc: "Structured fields are extracted and cross-checked against your transactions and the GST rulebook.",
  },
  {
    n: "03",
    title: "Get the plain-language meaning",
    desc: "A calm, four-part answer: what it means, why you likely got it, what to do next, and how confident we are.",
  },
];

const FEATURES = [
  {
    title: "Every sentence sourced",
    desc: "Each claim carries a small citation linking to the exact rule section or transaction behind it.",
  },
  {
    title: "Your keys, your control",
    desc: "Bring your own LLM, Supabase, and payment-provider keys. Nothing is shared or stored on our side.",
  },
  {
    title: "Built for small merchants",
    desc: "No compliance jargon. No dense legal text. Short sentences and clear next steps reduce the panic.",
  },
];

export default function Home() {
  return (
    <main className="min-h-screen flex flex-col">
      <SiteHeader />

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div
          className="pointer-events-none absolute inset-0 -z-10"
          aria-hidden="true"
        >
          <div className="absolute -top-40 right-0 h-96 w-96 rounded-full bg-accent-light blur-3xl opacity-70 dark:opacity-40" />
          <div className="absolute top-20 -left-20 h-72 w-72 rounded-full bg-accent-light blur-3xl opacity-50 dark:opacity-30" />
        </div>

        <div className="max-w-5xl mx-auto px-6 pt-20 pb-16 sm:pt-28 sm:pb-24 text-center">
          <p className="inline-flex items-center gap-2 text-xs font-medium text-accent-dark bg-accent-light/60 dark:bg-accent-light px-3 py-1.5 rounded-full">
            <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse-dot" />
            A GST notice, translated into plain language
          </p>

          <h1 className="mt-6 text-balance text-4xl sm:text-6xl font-display font-semibold tracking-tight text-ink">
            Tax notices shouldn&apos;t
            <span className="text-accent"> feel like a foreign language.</span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-pretty text-lg text-ink-muted">
            GST Saathi turns any tax letter into a calm, sourced
            explanation — what it means, why you got it, and exactly what to do
            next. Built for small merchants, not lawyers.
          </p>

          <div className="mt-9 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link
              href="/explainer"
              className="px-7 py-3.5 rounded-xl bg-accent text-accent-foreground text-base font-semibold hover:bg-accent-dark transition-all hover:-translate-y-0.5 shadow-sm"
            >
              Get started — explain a notice
            </Link>
            <a
              href="#how-it-works"
              className="px-7 py-3.5 rounded-xl border border-border text-ink font-medium hover:bg-surface-raised transition-colors"
            >
              See how it works
            </a>
          </div>

          <div className="mt-12 grid grid-cols-3 gap-4 max-w-lg mx-auto">
            {[
              { k: "15+", v: "GST rule sections" },
              { k: "4", v: "clear answer sections" },
              { k: "100%", v: "fresh & cited" },
            ].map((s) => (
              <div
                key={s.v}
                className="px-3 py-4 rounded-2xl border border-border bg-surface/80"
              >
                <div className="text-2xl font-semibold text-accent-dark dark:text-accent">
                  {s.k}
                </div>
                <div className="mt-1 text-xs text-ink-muted">{s.v}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how-it-works" className="bg-surface/60 border-y border-border">
        <div className="max-w-5xl mx-auto px-6 py-16 sm:py-20">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-wider text-accent-dark dark:text-accent">
              How it works
            </p>
            <h2 className="mt-2 text-2xl sm:text-3xl font-display font-semibold tracking-tight text-ink">
              Three steps from worry to clarity
            </h2>
          </div>

          <div className="mt-10 grid gap-4 sm:grid-cols-3">
            {STEPS.map((step) => (
              <div
                key={step.n}
                className="rounded-2xl border border-border bg-surface p-6 flex flex-col"
              >
                <span className="text-sm font-semibold text-ink-faint">
                  {step.n}
                </span>
                <h3 className="mt-3 text-lg font-semibold text-ink">
                  {step.title}
                </h3>
                <p className="mt-2 text-sm text-ink-muted leading-relaxed">
                  {step.desc}
                </p>
              </div>
            ))}
          </div>

          <div className="mt-10 text-center">
            <Link
              href="/explainer"
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-accent text-accent-foreground font-semibold hover:bg-accent-dark transition-colors"
            >
              Get started
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3"
                />
              </svg>
            </Link>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-5xl mx-auto px-6 py-16 sm:py-20">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-wider text-accent-dark dark:text-accent">
            Why it works
          </p>
          <h2 className="mt-2 text-2xl sm:text-3xl font-display font-semibold tracking-tight text-ink">
            Clarity is the point
          </h2>
        </div>

        <div className="mt-10 grid gap-4 sm:grid-cols-3">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="rounded-2xl border border-border bg-surface/70 p-6"
            >
              <div className="h-9 w-9 rounded-lg bg-accent-light text-accent-dark dark:text-accent flex items-center justify-center">
                <svg
                  className="h-5 w-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.75}
                  stroke="currentColor"
                  aria-hidden="true"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
              </div>
              <h3 className="mt-4 text-lg font-semibold text-ink">{f.title}</h3>
              <p className="mt-2 text-sm text-ink-muted leading-relaxed">
                {f.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Final CTA */}
      <section className="max-w-5xl mx-auto px-6 pb-20">
        <div className="rounded-3xl border border-border bg-gradient-to-br from-accent-light/50 to-surface p-10 sm:p-14 text-center overflow-hidden relative">
          <div className="pointer-events-none absolute -bottom-24 -right-24 h-72 w-72 rounded-full bg-accent-light blur-3xl opacity-70 dark:opacity-40" />
          <h2 className="relative text-2xl sm:text-3xl font-display font-semibold tracking-tight text-ink">
            Got a GST notice sitting open?
          </h2>
          <p className="relative mx-auto mt-3 max-w-xl text-ink-muted">
            Stop decoding legalese. Paste it in or upload it and get an explanation you can
            actually act on — in under a minute.
          </p>
          <div className="relative mt-7">
            <Link
              href="/explainer"
              className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl bg-accent text-accent-foreground font-semibold hover:bg-accent-dark transition-all hover:-translate-y-0.5 shadow-sm"
            >
              Get started now
            </Link>
          </div>
        </div>
      </section>

      <SiteFooter />
    </main>
  );
}
