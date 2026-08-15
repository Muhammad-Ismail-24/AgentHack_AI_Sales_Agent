import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import PageWrapper from '../components/layout/PageWrapper';
import TopBar from '../components/layout/TopBar';
import MeetingCard from '../components/meetings/MeetingCard';
import EmptyState from '../components/ui/EmptyState';
import Spinner from '../components/ui/Spinner';
import { useLeads } from '../hooks/useLeads';
import { usePipelineContext } from '../hooks/usePipeline';
import { describeError, getMeetings } from '../lib/api';
import type { Meeting } from '../lib/types';

export default function Meetings() {
  const navigate = useNavigate();
  const { isRunning } = usePipelineContext();
  const { leads } = useLeads();

  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMeetings = useCallback(async () => {
    try {
      setMeetings(await getMeetings());
      setError(null);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchMeetings();
  }, [fetchMeetings]);

  // Resolve company and contact names from the leads we already have, rather
  // than a request per meeting.
  const lookup = useMemo(() => {
    const map = new Map<string, { company: string; contacts: Map<string, string> }>();
    leads.forEach((lead) => {
      map.set(lead.id, {
        company: lead.company_name,
        contacts: new Map(
          lead.contacts.map((contact) => [contact.id, contact.name ?? '']),
        ),
      });
    });
    return map;
  }, [leads]);

  const { upcoming, past } = useMemo(() => {
    const now = Date.now();
    const isPast = (meeting: Meeting) =>
      meeting.scheduled_at !== null &&
      new Date(meeting.scheduled_at).getTime() < now;

    return {
      upcoming: meetings.filter((meeting) => !isPast(meeting)),
      past: meetings.filter(isPast),
    };
  }, [meetings]);

  function render(meeting: Meeting) {
    const entry = lookup.get(meeting.lead_id);
    return (
      <MeetingCard
        key={meeting.id}
        meeting={meeting}
        companyName={entry?.company ?? 'Unknown company'}
        contactName={
          meeting.contact_id ? entry?.contacts.get(meeting.contact_id) : null
        }
      />
    );
  }

  return (
    <>
      <TopBar
        title="Meetings"
        subtitle={`${upcoming.length} upcoming`}
        isRunning={isRunning}
      />

      <PageWrapper>
        {error && (
          <p className="mb-5 rounded-lg border border-red-500/30 bg-red-950/40 px-4 py-3 text-sm text-red-200">
            {error}
          </p>
        )}

        {isLoading ? (
          <div className="flex justify-center py-24 text-slate-500">
            <Spinner size="lg" />
          </div>
        ) : meetings.length === 0 ? (
          <EmptyState
            icon="◷"
            title="No meetings booked"
            description="When a prospect accepts, the meeting and its pre-meeting briefing show up here."
            actionLabel="Check the inbox"
            onAction={() => navigate('/inbox')}
          />
        ) : (
          <div className="space-y-8">
            {upcoming.length > 0 && (
              <section>
                <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Upcoming · {upcoming.length}
                </h2>
                <div className="space-y-4">{upcoming.map(render)}</div>
              </section>
            )}

            {past.length > 0 && (
              <section>
                <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Past · {past.length}
                </h2>
                <div className="space-y-4 opacity-70">{past.map(render)}</div>
              </section>
            )}
          </div>
        )}
      </PageWrapper>
    </>
  );
}
