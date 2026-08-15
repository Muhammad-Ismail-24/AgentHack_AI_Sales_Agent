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
    <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-900/85 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-8 py-5">
        <div className="min-w-0">
          <h1 className="truncate text-xl font-semibold text-white">{title}</h1>
          {subtitle && (
            <p className="mt-0.5 truncate text-sm text-slate-400">{subtitle}</p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-4">
          {actions}
          {isRunning ? (
            <span className="flex items-center gap-2 text-sm text-indigo-300">
              <Spinner size="sm" />
              {stage ? `${stage}…` : 'Pipeline running…'}
            </span>
          ) : (
            <span className="text-sm text-slate-500">Idle</span>
          )}
        </div>
      </div>
    </header>
  );
}
