import Button from './Button';

interface EmptyStateProps {
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
  /** A single glyph or emoji. Defaults to a neutral marker. */
  icon?: string;
}

export default function EmptyState({
  title,
  description,
  actionLabel,
  onAction,
  icon = '○',
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-16 text-center">
      <div
        aria-hidden="true"
        className="mb-4 flex h-14 w-14 items-center justify-center rounded-full border border-slate-700 bg-slate-800 text-2xl text-slate-500"
      >
        {icon}
      </div>

      <h3 className="text-base font-semibold text-slate-200">{title}</h3>

      {description && (
        <p className="mt-1.5 max-w-sm text-sm leading-relaxed text-slate-400">
          {description}
        </p>
      )}

      {actionLabel && onAction && (
        <Button onClick={onAction} className="mt-5">
          {actionLabel}
        </Button>
      )}
    </div>
  );
}
