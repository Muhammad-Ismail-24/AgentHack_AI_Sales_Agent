import { useNavigate } from 'react-router-dom';

import ReplyCard from '../components/inbox/ReplyCard';
import PageWrapper from '../components/layout/PageWrapper';
import TopBar from '../components/layout/TopBar';
import Button from '../components/ui/Button';
import EmptyState from '../components/ui/EmptyState';
import Spinner from '../components/ui/Spinner';
import { useInbox } from '../hooks/useInbox';
import { usePipelineContext } from '../hooks/usePipeline';

export default function Inbox() {
  const navigate = useNavigate();
  const { isRunning } = usePipelineContext();
  const { replies, isLoading, error, refetch } = useInbox();

  return (
    <>
      <TopBar
        title="Inbox"
        subtitle={`${replies.length} repl${replies.length === 1 ? 'y' : 'ies'}`}
        isRunning={isRunning}
        actions={
          <Button size="sm" variant="ghost" onClick={() => void refetch()}>
            Refresh
          </Button>
        }
      />

      <PageWrapper>
        {error && (
          <p className="mb-5 rounded-lg border border-red-500/30 bg-red-950/40 px-4 py-3 text-sm text-red-200">
            {error}
          </p>
        )}

        {isLoading ? (
          <div className="flex justify-center py-24 text-bark-500">
            <Spinner size="lg" />
          </div>
        ) : replies.length === 0 ? (
          <EmptyState
            icon="✉"
            title="No replies yet"
            description="Replies appear here as soon as prospects answer, already classified with a suggested next action."
            actionLabel="See the pipeline"
            onAction={() => navigate('/pipeline')}
          />
        ) : (
          <div className="space-y-4">
            {replies.map((item) => (
              <ReplyCard key={item.reply.id} item={item} />
            ))}
          </div>
        )}
      </PageWrapper>
    </>
  );
}
