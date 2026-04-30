import { useQuery, useQueries } from '@tanstack/react-query';
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

export function usePlayerTalentOhlc(playerId: string, talentType: string, season?: number) {
  return useQuery({
    queryKey: ['playerTalentOhlc', playerId, talentType, season],
    queryFn: () => talentApi.getPlayerTalentOhlc(playerId, talentType, season),
    enabled: !!playerId && !!talentType,
    staleTime: 60_000,
  });
}

export function useMultiPlayerTalentRadar(playerIds: string[]) {
  return useQueries({
    queries: playerIds.map(id => ({
      queryKey: ['playerTalentRadar', id],
      queryFn: () => talentApi.getPlayerTalentRadar(id),
      enabled: !!id,
      staleTime: 60_000,
    })),
  });
}

export function useTalentLeaderboard(params: TalentLeaderboardParams) {
  return useQuery({
    queryKey: ['talentLeaderboard', params],
    queryFn: () => talentApi.getTalentLeaderboard(params),
    staleTime: 60_000,
  });
}
