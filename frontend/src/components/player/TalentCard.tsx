import { Hand, Zap, Eye, Gauge, Trophy, Sparkles, Shield, Crosshair } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { getEloTier, getEloTierColor } from '../../types/elo';

const ICON_MAP: Record<string, LucideIcon> = {
  Hand, Zap, Eye, Gauge, Trophy, Sparkles, Shield, Crosshair,
};

interface TalentCardProps {
  label: string;
  iconName: string;
  elo: number;
  rank: number | null;
  totalPlayers: number;
  percentile: number | null;
}

export default function TalentCard({ label, iconName, elo, rank, totalPlayers, percentile }: TalentCardProps) {
  const Icon = ICON_MAP[iconName] || Hand;
  const tier = getEloTier(elo);
  const tierColor = getEloTierColor(tier);
  const topPercent = percentile !== null ? Math.round(100 - percentile) : null;

  return (
    <div className="bg-white rounded-lg shadow-sm p-3 text-center min-w-[100px] flex-1">
      <div className="flex items-center justify-center gap-1 mb-1">
        <Icon className="w-4 h-4 text-gray-400" />
        <span className="text-xs text-gray-500 uppercase tracking-wide font-medium">
          {label}
        </span>
      </div>
      <div className={`text-2xl font-bold ${tierColor}`}>
        {Math.round(elo).toLocaleString()}
      </div>
      <div className="text-xs text-gray-500 mt-1">
        {rank !== null && totalPlayers > 0 && (
          <span>#{rank}/{totalPlayers}</span>
        )}
        {topPercent !== null && topPercent > 0 && (
          <span className="ml-1">Top {topPercent}%</span>
        )}
      </div>
    </div>
  );
}
