import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';

import { describeError, getPipelineStatus } from '../lib/api';
import type { PipelineStatus } from '../lib/types';

const POLL_MS = 3000;

/** Stages that mean the run is over — polling stops on these. */
const TERMINAL_STAGES = new Set(['complete', 'idle', 'failed']);

export interface UsePipelineResult {
  status: PipelineStatus | null;
  isRunning: boolean;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

/**
 * Polls GET /pipeline/status every 3s while a run is live, and stops once the
 * backend reports a terminal stage. Safe to call with a null sessionId — it
 * simply does nothing until one exists.
 */
export function usePipeline(sessionId: string | null): UsePipelineResult {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Refs so the polling effect doesn't re-subscribe on every state change.
  const timerRef = useRef<number | null>(null);
  const cancelledRef = useRef(false);

  const fetchStatus = useCallback(async () => {
    if (!sessionId) return;
    try {
      const next = await getPipelineStatus(sessionId);
      if (cancelledRef.current) return;
      setStatus(next);
      setError(null);
    } catch (err) {
      if (cancelledRef.current) return;
      setError(describeError(err));
    } finally {
      if (!cancelledRef.current) setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    cancelledRef.current = false;

    if (!sessionId) {
      setStatus(null);
      setIsLoading(false);
      return undefined;
    }

    setIsLoading(true);
    void fetchStatus();

    timerRef.current = window.setInterval(() => {
      void fetchStatus();
    }, POLL_MS);

    return () => {
      cancelledRef.current = true;
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [sessionId, fetchStatus]);

  // Once the backend says the run finished, stop hammering it.
  const stage = status?.stage;
  const backendRunning = status?.is_running ?? false;
  const isRunning = backendRunning && !TERMINAL_STAGES.has(stage ?? 'idle');

  useEffect(() => {
    if (!status) return;
    if (isRunning) return;
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, [status, isRunning]);

  return { status, isRunning, isLoading, error, refetch: fetchStatus };
}

// ── Shared context ───────────────────────────────────────────────────
// The sidebar and each page's top bar both need the live status. Sharing one
// poller through context avoids three components polling the same endpoint.

const PipelineContext = createContext<UsePipelineResult>({
  status: null,
  isRunning: false,
  isLoading: false,
  error: null,
  refetch: async () => {},
});

export const PipelineProvider = PipelineContext.Provider;

export function usePipelineContext(): UsePipelineResult {
  return useContext(PipelineContext);
}
