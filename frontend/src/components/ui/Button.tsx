import type { ReactNode } from 'react';

import { cx } from '../../lib/utils';
import Spinner from './Spinner';

interface ButtonProps {
  children: ReactNode;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  loading?: boolean;
  type?: 'button' | 'submit';
  className?: string;
  title?: string;
}

// The landing page's buttons sit on a hard shadow and press down on click;
// these are the restrained dashboard version of that same gesture.
const VARIANTS = {
  primary:
    'bg-terra-600 text-white shadow-md shadow-terra-950/50 hover:bg-terra-500 ' +
    'active:translate-y-px active:shadow-sm disabled:bg-terra-900 disabled:text-terra-300/60 ' +
    'disabled:shadow-none disabled:translate-y-0',
  secondary:
    'bg-bark-700 text-bark-100 shadow-md shadow-black/30 hover:bg-bark-600 ' +
    'active:translate-y-px active:shadow-sm disabled:bg-bark-800 disabled:text-bark-500 ' +
    'disabled:shadow-none disabled:translate-y-0',
  ghost:
    'bg-transparent text-bark-300 hover:bg-bark-800 hover:text-cream disabled:text-bark-600',
  danger:
    'bg-red-700 text-white shadow-md shadow-red-950/50 hover:bg-red-600 ' +
    'active:translate-y-px active:shadow-sm disabled:bg-red-900 disabled:text-red-200/60 ' +
    'disabled:shadow-none disabled:translate-y-0',
} as const;

const SIZES = {
  sm: 'px-3 py-1.5 text-xs gap-1.5',
  md: 'px-4 py-2 text-sm gap-2',
  lg: 'px-6 py-3 text-base gap-2.5',
} as const;

export default function Button({
  children,
  onClick,
  variant = 'primary',
  size = 'md',
  disabled = false,
  loading = false,
  type = 'button',
  className,
  title,
}: ButtonProps) {
  return (
    <button
      type={type}
      title={title}
      onClick={onClick}
      disabled={disabled || loading}
      className={cx(
        'inline-flex items-center justify-center rounded-lg font-medium',
        'transition duration-150 disabled:cursor-not-allowed',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
    >
      {loading && <Spinner size="sm" />}
      {children}
    </button>
  );
}
