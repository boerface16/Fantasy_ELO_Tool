import { Link } from 'react-router-dom';
import { ArrowUp, ArrowDown, Minus } from 'lucide-react';
import type { FantasyHotColdPlayer } from '../../types/elo';
import { getTeamBorderColor } from '../../utils/teamColors';
import TeamLogo from '../common/TeamLogo';

interface FantasyPlayerCardProps {
  player: FantasyHotColdPlayer;
}

export default function FantasyPlayerCard({ player }: FantasyPlayerCardProps) {
  const teamBorderColor = getTeamBorderColor(player.team);
  const pts = player.fantasy_points;

  const PtsIcon = pts > 0 ? ArrowUp : pts < 0 ? ArrowDown : Minus;
  const ptsColor = pts > 0 ? 'text-delta-up' : pts < 0 ? 'text-delta-down' : 'text-gray-400';

  return (
    <Link
      to={`/player/${player.player_id}`}
      className="group bg-bg-card rounded-xl shadow-modern border-t-4 p-4 transition-transform hover:-translate-y-1 cursor-pointer block"
      style={{ borderTopColor: teamBorderColor }}
    >
      <div className="flex justify-between items-start mb-4">
        <div className="size-10 bg-white/10 rounded-full overflow-hidden border border-border-line flex items-center justify-center">
          <TeamLogo size={28} />
        </div>
        <div className="flex flex-col items-end">
          <span className={`${ptsColor} text-sm font-bold flex items-center`}>
            <PtsIcon className="w-3 h-3 mr-0.5" />
            {pts > 0 ? '+' : ''}{pts.toFixed(1)}
          </span>
          <span className="text-[10px] text-gray-400 uppercase font-bold tracking-tighter">
            Fantasy Pts
          </span>
        </div>
      </div>

      <div>
        <p className="text-gray-400 text-xs font-medium truncate">{player.team}</p>
        <h4 className="text-lg font-bold truncate group-hover:text-primary transition-colors">
          {player.full_name}
        </h4>
        <p className="text-xs text-gray-500 mt-1">{player.total_pa} PA</p>
      </div>
    </Link>
  );
}
