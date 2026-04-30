import { useState, useEffect } from 'react';
import { GitCompare, CalendarDays } from 'lucide-react';
import { usePlayerTalentRadar, useMultiPlayerTalentRadar } from '../../hooks/useTalent';
import { PLAYER_COLORS } from '../../constants/colors';
import EloRadarChart from './EloRadarChart';
import PlayerCompareSearch from './PlayerCompareSearch';
import type { ComparedPlayer } from './PlayerCompareSearch';

interface RadarSectionProps {
  playerId: string;
  role: 'batter' | 'pitcher';
  playerName: string;
  playerTeam: string;
}

export default function RadarSection({ playerId, role, playerName, playerTeam }: RadarSectionProps) {
  const [compareMode, setCompareMode] = useState(false);
  const [compared, setCompared] = useState<ComparedPlayer[]>([]);
  const [seasonMode, setSeasonMode] = useState(false);

  useEffect(() => {
    setCompared([]);
    setCompareMode(false);
  }, [role]);

  const { data: primaryRadar, isLoading } = usePlayerTalentRadar(playerId);
  const compareResults = useMultiPlayerTalentRadar(compared.map(p => p.playerId));

  if (isLoading) {
    return (
      <div className="rounded-2xl bg-bg-card border border-border-line p-6">
        <div className="h-4 w-36 bg-bg-elevated rounded animate-pulse mb-6" />
        <div className="max-w-sm mx-auto aspect-square bg-bg-elevated rounded-full animate-pulse" />
      </div>
    );
  }

  if (!primaryRadar) return null;

  const primary = {
    name: playerName,
    team: playerTeam,
    color: PLAYER_COLORS[0],
    radar: primaryRadar,
  };

  const comparedData = compared
    .map((p, i) => {
      const result = compareResults[i];
      if (!result?.data) return null;
      return {
        name: p.name,
        team: p.team,
        color: PLAYER_COLORS[i + 1] ?? '#aaa',
        radar: result.data,
      };
    })
    .filter((p): p is NonNullable<typeof p> => p !== null);

  const currentPlayer: ComparedPlayer = { playerId, name: playerName, team: playerTeam };
  const searchRole = role === 'batter' ? 'BATTING' : 'PITCHING';

  return (
    <div className="rounded-2xl bg-bg-card border border-border-line p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-text-secondary uppercase tracking-widest">
          ELO Fingerprint
        </h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setSeasonMode(m => !m)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              seasonMode
                ? 'bg-primary/20 text-primary border border-primary/40'
                : 'bg-bg-elevated text-text-secondary border border-border-line hover:text-text-primary'
            }`}
          >
            <CalendarDays className="w-3.5 h-3.5" />
            This Season
          </button>
          <button
            onClick={() => setCompareMode(m => !m)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              compareMode
                ? 'bg-primary/20 text-primary border border-primary/40'
                : 'bg-bg-elevated text-text-secondary border border-border-line hover:text-text-primary'
            }`}
          >
            <GitCompare className="w-3.5 h-3.5" />
            Compare
          </button>
        </div>
      </div>

      {compareMode && (
        <div className="mb-4">
          <PlayerCompareSearch
            currentPlayer={currentPlayer}
            role={searchRole}
            compared={compared}
            colors={PLAYER_COLORS}
            onAdd={p => setCompared(prev => [...prev, p])}
            onRemove={id => setCompared(prev => prev.filter(p => p.playerId !== id))}
          />
        </div>
      )}

      <div className="max-w-sm mx-auto">
        <EloRadarChart role={role} primary={primary} compared={comparedData} seasonMode={seasonMode} />
      </div>
    </div>
  );
}
