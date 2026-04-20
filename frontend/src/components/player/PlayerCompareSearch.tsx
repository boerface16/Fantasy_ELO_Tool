import { useState, useRef, useEffect } from 'react';
import { X, Search } from 'lucide-react';
import { usePlayerSearch } from '../../hooks/useElo';
import TeamBadge from '../common/TeamBadge';

export interface ComparedPlayer {
  playerId: string;
  name: string;
  team: string;
}

interface PlayerCompareSearchProps {
  currentPlayer: ComparedPlayer;
  role: 'BATTING' | 'PITCHING';
  compared: ComparedPlayer[];
  colors: string[];
  onAdd: (player: ComparedPlayer) => void;
  onRemove: (playerId: string) => void;
}

const MAX_PLAYERS = 5;

export default function PlayerCompareSearch({
  currentPlayer,
  role,
  compared,
  colors,
  onAdd,
  onRemove,
}: PlayerCompareSearchProps) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const { data: results = [] } = usePlayerSearch(query);

  const selectedIds = new Set([currentPlayer.playerId, ...compared.map(p => p.playerId)]);
  const canAddMore = selectedIds.size < MAX_PLAYERS;

  const filtered = results.filter(r => {
    if (selectedIds.has(String(r.player_id))) return false;
    if (role === 'PITCHING') return r.role === 'pitcher' || r.is_two_way;
    return r.role === 'batter' || r.is_two_way;
  });

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, []);

  return (
    <div className="space-y-3">
      {/* Selected player chips */}
      <div className="flex flex-wrap gap-2 items-center">
        {/* Current player chip */}
        <span
          className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-semibold"
          style={{ backgroundColor: `${colors[0]}25`, color: colors[0], border: `1px solid ${colors[0]}60` }}
        >
          <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: colors[0] }} />
          {currentPlayer.name}
        </span>

        {/* Compared player chips */}
        {compared.map((p, i) => (
          <span
            key={p.playerId}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-sm font-semibold"
            style={{ backgroundColor: `${colors[i + 1]}25`, color: colors[i + 1], border: `1px solid ${colors[i + 1]}60` }}
          >
            <span className="inline-block w-2 h-2 rounded-full" style={{ backgroundColor: colors[i + 1] }} />
            {p.name}
            <button
              onClick={() => onRemove(p.playerId)}
              className="ml-0.5 opacity-70 hover:opacity-100 transition-opacity"
            >
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}

        {canAddMore && (
          <span className="text-xs text-text-secondary">
            {MAX_PLAYERS - selectedIds.size} slot{MAX_PLAYERS - selectedIds.size !== 1 ? 's' : ''} left
          </span>
        )}
      </div>

      {/* Search input */}
      {canAddMore && (
        <div className="relative" ref={wrapperRef}>
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-secondary pointer-events-none" />
          <input
            type="text"
            value={query}
            onChange={e => { setQuery(e.target.value); setOpen(true); }}
            onFocus={() => setOpen(true)}
            placeholder={`Add ${role === 'PITCHING' ? 'pitcher' : 'batter'} to compare…`}
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-bg-elevated border border-border-line text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
          {open && filtered.length > 0 && (
            <div className="absolute z-20 top-full mt-1 left-0 right-0 bg-bg-card border border-border-line rounded-lg shadow-modern overflow-hidden max-h-56 overflow-y-auto">
              {filtered.slice(0, 8).map(r => (
                <button
                  key={r.player_id}
                  onMouseDown={e => {
                    e.preventDefault();
                    onAdd({ playerId: String(r.player_id), name: r.full_name, team: r.team });
                    setQuery('');
                    setOpen(false);
                  }}
                  className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-bg-elevated transition-colors text-left"
                >
                  <TeamBadge code={r.team} />
                  <span className="text-sm font-medium text-text-primary">{r.full_name}</span>
                  <span className="text-xs text-text-secondary ml-auto">{r.position}</span>
                  {r.is_two_way && (
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-400">TWP</span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
