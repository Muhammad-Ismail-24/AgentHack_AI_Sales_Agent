interface NextActionPanelProps {
  nextAction: string | null;
}

export default function NextActionPanel({ nextAction }: NextActionPanelProps) {
  if (!nextAction) return null;

  return (
    <div className="mt-3 flex items-start gap-2.5 rounded-lg border border-terra-500/30 bg-terra-950/40 px-3 py-2.5">
      <span
        aria-hidden="true"
        className="mt-0.5 text-xs font-semibold uppercase tracking-wide text-terra-400"
      >
        Next
      </span>
      <p className="text-sm leading-relaxed text-terra-100">{nextAction}</p>
    </div>
  );
}
