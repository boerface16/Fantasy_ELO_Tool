import { useQuery } from '@tanstack/react-query';
import * as matchupApi from '../api/matchup';
import { predictPlateAppearance } from '../lib/matchupPredictor';

export function useBatterTalentElo(playerId: number | null) {
  return useQuery({
    queryKey: ['batterTalentElo', playerId],
    queryFn: () => matchupApi.getBatterTalentElo(playerId!),
    enabled: playerId !== null,
    staleTime: 60_000,
  });
}

export function usePitcherTalentElo(playerId: number | null) {
  return useQuery({
    queryKey: ['pitcherTalentElo', playerId],
    queryFn: () => matchupApi.getPitcherTalentElo(playerId!),
    enabled: playerId !== null,
    staleTime: 60_000,
  });
}

export function useMatchupPrediction(batterId: number | null, pitcherId: number | null) {
  const batter = useBatterTalentElo(batterId);
  const pitcher = usePitcherTalentElo(pitcherId);

  const prediction =
    batter.data && pitcher.data
      ? predictPlateAppearance(batter.data, pitcher.data)
      : null;

  return {
    batter: batter.data ?? null,
    pitcher: pitcher.data ?? null,
    prediction,
    isLoading: batter.isLoading || pitcher.isLoading,
    error: batter.error || pitcher.error,
  };
}
