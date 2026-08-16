import Button from '../ui/Button';

export interface ICPFormValues {
  location: string;
  industry: string;
  company_size: string;
  special_focus: string;
}

interface ICPFormProps {
  values: ICPFormValues;
  onChange: (values: ICPFormValues) => void;
  onSubmit: () => void;
  isSubmitting?: boolean;
}

const COMPANY_SIZES = ['1-10', '11-50', '51-200', '201-1000', '1000+'];

export default function ICPForm({
  values,
  onChange,
  onSubmit,
  isSubmitting = false,
}: ICPFormProps) {
  const set = (key: keyof ICPFormValues) => (value: string) =>
    onChange({ ...values, [key]: value });

  const isValid =
    values.location.trim().length > 0 && values.industry.trim().length > 0;

  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        if (isValid) onSubmit();
      }}
    >
      {/* Location and industry are the two that actually build the search
          query, so they lead and sit together. */}
      <div className="grid gap-5 sm:grid-cols-2">
        <div>
          <label htmlFor="icp-location" className="label">
            Target location <span className="text-terra-400">*</span>
          </label>
          <input
            id="icp-location"
            className="input"
            value={values.location}
            onChange={(event) => set('location')(event.target.value)}
            placeholder="UAE, or Dubai, or Southeast Asia"
          />
        </div>

        <div>
          <label htmlFor="icp-industry" className="label">
            Target industry <span className="text-terra-400">*</span>
          </label>
          <input
            id="icp-industry"
            className="input"
            value={values.industry}
            onChange={(event) => set('industry')(event.target.value)}
            placeholder="logistics and e-commerce"
          />
        </div>
      </div>

      <div>
        <label htmlFor="icp-size" className="label">
          Company size
        </label>
        <select
          id="icp-size"
          className="select"
          value={values.company_size}
          onChange={(event) => set('company_size')(event.target.value)}
        >
          {COMPANY_SIZES.map((size) => (
            <option key={size} value={size}>
              {size} employees
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="icp-focus" className="label">
          Special focus{' '}
          <span className="font-normal text-bark-500">— optional</span>
        </label>
        <textarea
          id="icp-focus"
          rows={4}
          className="input resize-y leading-relaxed"
          value={values.special_focus}
          onChange={(event) => set('special_focus')(event.target.value)}
          placeholder="What problem should these companies have? e.g. drowning in WhatsApp customer enquiries"
        />
        <p className="field-hint">
          Sharpens qualification and the pitch angle a lot.
        </p>
      </div>

      <div className="flex items-center justify-between gap-4 border-t border-bark-700/70 pt-5">
        <p className="text-xs leading-relaxed text-bark-500">
          {isValid
            ? 'The agent will start searching as soon as you submit.'
            : 'Location and industry are required.'}
        </p>
        <Button
          type="submit"
          size="lg"
          loading={isSubmitting}
          disabled={!isValid}
          className="shrink-0"
        >
          Start pipeline →
        </Button>
      </div>
    </form>
  );
}
