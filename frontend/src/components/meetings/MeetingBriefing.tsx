import { useState } from 'react';

import type { MeetingBriefing as Briefing } from '../../lib/types';

interface MeetingBriefingProps {
  briefing: Briefing | null;
}

export default function MeetingBriefing({ briefing }: MeetingBriefingProps) {
  const [isOpen, setIsOpen] = useState(false);

  if (!briefing || Object.keys(briefing).length === 0) {
    return (
      <p className="mt-3 text-xs italic text-slate-500">
        No briefing generated for this meeting yet.
      </p>
    );
  }

  const keyPoints = briefing.key_points ?? [];
  const watchOut = briefing.watch_out_for ?? [];

  return (
    <div className="mt-3">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
        className="text-xs font-medium text-indigo-400 hover:text-indigo-300"
      >
        {isOpen ? 'Hide briefing' : 'Show pre-meeting briefing'}
      </button>

      {isOpen && (
        <div className="mt-3 animate-fade-in space-y-4 rounded-lg border border-slate-700 bg-slate-900/60 p-4">
          {briefing.customer_problem && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Their problem
              </h4>
              <p className="mt-1 text-sm leading-relaxed text-slate-300">
                {briefing.customer_problem}
              </p>
            </div>
          )}

          {briefing.recommended_service && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Pitch
              </h4>
              <p className="mt-1 text-sm text-indigo-300">
                {briefing.recommended_service}
              </p>
            </div>
          )}

          {keyPoints.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Key points
              </h4>
              <ul className="mt-1.5 space-y-1.5">
                {keyPoints.map((point) => (
                  <li
                    key={point}
                    className="flex gap-2 text-sm leading-relaxed text-slate-300"
                  >
                    <span aria-hidden="true" className="text-green-500">
                      ✓
                    </span>
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {watchOut.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Watch out for
              </h4>
              <ul className="mt-1.5 space-y-1.5">
                {watchOut.map((point) => (
                  <li
                    key={point}
                    className="flex gap-2 text-sm leading-relaxed text-slate-300"
                  >
                    <span aria-hidden="true" className="text-yellow-500">
                      !
                    </span>
                    {point}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
