import { X } from 'lucide-react';
import { MLB_TEAMS } from '../../constants/mlb';

interface TeamCompareSearchProps {
  primaryTeam: string;
  compared: string[];
  colors: string[];
  onAdd: (teamCode: string) => void;
  onRemove: (teamCode: string) => void;
}

const MAX_COMPARED = 4;

export default function TeamCompareSearch({
  primaryTeam,
  compared,
  colors,
  onAdd,
  onRemove,
}: TeamCompareSearchProps) {
  const excluded = new Set([primaryTeam, ...compared]);
  const available = MLB_TEAMS.filter(t => !excluded.has(t));
  const slotsLeft = MAX_COMPARED - compared.length;

  return (
    <div className="flex flex-wrap items-center gap-2">
      {compared.map((tc, i) => (
        <span
          key={tc}
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-semibold text-white"
          style={{ backgroundColor: colors[i + 1] ?? '#888' }}
        >
          {tc}
          <button onClick={() => onRemove(tc)} className="hover:opacity-70">
            <X className="w-3 h-3" />
          </button>
        </span>
      ))}

      {slotsLeft > 0 && (
        <select
          className="bg-bg-elevated border border-border-line rounded-lg px-2 py-1 text-sm text-text-primary focus:outline-none cursor-pointer"
          value=""
          onChange={e => { if (e.target.value) onAdd(e.target.value); }}
        >
          <option value="" disabled>
            + Add team ({slotsLeft} slot{slotsLeft !== 1 ? 's' : ''} left)
          </option>
          {available.map(t => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
      )}
    </div>
  );
}
