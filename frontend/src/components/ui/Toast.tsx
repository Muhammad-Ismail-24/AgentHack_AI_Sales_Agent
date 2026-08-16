import { useEffect } from 'react';

import { cx } from '../../lib/utils';

export type ToastType = 'success' | 'error' | 'info';

interface ToastProps {
  message: string;
  type?: ToastType;
  onClose: () => void;
  /** Milliseconds before auto-dismiss. Pass 0 to require a manual close. */
  duration?: number;
}

const STYLES: Record<ToastType, string> = {
  success: 'border-green-500/40 bg-green-950/90 text-green-100',
  error: 'border-red-500/40 bg-red-950/90 text-red-100',
  info: 'border-terra-500/40 bg-terra-950/90 text-terra-100',
};

const ICONS: Record<ToastType, string> = {
  success: '✓',
  error: '!',
  info: 'i',
};

export default function Toast({
  message,
  type = 'info',
  onClose,
  duration = 3000,
}: ToastProps) {
  useEffect(() => {
    if (duration <= 0) return undefined;
    const timer = window.setTimeout(onClose, duration);
    return () => window.clearTimeout(timer);
  }, [duration, onClose, message]);

  return (
    <div
      role="status"
      aria-live="polite"
      className={cx(
        'fixed bottom-6 right-6 z-50 flex max-w-md animate-slide-up items-start gap-3',
        'rounded-xl border px-4 py-3 shadow-xl backdrop-blur',
        STYLES[type],
      )}
    >
      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/15 text-xs font-bold">
        {ICONS[type]}
      </span>
      <p className="flex-1 text-sm leading-relaxed">{message}</p>
      <button
        type="button"
        onClick={onClose}
        aria-label="Dismiss"
        className="-mr-1 -mt-1 rounded px-1.5 text-lg leading-none opacity-60 hover:opacity-100"
      >
        ×
      </button>
    </div>
  );
}
