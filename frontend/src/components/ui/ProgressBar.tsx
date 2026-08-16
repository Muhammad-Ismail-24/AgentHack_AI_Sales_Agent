import { cx } from '../../lib/utils';

interface ProgressBarProps {
  label?: string;
  current: number;
  total: number;
  /** Renders a striped, animated bar while a run is live. */
  indeterminate?: boolean;
  className?: string;
}

export default function ProgressBar({
  label,
  current,
  total,
  indeterminate = false,
  className,
}: ProgressBarProps) {
  const safeTotal = total > 0 ? total : 0;
  const percent =
    safeTotal === 0 ? 0 : Math.min(100, Math.round((current / safeTotal) * 100));

  return (
    <div className={cx('w-full', className)}>
      {(label || safeTotal > 0) && (
        <div className="mb-1.5 flex items-baseline justify-between gap-4">
          {label && <span className="text-sm text-bark-300">{label}</span>}
          {safeTotal > 0 && (
            <span className="shrink-0 text-xs tabular-nums text-bark-400">
              {current} of {safeTotal}
            </span>
          )}
        </div>
      )}

      <div
        className="h-2 w-full overflow-hidden rounded-full bg-bark-700"
        role="progressbar"
        aria-valuenow={indeterminate ? undefined : percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? 'Progress'}
      >
        {indeterminate ? (
          <div className="h-full w-1/3 animate-pulse rounded-full bg-terra-500" />
        ) : (
          <div
            className="h-full rounded-full bg-terra-500 transition-all duration-500 ease-out"
            style={{ width: `${percent}%` }}
          />
        )}
      </div>
    </div>
  );
}
