import { useNavigate } from 'react-router-dom';
import { useAllTeamElos } from '../hooks/useFantasy';
import { TEAM_COLORS } from '../utils/teamColors';

export default function TeamElo() {
  const navigate = useNavigate();
  const { data: teams = [], isLoading } = useAllTeamElos();

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-bold tracking-tight">Team ELO</h2>
        <span className="text-xs font-medium px-2 py-0.5 rounded bg-primary/10 text-primary">
          All 30 Teams
        </span>
      </div>

      <div className="bg-bg-card rounded-lg border border-border-line overflow-hidden shadow-modern">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border-line text-text-secondary text-xs uppercase tracking-wider">
              <th className="text-left px-4 py-3 w-12">#</th>
              <th className="text-left px-4 py-3">Team</th>
              <th className="text-right px-4 py-3">ELO</th>
              <th className="text-right px-4 py-3 hidden sm:table-cell">Last Game</th>
              <th className="text-right px-4 py-3 hidden sm:table-cell">Run Diff</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={5} className="text-center py-12 text-text-secondary">Loading...</td>
              </tr>
            ) : teams.length === 0 ? (
              <tr>
                <td colSpan={5} className="text-center py-12 text-text-secondary">No team ELO data available</td>
              </tr>
            ) : (
              teams.map((team, idx) => {
                const color = TEAM_COLORS[team.teamCode];
                return (
                  <tr
                    key={team.teamCode}
                    onClick={() => navigate(`/team-elo/${team.teamCode}`)}
                    className="border-b border-border-line last:border-0 hover:bg-bg-elevated/60 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 text-text-secondary font-mono">{idx + 1}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span
                          className="w-3 h-3 rounded-full shrink-0"
                          style={{ backgroundColor: color?.primary ?? '#6B7280' }}
                        />
                        <span className="font-semibold text-text-primary">{team.teamCode}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right font-mono font-semibold text-text-primary">
                      {Math.round(team.elo)}
                    </td>
                    <td className="px-4 py-3 text-right hidden sm:table-cell">
                      <span className={team.lastResult === 'W' ? 'text-green-400' : 'text-red-400'}>
                        {team.lastResult}
                      </span>
                      <span className="text-text-secondary ml-1">vs {team.lastOpponent}</span>
                    </td>
                    <td className="px-4 py-3 text-right hidden sm:table-cell font-mono">
                      <span className={team.lastRunDiff > 0 ? 'text-green-400' : team.lastRunDiff < 0 ? 'text-red-400' : 'text-text-secondary'}>
                        {team.lastRunDiff > 0 ? '+' : ''}{team.lastRunDiff}
                      </span>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
