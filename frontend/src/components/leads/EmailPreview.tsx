import { useState } from 'react';

import type { Email } from '../../lib/types';
import { formatDate } from '../../lib/utils';
import Badge from '../ui/Badge';
import Button from '../ui/Button';

interface EmailPreviewProps {
  email: Email;
  onSend?: (email: Email) => void;
  isSending?: boolean;
}

const STATUS_COLORS = {
  draft: 'gray',
  sent: 'blue',
  replied: 'green',
  failed: 'red',
} as const;

export default function EmailPreview({ email, onSend, isSending }: EmailPreviewProps) {
  const [expanded, setExpanded] = useState(false);

  const body = email.body ?? '';
  const isLong = body.length > 420;
  const shown = expanded || !isLong ? body : `${body.slice(0, 420).trimEnd()}…`;

  return (
    <article className="card overflow-hidden">
      <div className="flex items-start justify-between gap-4 border-b border-slate-700 px-5 py-4">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-white">
            {email.subject || '(no subject)'}
          </p>
          <p className="mt-0.5 text-xs text-slate-500">
            {email.sent_at
              ? `Sent ${formatDate(email.sent_at)}`
              : `Drafted ${formatDate(email.created_at)}`}
          </p>
        </div>
        <Badge label={email.status} color={STATUS_COLORS[email.status] ?? 'gray'} />
      </div>

      <div className="px-5 py-4">
        {body ? (
          <p className="whitespace-pre-line text-sm leading-relaxed text-slate-300">
            {shown}
          </p>
        ) : (
          <p className="text-sm italic text-slate-500">This email has no body.</p>
        )}

        {isLong && (
          <button
            type="button"
            onClick={() => setExpanded((open) => !open)}
            className="mt-2 text-xs font-medium text-indigo-400 hover:text-indigo-300"
          >
            {expanded ? 'Show less' : 'Show full email'}
          </button>
        )}
      </div>

      {email.status === 'draft' && onSend && (
        <div className="flex justify-end border-t border-slate-700 px-5 py-3">
          <Button size="sm" loading={isSending} onClick={() => onSend(email)}>
            Send email
          </Button>
        </div>
      )}
    </article>
  );
}
