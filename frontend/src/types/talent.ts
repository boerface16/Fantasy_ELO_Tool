export type TalentType =
  | 'contact'
  | 'power'
  | 'discipline'
  | 'speed'
  | 'clutch'
  | 'stuff'
  | 'bip_suppression'
  | 'command'
  | 'pitcher_clutch';

export type DbTalentType =
  | 'contact'
  | 'power'
  | 'discipline'
  | 'speed'
  | 'clutch'
  | 'stuff'
  | 'bip_suppression'
  | 'command';

export interface TalentDimension {
  talentType: TalentType;
  playerRole: 'batter' | 'pitcher';
  seasonElo: number;
  careerElo: number;
  seasonRank: number | null;
  careerRank: number | null;
  totalPlayers: number;
}

export interface PlayerTalentRadar {
  playerId: number;
  dimensions: TalentDimension[];
}

export interface TalentMeta {
  type: TalentType;
  dbType: DbTalentType;
  label: string;
  icon: string;
  role: 'batter' | 'pitcher';
}

export const BATTER_TALENTS: TalentMeta[] = [
  { type: 'contact', dbType: 'contact', label: 'Contact', icon: 'Hand', role: 'batter' },
  { type: 'power', dbType: 'power', label: 'Power', icon: 'Zap', role: 'batter' },
  { type: 'discipline', dbType: 'discipline', label: 'Discipline', icon: 'Eye', role: 'batter' },
  // speed 비활성화 — DB 데이터는 유지, 프론트에서 미표시
  { type: 'clutch', dbType: 'clutch', label: 'Clutch', icon: 'Trophy', role: 'batter' },
];

export const PITCHER_TALENTS: TalentMeta[] = [
  { type: 'stuff', dbType: 'stuff', label: 'Stuff', icon: 'Sparkles', role: 'pitcher' },
  { type: 'bip_suppression', dbType: 'bip_suppression', label: 'BIP Supp.', icon: 'Shield', role: 'pitcher' },
  { type: 'command', dbType: 'command', label: 'Command', icon: 'Crosshair', role: 'pitcher' },
  { type: 'pitcher_clutch', dbType: 'clutch', label: 'Clutch', icon: 'Trophy', role: 'pitcher' },
];

export const ALL_TALENTS: TalentMeta[] = [...BATTER_TALENTS, ...PITCHER_TALENTS];

export function getTalentMeta(talentType: TalentType): TalentMeta | undefined {
  return ALL_TALENTS.find(t => t.type === talentType);
}

export function toUiTalentType(dbType: string, playerRole: string): TalentType {
  if (dbType === 'clutch' && playerRole === 'pitcher') return 'pitcher_clutch';
  return dbType as TalentType;
}

export interface TalentLeaderboardPlayer {
  player_id: number;
  season_elo: number;
  career_elo: number;
  pa_count: number;
  full_name: string;
  team: string;
  position: string;
}
