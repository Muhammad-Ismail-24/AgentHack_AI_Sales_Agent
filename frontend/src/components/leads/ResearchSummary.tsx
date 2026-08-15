import { useState } from 'react';

import type { Lead } from '../../lib/types';
import { formatEmployees } from '../../lib/utils';

interface ResearchSummaryProps {
  lead: Lead;
}

export default function ResearchSummary({ lead }: ResearchSummaryProps) {
  const [isOpen, setIsOpen] = useState(true);

  const facts = [
    lead.website && { label: 'Website', value: lead.website, href: lead.website },
    lead.industry && { label: 'Industry', value: lead.industry },
    lead.location && { label: 'Location', value: lead.location },
    lead.employee_count !== null && {
      label: 'Size',
      value: formatEmployees(lead.employee_count),
    },
  ].filter(Boolean) as { label: string; value: string; href?: string }[];

  return (
    <section className="card overflow-hidden">
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        aria-expanded={isOpen}
        className="flex w-full items-center justify-between px-5 py-4 text-left hover:bg-slate-700/40"
      >
        <h2 className="text-sm font-semibold text-white">Research summary</h2>
        <span aria-hidden="true" className="text-slate-500">
          {isOpen ? '−' : '+'}
        </span>
      </button>

      {isOpen && (
        <div className="animate-fade-in space-y-4 border-t border-slate-700 px-5 py-4">
          {facts.length > 0 && (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-3">
              {facts.map((fact) => (
                <div key={fact.label}>
                  <dt className="text-xs uppercase tracking-wide text-slate-500">
                    {fact.label}
                  </dt>
                  <dd className="mt-0.5 truncate text-sm text-slate-200">
                    {fact.href ? (
                      <a
                        href={fact.href}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="text-indigo-400 hover:underline"
                      >
                        {fact.value}
                      </a>
                    ) : (
                      fact.value
                    )}
                  </dd>
                </div>
              ))}
            </dl>
          )}

          {lead.research_summary ? (
            <p className="whitespace-pre-line text-sm leading-relaxed text-slate-300">
              {lead.research_summary}
            </p>
          ) : (
            <p className="text-sm italic text-slate-500">
              No research recorded for this lead yet.
            </p>
          )}

          {lead.apollo_data && Object.keys(lead.apollo_data).length > 0 && (
            <details className="rounded-lg border border-slate-700 bg-slate-900/60 px-4 py-3">
              <summary className="cursor-pointer text-xs font-medium text-slate-400 hover:text-slate-200">
                Enrichment data
              </summary>
              <pre className="mt-3 max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs text-slate-400">
                {JSON.stringify(lead.apollo_data, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}
    </section>
  );
}
