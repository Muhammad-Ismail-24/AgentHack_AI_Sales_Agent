import Spinner from '../ui/Spinner';

interface TopBarProps {
  title: string;
  subtitle?: string;
  isRunning?: boolean;
  stage?: string;
  actions?: React.ReactNode;
}

export default function TopBar({
  title,
  subtitle,
  isRunning = false,
  stage,
  actions,
}: TopBarProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-bark-800 bg-bark-900/85 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-8 py-5">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold tracking-tight text-cream">
            {title}
          </h1>
          {subtitle && (
            <p className="mt-0.5 truncate text-sm text-bark-400">{subtitle}</p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-4">
          {actions}
          {/* A live run is the one thing worth pulling the eye up here, so it
              gets the brand colour and a pulsing dot; idle stays quiet. */}
          {isRunning ? (
            <span
              className="flex items-center gap-2 rounded-full border border-terra-500/40
                         bg-terra-500/10 py-1 pl-2.5 pr-3 text-sm text-terra-200"
            >
              <Spinner size="sm" />
              {stage ? `${stage}…` : 'Pipeline running…'}
            </span>
          ) : (
            <span className="flex items-center gap-2 text-sm text-bark-500">
              <span
                aria-hidden="true"
                className="h-1.5 w-1.5 rounded-full bg-bark-600"
              />
              Idle
            </span>
          )}
        </div>
      </div>

      {/* Warm hairline under the bar, echoing the landing page's rules. */}
      <div aria-hidden="true" className="rule-ember" />
    </header>
  );
}
