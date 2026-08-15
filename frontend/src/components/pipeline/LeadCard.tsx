import { useNavigate } from 'react-router-dom';

import type { Lead } from '../../lib/types';
import { truncate } from '../../lib/utils';
import ScoreBadge from '../leads/ScoreBadge';

interface LeadCardProps {
  lead: Lead;
}

export default function LeadCard({ lead }: LeadCardProps) {
  const navigate = useNavigate();

  return (
    <button
      type="button"
      onClick={() => navigate(`/leads/${lead.id}`)}
      className="w-full rounded-lg border border-slate-700 bg-slate-800 p-3 text-left transition-colors hover:border-indigo-500 hover:bg-slate-700/50"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="min-w-0 flex-1 truncate text-sm font-medium text-white">
          {lead.company_name}
        </p>
        <ScoreBadge score={lead.lead_score} />
      </div>

      {(lead.industry || lead.location) && (
        <p className="mt-1.5 truncate text-xs text-slate-400">
          {[lead.industry, lead.location].filter(Boolean).join(' · ')}
        </p>
      )}

      {lead.recommended_service && (
        <p className="mt-2 truncate text-xs text-indigo-400">
          {truncate(lead.recommended_service, 40)}
        </p>
      )}
    </button>
  );
}
