import type { BadgeColor } from '../../lib/types';
import { cx } from '../../lib/utils';

interface BadgeProps {
  label: string;
  color?: BadgeColor;
  className?: string;
  title?: string;
}

// Warm-first. The only cool colours left in the app are the score bands'
// lime/emerald, which have to stay readable as "good" — everything else
// sits in the landing page's terracotta family.
const COLORS: Record<BadgeColor, string> = {
  green: 'bg-emerald-500 text-emerald-950',
  lime: 'bg-lime-500 text-lime-950',
  yellow: 'bg-amber-500 text-amber-950',
  honey: 'bg-honey-400 text-bark-950',
  red: 'bg-red-700 text-red-50',
  gray: 'bg-bark-600 text-bark-100',
  terra: 'bg-terra-600 text-terra-50',
};

export default function Badge({ label, color = 'gray', className, title }: BadgeProps) {
  return (
    <span
      title={title}
      className={cx(
        'inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5',
        'text-xs font-semibold',
        COLORS[color],
        className,
      )}
    >
      {label}
    </span>
  );
}
