import { useNavigate } from 'react-router-dom';
import type { LeaderboardPlayer } from '../../api/elo';
import { getEloTier, getEloTierColor } from '../../types/elo';
import TeamBadge from '../common/TeamBadge';

interface LeaderboardTableProps {
  players: LeaderboardPlayer[];
  isLoading?: boolean;
  startRank?: number;
  position?: string;
}

export default function LeaderboardTable({ players, isLoading = false, startRank = 1, position }: LeaderboardTableProps) {
  return (
    <div className="bg-bg-card rounded-lg shadow-modern border border-border-line overflow-hidden">
      <div className="overflow-x-auto">
      <table className="w-full">
        <thead>
          <tr className="border-b border-border-line bg-bg-elevated/40">
            <th className="px-4 py-3 text-left text-xs font-semibold text-text-secondary uppercase">#</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-text-secondary uppercase">Player</th>
            <th className="px-4 py-3 text-left text-xs font-semibold text-text-secondary uppercase">Team</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-text-secondary uppercase">ELO</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-text-secondary uppercase">PA</th>
            <th className="px-4 py-3 text-right text-xs font-semibold text-text-secondary uppercase">Last Game</th>
          </tr>
        </thead>
        <tbody>
          {isLoading ? (
            Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="animate-pulse border-b border-border-line">
                <td colSpan={6} className="px-4 py-4">
                  <div className="h-5 bg-bg-elevated/60 rounded w-full"></div>
                </td>
              </tr>
            ))
          ) : players.length === 0 ? (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-text-secondary">
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
      className="border-b border-border-line hover:bg-bg-elevated/60 cursor-pointer transition-colors"
    >
      <td className="px-4 py-3 text-sm font-bold text-text-secondary">{rank}</td>
      <td className="px-4 py-3 text-sm font-semibold text-text-primary">
        {player.full_name}
        {isTwoWay && (
          <span className="ml-1.5 text-[10px] font-semibold px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-400">
            TWP
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-sm"><TeamBadge code={player.team} /></td>
      <td className={`px-4 py-3 text-sm font-bold text-right ${tierColor}`}>
        {Math.round(roleElo)}
      </td>
      <td className="px-4 py-3 text-sm text-right text-text-secondary">{rolePa}</td>
      <td className="px-4 py-3 text-sm text-right text-text-secondary">{player.last_game_date}</td>
    </tr>
  );
}
