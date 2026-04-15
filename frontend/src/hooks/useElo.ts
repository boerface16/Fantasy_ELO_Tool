import { useQuery } from '@tanstack/react-query';
import * as eloApi from '../api/elo';
import type { LeaderboardParams } from '../api/elo';

export function useHotPlayers(date: string, role: string = 'BATTING') {
  return useQuery({
    queryKey: ['hotPlayers', date, role],
    queryFn: () => eloApi.getHotPlayers(date, role),
    enabled: !!date,
  });
}

export function useColdPlayers(date: string, role: string = 'BATTING') {
  return useQuery({
    queryKey: ['coldPlayers', date, role],
    queryFn: () => eloApi.getColdPlayers(date, role),
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

export function usePlayerOhlc(playerId: string, role?: string, season?: number) {
  return useQuery({
    queryKey: ['playerOhlc', playerId, role, season],
    queryFn: () => eloApi.getPlayerOhlc(playerId, role, season),
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

export function usePlayerGames(playerId: string, role: string = 'BATTING', limit: number = 5) {
  return useQuery({
    queryKey: ['playerGames', playerId, role, limit],
    queryFn: () => eloApi.getPlayerGames(playerId, role, limit),
    enabled: !!playerId,
    staleTime: 60_000,
  });
}

export function useHotFantasy(date: string, role: string) {
  return useQuery({
    queryKey: ['hotFantasy', date, role],
    queryFn: () => eloApi.getHotFantasy(date, role),
    enabled: !!date,
  });
}

export function useColdFantasy(date: string, role: string) {
  return useQuery({
    queryKey: ['coldFantasy', date, role],
    queryFn: () => eloApi.getColdFantasy(date, role),
    enabled: !!date,
  });
}

export function useFantasyLeaderboard(role: string, season: number, page: number, limit: number) {
  return useQuery({
    queryKey: ['fantasyLeaderboard', role, season, page],
    queryFn: () => eloApi.getFantasyLeaderboard(role, season, page, limit),
    staleTime: 60_000,
  });
}

export function usePlayerStatLine(playerId: string, role: string, season: number) {
  return useQuery({
    queryKey: ['playerStatLine', playerId, role, season],
    queryFn: () => eloApi.getPlayerStatLine(playerId, role, season),
    enabled: !!playerId,
    staleTime: 300_000,
  });
}
