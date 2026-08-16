import { ACTIVE_STAGES, REJECTED_STAGES, type Lead } from '../../lib/types';
import KanbanColumn from './KanbanColumn';

interface KanbanBoardProps {
  byStage: Record<string, Lead[]>;
}

export default function KanbanBoard({ byStage }: KanbanBoardProps) {
  const rejectedCount = REJECTED_STAGES.reduce(
    (total, stage) => total + (byStage[stage]?.length ?? 0),
    0,
  );

  return (
    <div className="space-y-8">
      <div className="flex gap-3 overflow-x-auto pb-3">
        {ACTIVE_STAGES.map((stage) => (
          <KanbanColumn key={stage} stage={stage} leads={byStage[stage] ?? []} />
        ))}
      </div>

      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-bark-500">
          Rejected · {rejectedCount}
        </h2>
        <div className="flex gap-3 overflow-x-auto pb-3">
          {REJECTED_STAGES.map((stage) => (
            <KanbanColumn key={stage} stage={stage} leads={byStage[stage] ?? []} />
          ))}
        </div>
      </section>
    </div>
  );
}
