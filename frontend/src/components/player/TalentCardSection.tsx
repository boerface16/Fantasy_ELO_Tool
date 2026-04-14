import { usePlayerTalentRadar } from '../../hooks/useTalent';
import TalentCard from './TalentCard';
import { BATTER_TALENTS, PITCHER_TALENTS, getTalentMeta } from '../../types/talent';
import type { TalentDimension } from '../../types/talent';

interface TalentCardSectionProps {
  playerId: string;
  position: 'batter' | 'pitcher';
}

export default function TalentCardSection({ playerId, position }: TalentCardSectionProps) {
  const { data: talentData, isLoading } = usePlayerTalentRadar(playerId);

  if (isLoading) {
    return (
      <div className="bg-bg-card rounded-lg shadow-modern p-4">
        <div className="flex gap-3 overflow-x-auto">
          {Array.from({ length: position === 'pitcher' ? 4 : 5 }).map((_, i) => (
            <div key={i} className="bg-bg-elevated rounded-lg p-3 min-w-[100px] flex-1 animate-pulse">
              <div className="h-4 bg-bg-elevated/60 rounded mb-2" />
              <div className="h-8 bg-bg-elevated/60 rounded mb-1" />
              <div className="h-3 bg-bg-elevated/60 rounded w-2/3 mx-auto" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (!talentData || talentData.dimensions.length === 0) {
    return null;
  }

  const relevantTalents = position === 'pitcher' ? PITCHER_TALENTS : BATTER_TALENTS;

  const sortedDimensions = relevantTalents
    .map(talent => talentData.dimensions.find(d => d.talentType === talent.type))
    .filter((d): d is TalentDimension => d !== undefined);

  if (sortedDimensions.length === 0) return null;

  return (
    <div className="bg-bg-card rounded-lg shadow-modern p-4">
      <h3 className="text-sm font-medium text-text-secondary mb-3">
        {position === 'pitcher' ? 'Pitching' : 'Batting'} Talent
      </h3>
      <div className="flex gap-3 overflow-x-auto pb-2">
        {sortedDimensions.map((dim) => {
          const meta = getTalentMeta(dim.talentType);
          if (!meta) return null;

          const percentile = dim.totalPlayers > 0 && dim.seasonRank !== null
            ? ((1 - dim.seasonRank / dim.totalPlayers) * 100)
            : null;

          return (
            <TalentCard
              key={dim.talentType}
              label={meta.label}
              iconName={meta.icon}
              elo={dim.seasonElo}
              rank={dim.seasonRank}
              totalPlayers={dim.totalPlayers}
              percentile={percentile}
            />
          );
        })}
      </div>
    </div>
  );
}
