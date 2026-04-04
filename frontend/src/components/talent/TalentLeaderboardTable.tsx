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
    <div className="bg-bg-card rounded-xl shadow-sm border border-border-line overflow-hidden">
      <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border-line bg-white/5">
            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">#</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Player</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-gray-400 uppercase">Team</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-400 uppercase">ELO</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-400 uppercase">PA</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-400 uppercase">Top %</th>
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="animate-pulse border-b border-border-line">
                <td colSpan={6} className="px-4 py-4">
                  <div className="h-5 bg-white/15 rounded w-full"></div>
                </td>
              </tr>
            ))
          ) : players.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-gray-400">
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
      className="border-b border-border-line hover:bg-white/5 cursor-pointer transition-colors"
    >
      <td className="px-4 py-3 text-sm font-bold text-gray-400">{rank}</td>
      <td className="px-4 py-3 text-sm font-semibold text-gray-100">
        {player.full_name}
      </td>
      <td className="px-4 py-3 text-sm text-gray-400">
        <div className="flex items-center gap-1.5">
          <TeamLogo size={20} />
          {player.team}
        </div>
      </td>
      <td className={`px-4 py-3 text-sm font-bold text-right ${tierColor}`}>
        {Math.round(player.season_elo)}
      </td>
      <td className="px-4 py-3 text-sm text-right text-gray-400">{player.pa_count}</td>
      <td className="px-4 py-3 text-sm text-right text-gray-400">
        {topPercent !== null ? `${topPercent}%` : '—'}
      </td>
    </tr>
  );
}
