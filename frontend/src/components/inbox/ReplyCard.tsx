import { useNavigate } from 'react-router-dom';

import type { InboxItem } from '../../lib/types';
import { formatDate, relativeTime } from '../../lib/utils';
import ClassificationBadge from './ClassificationBadge';
import NextActionPanel from './NextActionPanel';

interface ReplyCardProps {
  item: InboxItem;
}

export default function ReplyCard({ item }: ReplyCardProps) {
  const navigate = useNavigate();
  const { reply, email } = item;

  return (
    <article className="card p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => navigate(`/leads/${item.lead_id}`)}
            className="truncate text-sm font-semibold text-white hover:text-indigo-400 hover:underline"
          >
            {item.company_name}
          </button>
          <p className="mt-0.5 truncate text-xs text-slate-400">
            {item.contact_name ?? 'Unknown contact'}
            {email.subject ? ` · re: ${email.subject}` : ''}
          </p>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-1.5">
          <ClassificationBadge classification={reply.classification} />
          <time
            className="text-xs text-slate-500"
            dateTime={reply.received_at}
            title={formatDate(reply.received_at)}
          >
            {relativeTime(reply.received_at)}
          </time>
        </div>
      </div>

      {reply.summary ? (
        <p className="mt-3 text-sm leading-relaxed text-slate-300">{reply.summary}</p>
      ) : (
        reply.raw_body && (
          <p className="mt-3 line-clamp-3 whitespace-pre-line text-sm leading-relaxed text-slate-400">
            {reply.raw_body}
          </p>
        )
      )}

      {reply.summary && reply.raw_body && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-medium text-slate-500 hover:text-slate-300">
            Read the full reply
          </summary>
          <p className="mt-2 whitespace-pre-line rounded-lg bg-slate-900/60 p-3 text-sm leading-relaxed text-slate-400">
            {reply.raw_body}
          </p>
        </details>
      )}

      <NextActionPanel nextAction={reply.next_action} />
    </article>
  );
}
