export default function TransactionList({
  matched,
  flagged,
}: {
  matched: Array<{ payment_id: string; amount: number; date: string; status: string }>;
  flagged: Array<{ payment_id: string; amount: number; date: string; status: string; mismatch_reason?: string }>;
}) {
  if (!matched.length && !flagged.length) {
    return (
      <p className="text-sm text-ink-muted italic">
        No matching transactions found for this notice period.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {flagged.length > 0 && (
        <div>
          <p className="text-xs font-medium text-caution uppercase tracking-wide mb-2">
            Flagged ({flagged.length})
          </p>
          <div className="space-y-1.5">
            {flagged.map((t) => (
              <div
                key={t.payment_id}
                className="flex items-center justify-between py-2 px-3 rounded-lg bg-caution-light/50 border border-caution-border/20"
              >
                <div className="min-w-0">
                  <span className="text-sm font-mono text-ink">
                    {t.payment_id}
                  </span>
                  {t.mismatch_reason && (
                    <span className="block text-xs text-caution mt-0.5">
                      {t.mismatch_reason}
                    </span>
                  )}
                </div>
                <span className="text-sm font-medium text-ink shrink-0 ml-3">
                  ₹{t.amount.toLocaleString("en-IN")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {matched.length > 0 && (
        <div>
          {flagged.length > 0 && (
            <p className="text-xs font-medium text-ink-muted uppercase tracking-wide mb-2">
              Other matched ({matched.length})
            </p>
          )}
          {!flagged.length && (
            <p className="text-xs font-medium text-ink-muted uppercase tracking-wide mb-2">
              Matched ({matched.length})
            </p>
          )}
          <div className="space-y-1">
            {matched.slice(0, 5).map((t) => (
              <div
                key={t.payment_id}
                className="flex items-center justify-between py-1.5 px-3 rounded-lg hover:bg-ground-warm/50 transition-colors"
              >
                <span className="text-sm font-mono text-ink-muted">
                  {t.payment_id}
                </span>
                <span className="text-sm text-ink-muted">
                  ₹{t.amount.toLocaleString("en-IN")}
                </span>
              </div>
            ))}
            {matched.length > 5 && (
              <p className="text-xs text-ink-faint px-3">
                +{matched.length - 5} more
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
