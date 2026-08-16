import { NavLink } from 'react-router-dom';

import { cx } from '../../lib/utils';

interface SidebarProps {
  isRunning?: boolean;
}

const NAV_ITEMS = [
  { to: '/pipeline', label: 'Pipeline', icon: '▦' },
  { to: '/leads', label: 'Leads', icon: '☰' },
  { to: '/inbox', label: 'Inbox', icon: '✉' },
  { to: '/meetings', label: 'Meetings', icon: '◷' },
] as const;

export default function Sidebar({ isRunning = false }: SidebarProps) {
  return (
    <aside className="fixed inset-y-0 left-0 z-30 flex w-60 flex-col border-r border-bark-800 bg-bark-950">
      <div className="flex items-center gap-2.5 px-5 py-6">
        <span
          className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br
                     from-terra-400 to-terra-600 text-sm font-bold text-white
                     shadow-lg shadow-terra-950/60"
        >
          A
        </span>
        <div className="leading-tight">
          <p className="text-ember text-sm font-semibold">AgentHack</p>
          <p className="text-xs text-bark-500">AI Sales Agent</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cx(
                'flex items-center gap-3 rounded-lg border-l-2 px-3 py-2.5 text-sm transition-colors',
                isActive
                  ? 'border-terra-500 bg-gradient-to-r from-terra-500/20 via-terra-500/5 ' +
                    'to-transparent font-medium text-cream'
                  : 'border-transparent text-bark-400 hover:bg-bark-800/60 hover:text-bark-200',
              )
            }
          >
            <span aria-hidden="true" className="text-base">
              {item.icon}
            </span>
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t border-bark-800 px-5 py-4">
        <div className="flex items-center gap-2">
          <span
            className={cx(
              'h-2 w-2 shrink-0 rounded-full',
              isRunning ? 'animate-pulse bg-green-500' : 'bg-bark-600',
            )}
            aria-hidden="true"
          />
          <span className="text-xs text-bark-400">
            {isRunning ? 'Pipeline running' : 'Idle'}
          </span>
        </div>
      </div>
    </aside>
  );
}
