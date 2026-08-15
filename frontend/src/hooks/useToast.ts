import { useCallback, useState } from 'react';

import type { ToastType } from '../components/ui/Toast';

export interface ToastState {
  message: string;
  type: ToastType;
}

/** One toast at a time — a queue is more than this dashboard needs. */
export function useToast() {
  const [toast, setToast] = useState<ToastState | null>(null);

  const showToast = useCallback((message: string, type: ToastType = 'info') => {
    setToast({ message, type });
  }, []);

  const hideToast = useCallback(() => setToast(null), []);

  return { toast, showToast, hideToast };
}
