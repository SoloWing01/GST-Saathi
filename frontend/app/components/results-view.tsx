"use client";

import ConfidenceBadge from "./confidence-badge";
import CitationMarker from "./citation-marker";
import EscalationBanner from "./escalation-banner";
import AuditTrail from "./audit-trail";
import TransactionList from "./transaction-list";

type Citation = { text: string; source: string; type: string };

type Section = {
  title: string;
  content: string;
  citations: Array<{ claim: string; source: string; source_type: string }>;
};

type Sections = {
  what_it_means?: Section;
  why_you_got_it?: Section;
  what_to_do?: Section;
  confidence?: Section;
  confidence_and_disclaimer?: Section;
};

type Explanation = {
  sections: Sections;
  overall_confidence: string;
  is_low_confidence: boolean;
  ca_escalation_note?: string;
};

type ExtractionFields = {
  notice_type?: string;
  gstin?: string;
  tax_period?: string;
  amount?: number;
  section_cited?: string;
  due_date?: string;
};

type MatchedTxn = {
  payment_id: string;
  amount: number;
  date: string;
  status: string;
};

type FlaggedTxn = MatchedTxn & { mismatch_reason?: string };

type AuditEntry = {
  step: string;
  action: string;
  result: string;
  details?: string;
};

type Props = {
  explanation: Explanation;
  extraction?: { fields: ExtractionFields; confidence: string };
  cross_reference?: {
    matched_transactions: MatchedTxn[];
    flagged_transactions: FlaggedTxn[];
    total_transactions_in_period: number;
    total_amount_in_period: number;
  };
  audit_log: AuditEntry[];
  onReset: () => void;
};

function SectionCard({
  title,
  children,
  delay,
}: {
  title: string;
  children: React.ReactNode;
  delay: number;
}) {
  return (
    <div
      className="bg-surface rounded-2xl border border-border p-6 shadow-sm animate-fade-in"
      style={{ animationDelay: `${delay}ms` }}
    >
      <h3 className="text-sm font-semibold text-ink-muted uppercase tracking-wide mb-3">
        {title}
      </h3>
      <div className="text-ink leading-relaxed text-[15px]">{children}</div>
    </div>
  );
}

function renderWithCitations(
  section: Section | undefined,
  citations: Citation[]
): React.ReactNode {
  const text = section?.content;
  if (!text) return <span className="text-ink-faint italic">Not available</span>;

  const parts: React.ReactNode[] = [];
  let remaining = text;
  let citeIndex = 1;

  // Find citation patterns like [1], [2] etc in the text
  const citeRegex = /\[(\d+)\]/g;
  let match;
  let lastIndex = 0;

  while ((match = citeRegex.exec(remaining)) !== null) {
    // Text before citation
    if (match.index > lastIndex) {
      parts.push(
        <span key={`t-${lastIndex}`}>{remaining.slice(lastIndex, match.index)}</span>
      );
    }

    const citeNum = parseInt(match[1]);
    const cite = citations[citeNum - 1];
    if (cite) {
      parts.push(
        <CitationMarker key={`c-${match.index}`} index={citeNum} source={cite.source} />
      );
    } else {
      parts.push(<span key={`c-${match.index}`}>{match[0]}</span>);
    }

    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < remaining.length) {
    parts.push(<span key={`t-end`}>{remaining.slice(lastIndex)}</span>);
  }

  return parts.length > 0 ? parts : text;
}

export default function ResultsView({
  explanation,
  extraction,
  cross_reference,
  audit_log,
  onReset,
}: Props) {
  const sections = explanation.sections;
  const citations: Citation[] = [];

  // Collect citations from the explanation text patterns
  // The LLM typically includes [1], [2] etc referencing transaction IDs and KB sources
  if (cross_reference) {
    cross_reference.flagged_transactions.forEach((t, i) => {
      citations.push({
        text: t.payment_id,
        source: `Transaction ${t.payment_id}: ₹${t.amount.toLocaleString("en-IN")} on ${t.date} — ${t.mismatch_reason || t.status}`,
        type: "transaction",
      });
    });
    cross_reference.matched_transactions.slice(0, 3).forEach((t, i) => {
      citations.push({
        text: t.payment_id,
        source: `Transaction ${t.payment_id}: ₹${t.amount.toLocaleString("en-IN")} on ${t.date}`,
        type: "transaction",
      });
    });
  }

  return (
    <div className="w-full max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 animate-fade-in">
        <div className="min-w-0">
          {extraction?.fields && (
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <span className="text-sm font-medium text-ink bg-ground-warm px-2.5 py-0.5 rounded-md">
                {extraction.fields.notice_type}
              </span>
              {extraction.fields.section_cited && (
                <span className="text-sm text-ink-muted">
                  {extraction.fields.section_cited}
                </span>
              )}
            </div>
          )}
          <h2 className="text-xl font-semibold text-ink">Analysis results</h2>
        </div>
        <ConfidenceBadge
          level={explanation.overall_confidence as "high" | "medium" | "low"}
        />
      </div>

      {/* Escalation banner */}
      {explanation.is_low_confidence && (
        <EscalationBanner note={explanation.ca_escalation_note || ""} />
      )}

      {/* Extraction summary */}
      {extraction?.fields && (
        <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-ink-muted animate-fade-in">
          {extraction.fields.gstin && (
            <span>
              GSTIN: <span className="font-mono text-ink">{extraction.fields.gstin}</span>
            </span>
          )}
          {extraction.fields.tax_period && (
            <span>
              Period: <span className="text-ink">{extraction.fields.tax_period}</span>
            </span>
          )}
          {extraction.fields.amount != null && (
            <span>
              Amount: <span className="font-medium text-ink">
                ₹{extraction.fields.amount.toLocaleString("en-IN")}
              </span>
            </span>
          )}
          {extraction.fields.due_date && (
            <span>
              Due: <span className="text-ink">{extraction.fields.due_date}</span>
            </span>
          )}
        </div>
      )}

      {/* Four sections */}
      <SectionCard title="What this means" delay={100}>
        {renderWithCitations(sections.what_it_means, citations)}
      </SectionCard>

      <SectionCard title="Why you likely got it" delay={200}>
        {renderWithCitations(sections.why_you_got_it, citations)}
        {cross_reference && cross_reference.total_transactions_in_period > 0 && (
          <div className="mt-4 pt-4 border-t border-border">
            <TransactionList
              matched={cross_reference.matched_transactions}
              flagged={cross_reference.flagged_transactions}
            />
          </div>
        )}
      </SectionCard>

      <SectionCard title="What to do next" delay={300}>
        {renderWithCitations(sections.what_to_do, citations)}
      </SectionCard>

      <SectionCard title="Confidence & disclaimer" delay={400}>
        {renderWithCitations(sections.confidence || sections.confidence_and_disclaimer, citations)}
      </SectionCard>

      {/* Audit trail */}
      <div className="animate-fade-in" style={{ animationDelay: "500ms" }}>
        <AuditTrail entries={audit_log} />
      </div>

      {/* Actions */}
      <div className="flex justify-center pt-4 animate-fade-in" style={{ animationDelay: "600ms" }}>
        <button
          type="button"
          onClick={onReset}
          className="px-5 py-2.5 rounded-xl text-sm font-medium text-accent border border-accent/20 hover:bg-accent-light transition-colors cursor-pointer"
        >
          Analyze another notice
        </button>
      </div>
    </div>
  );
}
