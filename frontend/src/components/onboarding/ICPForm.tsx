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
      <div>
        <label htmlFor="icp-location" className="label">
          Target location
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
          Target industry
        </label>
        <input
          id="icp-industry"
          className="input"
          value={values.industry}
          onChange={(event) => set('industry')(event.target.value)}
          placeholder="logistics and e-commerce"
        />
      </div>

      <div>
        <label htmlFor="icp-size" className="label">
          Company size
        </label>
        <select
          id="icp-size"
          className="input"
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
          Special focus
        </label>
        <textarea
          id="icp-focus"
          rows={4}
          className="input resize-y"
          value={values.special_focus}
          onChange={(event) => set('special_focus')(event.target.value)}
          placeholder="What problem should these companies have? e.g. drowning in WhatsApp customer enquiries"
        />
        <p className="mt-1.5 text-xs text-slate-500">
          Optional, but it sharpens qualification and the pitch angle a lot.
        </p>
      </div>

      <Button type="submit" size="lg" loading={isSubmitting} disabled={!isValid}>
        Start pipeline →
      </Button>
    </form>
  );
}
