interface NextActionPanelProps {
  nextAction: string | null;
}

export default function NextActionPanel({ nextAction }: NextActionPanelProps) {
  if (!nextAction) return null;

  return (
    <div className="mt-3 flex items-start gap-2.5 rounded-lg border border-indigo-500/30 bg-indigo-950/40 px-3 py-2.5">
      <span
        aria-hidden="true"
        className="mt-0.5 text-xs font-semibold uppercase tracking-wide text-indigo-400"
      >
        Next
      </span>
      <p className="text-sm leading-relaxed text-indigo-100">{nextAction}</p>
    </div>
  );
}
