import { useNavigate } from 'react-router-dom';
import type { TalentLeaderboardPlayer } from '../../types/talent';
import { getEloTier, getEloTierColor } from '../../types/elo';
import TeamLogo from '../common/TeamLogo';

interface TalentLeaderboardTableProps {
  players: TalentLeaderboardPlayer[];
  isLoading?: boolean;
  startRank?: number;
  totalInDimension?: number;
}

export default function TalentLeaderboardTable({
  players,
  isLoading = false,
  startRank = 1,
  totalInDimension = 0,
}: TalentLeaderboardTableProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
      <table className="w-full">
        <thead>
          <tr className="border-b border-gray-100 bg-gray-50">
            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">#</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Player</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase">Team</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase">ELO</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase">PA</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase">Top %</th>
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="animate-pulse border-b border-gray-50">
                <td colSpan={6} className="px-4 py-4">
                  <div className="h-5 bg-gray-200 rounded w-full"></div>
                </td>
              </tr>
            ))
          ) : players.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-gray-500">
                No players found
              </td>
            </tr>
          ) : (
            players.map((player, index) => (
              <TalentLeaderboardRow
                key={player.player_id}
                player={player}
                rank={startRank + index}
                totalInDimension={totalInDimension}
              />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function TalentLeaderboardRow({
  player,
  rank,
  totalInDimension,
}: {
  player: TalentLeaderboardPlayer;
  rank: number;
  totalInDimension: number;
}) {
  const navigate = useNavigate();
  const tier = getEloTier(player.season_elo);
  const tierColor = getEloTierColor(tier);
  const topPercent = totalInDimension > 0 ? Math.round((rank / totalInDimension) * 100) : null;

  return (
    <tr
      onClick={() => navigate(`/player/${player.player_id}`)}
      className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors"
    >
      <td className="px-4 py-3 text-sm font-bold text-gray-400">{rank}</td>
      <td className="px-4 py-3 text-sm font-semibold text-gray-900">
        {player.full_name}
      </td>
      <td className="px-4 py-3 text-sm text-gray-600">
        <div className="flex items-center gap-1.5">
          <TeamLogo size={20} />
          {player.team}
        </div>
      </td>
      <td className={`px-4 py-3 text-sm font-bold text-right ${tierColor}`}>
        {Math.round(player.season_elo)}
      </td>
      <td className="px-4 py-3 text-sm text-right text-gray-500">{player.pa_count}</td>
      <td className="px-4 py-3 text-sm text-right text-gray-500">
        {topPercent !== null ? `${topPercent}%` : '—'}
      </td>
    </tr>
  );
}
