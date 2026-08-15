import type { BadgeColor } from '../../lib/types';
import { cx } from '../../lib/utils';

interface BadgeProps {
  label: string;
  color?: BadgeColor;
  className?: string;
  title?: string;
}

const COLORS: Record<BadgeColor, string> = {
  green: 'bg-green-600 text-green-50',
  yellow: 'bg-yellow-500 text-yellow-950',
  red: 'bg-red-600 text-red-50',
  blue: 'bg-blue-600 text-blue-50',
  gray: 'bg-slate-600 text-slate-100',
  indigo: 'bg-indigo-600 text-indigo-50',
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
