import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';

import PageWrapper from '../components/layout/PageWrapper';
import TopBar from '../components/layout/TopBar';
import ContactCard from '../components/leads/ContactCard';
import EmailPreview from '../components/leads/EmailPreview';
import ResearchSummary from '../components/leads/ResearchSummary';
import ScoreBadge from '../components/leads/ScoreBadge';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import Spinner from '../components/ui/Spinner';
import Toast from '../components/ui/Toast';
import { usePipelineContext } from '../hooks/usePipeline';
import { useToast } from '../hooks/useToast';
import { describeError, getLeadDetail, sendEmail } from '../lib/api';
import type { Email, LeadDetail as LeadDetailData } from '../lib/types';
import { formatDate, stageToColor } from '../lib/utils';

export default function LeadDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { isRunning } = usePipelineContext();
  const { toast, showToast, hideToast } = useToast();

  const [detail, setDetail] = useState<LeadDetailData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sendingId, setSendingId] = useState<string | null>(null);

  const fetchDetail = useCallback(async () => {
    if (!id) return;
    setIsLoading(true);
    try {
      setDetail(await getLeadDetail(id));
      setError(null);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void fetchDetail();
  }, [fetchDetail]);

  async function handleSend(email: Email) {
    setSendingId(email.id);
    try {
      const result = await sendEmail(
        email.lead_id,
        email.contact_id,
        email.subject ?? '',
        email.body ?? '',
      );
      showToast(result.message ?? 'Email sent.', 'success');
      await fetchDetail();
    } catch (err) {
      showToast(describeError(err), 'error');
    } finally {
      setSendingId(null);
    }
  }

  if (isLoading) {
    return (
      <>
        <TopBar title="Lead" isRunning={isRunning} />
        <PageWrapper>
          <div className="flex justify-center py-24 text-slate-500">
            <Spinner size="lg" />
          </div>
        </PageWrapper>
      </>
    );
  }

  if (error || !detail) {
    return (
      <>
        <TopBar title="Lead" isRunning={isRunning} />
        <PageWrapper>
          <EmptyState
            icon="!"
            title="Could not load this lead"
            description={error ?? 'It may have been deleted.'}
            actionLabel="Back to leads"
            onAction={() => navigate('/leads')}
          />
        </PageWrapper>
      </>
    );
  }

  const { lead, contacts, emails, replies, meetings, events } = detail;

  return (
    <>
      <TopBar
        title={lead.company_name}
        subtitle={[lead.industry, lead.location].filter(Boolean).join(' · ')}
        isRunning={isRunning}
        actions={
          <Button size="sm" variant="ghost" onClick={() => navigate('/leads')}>
            ← All leads
          </Button>
        }
      />

      <PageWrapper>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
          {/* Left — 60% */}
          <div className="space-y-6 lg:col-span-3">
            <ResearchSummary lead={lead} />

            <section>
              <h2 className="mb-3 text-sm font-semibold text-white">
                Emails {emails.length > 0 && `(${emails.length})`}
              </h2>
              {emails.length === 0 ? (
                <p className="card px-5 py-6 text-sm italic text-slate-500">
                  No email has been written for this lead yet.
                </p>
              ) : (
                <div className="space-y-4">
                  {emails.map((email) => (
                    <EmailPreview
                      key={email.id}
                      email={email}
                      onSend={handleSend}
                      isSending={sendingId === email.id}
                    />
                  ))}
                </div>
              )}
            </section>

            {replies.length > 0 && (
              <section>
                <h2 className="mb-3 text-sm font-semibold text-white">
                  Replies ({replies.length})
                </h2>
                <div className="space-y-3">
                  {replies.map((reply) => (
                    <div key={reply.id} className="card p-4">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-xs font-medium text-indigo-400">
                          {reply.classification ?? 'Unclassified'}
                        </span>
                        <span className="text-xs text-slate-500">
                          {formatDate(reply.received_at)}
                        </span>
                      </div>
                      <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-slate-300">
                        {reply.summary || reply.raw_body}
                      </p>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section>
              <h2 className="mb-3 text-sm font-semibold text-white">Timeline</h2>
              {events.length === 0 ? (
                <p className="card px-5 py-6 text-sm italic text-slate-500">
                  No stage changes recorded.
                </p>
              ) : (
                <ol className="card space-y-0 divide-y divide-slate-700">
                  {events.map((event) => (
                    <li key={event.id} className="flex gap-3 px-5 py-3.5">
                      <span
                        aria-hidden="true"
                        className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-indigo-500"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-slate-200">
                          {event.from_stage
                            ? `${event.from_stage} → ${event.to_stage}`
                            : `Entered ${event.to_stage}`}
                        </p>
                        {event.reason && (
                          <p className="mt-0.5 text-xs text-slate-500">
                            {event.reason}
                          </p>
                        )}
                      </div>
                      <time
                        className="shrink-0 text-xs text-slate-500"
                        dateTime={event.created_at}
                      >
                        {formatDate(event.created_at)}
                      </time>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          </div>

          {/* Right — 40% */}
          <div className="space-y-6 lg:col-span-2">
            <section className="card p-5">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                Lead score
              </h2>
              <div className="mt-2">
                <ScoreBadge score={lead.lead_score} size="lg" />
              </div>
              {lead.score_explanation && (
                <p className="mt-3 text-sm leading-relaxed text-slate-400">
                  {lead.score_explanation}
                </p>
              )}
              <div className="mt-4 border-t border-slate-700 pt-4">
                <span
                  className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${stageToColor(
                    lead.pipeline_stage,
                  )}`}
                >
                  {lead.pipeline_stage}
                </span>
              </div>
            </section>

            {(lead.recommended_service || lead.pitch_angle) && (
              <section className="card p-5">
                <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Recommended service
                </h2>
                {lead.recommended_service && (
                  <p className="mt-2 text-sm font-medium text-indigo-300">
                    {lead.recommended_service}
                  </p>
                )}
                {lead.pitch_angle && (
                  <p className="mt-2 text-sm leading-relaxed text-slate-400">
                    {lead.pitch_angle}
                  </p>
                )}
              </section>
            )}

            <section className="card p-5">
              <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Contacts {contacts.length > 0 && `(${contacts.length})`}
              </h2>
              {contacts.length === 0 ? (
                <p className="text-sm italic text-slate-500">
                  No decision maker found yet.
                </p>
              ) : (
                <div className="space-y-2.5">
                  {contacts.map((contact) => (
                    <ContactCard key={contact.id} contact={contact} />
                  ))}
                </div>
              )}
            </section>

            {meetings.length > 0 && (
              <section className="card p-5">
                <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-500">
                  Meetings
                </h2>
                <div className="space-y-3">
                  {meetings.map((meeting) => (
                    <div key={meeting.id} className="text-sm">
                      <p className="text-slate-200">
                        {formatDate(meeting.scheduled_at)}
                      </p>
                      {meeting.meeting_link && (
                        <a
                          href={meeting.meeting_link}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="text-xs text-indigo-400 hover:underline"
                        >
                          Join meeting ↗
                        </a>
                      )}
                    </div>
                  ))}
                </div>
              </section>
            )}
          </div>
        </div>
      </PageWrapper>

      {toast && (
        <Toast message={toast.message} type={toast.type} onClose={hideToast} />
      )}
    </>
  );
}
