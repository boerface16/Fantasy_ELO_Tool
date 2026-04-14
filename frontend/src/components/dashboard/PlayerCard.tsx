import { Link } from 'react-router-dom';
import { ArrowUp, ArrowDown, Minus } from 'lucide-react';
import type { HotColdPlayer } from '../../types/elo';
import { getTeamBorderColor } from '../../utils/teamColors';
import TeamLogo from '../common/TeamLogo';

interface PlayerCardProps {
  player: HotColdPlayer;
}

export default function PlayerCard({ player }: PlayerCardProps) {
  const teamBorderColor = getTeamBorderColor(player.team);
  const delta = player.delta;

  const DeltaIcon = delta > 0 ? ArrowUp : delta < 0 ? ArrowDown : Minus;
  const deltaColor = delta > 0 ? 'text-delta-up' : delta < 0 ? 'text-delta-down' : 'text-text-secondary';

  return (
    <Link
      to={`/player/${player.player_id}`}
      className="group bg-bg-card rounded-lg shadow-modern border border-border-line border-t-4 p-4 transition-transform hover:-translate-y-1 cursor-pointer block"
      style={{ borderTopColor: teamBorderColor }}
    >
      {/* Header: Team & Delta */}
      <div className="flex justify-between items-start mb-4">
        <div className="size-10 bg-bg-elevated rounded-full overflow-hidden border border-border-line flex items-center justify-center">
          <TeamLogo size={28} />
        </div>
        <div className="flex flex-col items-end">
          <span className={`${deltaColor} text-sm font-bold flex items-center`}>
            <DeltaIcon className="w-3 h-3 mr-0.5" />
            {delta > 0 ? '+' : ''}{Math.round(delta)}
          </span>
          <span className="text-[10px] text-text-secondary uppercase font-bold tracking-tighter">
            Daily Delta
          </span>
        </div>
      </div>

      {/* Player Info */}
      <div>
        <p className="text-text-secondary text-xs font-medium truncate">{player.team}</p>
        <h4 className="text-lg font-bold truncate group-hover:text-primary transition-colors">
          {player.full_name}
        </h4>
        <p className="text-3xl font-black mt-2" style={{ color: teamBorderColor }}>
          {Math.round(player.close)}
        </p>
      </div>
    </Link>
  );
}
