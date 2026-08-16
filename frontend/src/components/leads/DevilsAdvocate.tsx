import { useCallback, useEffect, useState } from 'react';

import { describeError, getDevilsAdvocate, runDevilsAdvocate } from '../../lib/api';
import type { DebateArgument, EvidenceStrength, Verdict } from '../../lib/types';
import { scoreToBadgeColor } from '../../lib/utils';
import Badge from '../ui/Badge';
import Button from '../ui/Button';
import Spinner from '../ui/Spinner';

interface DevilsAdvocateProps {
  leadId: string;
  onError: (message: string) => void;
}

const STRENGTH_LABELS: Record<EvidenceStrength, string> = {
  high: 'Strong evidence',
  medium: 'Partial evidence',
  low: 'Low evidence',
};

const STRENGTH_COLORS = {
  high: 'green',
  medium: 'yellow',
  low: 'red',
} as const;

interface SideProps {
  title: string;
  accent: string;
  args: DebateArgument[];
  closing: string | null;
  won: boolean;
}

function Side({ title, accent, args, closing, won }: SideProps) {
  return (
    <div
      className={`rounded-lg border bg-slate-900/60 p-4 ${
        won ? accent : 'border-slate-700 opacity-70'
      }`}
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          {title}
        </h4>
        {won && <Badge label="Prevailed" color="indigo" />}
      </div>

      {args.length === 0 ? (
        <p className="text-sm italic text-slate-500">No argument was made.</p>
      ) : (
        <ul className="space-y-3">
          {args.map((argument) => (
            <li key={argument.claim}>
              <p className="text-sm leading-relaxed text-slate-200">
                {argument.claim}
              </p>
              {/* Rule 1 of the build spec: every claim shows its grounding. */}
              <p className="mt-1 border-l-2 border-slate-700 pl-2 text-xs italic text-slate-500">
                {argument.evidence}
              </p>
            </li>
          ))}
        </ul>
      )}

      {closing && (
        <p className="mt-4 border-t border-slate-700 pt-3 text-sm font-medium text-slate-300">
          {closing}
        </p>
      )}
    </div>
  );
}

/**
 * The Devil's Advocate transcript: a Prosecutor and a Defender argue over the
 * lead, and the Judge's confidence becomes the score shown at the top.
 *
 * Fetches the last stored verdict on mount and renders an empty state when
 * there is none — a debate costs three LLM calls, so it only runs on a click.
 */
export default function DevilsAdvocate({ leadId, onError }: DevilsAdvocateProps) {
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRunning, setIsRunning] = useState(false);

  const fetchVerdict = useCallback(async () => {
    setIsLoading(true);
    try {
      setVerdict(await getDevilsAdvocate(leadId));
    } catch (err) {
      onError(describeError(err));
    } finally {
      setIsLoading(false);
    }
  }, [leadId, onError]);

  useEffect(() => {
    void fetchVerdict();
  }, [fetchVerdict]);

  async function handleRun() {
    setIsRunning(true);
    try {
      setVerdict(await runDevilsAdvocate(leadId));
    } catch (err) {
      onError(describeError(err));
    } finally {
      setIsRunning(false);
    }
  }

  const prosecutionWon = verdict?.winner === 'prosecution';
  const strength = verdict?.evidence_strength ?? null;

  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-white">Devil&apos;s Advocate</h2>
        <Button size="sm" variant="secondary" onClick={handleRun} loading={isRunning}>
          {verdict ? 'Re-run debate' : 'Run debate'}
        </Button>
      </div>

      {isLoading ? (
        <div className="card flex justify-center px-5 py-10 text-slate-500">
          <Spinner />
        </div>
      ) : !verdict ? (
        <p className="card px-5 py-6 text-sm italic text-slate-500">
          No debate held yet. Two agents will argue this lead — one to drop it,
          one to pursue it — and a third resolves the argument into a
          confidence score.
        </p>
      ) : (
        <div className="card space-y-5 p-5">
          <div className="flex flex-wrap items-center gap-3">
            <span aria-hidden="true" className="text-2xl">
              ⚖️
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-white">
                Verdict: {prosecutionWon ? 'drop this lead' : 'pursue this lead'}
              </p>
              {verdict.decisive_argument && (
                <p className="mt-0.5 text-xs text-slate-400">
                  Decided on: {verdict.decisive_argument}
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {strength && (
                <Badge
                  label={STRENGTH_LABELS[strength]}
                  color={STRENGTH_COLORS[strength]}
                  title="How much real research the debate had to work with"
                />
              )}
              <Badge
                label={`${verdict.confidence ?? '—'}% confident`}
                color={scoreToBadgeColor(verdict.confidence)}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Side
              title="Prosecution — drop it"
              accent="border-red-500/50"
              args={verdict.prosecution}
              closing={verdict.prosecution_closing}
              won={prosecutionWon}
            />
            <Side
              title="Defence — pursue it"
              accent="border-green-500/50"
              args={verdict.defense}
              closing={verdict.defense_closing}
              won={!prosecutionWon}
            />
          </div>

          {verdict.reasoning && (
            <div className="rounded-lg border border-indigo-500/30 bg-indigo-950/30 p-4">
              <h4 className="text-xs font-semibold uppercase tracking-wide text-indigo-400">
                The judge
              </h4>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-300">
                {verdict.reasoning}
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
