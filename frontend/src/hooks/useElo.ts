import { useQuery } from '@tanstack/react-query';
import * as eloApi from '../api/elo';
import type { LeaderboardParams } from '../api/elo';

export function useHotPlayers(date: string) {
  return useQuery({
    queryKey: ['hotPlayers', date],
    queryFn: () => eloApi.getHotPlayers(date),
    enabled: !!date,
  });
}

export function useColdPlayers(date: string) {
  return useQuery({
    queryKey: ['coldPlayers', date],
    queryFn: () => eloApi.getColdPlayers(date),
    enabled: !!date,
  });
}

export function useLeaderboard(params: LeaderboardParams) {
  return useQuery({
    queryKey: ['leaderboard', params],
    queryFn: () => eloApi.getLeaderboard(params),
    staleTime: 60_000,
  });
}

export function usePlayerElo(playerId: string) {
  return useQuery({
    queryKey: ['playerElo', playerId],
    queryFn: () => eloApi.getPlayerElo(playerId),
    enabled: !!playerId,
  });
}

export function usePlayerOhlc(playerId: string, role?: string) {
  return useQuery({
    queryKey: ['playerOhlc', playerId, role],
    queryFn: () => eloApi.getPlayerOhlc(playerId, role),
    enabled: !!playerId,
  });
}

export function usePlayerStats(playerId: string, role?: string) {
  return useQuery({
    queryKey: ['playerStats', playerId, role],
    queryFn: () => eloApi.getPlayerStats(playerId, role),
    enabled: !!playerId,
  });
}

export function useLeagueSummary() {
  return useQuery({
    queryKey: ['leagueSummary'],
    queryFn: () => eloApi.getLeagueSummary(),
  });
}

export function usePlayerSearch(query: string) {
  return useQuery({
    queryKey: ['playerSearch', query],
    queryFn: () => eloApi.searchPlayers(query),
    enabled: query.length >= 2,
    staleTime: 30_000,
  });
}

export function useLatestDate() {
  return useQuery({
    queryKey: ['latestDate'],
    queryFn: () => eloApi.getLatestDate(),
    staleTime: 300_000,
  });
}

export function useSeasonMeta() {
  return useQuery({
    queryKey: ['seasonMeta'],
    queryFn: () => eloApi.getSeasonMeta(),
    staleTime: 300_000,
  });
}
