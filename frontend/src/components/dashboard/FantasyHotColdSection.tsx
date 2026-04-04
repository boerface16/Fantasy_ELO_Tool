import { useState } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { useHotFantasy, useColdFantasy } from '../../hooks/useElo';
import FantasyPlayerCard from './FantasyPlayerCard';

interface FantasyHotColdSectionProps {
  type: 'hot' | 'cold';
  date: string;
}

export default function FantasyHotColdSection({ type, date }: FantasyHotColdSectionProps) {
  const [role, setRole] = useState<'batter' | 'pitcher'>('batter');

  const hotResult = useHotFantasy(type === 'hot' ? date : '', role);
  const coldResult = useColdFantasy(type === 'cold' ? date : '', role);
  const { data: players = [], isLoading } = type === 'hot' ? hotResult : coldResult;

  const isHot = type === 'hot';
  const Icon = isHot ? TrendingUp : TrendingDown;
  const title = isHot ? 'Fantasy Leaders Today' : 'Fantasy Losers Today';
  const iconColor = isHot ? 'text-green-500' : 'text-red-500';

  return (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-4 px-1">
        <Icon className={`w-5 h-5 ${iconColor}`} />
        <h3 className="text-xl font-bold">{title}</h3>
        <div className="ml-auto flex gap-1">
          {(['batter', 'pitcher'] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRole(r)}
              className={`px-3 py-1 rounded text-xs font-semibold transition-all ${
                role === r
                  ? 'bg-primary text-white'
                  : 'bg-white/10 text-gray-400 hover:bg-white/15'
              }`}
            >
              {r === 'batter' ? 'Batters' : 'Pitchers'}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="bg-bg-card rounded-xl h-40 animate-pulse shadow-modern" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {players.slice(0, 5).map((p) => (
            <FantasyPlayerCard key={p.player_id} player={p} />
          ))}
        </div>
      )}
    </section>
  );
}
