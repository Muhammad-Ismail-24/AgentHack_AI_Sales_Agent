import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import ICPForm, { type ICPFormValues } from '../components/onboarding/ICPForm';
import Toast from '../components/ui/Toast';
import { useToast } from '../hooks/useToast';
import { defineICP, describeError, startPipeline } from '../lib/api';
import { loadSessionId } from '../lib/utils';

const DEFAULTS: ICPFormValues = {
  location: '',
  industry: '',
  company_size: '51-200',
  special_focus: '',
};

export default function ICP() {
  const navigate = useNavigate();
  const { toast, showToast, hideToast } = useToast();

  const [values, setValues] = useState<ICPFormValues>(DEFAULTS);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const sessionId = loadSessionId();

  async function handleSubmit() {
    if (!sessionId) {
      showToast('No company loaded yet — start from the beginning.', 'error');
      navigate('/onboarding');
      return;
    }

    setIsSubmitting(true);
    try {
      await defineICP({ session_id: sessionId, ...values });

      // A missing agent pipeline must not strand the user on this page — the
      // dashboard is still worth showing, so warn and continue.
      try {
        await startPipeline(sessionId);
      } catch (error) {
        showToast(describeError(error), 'error');
        window.setTimeout(() => navigate('/pipeline'), 2500);
        return;
      }

      navigate('/pipeline');
    } catch (error) {
      showToast(describeError(error), 'error');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-full items-center justify-center px-6 py-12">
      <div className="w-full max-w-xl">
        <header className="mb-8">
          <p className="text-xs font-semibold uppercase tracking-wide text-indigo-400">
            Step 2 of 2
          </p>
          <h1 className="mt-1.5 text-2xl font-semibold text-white">
            Who should the agent go after?
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            This becomes the ideal customer profile every lead is scored against.
          </p>
        </header>

        <div className="card p-6">
          <ICPForm
            values={values}
            onChange={setValues}
            onSubmit={handleSubmit}
            isSubmitting={isSubmitting}
          />
        </div>

        <button
          type="button"
          onClick={() => navigate('/onboarding')}
          className="mt-6 text-xs text-slate-500 hover:text-slate-300"
        >
          ← Back to company info
        </button>
      </div>

      {toast && (
        <Toast message={toast.message} type={toast.type} onClose={hideToast} />
      )}
    </div>
  );
}
