import { Trophy, Swords, Shield } from 'lucide-react';

interface Props {
  totalPoints: number;
  batterPoints: number;
  pitcherPoints: number;
  weekLabel?: string;
}

function StatCard({ label, value, icon: Icon, color }: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}) {
  return (
    <div className="bg-white rounded-xl p-4 border border-gray-100 shadow-sm">
      <div className="flex items-center gap-2 mb-1">
        <Icon className={`w-4 h-4 ${color}`} />
        <span className="text-xs font-semibold text-gray-400 uppercase">{label}</span>
      </div>
      <div className="text-2xl font-bold tabular-nums">{value.toFixed(1)}</div>
    </div>
  );
}

export default function FantasyPointsPanel({ totalPoints, batterPoints, pitcherPoints, weekLabel }: Props) {
  return (
    <div>
      {weekLabel && (
        <h3 className="text-sm font-semibold text-gray-500 mb-3">{weekLabel}</h3>
      )}
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Total" value={totalPoints} icon={Trophy} color="text-amber-500" />
        <StatCard label="Batters" value={batterPoints} icon={Swords} color="text-blue-500" />
        <StatCard label="Pitchers" value={pitcherPoints} icon={Shield} color="text-purple-500" />
      </div>
    </div>
  );
}
