import { useNavigate } from 'react-router-dom';
import type { FantasyLeaderboardPlayer } from '../../types/elo';
import TeamBadge from '../common/TeamBadge';

interface FantasyLeaderboardTableProps {
  players: FantasyLeaderboardPlayer[];
  isLoading?: boolean;
  startRank?: number;
  role?: 'batter' | 'pitcher';
}

export default function FantasyLeaderboardTable({
  players,
  isLoading = false,
  startRank = 1,
  role = 'batter',
}: FantasyLeaderboardTableProps) {
  const paLabel = role === 'pitcher' ? 'BF' : 'PA';

  return (
    <div className="bg-bg-card rounded-lg shadow-modern border border-border-line overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border-line bg-bg-elevated/40">
              <th className="px-4 py-3 text-left text-xs font-semibold text-text-secondary uppercase">#</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-text-secondary uppercase">Player</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-text-secondary uppercase">Team</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-text-secondary uppercase">Pts</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-text-secondary uppercase">{paLabel}</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="animate-pulse border-b border-border-line">
                  <td colSpan={5} className="px-4 py-4">
                    <div className="h-5 bg-bg-elevated/60 rounded w-full"></div>
                  </td>
                </tr>
              ))
            ) : players.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-text-secondary">
                  No players found
                </td>
              </tr>
            ) : (
              players.map((player, index) => (
                <FantasyLeaderboardRow
                  key={player.player_id}
                  player={player}
                  rank={startRank + index}
                />
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FantasyLeaderboardRow({
  player,
  rank,
}: {
  player: FantasyLeaderboardPlayer;
  rank: number;
}) {
  const navigate = useNavigate();
  const ptsColor = player.total_pts > 0 ? 'text-delta-up' : player.total_pts < 0 ? 'text-delta-down' : 'text-text-secondary';

  return (
    <tr
      onClick={() => navigate(`/player/${player.player_id}`)}
      className="border-b border-border-line hover:bg-bg-elevated/60 cursor-pointer transition-colors"
    >
      <td className="px-4 py-3 text-sm font-bold text-text-secondary">{rank}</td>
      <td className="px-4 py-3 text-sm font-semibold text-text-primary">{player.full_name}</td>
      <td className="px-4 py-3 text-sm"><TeamBadge code={player.team} /></td>
      <td className={`px-4 py-3 text-sm font-bold text-right ${ptsColor}`}>
        {player.total_pts > 0 ? '+' : ''}{player.total_pts.toFixed(1)}
      </td>
      <td className="px-4 py-3 text-sm text-right text-text-secondary">{player.total_pa}</td>
    </tr>
  );
}
