import { TrendingUp, TrendingDown } from 'lucide-react';
import type { HotColdPlayer } from '../../types/elo';
import PlayerCard from './PlayerCard';

interface HotColdSectionProps {
  type: 'hot' | 'cold';
  players: HotColdPlayer[];
  isLoading?: boolean;
}

export default function HotColdSection({ type, players, isLoading }: HotColdSectionProps) {
  const isHot = type === 'hot';
  const Icon = isHot ? TrendingUp : TrendingDown;
  const title = isHot ? 'Daily Hot Players' : 'Daily Cold Players';
  const iconColor = isHot ? 'text-green-600' : 'text-red-600';
  const badge = isHot ? 'High Gainers' : 'Risk Alert';
  const badgeColor = isHot ? 'text-primary' : 'text-blue-600';

  if (isLoading) {
    return (
      <section className="mb-8">
        <div className="flex items-center gap-2 mb-4 px-1">
          <Icon className={`w-5 h-5 ${iconColor}`} />
          <h3 className="text-xl font-bold">{title}</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="bg-white rounded-xl h-40 animate-pulse shadow-modern" />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="mb-8">
      <div className="flex items-center gap-2 mb-4 px-1">
        <Icon className={`w-5 h-5 ${iconColor}`} />
        <h3 className="text-xl font-bold">{title}</h3>
        <span className={`ml-auto text-xs font-bold uppercase tracking-wider ${badgeColor}`}>
          {badge}
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {players.slice(0, 5).map((player) => (
          <PlayerCard
            key={player.player_id}
            player={player}
          />
        ))}
      </div>
    </section>
  );
}
