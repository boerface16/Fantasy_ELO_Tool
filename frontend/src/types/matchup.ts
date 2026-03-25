export interface BatterTalentElo {
  playerId: number;
  fullName: string;
  team: string;
  contact: number;
  power: number;
  discipline: number;
}

export interface PitcherTalentElo {
  playerId: number;
  fullName: string;
  team: string;
  stuff: number;
  bipSuppression: number;
  command: number;
}

export interface PAProbabilities {
  BB: number;
  K: number;
  OUT: number;
  '1B': number;
  '2B': number;
  '3B': number;
  HR: number;
}

export interface ZScoreDiffs {
  zDiscCmd: number;
  zStuffContact: number;
  zContactBip: number;
  zPower: number;
}

export interface StageBreakdown {
  stage1: { pBB: number; pK: number; pBIP: number };
  stage2: { pHitGivenBIP: number; pOutGivenBIP: number };
  stage3: { pXBHGivenHit: number; p1BGivenHit: number };
}

export interface MatchupPrediction {
  probabilities: PAProbabilities;
  expectedWoba: number;
  zDiffs: ZScoreDiffs;
  stages: StageBreakdown;
}

export type MatchupRole = 'batter' | 'pitcher';
