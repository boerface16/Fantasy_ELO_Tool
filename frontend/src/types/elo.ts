export interface Player {
  player_id: number;
  full_name: string;
  team: string;
  position: string;
}

export interface PlayerElo {
  player_id: number;
  composite_elo: number;
  batting_elo: number;
  pitching_elo: number;
  pa_count: number;
  batting_pa: number;
  pitching_pa: number;
  last_game_date: string;
  player?: Player;
}

export interface DailyOhlc {
  game_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  delta: number;
  total_pa: number;
  role: string;
}

export interface PlayerStats {
  totalPa: number;
  avgDelta: number;
  highestElo: { value: number; date: string };
  lowestElo: { value: number; date: string };
  avgRange: number;
}

export interface HotColdPlayer {
  player_id: number;
  game_date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  delta: number;
  total_pa: number;
  full_name: string;
  team: string;
  position: string;
}

export interface LeagueSummary {
  activePlayersCount: number;
  averageElo: number;
  eliteCount: number;
}

export interface PlayerSearchResult {
  player_id: number;
  full_name: string;
  team: string;
  position: string;
  is_two_way: boolean;
}

export interface SeasonMeta {
  year: number;
  startDate: string;
  endDate: string;
}

export type EloTier = 'elite' | 'high' | 'above' | 'average' | 'below' | 'low' | 'cold';

export function getEloTier(elo: number): EloTier {
  if (elo >= 1800) return 'elite';
  if (elo >= 1650) return 'high';
  if (elo >= 1550) return 'above';
  if (elo >= 1450) return 'average';
  if (elo >= 1350) return 'below';
  if (elo >= 1200) return 'low';
  return 'cold';
}

export function getEloTierColor(tier: EloTier): string {
  const colors: Record<EloTier, string> = {
    elite: 'text-elo-elite',
    high: 'text-elo-high',
    above: 'text-elo-above',
    average: 'text-elo-average',
    below: 'text-elo-below',
    low: 'text-elo-low',
    cold: 'text-elo-cold',
  };
  return colors[tier];
}

export function getEloTierBorderColor(tier: EloTier): string {
  const colors: Record<EloTier, string> = {
    elite: 'border-t-elo-elite',
    high: 'border-t-elo-high',
    above: 'border-t-elo-above',
    average: 'border-t-elo-average',
    below: 'border-t-elo-below',
    low: 'border-t-elo-low',
    cold: 'border-t-elo-cold',
  };
  return colors[tier];
}
