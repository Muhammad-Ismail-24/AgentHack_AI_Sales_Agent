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
    <div className="flex flex-col items-center justify-center px-6 py-20 text-center">
      {/* Warm halo behind the glyph so an empty screen still feels designed
          rather than unfinished — this is the most-seen state before a run. */}
      <div className="relative mb-5">
        <div
          aria-hidden="true"
          className="absolute inset-0 -m-6 rounded-full bg-terra-600/10 blur-2xl"
        />
        <div
          aria-hidden="true"
          className="relative flex h-16 w-16 items-center justify-center rounded-2xl
                     border border-bark-700 bg-gradient-to-br from-bark-800 to-bark-900
                     text-2xl text-terra-400/80 shadow-lg shadow-black/40"
        >
          {icon}
        </div>
      </div>

      <h3 className="text-base font-semibold text-bark-100">{title}</h3>

      {description && (
        <p className="mt-2 max-w-sm text-sm leading-relaxed text-bark-400">
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
