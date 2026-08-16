import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import FileUpload from '../components/onboarding/FileUpload';
import OnboardingShell from '../components/onboarding/OnboardingShell';
import TextInput from '../components/onboarding/TextInput';
import Button from '../components/ui/Button';
import Toast from '../components/ui/Toast';
import { useToast } from '../hooks/useToast';
import { describeError, submitCompanyText, uploadCompanyPDF } from '../lib/api';
import { cx, saveSessionId } from '../lib/utils';

type Tab = 'upload' | 'text';

export default function Onboarding() {
  const navigate = useNavigate();
  const { toast, showToast, hideToast } = useToast();

  const [tab, setTab] = useState<Tab>('upload');
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [companyName, setCompanyName] = useState<string | null>(null);

  const canSubmit = tab === 'upload' ? file !== null : text.trim().length >= 20;

  async function handleSubmit() {
    if (!canSubmit) return;
    setIsSubmitting(true);
    try {
      const result =
        tab === 'upload'
          ? await uploadCompanyPDF(file!)
          : await submitCompanyText(text);

      saveSessionId(result.session_id);
      setCompanyName(result.company_name);
      showToast(
        result.message ?? `Loaded ${result.company_name}.`,
        result.message ? 'info' : 'success',
      );
    } catch (error) {
      showToast(describeError(error), 'error');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <OnboardingShell
      wide
      step={1}
      title="Tell the agent about your company"
      subtitle="Upload a company PDF or paste a description. Everything the agent pitches comes from this."
      footer={
        <p className="text-xs text-bark-600">
          Already ran the pipeline?{' '}
          <button
            type="button"
            onClick={() => navigate('/pipeline')}
            className="text-bark-400 underline decoration-bark-700 underline-offset-2
                       transition-colors hover:text-terra-300"
          >
            Skip to the dashboard
          </button>
        </p>
      }
    >
      <div className="card p-6 sm:p-7">
        <div
          role="tablist"
          className="mb-6 inline-flex rounded-lg border border-bark-700 bg-bark-950/60 p-1"
        >
          {(
            [
              ['upload', 'Upload PDF', '⇪'],
              ['text', 'Paste text', '¶'],
            ] as const
          ).map(([value, label, icon]) => (
            <button
              key={value}
              type="button"
              role="tab"
              aria-selected={tab === value}
              onClick={() => setTab(value)}
              className={cx(
                'flex items-center gap-2 rounded-md px-4 py-1.5 text-sm font-medium transition-all',
                tab === value
                  ? 'bg-terra-600 text-white shadow-md shadow-terra-950/50'
                  : 'text-bark-400 hover:text-bark-200',
              )}
            >
              <span aria-hidden="true" className="text-xs opacity-80">
                {icon}
              </span>
              {label}
            </button>
          ))}
        </div>

        {tab === 'upload' ? (
          <FileUpload
            file={file}
            onFileSelected={setFile}
            disabled={isSubmitting}
          />
        ) : (
          <TextInput value={text} onChange={setText} disabled={isSubmitting} />
        )}

        {companyName && (
          <div
            className="mt-5 flex items-center gap-3 rounded-lg border border-emerald-500/30
                       bg-emerald-950/30 px-4 py-3.5 animate-slide-up"
          >
            <span
              aria-hidden="true"
              className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full
                         bg-emerald-500 text-sm font-bold text-emerald-950"
            >
              ✓
            </span>
            <p className="text-sm text-emerald-100">
              Company info loaded — <strong className="font-semibold">{companyName}</strong>
            </p>
          </div>
        )}

        <div className="mt-6 flex justify-end gap-3">
          {!companyName ? (
            <Button
              size="lg"
              onClick={handleSubmit}
              disabled={!canSubmit}
              loading={isSubmitting}
            >
              Load company info
            </Button>
          ) : (
            <Button size="lg" onClick={() => navigate('/icp')}>
              Continue →
            </Button>
          )}
        </div>
      </div>

      {toast && (
        <Toast message={toast.message} type={toast.type} onClose={hideToast} />
      )}
    </OnboardingShell>
  );
}
