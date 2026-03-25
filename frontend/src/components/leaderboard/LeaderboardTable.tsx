import { useNavigate } from 'react-router-dom';
import type { LeaderboardPlayer } from '../../api/elo';
import { getEloTier, getEloTierColor } from '../../types/elo';
import TeamLogo from '../common/TeamLogo';

interface LeaderboardTableProps {
  players: LeaderboardPlayer[];
  isLoading?: boolean;
  startRank?: number;
  position?: string;
}

export default function LeaderboardTable({ players, isLoading = false, startRank = 1, position }: LeaderboardTableProps) {
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
            <th className="px-4 py-3 text-right text-xs font-semibold text-gray-500 uppercase">Last Game</th>
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
              <LeaderboardRow
                key={player.player_id}
                player={player}
                rank={startRank + index}
                position={position}
              />
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

function LeaderboardRow({ player, rank, position }: { player: LeaderboardPlayer; rank: number; position?: string }) {
  const navigate = useNavigate();
  const roleElo = position === 'pitcher' ? player.pitching_elo : player.batting_elo;
  const rolePa = position === 'pitcher' ? player.pitching_pa : player.batting_pa;
  const tier = getEloTier(roleElo);
  const tierColor = getEloTierColor(tier);
  const isTwoWay = player.batting_pa > 0 && player.pitching_pa > 0;

  return (
    <tr
      onClick={() => navigate(`/player/${player.player_id}`)}
      className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors"
    >
      <td className="px-4 py-3 text-sm font-bold text-gray-400">{rank}</td>
      <td className="px-4 py-3 text-sm font-semibold text-gray-900">
        {player.full_name}
        {isTwoWay && (
          <span className="ml-1.5 text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-100 text-amber-700">
            TWP
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-sm text-gray-600">
        <div className="flex items-center gap-1.5">
          <TeamLogo size={20} />
          {player.team}
        </div>
      </td>
      <td className={`px-4 py-3 text-sm font-bold text-right ${tierColor}`}>
        {Math.round(roleElo)}
      </td>
      <td className="px-4 py-3 text-sm text-right text-gray-500">{rolePa}</td>
      <td className="px-4 py-3 text-sm text-right text-gray-500">{player.last_game_date}</td>
    </tr>
  );
}
