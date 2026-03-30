import type { PAProbabilities } from './matchup';

// --- Team ELO ---

export interface TeamElo {
  teamCode: string;
  elo: number;
  lastGameDate: string;
  lastOpponent: string;
  lastResult: 'W' | 'L';
  lastRunDiff: number;
}

export interface TeamEloTrendEntry {
  date: string;
  eloBefore: number;
  eloAfter: number;
  opponent: string;
  result: 'W' | 'L';
  runDiff: number;
}

export interface TeamEloDetail {
  teamCode: string;
  currentElo: number;
  trend: TeamEloTrendEntry[];
}

// --- Roster ---

export interface RosterEntry {
  slot: string;
  name: string;
  team: string;
  playerId: number | null;
  matchedName: string | null;
  dbTeam: string | null;
  position: string | null;
}

export interface RosterParseResult {
  entries: RosterEntry[];
  count: number;
}

// --- Schedule ---

export interface ScheduleGame {
  date: string;
  gamePk: number;
  awayTeam: string;
  homeTeam: string;
  awayPitcher: string;
  awayPitcherId: number | null;
  homePitcher: string;
  homePitcherId: number | null;
  venue: string;
}

export interface ScheduleResult {
  games: ScheduleGame[];
  count: number;
}

// --- Weekly Projection ---

export interface BatterMatchup {
  date: string;
  opponent: string;
  pitcher: string;
  isHome: boolean;
  expectedWoba: number;
  expectedPoints: number;
}

export interface BatterProjection {
  name: string;
  team: string;
  slot: string;
  games: number;
  totalPoints: number;
  pointsPerGame: number;
  matchups: BatterMatchup[];
}

export interface PitcherMatchup {
  date: string;
  opponent: string;
  isHome: boolean;
  expectedWoba: number;
  expectedPoints: number;
}

export interface PitcherProjection {
  name: string;
  team: string;
  slot: string;
  starts: number;
  totalPoints: number;
  matchups: PitcherMatchup[];
}

export interface WeeklyProjection {
  weekStart: string;
  weekEnd: string;
  totalPoints: number;
  totalBatterPoints: number;
  totalPitcherPoints: number;
  batters: BatterProjection[];
  pitchers: PitcherProjection[];
}

// --- Fantasy Matchup ---

export interface FantasyMatchupResult {
  batterId: number;
  pitcherId: number;
  probabilities: PAProbabilities;
  expectedWoba: number;
  expectedPoints: number;
  zDiffs: Record<string, number>;
}
