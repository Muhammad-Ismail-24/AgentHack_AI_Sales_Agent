import { useNavigate } from 'react-router-dom';

import type { Meeting } from '../../lib/types';
import { formatDate, relativeTime } from '../../lib/utils';
import Badge from '../ui/Badge';
import Button from '../ui/Button';
import ExecutiveWhisper from './ExecutiveWhisper';
import MeetingBriefing from './MeetingBriefing';

interface MeetingCardProps {
  meeting: Meeting;
  companyName: string;
  contactName?: string | null;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
}

const STATUS_COLORS = {
  link_sent: 'honey',
  confirmed: 'green',
  completed: 'gray',
  cancelled: 'red',
} as const;

const STATUS_LABELS = {
  link_sent: 'Link sent',
  confirmed: 'Confirmed',
  completed: 'Completed',
  cancelled: 'Cancelled',
} as const;

export default function MeetingCard({
  meeting,
  companyName,
  contactName,
  onError,
  onNotice,
}: MeetingCardProps) {
  const navigate = useNavigate();

  return (
    <article className="card p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <button
            type="button"
            onClick={() => navigate(`/leads/${meeting.lead_id}`)}
            className="truncate text-sm font-semibold text-white hover:text-terra-400 hover:underline"
          >
            {companyName}
          </button>
          {contactName && (
            <p className="mt-0.5 truncate text-xs text-bark-400">with {contactName}</p>
          )}

          <p className="mt-2 text-sm text-bark-300">
            {formatDate(meeting.scheduled_at)}
            {meeting.scheduled_at && (
              <span className="ml-2 text-xs text-bark-500">
                ({relativeTime(meeting.scheduled_at)})
              </span>
            )}
          </p>
        </div>

        <div className="flex shrink-0 flex-col items-end gap-2">
          <Badge
            label={STATUS_LABELS[meeting.status] ?? meeting.status}
            color={STATUS_COLORS[meeting.status] ?? 'gray'}
          />
          {meeting.meeting_link && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() =>
                window.open(meeting.meeting_link!, '_blank', 'noopener,noreferrer')
              }
            >
              Join meeting ↗
            </Button>
          )}
        </div>
      </div>

      <MeetingBriefing briefing={meeting.briefing} />
      <ExecutiveWhisper
        meetingId={meeting.id}
        onError={onError}
        onNotice={onNotice}
      />
    </article>
  );
}
