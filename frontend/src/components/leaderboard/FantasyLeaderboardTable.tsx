import { useNavigate } from 'react-router-dom';
import type { FantasyLeaderboardPlayer } from '../../types/elo';
import TeamLogo from '../common/TeamLogo';

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
    <div className="bg-bg-card rounded-xl shadow-sm border border-border-line overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border-line bg-white/5">
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">#</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Player</th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Team</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-gray-400 uppercase">Pts</th>
              <th className="px-4 py-3 text-right text-xs font-semibold text-gray-400 uppercase">{paLabel}</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="animate-pulse border-b border-border-line">
                  <td colSpan={5} className="px-4 py-4">
                    <div className="h-5 bg-white/15 rounded w-full"></div>
                  </td>
                </tr>
              ))
            ) : players.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-4 py-8 text-center text-gray-400">
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
  const ptsColor = player.total_pts > 0 ? 'text-delta-up' : player.total_pts < 0 ? 'text-delta-down' : 'text-gray-400';

  return (
    <tr
      onClick={() => navigate(`/player/${player.player_id}`)}
      className="border-b border-border-line hover:bg-white/5 cursor-pointer transition-colors"
    >
      <td className="px-4 py-3 text-sm font-bold text-gray-400">{rank}</td>
      <td className="px-4 py-3 text-sm font-semibold text-gray-100">{player.full_name}</td>
      <td className="px-4 py-3 text-sm text-gray-400">
        <div className="flex items-center gap-1.5">
          <TeamLogo size={20} />
          {player.team}
        </div>
      </td>
      <td className={`px-4 py-3 text-sm font-bold text-right ${ptsColor}`}>
        {player.total_pts > 0 ? '+' : ''}{player.total_pts.toFixed(1)}
      </td>
      <td className="px-4 py-3 text-sm text-right text-gray-400">{player.total_pa}</td>
    </tr>
  );
}
