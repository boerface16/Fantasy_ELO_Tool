import { apiFetch } from '../lib/apiClient';
import type { PlayerTalentRadar, TalentLeaderboardPlayer } from '../types/talent';
import type { DailyOhlc } from '../types/elo';

export async function getPlayerTalentRadar(playerId: string): Promise<PlayerTalentRadar> {
  return apiFetch(`/api/talent/players/${playerId}/radar`);
}

export interface TalentLeaderboardParams {
  talentType: string;
  playerRole: string;
  page?: number;
  limit?: number;
  team?: string;
  days?: number;
  from_date?: string;
}

export async function getPlayerTalentOhlc(playerId: string, talentType: string, season?: number): Promise<DailyOhlc[]> {
  const params = new URLSearchParams({ talent_type: talentType });
  if (season !== undefined) params.set('season', String(season));
  return apiFetch(`/api/talent/players/${playerId}/ohlc?${params}`);
}

export async function getTalentLeaderboard(params: TalentLeaderboardParams): Promise<TalentLeaderboardPlayer[]> {
  const { talentType, playerRole, page = 1, limit = 20, team, days, from_date } = params;
  const p = new URLSearchParams({ type: talentType, role: playerRole, page: String(page), limit: String(limit) });
  if (team) p.set('team', team);
  if (days) p.set('days', String(days));
  if (from_date) p.set('from_date', from_date);
  return apiFetch(`/api/talent/leaderboard?${p.toString()}`);
}
