import { apiFetch } from '../lib/apiClient';
import type { BatterTalentElo, PitcherTalentElo } from '../types/matchup';

export async function getBatterTalentElo(playerId: number): Promise<BatterTalentElo> {
  return apiFetch(`/api/matchup/batter/${playerId}/talent`);
}

export async function getPitcherTalentElo(playerId: number): Promise<PitcherTalentElo> {
  return apiFetch(`/api/matchup/pitcher/${playerId}/talent`);
}
