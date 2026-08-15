import { useCallback, useEffect, useRef, useState } from 'react';

import { describeError, getInbox } from '../lib/api';
import type { InboxItem } from '../lib/types';

const REFRESH_MS = 30_000;

export interface UseInboxResult {
  replies: InboxItem[];
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * Replies with their lead and contact already resolved by the backend
 * (GET /inbox), auto-refreshing every 30s so a reply that lands mid-demo
 * appears without a manual reload.
 */
export function useInbox(): UseInboxResult {
  const [replies, setReplies] = useState<InboxItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const cancelledRef = useRef(false);

  const fetchInbox = useCallback(async () => {
    try {
      const data = await getInbox();
      if (cancelledRef.current) return;
      setReplies(data);
      setError(null);
    } catch (err) {
      if (cancelledRef.current) return;
      setError(describeError(err));
    } finally {
      if (!cancelledRef.current) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    cancelledRef.current = false;
    void fetchInbox();

    const timer = window.setInterval(() => {
      void fetchInbox();
    }, REFRESH_MS);

    return () => {
      cancelledRef.current = true;
      window.clearInterval(timer);
    };
  }, [fetchInbox]);

  return { replies, isLoading, error, refetch: fetchInbox };
}
