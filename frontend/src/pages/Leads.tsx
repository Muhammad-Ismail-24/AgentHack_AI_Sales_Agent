import { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import PageWrapper from '../components/layout/PageWrapper';
import TopBar from '../components/layout/TopBar';
import ScoreBadge from '../components/leads/ScoreBadge';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import Spinner from '../components/ui/Spinner';
import { useLeads } from '../hooks/useLeads';
import { usePipelineContext } from '../hooks/usePipeline';
import { PIPELINE_STAGES } from '../lib/types';
import { stageToColor, truncate } from '../lib/utils';

type SortKey = 'score' | 'name' | 'recent';

export default function Leads() {
  const navigate = useNavigate();
  const { isRunning } = usePipelineContext();
  const { leads, isLoading, error } = useLeads();

  const [search, setSearch] = useState('');
  const [stageFilter, setStageFilter] = useState<string>('all');
  const [sort, setSort] = useState<SortKey>('score');

  const visible = useMemo(() => {
    const term = search.trim().toLowerCase();

    const filtered = leads.filter((lead) => {
      const matchesStage =
        stageFilter === 'all' || lead.pipeline_stage === stageFilter;
      const matchesSearch =
        term.length === 0 ||
        lead.company_name.toLowerCase().includes(term) ||
        (lead.industry ?? '').toLowerCase().includes(term) ||
        (lead.location ?? '').toLowerCase().includes(term);
      return matchesStage && matchesSearch;
    });

    return [...filtered].sort((a, b) => {
      if (sort === 'name') return a.company_name.localeCompare(b.company_name);
      if (sort === 'recent') {
        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      }
      // Unscored leads sink to the bottom.
      return (b.lead_score ?? -1) - (a.lead_score ?? -1);
    });
  }, [leads, search, stageFilter, sort]);

  return (
    <>
      <TopBar
        title="Leads"
        subtitle={`${visible.length} of ${leads.length} shown`}
        isRunning={isRunning}
      />

      <PageWrapper>
        <div className="mb-5 flex flex-wrap items-center gap-3">
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search company, industry or location"
            className="input max-w-xs"
            aria-label="Search leads"
          />

          <select
            value={stageFilter}
            onChange={(event) => setStageFilter(event.target.value)}
            className="input max-w-[14rem]"
            aria-label="Filter by stage"
          >
            <option value="all">All stages</option>
            {PIPELINE_STAGES.map((stage) => (
              <option key={stage} value={stage}>
                {stage}
              </option>
            ))}
          </select>

          <select
            value={sort}
            onChange={(event) => setSort(event.target.value as SortKey)}
            className="input max-w-[12rem]"
            aria-label="Sort leads"
          >
            <option value="score">Highest score</option>
            <option value="name">Company A–Z</option>
            <option value="recent">Most recent</option>
          </select>
        </div>

        {error && (
          <p className="mb-5 rounded-lg border border-red-500/30 bg-red-950/40 px-4 py-3 text-sm text-red-200">
            {error}
          </p>
        )}

        {isLoading ? (
          <div className="flex justify-center py-24 text-bark-500">
            <Spinner size="lg" />
          </div>
        ) : visible.length === 0 ? (
          <EmptyState
            icon="☰"
            title={leads.length === 0 ? 'No leads yet' : 'Nothing matches those filters'}
            description={
              leads.length === 0
                ? 'Run the pipeline to discover and qualify leads.'
                : 'Try clearing the search box or picking a different stage.'
            }
            actionLabel={leads.length === 0 ? 'Set up a run' : 'Clear filters'}
            onAction={() => {
              if (leads.length === 0) {
                navigate('/onboarding');
              } else {
                setSearch('');
                setStageFilter('all');
              }
            }}
          />
        ) : (
          <div className="card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-bark-700 bg-bark-900/60">
                  <tr className="text-xs uppercase tracking-wide text-bark-500">
                    <th className="px-4 py-3 font-medium">Company</th>
                    <th className="px-4 py-3 font-medium">Industry</th>
                    <th className="px-4 py-3 font-medium">Location</th>
                    <th className="px-4 py-3 font-medium">Score</th>
                    <th className="px-4 py-3 font-medium">Stage</th>
                    <th className="px-4 py-3 font-medium">Service</th>
                    <th className="px-4 py-3 font-medium">Contacts</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>

                <tbody className="divide-y divide-bark-800">
                  {visible.map((lead) => (
                    <tr key={lead.id} className="hover:bg-bark-700/30">
                      <td className="px-4 py-3 font-medium text-white">
                        {lead.company_name}
                      </td>
                      <td className="px-4 py-3 text-bark-400">
                        {lead.industry ?? '—'}
                      </td>
                      <td className="px-4 py-3 text-bark-400">
                        {lead.location ?? '—'}
                      </td>
                      <td className="px-4 py-3">
                        <ScoreBadge score={lead.lead_score} />
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${stageToColor(
                            lead.pipeline_stage,
                          )}`}
                        >
                          {lead.pipeline_stage}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-bark-400">
                        {truncate(lead.recommended_service, 28) || '—'}
                      </td>
                      <td className="px-4 py-3 tabular-nums text-bark-400">
                        {lead.contacts.length}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => navigate(`/leads/${lead.id}`)}
                        >
                          View details
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </PageWrapper>
    </>
  );
}
