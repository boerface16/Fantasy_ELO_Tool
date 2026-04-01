export interface TeamColor {
  primary: string;
  primaryText: string;
  secondary: string;
  secondaryText: string;
}

export const TEAM_COLORS: Record<string, TeamColor> = {
  // American League East
  'NYY': { primary: '#003087', primaryText: '#ffffff', secondary: '#E4002B', secondaryText: '#ffffff' },
  'BOS': { primary: '#BD3039', primaryText: '#ffffff', secondary: '#0C2340', secondaryText: '#ffffff' },
  'TOR': { primary: '#134A8E', primaryText: '#ffffff', secondary: '#1D2D5C', secondaryText: '#ffffff' },
  'BAL': { primary: '#DF4601', primaryText: '#ffffff', secondary: '#27251F', secondaryText: '#ffffff' },
  'TB':  { primary: '#092C5C', primaryText: '#ffffff', secondary: '#8FBCE6', secondaryText: '#092C5C' },
  // American League Central
  'CLE': { primary: '#00385D', primaryText: '#ffffff', secondary: '#E50022', secondaryText: '#ffffff' },
  'MIN': { primary: '#002B5C', primaryText: '#ffffff', secondary: '#D31145', secondaryText: '#ffffff' },
  'DET': { primary: '#0C2340', primaryText: '#ffffff', secondary: '#FA4616', secondaryText: '#ffffff' },
  'KC':  { primary: '#004687', primaryText: '#ffffff', secondary: '#BD9B60', secondaryText: '#004687' },
  'CWS': { primary: '#27251F', primaryText: '#ffffff', secondary: '#C4CED4', secondaryText: '#27251F' },
  // American League West
  'HOU': { primary: '#002D62', primaryText: '#ffffff', secondary: '#EB6E1F', secondaryText: '#ffffff' },
  'SEA': { primary: '#0C2C56', primaryText: '#ffffff', secondary: '#005C5C', secondaryText: '#ffffff' },
  'TEX': { primary: '#003278', primaryText: '#ffffff', secondary: '#C0111F', secondaryText: '#ffffff' },
  'LAA': { primary: '#BA0021', primaryText: '#ffffff', secondary: '#003263', secondaryText: '#ffffff' },
  'OAK': { primary: '#003831', primaryText: '#ffffff', secondary: '#EFB21E', secondaryText: '#003831' },
  // National League East
  'ATL': { primary: '#CE1141', primaryText: '#ffffff', secondary: '#13274F', secondaryText: '#ffffff' },
  'NYM': { primary: '#002D72', primaryText: '#ffffff', secondary: '#FF5910', secondaryText: '#ffffff' },
  'PHI': { primary: '#E81828', primaryText: '#ffffff', secondary: '#002D72', secondaryText: '#ffffff' },
  'MIA': { primary: '#00A3E0', primaryText: '#ffffff', secondary: '#EF3340', secondaryText: '#ffffff' },
  'WSH': { primary: '#AB0003', primaryText: '#ffffff', secondary: '#14225A', secondaryText: '#ffffff' },
  // National League Central
  'MIL': { primary: '#FFC52F', primaryText: '#12284B', secondary: '#12284B', secondaryText: '#ffffff' },
  'CHC': { primary: '#0E3386', primaryText: '#ffffff', secondary: '#CC3433', secondaryText: '#ffffff' },
  'STL': { primary: '#C41E3A', primaryText: '#ffffff', secondary: '#0C2340', secondaryText: '#ffffff' },
  'PIT': { primary: '#27251F', primaryText: '#FDB827', secondary: '#FDB827', secondaryText: '#27251F' },
  'CIN': { primary: '#C6011F', primaryText: '#ffffff', secondary: '#27251F', secondaryText: '#ffffff' },
  // National League West
  'LAD': { primary: '#005A9C', primaryText: '#ffffff', secondary: '#EF3E42', secondaryText: '#ffffff' },
  'SD':  { primary: '#2F241D', primaryText: '#FFC425', secondary: '#FFC425', secondaryText: '#2F241D' },
  'AZ':  { primary: '#A71930', primaryText: '#ffffff', secondary: '#E3D4AD', secondaryText: '#A71930' },
  'SF':  { primary: '#FD5A1E', primaryText: '#ffffff', secondary: '#27251F', secondaryText: '#ffffff' },
  'COL': { primary: '#33006F', primaryText: '#ffffff', secondary: '#C4CED4', secondaryText: '#33006F' },
};

export function getTeamBorderColor(teamName: string): string {
  const color = TEAM_COLORS[teamName];
  return color?.primary || '#9ca3af';
}

export function getTeamColor(teamName: string): TeamColor | null {
  return TEAM_COLORS[teamName] || null;
}
