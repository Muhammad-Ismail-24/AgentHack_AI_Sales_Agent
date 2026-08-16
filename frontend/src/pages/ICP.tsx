import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import ICPForm, { type ICPFormValues } from '../components/onboarding/ICPForm';
import OnboardingShell from '../components/onboarding/OnboardingShell';
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
    <OnboardingShell
      step={2}
      title="Who should the agent go after?"
      subtitle="This becomes the ideal customer profile every lead is scored against."
      footer={
        <button
          type="button"
          onClick={() => navigate('/onboarding')}
          className="text-xs text-bark-500 transition-colors hover:text-terra-300"
        >
          ← Back to company info
        </button>
      }
    >
      <div className="card p-6 sm:p-7">
        <ICPForm
          values={values}
          onChange={setValues}
          onSubmit={handleSubmit}
          isSubmitting={isSubmitting}
        />
      </div>

      {toast && (
        <Toast message={toast.message} type={toast.type} onClose={hideToast} />
      )}
    </OnboardingShell>
  );
}
