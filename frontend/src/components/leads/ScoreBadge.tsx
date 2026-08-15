import Badge from '../ui/Badge';
import { scoreToBadgeColor } from '../../lib/utils';

interface ScoreBadgeProps {
  score: number | null;
  /** "lg" renders the big number used on the lead detail page. */
  size?: 'sm' | 'lg';
}

export default function ScoreBadge({ score, size = 'sm' }: ScoreBadgeProps) {
  if (size === 'lg') {
    const color = scoreToBadgeColor(score);
    const TEXT: Record<string, string> = {
      green: 'text-green-400',
      blue: 'text-blue-400',
      yellow: 'text-yellow-400',
      red: 'text-red-400',
      gray: 'text-slate-400',
      indigo: 'text-indigo-400',
    };
    return (
      <div className="flex items-baseline gap-1.5">
        <span className={`text-5xl font-bold tabular-nums ${TEXT[color]}`}>
          {score ?? '—'}
        </span>
        {score !== null && <span className="text-lg text-slate-500">/ 100</span>}
      </div>
    );
  }

  return (
    <Badge
      label={score === null ? 'Unscored' : String(score)}
      color={scoreToBadgeColor(score)}
      title={score === null ? 'Not scored yet' : `Lead score ${score} of 100`}
    />
  );
}
