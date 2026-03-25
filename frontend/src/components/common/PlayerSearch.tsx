import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search } from 'lucide-react';
import { usePlayerSearch } from '../../hooks/useElo';

export default function PlayerSearch() {
  const [query, setQuery] = useState('');
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

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

  const handleSelect = (playerId: number) => {
    setQuery('');
    setIsOpen(false);
    navigate(`/player/${playerId}`);
  };

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
          placeholder="Search players..."
          className="w-48 lg:w-64 h-10 rounded-lg border-none bg-gray-100 px-4 pl-10 text-sm focus:ring-2 focus:ring-primary/50"
        />
        <Search className="absolute left-3 top-2.5 text-gray-500 w-5 h-5" />
      </div>

      {isOpen && (
        <div className="absolute top-12 left-0 w-72 bg-white rounded-lg shadow-lg border border-gray-200 py-2 z-50">
          {isLoading ? (
            <div className="px-4 py-2 text-gray-500 text-sm">Loading...</div>
          ) : results.length === 0 ? (
            <div className="px-4 py-2 text-gray-500 text-sm">No results found</div>
          ) : (
            results.map((player) => (
              <button
                key={player.player_id}
                onClick={() => handleSelect(player.player_id)}
                className="w-full px-4 py-2 text-left hover:bg-gray-50 flex items-center gap-3"
              >
                <span className="font-medium">{player.full_name}</span>
                <span className="text-gray-400">|</span>
                <span className="text-sm text-gray-600">
                  {player.is_two_way ? 'Two-Way' : player.position === 'pitcher' ? 'Pitcher' : 'Batter'}
                </span>
                {player.is_two_way && (
                  <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
                    TWP
                  </span>
                )}
                <span className="text-gray-400">|</span>
                <span className="text-sm text-gray-500">{player.team}</span>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
