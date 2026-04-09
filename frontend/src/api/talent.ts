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
}

export async function getPlayerTalentOhlc(playerId: string, talentType: string, season?: number): Promise<DailyOhlc[]> {
  const params = new URLSearchParams({ talent_type: talentType });
  if (season !== undefined) params.set('season', String(season));
  return apiFetch(`/api/talent/players/${playerId}/ohlc?${params}`);
}

export async function getTalentLeaderboard(params: TalentLeaderboardParams): Promise<TalentLeaderboardPlayer[]> {
  const { talentType, playerRole, page = 1, limit = 20 } = params;
  return apiFetch(`/api/talent/leaderboard?type=${talentType}&role=${playerRole}&page=${page}&limit=${limit}`);
}
