import type { ReactNode } from 'react';

import { cx } from '../../lib/utils';

interface OnboardingShellProps {
  /** 1 = company info, 2 = ideal customer profile. */
  step: 1 | 2;
  title: ReactNode;
  subtitle: string;
  children: ReactNode;
  /** Optional row under the card — the "skip" / "back" links. */
  footer?: ReactNode;
  /** Wider column for the two-pane company step. */
  wide?: boolean;
}

const STEPS = [
  { n: 1, label: 'Company' },
  { n: 2, label: 'Ideal customer' },
] as const;

/**
 * The full-screen chrome shared by /onboarding and /icp — brand mark, the
 * two-step progress rail, headline, and the card slot.
 *
 * Both steps used to build this themselves, which is how they drifted: step 2
 * announced "Step 2 of 2" while step 1 said nothing at all, so the flow never
 * told you it was a flow.
 */
export default function OnboardingShell({
  step,
  title,
  subtitle,
  children,
  footer,
  wide = false,
}: OnboardingShellProps) {
  return (
    <div className="relative flex min-h-full items-center justify-center px-6 py-12">
      {/* Warm bloom behind the card — the landing page's glow, dialled down. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[38rem] bg-gradient-to-b
                   from-terra-600/20 via-terra-900/5 to-transparent blur-2xl"
      />

      <div className={cx('relative w-full', wide ? 'max-w-3xl' : 'max-w-xl')}>
        <header className="mb-8 flex flex-col items-center text-center">
          <span
            className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl
                       bg-gradient-to-br from-terra-400 to-terra-600 text-lg font-bold
                       text-white shadow-xl shadow-terra-950/60"
          >
            A
          </span>

          <ol className="mb-6 flex items-center gap-2" aria-label="Setup progress">
            {STEPS.map(({ n, label }, index) => {
              const state =
                n < step ? 'done' : n === step ? 'current' : 'upcoming';
              return (
                <li key={n} className="flex items-center gap-2">
                  <span
                    aria-current={state === 'current' ? 'step' : undefined}
                    className={cx(
                      'flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition-colors',
                      state === 'current' &&
                        'border-terra-500/60 bg-terra-500/15 text-cream',
                      state === 'done' &&
                        'border-terra-600/40 bg-terra-950/40 text-terra-300',
                      state === 'upcoming' &&
                        'border-bark-700 bg-bark-900/60 text-bark-500',
                    )}
                  >
                    <span
                      className={cx(
                        'flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold',
                        state === 'upcoming'
                          ? 'bg-bark-700 text-bark-400'
                          : 'bg-terra-600 text-white',
                      )}
                    >
                      {state === 'done' ? '✓' : n}
                    </span>
                    {label}
                  </span>

                  {index === 0 && (
                    <span
                      aria-hidden="true"
                      className={cx(
                        'h-px w-6',
                        step > 1 ? 'bg-terra-600/60' : 'bg-bark-700',
                      )}
                    />
                  )}
                </li>
              );
            })}
          </ol>

          <h1 className="text-2xl font-semibold tracking-tight text-cream sm:text-3xl">
            {title}
          </h1>
          <p className="mt-2.5 max-w-md text-sm leading-relaxed text-bark-400">
            {subtitle}
          </p>
        </header>

        {children}

        {footer && <div className="mt-6 text-center">{footer}</div>}
      </div>
    </div>
  );
}
