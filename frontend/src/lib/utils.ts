/** Small shared helpers: colours, dates, text. No API calls, no React. */

import type { BadgeColor, Classification } from './types';

/** Tailwind text colour for a lead score.
 *
 * A warm heat ramp — rose, amber, lime, emerald. The 66-80 band used to be
 * blue, which was the one colour in the app that fought the terracotta
 * chrome; lime sits naturally between amber and emerald and keeps all four
 * bands distinguishable from each other on a dark warm background.
 */
export function scoreToColor(score: number | null): string {
  if (score === null || Number.isNaN(score)) return 'text-bark-400';
  if (score <= 40) return 'text-rose-400';
  if (score <= 65) return 'text-amber-400';
  if (score <= 80) return 'text-lime-400';
  return 'text-emerald-400';
}

/** Badge colour name for a lead score — pairs with <Badge color={...} />. */
export function scoreToBadgeColor(score: number | null): BadgeColor {
  if (score === null || Number.isNaN(score)) return 'gray';
  if (score <= 40) return 'red';
  if (score <= 65) return 'yellow';
  if (score <= 80) return 'lime';
  return 'green';
}

/** Tailwind background classes for a stage chip.
 *
 * The stages read as a heat ramp: cold bark for a lead nobody has touched,
 * warming through honey and terracotta as it engages, emerald once it is
 * won, red when it is dead. That ordering is the point — a glance down the
 * pipeline column should show progress as rising temperature, so keep any
 * new stage in its place on the gradient rather than picking a fresh hue.
 */
export function stageToColor(stage: string): string {
  const map: Record<string, string> = {
    Discovered: 'bg-bark-600 text-bark-100',
    Potential: 'bg-bark-500 text-bark-950',
    Researching: 'bg-honey-600 text-bark-950',
    Qualified: 'bg-honey-400 text-bark-950',
    Contacted: 'bg-terra-600 text-terra-50',
    Interested: 'bg-terra-400 text-bark-950',
    'Meeting Scheduled': 'bg-emerald-500 text-emerald-950',
    Converted: 'bg-emerald-400 text-emerald-950',
    'Not Qualified': 'bg-red-950 text-red-300',
    'Not Interested': 'bg-red-900 text-red-200',
    'Do Not Contact': 'bg-red-700 text-red-50',
  };
  return map[stage] ?? 'bg-bark-700 text-bark-200';
}

/** Badge colour for a reply classification. */
export function classificationToColor(
  classification: Classification | string | null,
): BadgeColor {
  const map: Record<string, BadgeColor> = {
    Interested: 'green',
    'Pricing Objection': 'yellow',
    'Not Interested': 'red',
    'Meeting Requested': 'terra',
    'Out of Office': 'gray',
    Unclear: 'gray',
  };
  return (classification && map[classification]) || 'gray';
}

/** "15 Feb 2025, 10:00" — returns an em dash for null/unparseable input. */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';

  return date.toLocaleString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

/** "3 days ago", "in 2 hours", "just now". */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';

  const diffMs = date.getTime() - Date.now();
  const absMinutes = Math.round(Math.abs(diffMs) / 60_000);
  if (absMinutes < 1) return 'just now';

  const units: [number, Intl.RelativeTimeFormatUnit][] = [
    [60, 'minute'],
    [24 * 60, 'hour'],
    [7 * 24 * 60, 'day'],
    [30 * 24 * 60, 'week'],
    [365 * 24 * 60, 'month'],
    [Number.POSITIVE_INFINITY, 'year'],
  ];
  const divisors = [1, 60, 24 * 60, 7 * 24 * 60, 30 * 24 * 60, 365 * 24 * 60];

  const formatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  for (let i = 0; i < units.length; i += 1) {
    if (absMinutes < units[i][0]) {
      const value = Math.round(diffMs / 60_000 / divisors[i]);
      return formatter.format(value, units[i][1]);
    }
  }
  return formatDate(iso);
}

/** Cut to n characters on a word boundary, appending an ellipsis. */
export function truncate(text: string | null | undefined, n: number): string {
  if (!text) return '';
  if (text.length <= n) return text;

  const cut = text.slice(0, n);
  const lastSpace = cut.lastIndexOf(' ');
  return `${(lastSpace > n * 0.6 ? cut.slice(0, lastSpace) : cut).trimEnd()}…`;
}

/** "NovaTech Solutions" -> "NS" — for contact and company avatars. */
export function initials(name: string | null | undefined): string {
  if (!name) return '?';
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('');
}

/** Human label for employee_count. */
export function formatEmployees(count: number | null): string {
  if (count === null || count === undefined) return '—';
  if (count >= 1000) return `${Math.round(count / 1000)}k employees`;
  return `${count} employees`;
}

/** Join truthy class names. */
export function cx(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ');
}

/** Persist the active session id so a page refresh doesn't lose the run. */
const SESSION_KEY = 'agenthack.session_id';

export function saveSessionId(sessionId: string): void {
  try {
    window.localStorage.setItem(SESSION_KEY, sessionId);
  } catch {
    // Private mode with storage disabled — the app still works, it just
    // forgets the session on refresh.
  }
}

export function loadSessionId(): string | null {
  try {
    return window.localStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

export function clearSessionId(): void {
  try {
    window.localStorage.removeItem(SESSION_KEY);
  } catch {
    // ignore
  }
}
