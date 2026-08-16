import { useCallback, useEffect, useState } from 'react';

import {
  describeError,
  getAutopsy,
  getAutopsyInsights,
  runAutopsy,
} from '../../lib/api';
import type { Autopsy, AutopsyInsights, MisfireTag } from '../../lib/types';
import { formatDate } from '../../lib/utils';
import Badge from '../ui/Badge';
import Button from '../ui/Button';
import Spinner from '../ui/Spinner';

interface DealAutopsyProps {
  leadId: string;
  onError: (message: string) => void;
}

const MISFIRE_LABELS: Record<MisfireTag, string> = {
  wrong_service: 'Wrong service',
  wrong_persona: 'Wrong persona',
  wrong_timing: 'Wrong timing',
  slow_response: 'Too slow',
  weak_personalisation: 'Thin personalisation',
  no_engagement: 'Never engaged',
  price: 'Price',
};

interface StatProps {
  label: string;
  value: string;
  alarming?: boolean;
}

function Stat({ label, value, alarming = false }: StatProps) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd
        className={`mt-0.5 text-sm font-semibold tabular-nums ${
          alarming ? 'text-red-400' : 'text-slate-200'
        }`}
      >
        {value}
      </dd>
    </div>
  );
}

function hours(value: number | null): string {
  return value === null ? '—' : `${value}h`;
}

/**
 * The toe tag on a dead lead: cause of death, the misfire, the correction —
 * and what every autopsy so far argues the ICP should change to, which is the
 * part that closes the learning loop.
 *
 * Only rendered for leads in a rejected stage; the backend refuses an autopsy
 * on a live deal, since a "cause of death" for a deal still in play would be
 * a fabrication.
 */
export default function DealAutopsy({ leadId, onError }: DealAutopsyProps) {
  const [autopsy, setAutopsy] = useState<Autopsy | null>(null);
  const [insights, setInsights] = useState<AutopsyInsights | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);

  const fetchAutopsy = useCallback(async () => {
    setIsLoading(true);
    try {
      const [existing, rollup] = await Promise.all([
        getAutopsy(leadId),
        getAutopsyInsights(),
      ]);
      setAutopsy(existing);
      setInsights(rollup);
    } catch (err) {
      onError(describeError(err));
    } finally {
      setIsLoading(false);
    }
  }, [leadId, onError]);

  useEffect(() => {
    void fetchAutopsy();
  }, [fetchAutopsy]);

  async function handleRun() {
    setIsRunning(true);
    try {
      setAutopsy(await runAutopsy(leadId));
      setInsights(await getAutopsyInsights());
    } catch (err) {
      onError(describeError(err));
    } finally {
      setIsRunning(false);
    }
  }

  const stats = autopsy?.engagement_stats ?? null;
  // The gap that usually explains the death: we answered slower than they did.
  const weWereSlower =
    stats !== null &&
    stats.our_avg_response_hours !== null &&
    stats.their_avg_response_hours !== null &&
    stats.our_avg_response_hours > stats.their_avg_response_hours;

  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-white">Deal autopsy</h2>
        <Button size="sm" variant="danger" onClick={handleRun} loading={isRunning}>
          {autopsy ? 'Re-run autopsy' : 'Run autopsy'}
        </Button>
      </div>

      {isLoading ? (
        <div className="card flex justify-center px-5 py-10 text-slate-500">
          <Spinner />
        </div>
      ) : !autopsy ? (
        <p className="card px-5 py-6 text-sm italic text-slate-500">
          This deal is dead and has not been examined. An autopsy reads the
          whole thread and returns the cause of death, the misfire, and the
          correction — then feeds that back into the ICP.
        </p>
      ) : (
        <div className="space-y-4">
          <article className="rounded-xl border border-red-900/60 bg-red-950/30 p-5">
            <div className="flex items-start justify-between gap-3 border-b border-dashed border-red-900/60 pb-3">
              <div className="min-w-0">
                <p className="text-xs uppercase tracking-widest text-red-400">
                  Cause of death
                </p>
                <p className="mt-1 text-sm font-semibold leading-relaxed text-red-100">
                  {autopsy.cause_of_death}
                </p>
              </div>
              {autopsy.misfire_tag && (
                <Badge
                  label={MISFIRE_LABELS[autopsy.misfire_tag] ?? autopsy.misfire_tag}
                  color="red"
                />
              )}
            </div>

            {autopsy.cause_evidence && (
              <p className="mt-3 border-l-2 border-red-900/60 pl-2 text-xs italic text-red-300/80">
                {autopsy.cause_evidence}
              </p>
            )}

            <dl className="mt-4 space-y-3">
              {autopsy.misfire && (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">
                    The misfire
                  </dt>
                  <dd className="mt-0.5 text-sm leading-relaxed text-slate-300">
                    {autopsy.misfire}
                  </dd>
                </div>
              )}
              {autopsy.correction && (
                <div>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">
                    The correction
                  </dt>
                  <dd className="mt-0.5 text-sm leading-relaxed text-slate-300">
                    {autopsy.correction}
                  </dd>
                </div>
              )}
            </dl>

            {stats && (
              <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-red-900/60 pt-4 sm:grid-cols-4">
                <Stat label="Emails sent" value={String(stats.emails_sent)} />
                <Stat label="Replies" value={String(stats.replies_received)} />
                <Stat
                  label="Their reply time"
                  value={hours(stats.their_avg_response_hours)}
                />
                <Stat
                  label="Our reply time"
                  value={hours(stats.our_avg_response_hours)}
                  alarming={weWereSlower}
                />
              </dl>
            )}

            <p className="mt-4 text-xs text-slate-500">
              Examined {formatDate(autopsy.created_at)}
              {autopsy.confidence !== null &&
                ` · ${autopsy.confidence}% diagnostic confidence`}
            </p>
          </article>

          {autopsy.icp_adjustment && (
            <div className="rounded-lg border border-indigo-500/30 bg-indigo-950/30 p-4">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-indigo-400">
                Fed back into the ICP
              </h4>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-300">
                {autopsy.icp_adjustment}
              </p>
              {insights && insights.total_autopsies > 0 && (
                <p className="mt-3 border-t border-indigo-500/20 pt-3 text-xs text-slate-400">
                  Across {insights.total_autopsies} autops
                  {insights.total_autopsies === 1 ? 'y' : 'ies'}, the leading
                  misfire is{' '}
                  <span className="font-semibold text-indigo-300">
                    {insights.top_misfire
                      ? MISFIRE_LABELS[insights.top_misfire] ?? insights.top_misfire
                      : 'not yet clear'}
                  </span>
                  {insights.lessons[0] && ` — ${insights.lessons[0].adjustment}`}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
