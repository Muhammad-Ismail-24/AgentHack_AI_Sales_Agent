import { useCallback, useEffect, useMemo, useState } from 'react';

import { describeError, getLeads } from '../lib/api';
import type { Lead, PipelineStage } from '../lib/types';

export interface UseLeadsResult {
  leads: Lead[];
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  filterByStage: (stage: PipelineStage) => Lead[];
  sortByScore: (direction?: 'asc' | 'desc') => Lead[];
  byStage: Record<string, Lead[]>;
}

/** Fetches leads on mount, with helpers for the table and the Kanban board. */
export function useLeads(sessionId?: string | null): UseLeadsResult {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLeads = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await getLeads(sessionId ?? undefined);
      setLeads(data);
      setError(null);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void fetchLeads();
  }, [fetchLeads]);

  /** Leads grouped by stage — the Kanban board reads straight off this. */
  const byStage = useMemo(() => {
    return leads.reduce<Record<string, Lead[]>>((acc, lead) => {
      (acc[lead.pipeline_stage] ??= []).push(lead);
      return acc;
    }, {});
  }, [leads]);

  const filterByStage = useCallback(
    (stage: PipelineStage) => leads.filter((lead) => lead.pipeline_stage === stage),
    [leads],
  );

  const sortByScore = useCallback(
    (direction: 'asc' | 'desc' = 'desc') =>
      [...leads].sort((a, b) => {
        // Unscored leads always sink to the bottom, whichever way we sort.
        const left = a.lead_score ?? -1;
        const right = b.lead_score ?? -1;
        return direction === 'desc' ? right - left : left - right;
      }),
    [leads],
  );

  return { leads, isLoading, error, refetch: fetchLeads, filterByStage, sortByScore, byStage };
}
