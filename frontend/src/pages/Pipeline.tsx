import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

import PageWrapper from '../components/layout/PageWrapper';
import TopBar from '../components/layout/TopBar';
import KanbanBoard from '../components/pipeline/KanbanBoard';
import EmptyState from '../components/ui/EmptyState';
import ProgressBar from '../components/ui/ProgressBar';
import Spinner from '../components/ui/Spinner';
import { useLeads } from '../hooks/useLeads';
import { usePipelineContext } from '../hooks/usePipeline';

/** The nine graph nodes, in the order the orchestrator runs them. */
const STAGE_ORDER = [
  'Ingesting company',
  'Defining ICP',
  'Discovering leads',
  'Filtering leads',
  'Researching leads',
  'Qualifying leads',
  'Matching services',
  'Finding decision makers',
  'Writing emails',
];

function stageProgress(stage: string): number {
  const index = STAGE_ORDER.findIndex(
    (name) => name.toLowerCase() === stage.toLowerCase(),
  );
  if (index >= 0) return index + 1;
  return stage === 'complete' ? STAGE_ORDER.length : 0;
}

export default function Pipeline() {
  const navigate = useNavigate();
  const { status, isRunning, error: statusError } = usePipelineContext();
  const { leads, byStage, isLoading, error, refetch } = useLeads();

  // While a run is live, new leads land continuously — pull the board again
  // each time the backend reports a new stage.
  const stage = status?.stage;
  useEffect(() => {
    if (isRunning) void refetch();
  }, [stage, isRunning, refetch]);

  const current = stage ?? 'idle';
  const step = stageProgress(current);

  return (
    <>
      <TopBar
        title="Pipeline"
        subtitle={`${leads.length} lead${leads.length === 1 ? '' : 's'} in play`}
        isRunning={isRunning}
        stage={current}
      />

      <PageWrapper wide>
        {(isRunning || step > 0) && current !== 'idle' && (
          <div className="card mb-6 p-5">
            <ProgressBar
              label={
                isRunning
                  ? `Pipeline running — ${current} (stage ${step} of ${STAGE_ORDER.length})`
                  : `Pipeline ${current}`
              }
              current={step}
              total={STAGE_ORDER.length}
            />

            {status && (
              <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
                {[
                  ['Discovered', status.raw_leads_count],
                  ['Filtered', status.filtered_count],
                  ['Qualified', status.qualified_count],
                  ['Outreach', status.outreach_count],
                ].map(([label, value]) => (
                  <div key={String(label)}>
                    <dt className="text-xs uppercase tracking-wide text-slate-500">
                      {label}
                    </dt>
                    <dd className="mt-0.5 text-xl font-semibold tabular-nums text-white">
                      {value}
                    </dd>
                  </div>
                ))}
              </dl>
            )}

            {status?.error && (
              <p className="mt-4 rounded-lg border border-red-500/30 bg-red-950/40 px-3 py-2 text-sm text-red-200">
                {status.error}
              </p>
            )}
          </div>
        )}

        {(error || statusError) && (
          <p className="mb-6 rounded-lg border border-red-500/30 bg-red-950/40 px-4 py-3 text-sm text-red-200">
            {error ?? statusError}
          </p>
        )}

        {isLoading ? (
          <div className="flex justify-center py-24 text-slate-500">
            <Spinner size="lg" />
          </div>
        ) : leads.length === 0 ? (
          <EmptyState
            icon="▦"
            title="No leads yet"
            description="Run the pipeline against your ICP — every lead here comes from a real run."
            actionLabel="Set up a run"
            onAction={() => navigate('/onboarding')}
          />
        ) : (
          <KanbanBoard byStage={byStage} />
        )}
      </PageWrapper>
    </>
  );
}
