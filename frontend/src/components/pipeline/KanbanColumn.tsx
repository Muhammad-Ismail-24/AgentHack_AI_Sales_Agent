import type { Lead } from '../../lib/types';
import LeadCard from './LeadCard';

interface KanbanColumnProps {
  stage: string;
  leads: Lead[];
}

export default function KanbanColumn({ stage, leads }: KanbanColumnProps) {
  return (
    <div className="flex w-64 shrink-0 flex-col rounded-xl border border-bark-800 bg-bark-900/60">
      <div className="flex items-center justify-between gap-2 border-b border-bark-800 px-3 py-2.5">
        <h3 className="truncate text-xs font-semibold uppercase tracking-wide text-bark-400">
          {stage}
        </h3>
        <span className="shrink-0 rounded-full bg-bark-700 px-2 py-0.5 text-xs font-semibold tabular-nums text-bark-200">
          {leads.length}
        </span>
      </div>

      <div className="flex-1 space-y-2 overflow-y-auto p-2">
        {leads.length === 0 ? (
          <p className="px-2 py-6 text-center text-xs text-bark-600">Empty</p>
        ) : (
          leads.map((lead) => <LeadCard key={lead.id} lead={lead} />)
        )}
      </div>
    </div>
  );
}
