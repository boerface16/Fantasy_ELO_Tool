import { apiFetch } from '../lib/apiClient';
import type { HotColdPlayer, PlayerElo, Player, DailyOhlc, PlayerStats, LeagueSummary, PlayerSearchResult, SeasonMeta } from '../types/elo';

export async function getHotPlayers(date: string): Promise<HotColdPlayer[]> {
  return apiFetch(`/api/elo/hot-players?date=${date}`);
}

export async function getColdPlayers(date: string): Promise<HotColdPlayer[]> {
  return apiFetch(`/api/elo/cold-players?date=${date}`);
}

export interface LeaderboardParams {
  position?: string;
  page?: number;
  limit?: number;
}

export interface LeaderboardPlayer {
  player_id: number;
  composite_elo: number;
  batting_elo: number;
  pitching_elo: number;
  pa_count: number;
  batting_pa: number;
  pitching_pa: number;
  last_game_date: string;
  full_name: string;
  team: string;
  position: string;
}

export async function getLeaderboard(params: LeaderboardParams): Promise<LeaderboardPlayer[]> {
  const { position = 'batter', page = 1, limit = 20 } = params;
  return apiFetch(`/api/elo/leaderboard?position=${position}&page=${page}&limit=${limit}`);
}

export async function getPlayerElo(playerId: string): Promise<PlayerElo & { player: Player }> {
  return apiFetch(`/api/elo/players/${playerId}`);
}

export async function getPlayerOhlc(playerId: string, role?: string): Promise<DailyOhlc[]> {
  const roleParam = role ? `?role=${role}` : '';
  return apiFetch(`/api/elo/players/${playerId}/ohlc${roleParam}`);
}

export async function getPlayerStats(playerId: string, role?: string): Promise<PlayerStats> {
  const roleParam = role ? `?role=${role}` : '';
  return apiFetch(`/api/elo/players/${playerId}/stats${roleParam}`);
}

export async function searchPlayers(query: string): Promise<PlayerSearchResult[]> {
  if (query.length < 2) return [];
  return apiFetch(`/api/elo/search?q=${encodeURIComponent(query)}`);
}

export async function getLeagueSummary(): Promise<LeagueSummary> {
  return apiFetch('/api/elo/league-summary');
}

export async function getLatestDate(): Promise<string> {
  const resp = await apiFetch<{ date: string | null }>('/api/elo/latest-date');
  return resp.date ?? new Date().toISOString().slice(0, 10);
}

export async function getSeasonMeta(): Promise<SeasonMeta> {
  return apiFetch('/api/elo/season-meta');
}

export interface PlayerGameEntry {
  gamePk: number;
  date: string;
  opponent: string;
  elo: number;
  eloDelta: number;
  fantasyPoints: number;
  stats: {
    pa?: number;
    bf?: number;
    tb?: number;
    hr?: number;
    bb: number;
    k: number;
    ip?: number;
    h?: number;
  };
}

export async function getPlayerGames(
  playerId: string,
  role: string = 'BATTING',
  limit: number = 5,
): Promise<PlayerGameEntry[]> {
  const resp = await apiFetch<{ games: PlayerGameEntry[] }>(
    `/api/elo/players/${playerId}/games?role=${role}&limit=${limit}`,
  );
  return resp.games;
}
