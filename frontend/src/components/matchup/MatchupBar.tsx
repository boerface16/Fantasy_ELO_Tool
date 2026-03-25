import type { PAProbabilities } from '../../types/matchup';

const OUTCOME_CONFIG: { key: keyof PAProbabilities; label: string; color: string }[] = [
  { key: 'BB',  label: 'BB',  color: 'bg-blue-500' },
  { key: 'K',   label: 'K',   color: 'bg-red-500' },
  { key: 'OUT', label: 'OUT', color: 'bg-gray-400' },
  { key: '1B',  label: '1B',  color: 'bg-green-400' },
  { key: '2B',  label: '2B',  color: 'bg-green-500' },
  { key: '3B',  label: '3B',  color: 'bg-green-600' },
  { key: 'HR',  label: 'HR',  color: 'bg-green-700' },
];

interface MatchupBarProps {
  probabilities: PAProbabilities;
}

export default function MatchupBar({ probabilities }: MatchupBarProps) {
  return (
    <div className="space-y-2">
      {/* Stacked bar */}
      <div className="flex h-8 rounded-lg overflow-hidden">
        {OUTCOME_CONFIG.map(({ key, color }) => {
          const pct = probabilities[key] * 100;
          if (pct < 0.5) return null;
          return (
            <div
              key={key}
              className={`${color} flex items-center justify-center text-[10px] font-semibold text-white transition-all`}
              style={{ width: `${pct}%` }}
            >
              {pct >= 3 ? `${pct.toFixed(0)}%` : ''}
            </div>
          );
        })}
      </div>

      {/* Legend row */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
        {OUTCOME_CONFIG.map(({ key, label, color }) => (
          <div key={key} className="flex items-center gap-1.5">
            <span className={`inline-block w-2.5 h-2.5 rounded-sm ${color}`} />
            <span>{label}</span>
            <span className="font-semibold tabular-nums">
              {(probabilities[key] * 100).toFixed(1)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
