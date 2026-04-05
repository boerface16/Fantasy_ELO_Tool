import { useState, useRef, useEffect } from 'react';
import { Search, X } from 'lucide-react';
import { usePlayerSearch } from '../../hooks/useElo';
import type { MatchupRole } from '../../types/matchup';

interface PlayerSelectorProps {
  role: MatchupRole;
  selectedName?: string;
  onSelect: (id: number, name: string) => void;
}

export default function PlayerSelector({ role, selectedName, onSelect }: PlayerSelectorProps) {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const { data: results = [], isLoading } = usePlayerSearch(query);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Filter by role: batters = non-pitcher OR two-way, pitchers = pitcher OR two-way
  // DB stores MLB position abbreviations: "P", "SP", "RP" for pitchers
  const PITCHER_POSITIONS = new Set(['P', 'SP', 'RP']);
  const filtered = results.filter((p) => {
    if (role === 'batter') return !PITCHER_POSITIONS.has(p.position) || p.is_two_way;
    return PITCHER_POSITIONS.has(p.position) || p.is_two_way;
  });

  const handleSelect = (playerId: number, fullName: string) => {
    setQuery('');
    setIsOpen(false);
    onSelect(playerId, fullName);
  };

  const handleClear = () => {
    setQuery('');
    setIsOpen(false);
    onSelect(0, '');
  };

  if (selectedName) {
    return (
      <button
        onClick={handleClear}
        className="flex items-center gap-2 px-4 py-2.5 rounded-lg bg-bg-card/10 hover:bg-bg-card/15 transition-colors text-sm font-medium w-full"
      >
        <span className="truncate flex-1 text-left">{selectedName}</span>
        <X className="w-4 h-4 text-gray-400 shrink-0" />
      </button>
    );
  }

  return (
    <div ref={dropdownRef} className="relative">
      <div className="relative">
        <input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(e.target.value.length >= 2);
          }}
          onFocus={() => query.length >= 2 && setIsOpen(true)}
          placeholder={`Search ${role === 'batter' ? 'batter' : 'pitcher'}...`}
          className="w-full h-10 rounded-lg border-none bg-bg-card/10 px-4 pl-10 text-sm focus:ring-2 focus:ring-primary/50"
        />
        <Search className="absolute left-3 top-2.5 text-gray-400 w-5 h-5" />
      </div>

      {isOpen && (
        <div className="absolute top-12 left-0 w-full bg-bg-card rounded-lg shadow-lg border border-border-line py-2 z-50 max-h-60 overflow-y-auto">
          {isLoading ? (
            <div className="px-4 py-2 text-gray-400 text-sm">Loading...</div>
          ) : filtered.length === 0 ? (
            <div className="px-4 py-2 text-gray-400 text-sm">No results found</div>
          ) : (
            filtered.map((player) => (
              <button
                key={player.player_id}
                onClick={() => handleSelect(player.player_id, player.full_name)}
                className="w-full px-4 py-2 text-left hover:bg-white/5 flex items-center gap-3"
              >
                <span className="font-medium">{player.full_name}</span>
                <span className="text-gray-400">|</span>
                <span className="text-sm text-gray-400">{player.team}</span>
                {player.is_two_way && (
                  <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
                    TWP
                  </span>
                )}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
