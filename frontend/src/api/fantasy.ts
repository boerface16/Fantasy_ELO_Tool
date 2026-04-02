import { apiFetch } from '../lib/apiClient';
import type {
  TeamElo,
  TeamEloDetail,
  TeamEloTrendEntry,
  RosterParseResult,
  ScheduleResult,
  WeeklyProjection,
  FantasyMatchupResult,
} from '../types/fantasy';

export async function getAllTeamElos(): Promise<TeamElo[]> {
  return apiFetch('/api/fantasy/team-elo/all');
}

export async function getTeamElo(teamCode: string): Promise<TeamEloDetail> {
  return apiFetch(`/api/fantasy/team-elo/${teamCode}`);
}

export async function getTeamEloHistory(teamCode: string): Promise<TeamEloTrendEntry[]> {
  return apiFetch(`/api/fantasy/team-elo/${teamCode}/history`);
}

export async function parseRoster(rosterText: string): Promise<RosterParseResult> {
  return apiFetch('/api/fantasy/roster', {
    method: 'POST',
    body: JSON.stringify({ roster_text: rosterText }),
  });
}

export async function getSchedule(week?: string): Promise<ScheduleResult> {
  const params = week ? `?week=${week}` : '';
  return apiFetch(`/api/fantasy/schedule${params}`);
}

export async function getWeeklyProjection(
  rosterText: string,
  refDate?: string,
): Promise<WeeklyProjection> {
  return apiFetch('/api/fantasy/weekly-projection', {
    method: 'POST',
    body: JSON.stringify({ roster_text: rosterText, ref_date: refDate ?? null }),
  });
}

export async function getFantasyMatchup(
  batterId: number,
  pitcherId: number,
): Promise<FantasyMatchupResult> {
  return apiFetch(`/api/fantasy/matchup/${batterId}/${pitcherId}`);
}
