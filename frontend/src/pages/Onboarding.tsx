import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import FileUpload from '../components/onboarding/FileUpload';
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
    <div className="flex min-h-full items-center justify-center px-6 py-12">
      <div className="w-full max-w-2xl">
        <header className="mb-8 text-center">
          <span className="mx-auto mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-indigo-600 text-lg font-bold text-white">
            A
          </span>
          <h1 className="text-2xl font-semibold text-white">
            Tell the agent about your company
          </h1>
          <p className="mt-2 text-sm text-slate-400">
            Upload a company PDF or paste a description. Everything the agent
            pitches comes from this.
          </p>
        </header>

        <div className="card p-6">
          <div
            role="tablist"
            className="mb-6 inline-flex rounded-lg border border-slate-700 bg-slate-900 p-1"
          >
            {(
              [
                ['upload', 'Upload PDF'],
                ['text', 'Paste text'],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="tab"
                aria-selected={tab === value}
                onClick={() => setTab(value)}
                className={cx(
                  'rounded-md px-4 py-1.5 text-sm font-medium transition-colors',
                  tab === value
                    ? 'bg-indigo-600 text-white'
                    : 'text-slate-400 hover:text-slate-200',
                )}
              >
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
            <div className="mt-5 flex items-center gap-2 rounded-lg border border-green-500/30 bg-green-950/30 px-4 py-3">
              <span aria-hidden="true" className="text-green-400">
                ✓
              </span>
              <p className="text-sm text-green-100">
                Company info loaded — <strong>{companyName}</strong>
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

        <p className="mt-6 text-center text-xs text-slate-600">
          Already have seed data loaded?{' '}
          <button
            type="button"
            onClick={() => navigate('/pipeline')}
            className="text-slate-400 underline hover:text-slate-200"
          >
            Skip to the dashboard
          </button>
        </p>
      </div>

      {toast && (
        <Toast message={toast.message} type={toast.type} onClose={hideToast} />
      )}
    </div>
  );
}
