export default function EscalationBanner({ note }: { note: string }) {
  return (
    <div className="rounded-xl border border-caution-border/40 bg-caution-light p-5 animate-fade-in">
      <div className="flex gap-3">
        <svg
          className="h-5 w-5 text-caution shrink-0 mt-0.5"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z"
          />
        </svg>
        <div>
          <p className="text-sm font-semibold text-caution">
            Please consult a Chartered Accountant
          </p>
          <p className="text-sm text-caution/80 mt-1 leading-relaxed">
            {note ||
              "Our analysis has low confidence for this notice. A qualified CA can verify the details and advise on the correct response."}
          </p>
        </div>
      </div>
    </div>
  );
}
