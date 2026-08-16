import { cx } from '../../lib/utils';

interface TextInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

const MIN_CHARS = 20;
/** Not enforced — the point at which the description is genuinely useful. */
const GOOD_CHARS = 400;

export default function TextInput({ value, onChange, disabled }: TextInputProps) {
  const length = value.trim().length;
  const remaining = MIN_CHARS - length;
  const progress = Math.min(100, (length / GOOD_CHARS) * 100);

  return (
    <div>
      <label htmlFor="company-text" className="label">
        Describe your company
      </label>

      <textarea
        id="company-text"
        rows={12}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        placeholder={
          'What you sell, who you sell it to, your pricing, and a couple of case studies.\n\n' +
          'The more detail you give, the better the agent matches services to each prospect.'
        }
        className="input resize-y font-normal leading-relaxed disabled:opacity-60"
      />

      {/* The agent's pitch is only as good as this text, so show progress
          towards "enough detail" rather than just the raw count. */}
      <div className="mt-2.5 flex items-center gap-3">
        <div className="h-1 flex-1 overflow-hidden rounded-full bg-bark-800">
          <div
            className={cx(
              'h-full rounded-full transition-all duration-300',
              length < MIN_CHARS
                ? 'bg-bark-600'
                : 'bg-gradient-to-r from-terra-500 to-honey-400',
            )}
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="shrink-0 text-xs tabular-nums text-bark-500">
          {remaining > 0
            ? `${remaining} more character${remaining === 1 ? '' : 's'}`
            : `${length.toLocaleString()} characters`}
        </p>
      </div>
    </div>
  );
}
