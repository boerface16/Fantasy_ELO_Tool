import { useQuery } from '@tanstack/react-query';
import * as talentApi from '../api/talent';
import type { TalentLeaderboardParams } from '../api/talent';

export function usePlayerTalentRadar(playerId: string) {
  return useQuery({
    queryKey: ['playerTalentRadar', playerId],
    queryFn: () => talentApi.getPlayerTalentRadar(playerId),
    enabled: !!playerId,
    staleTime: 60_000,
  });
}

export function useTalentLeaderboard(params: TalentLeaderboardParams) {
  return useQuery({
    queryKey: ['talentLeaderboard', params],
    queryFn: () => talentApi.getTalentLeaderboard(params),
    staleTime: 60_000,
  });
}
