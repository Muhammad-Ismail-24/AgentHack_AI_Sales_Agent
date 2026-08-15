interface TextInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

const MIN_CHARS = 20;

export default function TextInput({ value, onChange, disabled }: TextInputProps) {
  const remaining = MIN_CHARS - value.trim().length;

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
      <p className="mt-1.5 text-xs text-slate-500">
        {remaining > 0
          ? `At least ${remaining} more character${remaining === 1 ? '' : 's'}.`
          : `${value.trim().length.toLocaleString()} characters`}
      </p>
    </div>
  );
}
