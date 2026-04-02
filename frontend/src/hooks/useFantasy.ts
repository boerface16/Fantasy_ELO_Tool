import { useQuery, useMutation } from '@tanstack/react-query';
import * as fantasyApi from '../api/fantasy';

export function useAllTeamElos() {
  return useQuery({
    queryKey: ['teamElos'],
    queryFn: fantasyApi.getAllTeamElos,
    staleTime: 60_000,
  });
}

export function useTeamElo(teamCode: string) {
  return useQuery({
    queryKey: ['teamElo', teamCode],
    queryFn: () => fantasyApi.getTeamElo(teamCode),
    enabled: !!teamCode,
    staleTime: 60_000,
  });
}

export function useTeamEloHistory(teamCode: string) {
  return useQuery({
    queryKey: ['teamEloHistory', teamCode],
    queryFn: () => fantasyApi.getTeamEloHistory(teamCode),
    enabled: !!teamCode,
    staleTime: 60_000,
  });
}

export function useParseRoster() {
  return useMutation({
    mutationFn: (rosterText: string) => fantasyApi.parseRoster(rosterText),
  });
}

export function useSchedule(week?: string) {
  return useQuery({
    queryKey: ['schedule', week],
    queryFn: () => fantasyApi.getSchedule(week),
    staleTime: 300_000,
  });
}

export function useWeeklyProjection() {
  return useMutation({
    mutationFn: ({ rosterText, refDate }: { rosterText: string; refDate?: string }) =>
      fantasyApi.getWeeklyProjection(rosterText, refDate),
  });
}

export function useFantasyMatchup(batterId: number | null, pitcherId: number | null) {
  return useQuery({
    queryKey: ['fantasyMatchup', batterId, pitcherId],
    queryFn: () => fantasyApi.getFantasyMatchup(batterId!, pitcherId!),
    enabled: !!batterId && !!pitcherId,
    staleTime: 60_000,
  });
}
